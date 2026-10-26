"""
Database models for the attendance system.

Tables:
- User        : enrolled people, with their face encodings stored as JSON
- Attendance  : one row per person per day (enforced by a unique constraint)
- Admin       : dashboard login accounts
"""

from datetime import datetime, date
import json

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, ForeignKey,
    UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    roll_number = Column(String(80), nullable=True)
    email = Column(String(160), nullable=True)
    section = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Stored as JSON text: a list of 128-float lists, one per enrollment photo.
    # Encodings (numbers), not raw images -> keeps biometric storage minimal.
    encodings_json = Column(Text, nullable=False, default="[]")

    attendance_records = relationship(
        "Attendance", back_populates="user", cascade="all, delete-orphan"
    )

    def get_encodings(self):
        """Return encodings as a list of lists of floats."""
        return json.loads(self.encodings_json or "[]")

    def set_encodings(self, encodings_list):
        """encodings_list: list of numpy arrays or lists -> stored as JSON."""
        as_lists = [
            list(map(float, enc)) if hasattr(enc, "__iter__") else enc
            for enc in encodings_list
        ]
        self.encodings_json = json.dumps(as_lists)

    def __repr__(self):
        return f"<User id={self.id} name={self.name!r}>"


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    time_in = Column(DateTime, default=datetime.utcnow)
    snapshot_path = Column(String(255), nullable=True)
    status = Column(String(20), default="present")  # "present" | "late"

    user = relationship("User", back_populates="attendance_records")

    __table_args__ = (
        # This is what actually stops duplicate marking -- enforced by the
        # DB, not just by checking in application code first.
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )

    def __repr__(self):
        return f"<Attendance user_id={self.user_id} date={self.date} status={self.status}>"


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<Admin username={self.username!r}>"