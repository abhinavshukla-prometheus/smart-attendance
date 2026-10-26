"""
Flask app factory. Run with: python run.py (at project root)
"""

import functools
import os
import secrets
from pathlib import Path

from flask import Flask, session, redirect, url_for

from database.db import init_db

SECRET_KEY_FILE = Path(__file__).parent.parent / ".flask_secret_key"


def _get_or_create_secret_key():
    """
    Reads a random secret key from .flask_secret_key, creating it on first
    run. This replaces a hardcoded key -- each install gets its own random
    key automatically, with no manual setup step and nothing to remember.
    The file is sensitive (it lets someone forge login sessions if leaked)
    but is just a local file, same trust level as attendance.db already has.
    """
    configured_key = os.environ.get("FLASK_SECRET_KEY")
    if configured_key:
        return configured_key

    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()

    key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(key)
    return key


def login_required(view):
    """Decorator: redirect to login if no admin is logged in."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = _get_or_create_secret_key()

    init_db()  # make sure tables exist on startup

    from app.routes_auth import auth_bp
    from app.routes_attendance import attendance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)

    return app