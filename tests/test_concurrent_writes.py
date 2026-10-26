"""
E6 (from the synopsis's evaluation plan): verifies the uniqueness
guarantee holds under CONCURRENT write attempts, not just sequential
ones. Fires many threads at mark_attendance() for the same user at
(almost) the same instant, then checks the database for duplicate rows.

This needs no webcam and no Flask server running -- it tests the
database layer directly. Run from the project root:
    python3 -m tests.test_concurrent_writes

Expected output: exactly one "marked", all others "duplicate", and a
final count confirming zero duplicate rows in a temporary test database.
"""

import os
import sys
import threading
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db
from database.db import get_session, mark_attendance
from database.models import User, Attendance
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

N_THREADS = 20

with tempfile.TemporaryDirectory() as temp_dir:
    test_db = Path(temp_dir) / "attendance.db"
    db.ENGINE = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"timeout": 30, "check_same_thread": False},
    )
    db.SessionLocal = sessionmaker(bind=db.ENGINE)
    db.Base.metadata.create_all(db.ENGINE)

    setup_session = get_session()
    user = User(name="Concurrency Test User")
    user.set_encodings([[0.1] * 128])  # fake encoding, not used by this test
    setup_session.add(user)
    setup_session.commit()
    user_id = user.id
    setup_session.close()

    print(f"Created user id={user_id}. Firing {N_THREADS} concurrent mark_attendance() calls...")

    results = []
    results_lock = threading.Lock()
    start_barrier = threading.Barrier(N_THREADS)

    def worker():
        start_barrier.wait()
        session = get_session()
        try:
            result = mark_attendance(session, user_id)
            with results_lock:
                results.append(result)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    marked_count = results.count("marked")
    duplicate_count = results.count("duplicate")
    print(f"\nResults across {N_THREADS} concurrent attempts:")
    print(f"  'marked':    {marked_count}")
    print(f"  'duplicate': {duplicate_count}")

    verify_session = get_session()
    row_count = verify_session.query(Attendance).filter_by(user_id=user_id).count()
    verify_session.close()
    print(f"\nActual attendance rows in the test database: {row_count}")

    assert marked_count == 1, f"Expected exactly 1 'marked' result, got {marked_count}"
    assert duplicate_count == N_THREADS - 1, (
        f"Expected {N_THREADS - 1} 'duplicate' results, got {duplicate_count}"
    )
    assert row_count == 1, (
        f"Expected exactly 1 database row, found {row_count} "
        "-- uniqueness constraint did NOT hold!"
    )

    db.ENGINE.dispose()
    print("\nE6 PASSED: uniqueness constraint holds under concurrent writes.")