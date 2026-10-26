"""
Engine/session setup, plus the helper that replaces your old on_confirmed().

Usage from run_recognition.py:

    from database.db import init_db, get_session, mark_attendance

    init_db()  # call once at startup, creates attendance.db + tables if missing

    def on_confirmed(user_id, snapshot_path=None):
        session = get_session()
        result = mark_attendance(session, user_id, snapshot_path=snapshot_path)
        if result == "marked":
            print(f"Attendance marked for user {user_id}")
        elif result == "duplicate":
            print(f"User {user_id} already marked today")
"""

from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy import event

from database.models import Base, Attendance, User

DB_PATH = Path(__file__).parent / "attendance.db"
ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"timeout": 30},
)
SessionLocal = sessionmaker(bind=ENGINE)


@event.listens_for(ENGINE, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Keep SQLite foreign-key behavior consistent with the model definition."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db():
    """Create all tables if they don't exist yet. Call once at startup."""
    Base.metadata.create_all(ENGINE)
    with ENGINE.begin() as connection:
        columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(users)"))
        }
        for column, definition in (
            ("roll_number", "VARCHAR(80)"),
            ("email", "VARCHAR(160)"),
            ("section", "VARCHAR(120)"),
        ):
            if column not in columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} {definition}"))


def get_session():
    """New session per call; caller is responsible for closing it."""
    return SessionLocal()


def mark_attendance(
    session, user_id: int, snapshot_path: str = None, status: str = "present"
) -> str:
    """
    Insert an attendance row for user_id for today.

    Returns:
        "marked"    - new row inserted
        "duplicate" - user already has a row for today (unique constraint hit)
    """
    record = Attendance(
        user_id=user_id,
        date=date.today(),
        snapshot_path=snapshot_path,
        status=status,
    )
    session.add(record)
    try:
        session.commit()
        return "marked"
    except IntegrityError as error:
        session.rollback()
        message = str(error.orig).lower()
        if "unique constraint failed" in message and "attendance.user_id" in message:
            return "duplicate"
        raise


def get_all_users(session):
    """Return every enrolled User row. Used by FaceRecognizer.load_known_faces()."""
    return session.query(User).all()


def get_user(session, user_id: int):
    return session.query(User).filter(User.id == user_id).first()


def get_users(session):
    return session.query(User).order_by(User.name.asc()).all()


def get_attendance_for_month(session, year: int, month: int):
    from calendar import monthrange
    from datetime import date

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return (
        session.query(Attendance)
        .filter(Attendance.date >= start, Attendance.date <= end)
        .all()
    )


def get_attendance_for_date(session, target_date: date):
    """Return all Attendance rows for a given date, newest first."""
    return (
        session.query(Attendance)
        .filter(Attendance.date == target_date)
        .order_by(Attendance.time_in.desc())
        .all()
    )