"""
Attendance/dashboard routes: live feed, and the attendance table with
date filtering + CSV export.
"""

import csv
import io
from calendar import monthrange
from datetime import date, datetime

from flask import Blueprint, render_template, Response, session, request, redirect, url_for, flash

from app import login_required
from app.camera_stream import gen_mjpeg, get_camera
from database.db import (
    get_session as get_db_session,
    get_attendance_for_date,
    get_attendance_for_month,
    get_users,
)
from database.models import Attendance, User

attendance_bp = Blueprint("attendance", __name__)


def _days_in_register_month(selected):
    last_day = monthrange(selected.year, selected.month)[1]
    end_day = last_day
    today = date.today()
    if selected.year == today.year and selected.month == today.month:
        end_day = today.day
    return [
        date(selected.year, selected.month, day)
        for day in range(1, end_day + 1)
    ]


def _parse_date_param():
    """Reads ?date=YYYY-MM-DD from the query string, defaults to today."""
    raw = request.args.get("date")
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass  # fall through to today on a bad/garbled value
    return date.today()


@attendance_bp.route("/")
@login_required
def index():
    db_session = get_db_session()
    try:
        users = get_users(db_session)
        today_records = get_attendance_for_date(db_session, date.today())
    finally:
        db_session.close()
    present_ids = {record.user_id for record in today_records}
    return render_template(
        "dashboard.html",
        username=session.get("admin_username"),
        total_users=len(users),
        present_today=len(present_ids),
        pending_enrollment=sum(not user.get_encodings() for user in users),
    )


@attendance_bp.route("/students", methods=["GET", "POST"])
@login_required
def students():
    db_session = get_db_session()
    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Name is required.")
            else:
                user = User(
                    name=name,
                    roll_number=request.form.get("roll_number", "").strip() or None,
                    email=request.form.get("email", "").strip() or None,
                    section=request.form.get("section", "").strip() or None,
                )
                db_session.add(user)
                db_session.commit()
                flash(f"Profile created for {name}. Run the enrollment command shown below.")
                return redirect(url_for("attendance.students"))
        users = get_users(db_session)
        return render_template("students.html", users=users, username=session.get("admin_username"))
    finally:
        db_session.close()


@attendance_bp.route("/api/stream")
@login_required
def stream():
    return Response(
        gen_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@attendance_bp.route("/api/last_event")
@login_required
def last_event():
    """Small polling endpoint so the dashboard can show the most recent
    'Marked present: ...' message without reloading the page."""
    camera = get_camera()
    return {"event": camera.last_event}


@attendance_bp.route("/attendance")
@login_required
def attendance_table():
    target_date = _parse_date_param()
    db_session = get_db_session()
    try:
        records = get_attendance_for_date(db_session, target_date)
        # Pull the name alongside each record while the session is still open
        # (record.user is a relationship -- accessing it after close() would fail).
        rows = [
            {"name": r.user.name, "time_in": r.time_in.strftime("%H:%M:%S"), "status": r.status}
            for r in records
        ]
    finally:
        db_session.close()

    return render_template(
        "attendance.html",
        rows=rows,
        selected_date=target_date.isoformat(),
        username=session.get("admin_username"),
    )


@attendance_bp.route("/register")
@login_required
def register():
    raw_month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        selected = datetime.strptime(raw_month, "%Y-%m").date().replace(day=1)
    except ValueError:
        selected = date.today().replace(day=1)

    db_session = get_db_session()
    try:
        users = get_users(db_session)
        records = get_attendance_for_month(db_session, selected.year, selected.month)
    finally:
        db_session.close()

    record_map = {(record.user_id, record.date): record for record in records}
    days = _days_in_register_month(selected)
    rows = [
        {
            "user": user,
            "cells": [record_map.get((user.id, day)) for day in days],
            "present": sum((user.id, day) in record_map for day in days),
        }
        for user in users
    ]
    total_possible = len(users) * len(days)
    total_present = sum(row["present"] for row in rows)
    return render_template(
        "register.html",
        username=session.get("admin_username"),
        selected=selected,
        days=days,
        rows=rows,
        total_present=total_present,
        total_possible=total_possible,
        attendance_rate=(total_present / total_possible * 100) if total_possible else 0,
    )


@attendance_bp.route("/register/update", methods=["POST"])
@login_required
def update_register():
    user_id = request.form.get("user_id", type=int)
    raw_date = request.form.get("date", "")
    target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    db_session = get_db_session()
    try:
        record = (
            db_session.query(Attendance)
            .filter(Attendance.user_id == user_id, Attendance.date == target_date)
            .first()
        )
        if request.form.get("present") == "1" and record is None:
            db_session.add(Attendance(user_id=user_id, date=target_date, status="present"))
        elif request.form.get("present") != "1" and record is not None:
            db_session.delete(record)
        db_session.commit()
    finally:
        db_session.close()
    return redirect(url_for("attendance.register", month=target_date.strftime("%Y-%m")))


@attendance_bp.route("/attendance/export.csv")
@login_required
def export_csv():
    target_date = _parse_date_param()
    db_session = get_db_session()
    try:
        records = get_attendance_for_date(db_session, target_date)
        rows = [(r.user.name, r.date.isoformat(), r.time_in.strftime("%H:%M:%S"), r.status) for r in records]
    finally:
        db_session.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Date", "Time In", "Status"])
    writer.writerows(rows)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{target_date.isoformat()}.csv"},
    )


@attendance_bp.route("/register/export.csv")
@login_required
def export_register():
    raw_month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        selected = datetime.strptime(raw_month, "%Y-%m").date().replace(day=1)
    except ValueError:
        selected = date.today().replace(day=1)
    db_session = get_db_session()
    try:
        users = get_users(db_session)
        records = get_attendance_for_month(db_session, selected.year, selected.month)
    finally:
        db_session.close()
    record_map = {(record.user_id, record.date) for record in records}
    days = _days_in_register_month(selected)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Roll/Employee No.", "Email", "Section/Team/Group", *days])
    for user in users:
        writer.writerow([
            user.name,
            user.roll_number or "",
            user.email or "",
            user.section or "",
            *["P" if (user.id, day) in record_map else "A" for day in days],
        ])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_register_{selected:%Y-%m}.csv"},
    )


@attendance_bp.route("/api/refresh_faces", methods=["POST"])
@login_required
def refresh_faces():
    """
    Call this after enrolling someone new with enroll.py while the server
    is already running. enroll.py runs as a separate process, so it can't
    reach into this server's memory directly -- this route re-reads the
    database so the running recognizer picks up the new person without
    needing a full server restart.
    """
    camera = get_camera()
    camera.refresh_known_faces()
    return {"status": "refreshed", "known_people": len(set(camera.recognizer.known_user_ids))}