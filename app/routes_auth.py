"""
Auth routes: login form checks the Admin table (hashed password),
stores admin_id in the session on success. Logout clears the session.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

from database.db import get_session as get_db_session
from database.models import Admin

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    db_session = get_db_session()
    try:
        admin = db_session.query(Admin).filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            session["admin_username"] = admin.username
            return redirect(url_for("attendance.index"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("auth.login"))
    finally:
        db_session.close()


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
