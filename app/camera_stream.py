"""
Adapts the working run_recognition.py loop into something Flask can serve
as an MJPEG stream. Pipeline per processed frame:

    identity match -> N-frame confirmation streak -> LIVENESS GATE
    (wait for a blink) -> mark_attendance() -> dashboard event text

The liveness gate is the piece that was previously just a dashed box
("planned") in the architecture diagram -- it's live here. See
engine/liveness.py for the blink-detection method and its honest limits.

Design note: the camera and all per-person state (identity streaks,
liveness waiting state, confirmed-this-session) are held in ONE shared
singleton (get_camera() below), not recreated per browser request.

REQUIRES: config.py must define ENABLE_LIVENESS, BLINK_EAR_THRESHOLD,
BLINK_CONSEC_FRAMES, and LIVENESS_TIMEOUT_FRAMES -- this file will fail
to construct CameraStream (AttributeError) if those are missing.
"""

import time
import threading
from collections import defaultdict

import cv2

import config
from engine.recognizer import FaceRecognizer
from engine.liveness import LivenessDetector
from database.db import get_session, mark_attendance


class CameraStream:
    def __init__(self):
        self.recognizer = FaceRecognizer()
        self.liveness = LivenessDetector() if config.ENABLE_LIVENESS else None
        self.cap = None

        # Identity-confirmation state (unchanged from before liveness was added)
        self.streak = defaultdict(int)
        self.confirmed_this_session = set()

        # Liveness-gate state
        self.awaiting_liveness = set()       # user_ids who passed identity streak, waiting on a blink
        self.closed_frames = defaultdict(int)  # consecutive frames each user's eyes have been "closed"
        self.liveness_wait_frames = defaultdict(int)  # how long each user has been waiting, for timeout

        self.frame_idx = 0
        self.last_results = []
        self.last_event = None  # most recent human-readable event string, for the dashboard to show
        self._state_lock = threading.Lock()

    def _ensure_camera_open(self):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise RuntimeError("Could not open webcam (index 0).")

    def _on_confirmed(self, user_id: int, name: str):
        session = get_session()
        try:
            result = mark_attendance(session, user_id)
            if result == "marked":
                self.last_event = f"Marked present: {name} at {time.strftime('%H:%M:%S')}"
            else:
                self.last_event = f"{name} already marked present today"
            print(f"[{result.upper()}] {name} (id={user_id})")
        finally:
            session.close()

    def _reset_person(self, uid):
        """Fully resets one person's state, so they must re-confirm identity AND re-blink."""
        self.streak[uid] = 0
        self.confirmed_this_session.discard(uid)
        self.awaiting_liveness.discard(uid)
        self.closed_frames[uid] = 0
        self.liveness_wait_frames[uid] = 0

    def _get_jpeg_frame(self):
        """Read one frame, run recognition + liveness (every Nth frame), draw overlays, return JPEG bytes."""
        self._ensure_camera_open()

        ok, frame = self.cap.read()
        if not ok:
            return None

        self.frame_idx += 1
        process_this_frame = (self.frame_idx % config.PROCESS_EVERY_N_FRAMES == 0)

        if process_this_frame:
            results = self.recognizer.match_frame(frame)
            self.last_results = results

            known_in_frame = {
                (r["user_id"], r["name"], r["box"]) for r in results if r["user_id"] is not None
            }
            ids_in_frame = {uid for uid, _, _ in known_in_frame}

            # Anyone who dropped out of frame loses ALL progress (identity streak AND liveness wait).
            for uid in list(self.streak.keys()):
                if uid not in ids_in_frame:
                    self._reset_person(uid)

            # Run face-mesh landmark detection once per frame if liveness is enabled and needed.
            mesh_faces = []
            needs_mesh = config.ENABLE_LIVENESS and any(
                uid in self.awaiting_liveness or self.streak[uid] + 1 >= config.CONFIRM_FRAMES
                for uid, _, _ in known_in_frame
            )
            if needs_mesh:
                mesh_faces = self.liveness.process(frame)

            for uid, name, box in known_in_frame:
                self.streak[uid] += 1

                # Identity streak just reached the threshold -> enter the liveness-waiting state.
                if self.streak[uid] >= config.CONFIRM_FRAMES and uid not in self.confirmed_this_session:
                    if not config.ENABLE_LIVENESS:
                        # Liveness disabled entirely (e.g. for a quick demo without blinking) -> mark immediately.
                        self._on_confirmed(uid, name)
                        self.confirmed_this_session.add(uid)
                        continue

                    self.awaiting_liveness.add(uid)
                    self.liveness_wait_frames[uid] += 1

                    top, right, bottom, left = box
                    box_center = ((left + right) / 2, (top + bottom) / 2)
                    matched_face = self.liveness.closest_face(mesh_faces, box_center)

                    if matched_face is not None:
                        self.liveness.draw_mesh(frame, matched_face["raw_landmarks"])
                        ear = matched_face["ear"]

                        if ear < config.BLINK_EAR_THRESHOLD:
                            self.closed_frames[uid] += 1
                        else:
                            if self.closed_frames[uid] >= config.BLINK_CONSEC_FRAMES:
                                # Eyes were closed long enough and have now reopened -- that's a blink.
                                self._on_confirmed(uid, name)
                                self.confirmed_this_session.add(uid)
                                self.awaiting_liveness.discard(uid)
                            self.closed_frames[uid] = 0

                    if uid in self.awaiting_liveness and self.liveness_wait_frames[uid] > config.LIVENESS_TIMEOUT_FRAMES:
                        # Gave up waiting for a blink -- reset so they must re-approach and re-confirm.
                        self.last_event = f"{name}: liveness check timed out, please try again"
                        self._reset_person(uid)

        frame = self.recognizer.draw_results(frame, self.last_results)

        # Label anyone currently mid-liveness-check, so the demo visibly shows the gate working.
        for r in self.last_results:
            if r["user_id"] in self.awaiting_liveness:
                top, right, bottom, left = r["box"]
                cv2.putText(
                    frame, "Verifying liveness - please blink",
                    (left, max(top - 10, 15)), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 165, 255), 1
                )

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return buffer.tobytes()

    def get_jpeg_frame(self):
        """Serialize access to the shared camera and recognition state."""
        with self._state_lock:
            return self._get_jpeg_frame()

    def refresh_known_faces(self):
        """Reload identities and discard recognition state from the old roster."""
        with self._state_lock:
            self.recognizer.load_known_faces()
            self.streak.clear()
            self.confirmed_this_session.clear()
            self.awaiting_liveness.clear()
            self.closed_frames.clear()
            self.liveness_wait_frames.clear()
            self.last_results = []

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


# --- Singleton so all requests share one camera + one set of streak state ---
_camera_instance = None


def get_camera() -> CameraStream:
    global _camera_instance
    if _camera_instance is None:
        _camera_instance = CameraStream()
    return _camera_instance


def gen_mjpeg():
    """Generator Flask's Response() streams as multipart/x-mixed-replace (MJPEG)."""
    camera = get_camera()
    while True:
        jpeg_bytes = camera.get_jpeg_frame()
        if jpeg_bytes is None:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
        )
