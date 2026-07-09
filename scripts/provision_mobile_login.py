#!/usr/bin/env python3
"""Provision (or repair) a mobile login for an existing user_ref — idempotently.

Existing mobile data (favorites, enrollments, challenge logs) is keyed by the
free-text user_ref the app has been sending (e.g. "scott_mobile"). Mobile
login makes the JWT's sub the user's user_id, so for that data to stay
attached the user row's user_id must EQUAL the historical user_ref. This
script guarantees that, without touching any favorites/enrollment rows:

  1. ensures a users row with user_id == <user-ref> exists
     (creates it if missing; existing rows are updated, never recreated)
  2. sets the login password (pbkdf2:sha256)
  3. optionally re-points a home's owner (homes.user_id) to this user so
     GET /me returns that home — this only changes the owner column on the
     homes row; scenes, favorites and tokens reference home_id and are
     unaffected

Usage:
  DATABASE_URL=postgresql://... python scripts/provision_mobile_login.py \
      --user-ref scott_mobile \
      --email scott@example.com \
      --full-name "Scott" \
      --password 'choose-a-password' \
      --home scott_home

Run it again any time — it converges to the same state (idempotent).
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

from app.repositories.implementations.sqlalchemy_models import HomeModel, UserModel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user-ref", required=True,
                   help="Existing mobile user_ref; becomes/matches users.user_id")
    p.add_argument("--password", default=None,
                   help="Login password to set (omit to be prompted securely, "
                        "or set MOBILE_LOGIN_PASSWORD env var — both keep the "
                        "password out of shell history)")
    p.add_argument("--email", default=None, help="Login email (recommended)")
    p.add_argument("--username", default=None,
                   help="Username (defaults to --user-ref)")
    p.add_argument("--full-name", default=None,
                   help="Full name (defaults to --user-ref)")
    p.add_argument("--home", action="append", default=[],
                   help="home_id to attach to this user (repeatable)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing")
    args = p.parse_args()

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: DATABASE_URL env var is required", file=sys.stderr)
        return 1

    password = args.password or os.environ.get("MOBILE_LOGIN_PASSWORD", "").strip()
    if not password and not args.dry_run:
        import getpass
        password = getpass.getpass(f"New password for {args.user_ref!r}: ")
    if not args.dry_run and (len(password) < 8 or len(password) > 256):
        print("ERROR: password must be 8-256 characters", file=sys.stderr)
        return 1

    engine = create_engine(db_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()

    user_ref = args.user_ref.strip()
    username = (args.username or user_ref).strip()
    changes = []

    user = session.get(UserModel, user_ref)
    if user is None:
        user = UserModel(
            user_id=user_ref,
            username=username,
            full_name=(args.full_name or user_ref).strip(),
            email=args.email,
            is_active=True,
            created_at=datetime.now(),
        )
        session.add(user)
        changes.append(f"create user user_id={user_ref!r} username={username!r}")
    else:
        changes.append(f"user user_id={user_ref!r} already exists — keeping it")
        if args.email and user.email != args.email:
            changes.append(f"update email {user.email!r} -> {args.email!r}")
            user.email = args.email
        if args.full_name and user.full_name != args.full_name:
            changes.append(f"update full_name {user.full_name!r} -> {args.full_name!r}")
            user.full_name = args.full_name
        if not user.is_active:
            changes.append("re-activate user")
            user.is_active = True

    changes.append("set password")
    if not args.dry_run:
        user.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    for home_id in args.home:
        home = session.get(HomeModel, home_id.strip())
        if home is None:
            print(f"ERROR: home {home_id!r} not found — create it first via "
                  f"POST /admin/homes", file=sys.stderr)
            session.rollback()
            return 1
        if home.user_id != user_ref:
            changes.append(f"re-point home {home_id!r} owner {home.user_id!r} -> {user_ref!r}")
            home.user_id = user_ref
        else:
            changes.append(f"home {home_id!r} already owned by {user_ref!r}")

    print("Plan:" if args.dry_run else "Applying:")
    for c in changes:
        print(f"  - {c}")

    if args.dry_run:
        session.rollback()
        print("Dry run — nothing written.")
        return 0

    session.commit()
    print(f"Done. {user_ref!r} can now POST /auth/login and GET /me.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
