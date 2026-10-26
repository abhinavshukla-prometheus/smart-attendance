"""
Core recognition engine: loads known face encodings FROM THE DATABASE
(not a pickle file -- the DB is the single source of truth now), and
matches faces found in a video frame against them.

This module has NO webcam code -- it's pure "given a frame, tell me
who's in it". That makes it reusable later from the Flask API too.
"""

import cv2
import face_recognition
import numpy as np

import config
from database.db import get_session, get_all_users


class FaceRecognizer:
    def __init__(self):
        self.known_user_ids = []    # parallel list: user.id per encoding
        self.known_names = []       # parallel list: user.name per encoding
        self.known_encodings = []   # parallel list: 128-d vector per encoding
        self.load_known_faces()

    def load_known_faces(self):
        """
        Load every enrolled user's encodings from the database. Call again
        any time to refresh after a new enrollment (e.g. before starting
        a new recognition session).
        """
        self.known_user_ids = []
        self.known_names = []
        self.known_encodings = []

        session = get_session()
        try:
            users = get_all_users(session)
            for user in users:
                for encoding in user.get_encodings():
                    self.known_user_ids.append(user.id)
                    self.known_names.append(user.name)
                    self.known_encodings.append(np.array(encoding))
        finally:
            session.close()

    def match_frame(self, frame):
        """
        Given a BGR frame (as OpenCV reads it), find every face, and
        return a list of dicts:
            [{"user_id": 101, "name": "Abhinav" or None,
              "distance": 0.41,
              "box": (top, right, bottom, left)}, ...]

        user_id/name are None when the face doesn't match anyone closely
        enough (i.e. "Unknown"). "box" coordinates are in ORIGINAL frame
        scale, already adjusted back up from the shrunk detection frame.
        """
        small_frame = cv2.resize(
            frame, (0, 0),
            fx=config.FRAME_RESIZE_SCALE, fy=config.FRAME_RESIZE_SCALE
        )
        rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(
            rgb_small, model=config.DETECTION_MODEL
        )
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

        results = []
        scale_back = int(1 / config.FRAME_RESIZE_SCALE)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            user_id = None
            name = None
            distance = None

            if self.known_encodings:
                distances = face_recognition.face_distance(
                    self.known_encodings, face_encoding
                )
                best_idx = int(np.argmin(distances))
                best_distance = float(distances[best_idx])

                if best_distance <= config.TOLERANCE:
                    user_id = self.known_user_ids[best_idx]
                    name = self.known_names[best_idx]
                    distance = best_distance

            results.append({
                "user_id": user_id,
                "name": name,
                "distance": distance,
                "box": (
                    top * scale_back, right * scale_back,
                    bottom * scale_back, left * scale_back,
                ),
            })

        return results

    @staticmethod
    def draw_results(frame, results):
        """Draw boxes + labels on the frame in place. Returns the frame."""
        for r in results:
            top, right, bottom, left = r["box"]
            is_known = r["user_id"] is not None
            color = (0, 200, 0) if is_known else (0, 0, 200)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            label = r["name"] if is_known else "Unknown"
            if r["distance"] is not None:
                label += f" ({r['distance']:.2f})"

            cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
            cv2.putText(
                frame, label, (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1
            )
        return frame