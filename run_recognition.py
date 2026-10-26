"""
Live recognition loop. Opens the webcam, runs FaceRecognizer on frames,
and calls on_confirmed(user_id, name) once a person matches for
CONFIRM_FRAMES consecutive processed frames in a row -- then marks them
present in the database (duplicate-per-day blocked automatically).

Usage:
    python run_recognition.py
    Q to quit.
"""

import time
from collections import defaultdict

import cv2

import config
from engine.recognizer import FaceRecognizer
from database.db import init_db, get_session, mark_attendance


def on_confirmed(user_id: int, name: str):
    """Marks the person present in the database. Prints the outcome either way."""
    session = get_session()
    try:
        result = mark_attendance(session, user_id)
        if result == "marked":
            print(f"[MARKED PRESENT] {name} (id={user_id}) at {time.strftime('%H:%M:%S')}")
        else:
            print(f"[ALREADY MARKED] {name} (id={user_id}) already present today")
    finally:
        session.close()


def main():
    init_db()  # make sure tables exist before anything else runs

    recognizer = FaceRecognizer()
    if not recognizer.known_encodings:
        print("Warning: no known faces loaded. Run enroll.py first.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0). Check camera permissions/connection.")

    # Tracks how many consecutive processed frames each user_id has matched.
    streak = defaultdict(int)
    # Tracks who's already been confirmed this "visit", so we don't spam
    # on_confirmed() every frame once someone is standing in front of the camera.
    confirmed_this_session = set()

    frame_idx = 0
    last_results = []  # cached so we can draw on every frame, not just processed ones
    print("Running. Press Q to quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from webcam.")
            break

        frame_idx += 1
        process_this_frame = (frame_idx % config.PROCESS_EVERY_N_FRAMES == 0)

        if process_this_frame:
            results = recognizer.match_frame(frame)
            last_results = results  # cache for the in-between frames
            known_in_frame = {
                (r["user_id"], r["name"]) for r in results if r["user_id"] is not None
            }
            ids_in_frame = {uid for uid, _ in known_in_frame}

            # Reset streaks for anyone who dropped out of frame.
            for uid in list(streak.keys()):
                if uid not in ids_in_frame:
                    streak[uid] = 0
                    confirmed_this_session.discard(uid)

            for uid, name in known_in_frame:
                streak[uid] += 1
                if streak[uid] >= config.CONFIRM_FRAMES and uid not in confirmed_this_session:
                    on_confirmed(uid, name)
                    confirmed_this_session.add(uid)

        # Draw the most recent results on every frame, even skipped ones,
        # so the box doesn't flicker on/off between processed frames.
        frame = recognizer.draw_results(frame, last_results)
        cv2.imshow("Attendance - Live Recognition", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()