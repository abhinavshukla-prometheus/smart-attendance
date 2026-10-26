"""
Creates the first admin account. Run once before using the dashboard.

Usage:
    python seed_admin.py --username admin --password yourpassword
"""

import argparse

from werkzeug.security import generate_password_hash

from database.db import init_db, get_session
from database.models import Admin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    init_db()
    session = get_session()
    try:
        existing = session.query(Admin).filter_by(username=args.username).first()
        if existing:
            print(f"Admin '{args.username}' already exists. Nothing changed.")
            return

        admin = Admin(username=args.username, password_hash=generate_password_hash(args.password))
        session.add(admin)
        session.commit()
        print(f"Created admin '{args.username}'.")
    finally:
        session.close()


if __name__ == "__main__":
    main()