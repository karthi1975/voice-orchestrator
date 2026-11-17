#!/usr/bin/env python3
"""Enroll every ACTIVE smart home user as an SCI Companion portal member.

For each active user this signs a purpose="enroll" ES256 assertion (identity
only: user_id, name, email, gender — never passwords or hashes) and POSTs it
to the portal's /session/enroll. No tokens are minted and no login is
recorded, so the portal shows "last login: never" until the person really
opens health education from the app.

Idempotent and safe to repeat: already-enrolled users come back
created=False linked=False and only have their gender refreshed.
Inactive and pending users are skipped entirely.

Usage (inside the app container, where DATABASE_URL and the
HEALTH_EDUCATOR_* env vars are set):

    python scripts/enroll_health_educator_users.py --dry-run   # counts only
    python scripts/enroll_health_educator_users.py             # real run

Exit code 0 = every active user enrolled (or already was); 1 = errors.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import User
from app.repositories.implementations.sqlalchemy_models import UserModel
from app.services.health_educator_service import (HealthEducatorNotConfigured,
                                                  HealthEducatorRefused,
                                                  HealthEducatorService,
                                                  HealthEducatorUnavailable)

PAUSE_SECONDS = 0.3
RETRY_BACKOFF_SECONDS = 2.0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Count who would be enrolled; no portal calls")
    args = p.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1
    session = sessionmaker(bind=create_engine(url))()
    rows = (session.query(UserModel)
            .order_by(UserModel.created_at)
            .all())
    active = [r for r in rows if r.is_active]
    print(f"users: {len(rows)} total, {len(active)} active "
          f"(skipping {len(rows) - len(active)} inactive/pending)")

    if args.dry_run:
        unset = sum(1 for r in active if not r.gender)
        print(f"would enroll {len(active)} active users "
              f"({unset} with gender unspecified)")
        return 0

    svc = HealthEducatorService()
    if not svc.configured:
        print("health educator SSO is not configured on this server",
              file=sys.stderr)
        return 1

    tally = {"created": 0, "linked": 0, "already": 0, "refused": 0, "error": 0}
    failures = []  # (user_id, reason) — never assertions, names or emails

    for i, row in enumerate(active):
        user = User(
            user_id=row.user_id, username=row.username, email=row.email,
            full_name=row.full_name, is_active=row.is_active,
            created_at=row.created_at, gender=row.gender,
        )
        outcome = None
        for attempt in (1, 2):
            try:
                r = svc.enroll(user)
                outcome = ("created" if r["created"]
                           else "linked" if r["linked"] else "already")
                break
            except HealthEducatorRefused:
                outcome = "refused"
                failures.append((user.user_id, "refused (403)"))
                break
            except HealthEducatorUnavailable:
                if attempt == 1:  # one retry on 502/503/timeout
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                outcome = "error"
                failures.append((user.user_id, "portal unavailable"))
            except HealthEducatorNotConfigured:
                print("SSO became unconfigured mid-run; stopping",
                      file=sys.stderr)
                return 1
        tally[outcome] += 1
        if i < len(active) - 1:
            time.sleep(PAUSE_SECONDS)

    print(f"done: created={tally['created']} linked={tally['linked']} "
          f"already-enrolled={tally['already']} refused={tally['refused']} "
          f"errors={tally['error']}")
    for user_id, reason in failures:
        print(f"  failed: {user_id}  {reason}")
    return 1 if (tally["error"] or tally["refused"]) else 0


if __name__ == "__main__":
    sys.exit(main())
