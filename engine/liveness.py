"""
Liveness / anti-spoofing check using MediaPipe Face Mesh.

Computes the Eye Aspect Ratio (EAR) from facial landmarks to detect a
blink in real time -- the technique described by Soukupova & Cech
(2016) -- used as a lightweight defence against someone holding up a
photo to fake attendance. Also draws the dot-and-line landmark mesh
overlay used for the live demo visual.

Honest limits (see the synopsis's Section 4.4): this blocks a STATIC
photo, since a photo cannot blink. It does NOT reliably block a played
video of a real person blinking -- that would need a stronger defence
(texture/depth cues, randomized challenges) noted as future work.
"""

import math

import cv2
import mediapipe as mp

# Standard MediaPipe Face Mesh landmark indices for a 6-point eye,
# ordered to match the classic EAR formula: (outer corner, two upper
# lid points, inner corner, two lower lid points).
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _eye_aspect_ratio(points):
    """points: 6 (x, y) tuples in the order above. Returns the EAR value."""
    p1, p2, p3, p4, p5, p6 = points
    vertical = _dist(p2, p6) + _dist(p3, p5)
    horizontal = _dist(p1, p4)
    if horizontal == 0:
        return 0.0
    return vertical / (2.0 * horizontal)


class LivenessDetector:
    def __init__(self):
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=5,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._drawing = mp.solutions.drawing_utils
        self._drawing_styles = mp.solutions.drawing_styles
        self._connections = mp.solutions.face_mesh.FACEMESH_TESSELATION

    def process(self, frame_bgr):
        """
        Runs face-mesh landmark detection on a frame.
        Returns a list of dicts, one per detected face:
            {"center": (x, y), "ear": float, "raw_landmarks": <mediapipe landmark object>}
        Coordinates are in the frame's own pixel space.
        """
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)

        faces = []
        if not result.multi_face_landmarks:
            return faces

        for face_landmarks in result.multi_face_landmarks:
            pts = [(lm.x * w, lm.y * h) for lm in face_landmarks.landmark]
            left_ear = _eye_aspect_ratio([pts[i] for i in LEFT_EYE])
            right_ear = _eye_aspect_ratio([pts[i] for i in RIGHT_EYE])
            ear = (left_ear + right_ear) / 2.0

            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            center = (sum(xs) / len(xs), sum(ys) / len(ys))

            faces.append({"center": center, "ear": ear, "raw_landmarks": face_landmarks})

        return faces

    def draw_mesh(self, frame_bgr, raw_landmarks):
        """Draws the dot/line mesh overlay for one face onto the frame, in place."""
        self._drawing.draw_landmarks(
            image=frame_bgr,
            landmark_list=raw_landmarks,
            connections=self._connections,
            landmark_drawing_spec=None,
            connection_drawing_spec=self._drawing_styles.get_default_face_mesh_tesselation_style(),
        )

    @staticmethod
    def closest_face(faces, point):
        """Finds whichever MediaPipe face is nearest to a given (x, y) point --
        used to match a dlib-detected identity box to its MediaPipe landmarks."""
        if not faces:
            return None
        return min(faces, key=lambda f: _dist(f["center"], point))