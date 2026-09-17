"""OTP-style home invite codes.

An admin generates a short code for a home (admin API or dashboard). A new
user types it at sign-up and gets an ACTIVE account attached to that home
in one step — no manual approval round-trip. An existing active user can
redeem a code from the app to join an additional home.

Code format: 8 characters from an unambiguous alphabet (no 0/O/1/I),
shown to humans as XXXX-XXXX. Stored canonical (uppercase, no dash).
Lookups normalise whatever the user typed, so "k7qx 4mrp" works.

Defaults: single use, expires after 7 days. Both are per-invite settings
(a family can share one code with max_uses > 1).
"""

import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from app.domain.models import HOME_ROLES, HomeInvite, HomeMember
from app.repositories.home_invite_repository import IHomeInviteRepository
from app.repositories.home_repository import IHomeRepository
from app.repositories.user_repository import IUserRepository

logger = logging.getLogger(__name__)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 32 symbols, no 0/O/1/I
CODE_LENGTH = 8
DEFAULT_EXPIRES_HOURS = 24 * 7
MAX_EXPIRES_HOURS = 24 * 365
MAX_USES_LIMIT = 100

_NON_ALNUM = re.compile(r"[^A-Z0-9]")


class InvalidInviteError(Exception):
    """Code unknown, expired, exhausted or revoked. `reason` is one of
    unknown | expired | exhausted | revoked | home_inactive."""

    def __init__(self, reason: str = "unknown"):
        super().__init__(reason)
        self.reason = reason


def normalize_code(raw: str) -> str:
    """Canonical form of user input: uppercase, separators dropped.

    The alphabet contains neither 0/O nor 1/I, so a mistyped ambiguous
    glyph can never match a real code — it simply fails validation.
    """
    if not isinstance(raw, str):
        return ""
    return _NON_ALNUM.sub("", raw.strip().upper())


class HomeInviteService:
    def __init__(
        self,
        invite_repository: IHomeInviteRepository,
        home_repository: IHomeRepository,
        user_repository: IUserRepository,
    ):
        self._invites = invite_repository
        self._homes = home_repository
        self._users = user_repository

    # ---- Admin side ------------------------------------------------------

    @staticmethod
    def _generate_code() -> str:
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

    def create_invite(
        self,
        home_id: str,
        role: str = "member",
        expires_in_hours: Optional[int] = None,
        max_uses: int = 1,
        created_by: Optional[str] = None,
    ) -> HomeInvite:
        """Generate a fresh code for `home_id`.

        Raises:
            ValueError: unknown home, bad role, or out-of-range settings.
        """
        home = self._homes.get_by_home_id(home_id)
        if home is None:
            raise ValueError(f"Home with ID '{home_id}' not found")
        role = (role or "member").strip().lower()
        if role not in HOME_ROLES:
            raise ValueError(f"role must be one of {', '.join(HOME_ROLES)}")
        hours = DEFAULT_EXPIRES_HOURS if expires_in_hours is None else int(expires_in_hours)
        if hours < 1 or hours > MAX_EXPIRES_HOURS:
            raise ValueError(f"expires_in_hours must be 1-{MAX_EXPIRES_HOURS}")
        max_uses = int(max_uses)
        if max_uses < 1 or max_uses > MAX_USES_LIMIT:
            raise ValueError(f"max_uses must be 1-{MAX_USES_LIMIT}")

        now = datetime.now()
        for _ in range(5):  # collision is ~1e-12 per try; be safe anyway
            invite = HomeInvite(
                code=self._generate_code(), home_id=home_id, role=role,
                created_by=created_by, created_at=now,
                expires_at=now + timedelta(hours=hours),
                max_uses=max_uses, use_count=0,
            )
            try:
                created = self._invites.add(invite)
                logger.info(f"invite created home={home_id} code={created.display_code} "
                            f"max_uses={max_uses} expires={created.expires_at:%Y-%m-%d}")
                return created
            except ValueError:
                continue
        raise RuntimeError("could not generate a unique invite code")

    def list_invites(self, home_id: str) -> List[HomeInvite]:
        if not self._homes.exists(home_id):
            raise ValueError(f"Home with ID '{home_id}' not found")
        return self._invites.list_by_home(home_id)

    def get_invite(self, code: str) -> Optional[HomeInvite]:
        return self._invites.get_by_code(normalize_code(code))

    def revoke_invite(self, code: str) -> HomeInvite:
        """Revoke early. Raises ValueError when the code does not exist."""
        invite = self._invites.get_by_code(normalize_code(code))
        if invite is None:
            raise ValueError("Invite code not found")
        if invite.revoked_at is None:
            invite.revoked_at = datetime.now()
            invite = self._invites.update(invite)
        return invite

    # ---- User side -------------------------------------------------------

    def validate(self, code: str) -> HomeInvite:
        """Return the invite if it can be redeemed right now, else raise.

        Raises:
            InvalidInviteError(reason)
        """
        invite = self._invites.get_by_code(normalize_code(code))
        if invite is None:
            raise InvalidInviteError("unknown")
        status = invite.status()
        if status != "active":
            raise InvalidInviteError(status)
        home = self._homes.get_by_home_id(invite.home_id)
        if home is None or not home.is_active:
            raise InvalidInviteError("home_inactive")
        return invite

    def redeem(self, code: str, user_id: str) -> HomeMember:
        """Attach `user_id` to the invite's home and consume one use.

        Raises:
            InvalidInviteError: see validate()
            ValueError: unknown user
        """
        invite = self.validate(code)
        if not self._users.exists(user_id):
            raise ValueError(f"User with ID '{user_id}' not found")
        member = self._homes.add_member(invite.home_id, user_id, invite.role)
        invite.use_count += 1
        self._invites.update(invite)
        logger.info(f"invite redeemed code={invite.display_code} home={invite.home_id} "
                    f"user={user_id} uses={invite.use_count}/{invite.max_uses}")
        return member
