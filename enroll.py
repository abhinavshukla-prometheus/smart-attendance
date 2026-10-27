"""
Enroll a person: capture several webcam photos, encode each one, and
create a User row in the database (the database is now the single
source of truth -- no more pickle file).

Usage:
    python enroll.py --name "Abhinav"

Controls while the webcam window is open:
    SPACE -> capture current frame (do 15-20 shots, varying angle/lighting)
    Q     -> finish and save
"""

import argparse

import cv2
import face_recognition

import config
from database.db import init_db, get_session
from database.models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Display name for this person")
    parser.add_argument("--user-id", type=int, help="Existing profile ID created from the dashboard")
    parser.add_argument("--roll-number", help="Optional roll or employee number")
    parser.add_argument("--email", help="Optional email address")
    parser.add_argument("--section", help="Optional section, team, or group")
    args = parser.parse_args()

    init_db()  # make sure tables exist

    save_dir = config.FACES_DIR / args.name.replace(" ", "_")
    save_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam (index 0). Check camera permissions/connection.")

    captured_encodings = []
    shot_count = 0

    print(f"Enrolling '{args.name}'")
    print("SPACE to capture, Q to finish. Aim for 15-20 shots, varying angle/lighting.")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from webcam.")
            break

        display = frame.copy()
        cv2.putText(
            display, f"Captured: {shot_count}  (SPACE=capture, Q=done)",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )
        cv2.imshow("Enroll", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb, model=config.DETECTION_MODEL)

            if len(locations) != 1:
                print(f"  Skipped shot: found {len(locations)} faces, need exactly 1 in frame.")
                continue

            encoding = face_recognition.face_encodings(rgb, locations)[0]
            captured_encodings.append(encoding)
            shot_count += 1

            img_path = save_dir / f"{shot_count:02d}.jpg"
            cv2.imwrite(str(img_path), frame)
            print(f"  Captured shot {shot_count} -> {img_path}")

        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    if not captured_encodings:
        print("No faces captured -- nothing saved. Try again with better lighting.")
        return

    session = get_session()
    try:
        user = session.get(User, args.user_id) if args.user_id else None
        if user is None:
            user = User(name=args.name)
            session.add(user)
        else:
            user.name = args.name
        # The dashboard creates these details before enrollment. Only replace
        # them when an optional command-line value was explicitly supplied.
        if args.roll_number is not None:
            user.roll_number = args.roll_number
        if args.email is not None:
            user.email = args.email
        if args.section is not None:
            user.section = args.section
        user.set_encodings(captured_encodings)
        session.commit()
        print(f"\nSaved user '{args.name}' with id={user.id} ({len(captured_encodings)} encodings).")
    finally:
        session.close()


if __name__ == "__main__":
    main()