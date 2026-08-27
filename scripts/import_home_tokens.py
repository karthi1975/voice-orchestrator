#!/usr/bin/env python3
"""One-time import: legacy HOME_CONFIGS_JSON env tokens -> encrypted DB storage.

For every home in HOME_CONFIGS_JSON that also exists in the homes table and
has no portal-stored token yet, encrypt the env token and store it. Idempotent:
re-running skips homes that already have a DB token. Nothing is removed from
the env var (it stays as fallback until you choose to drop it).

Run inside the prod container (has DATABASE_URL + HOME_CONFIGS_JSON):
    docker exec voice-orchestrator python scripts/import_home_tokens.py
Add --dry-run to preview.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.security.token_vault import TokenVault
from app.repositories.implementations.sqlalchemy_models import HomeModel


def main() -> int:
    dry = "--dry-run" in sys.argv
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("ERROR: DATABASE_URL env var required", file=sys.stderr)
        return 1
    try:
        cfg = json.loads(os.environ.get("HOME_CONFIGS_JSON", "{}"))
    except ValueError as e:
        print(f"ERROR: HOME_CONFIGS_JSON invalid JSON: {e}", file=sys.stderr)
        return 1
    if not cfg:
        print("HOME_CONFIGS_JSON is empty — nothing to import.")
        return 0

    vault = TokenVault()
    session = sessionmaker(bind=create_engine(db_url, pool_pre_ping=True))()
    imported = skipped = missing = 0
    for home_id, c in cfg.items():
        token = ((c or {}).get("ha_token") or "").strip()
        if not token:
            print(f"  - {home_id}: no ha_token in env entry — skip")
            continue
        home = session.get(HomeModel, home_id)
        if home is None:
            print(f"  - {home_id}: in env but NOT in homes table — skip "
                  f"(register it in the portal first)")
            missing += 1
            continue
        if home.ha_token_encrypted and vault.decrypt(home.ha_token_encrypted):
            print(f"  - {home_id}: already has a portal token — skip")
            skipped += 1
            continue
        print(f"  - {home_id}: import env token -> encrypted DB storage"
              + (" (dry-run)" if dry else ""))
        if not dry:
            home.ha_token_encrypted = vault.encrypt(token)
        imported += 1
    if dry:
        session.rollback()
    else:
        session.commit()
    print(f"Done: {imported} imported, {skipped} already stored, {missing} not in DB."
          + (" (dry-run, nothing written)" if dry else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
