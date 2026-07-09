"""Mobile app login + identity bootstrap (Tier 2 auth).

Gives the SmartHome mobile app a way to learn its own `user_ref` and
`home_id` instead of hardcoding them:

    POST /auth/login  {email|username, password}  ->  JWT + user + homes
    GET  /me          Authorization: Bearer <jwt>  ->  user + homes

Tokens are standard HS256 JWTs (sub = user_id) implemented with the
stdlib only — no new dependencies. The same verify function is handed to
the voice-auth API-key middleware so JWTs are accepted everywhere the
static platform keys are, without changing the static-key behavior.

Data-continuity rule: the JWT `sub` IS the user_id, and `/me` reports it
as `user_ref`. Provision existing users so their user_id equals the
user_ref their data is already keyed by (e.g. "scott_mobile") and all
favorites/enrollments stay attached — nothing is migrated or renamed.

Config (env):
    MOBILE_JWT_SECRET       signing secret. If unset, an ephemeral random
                            secret is generated at boot (tokens die on
                            restart) and a warning is logged — fine for
                            dev, set it in prod.
    MOBILE_JWT_TTL_SECONDS  token lifetime, default 30 days.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

from app.domain.models import Home, User
from app.repositories.home_repository import IHomeRepository
from app.repositories.user_repository import IUserRepository
from app.utils.login_throttle import LoginThrottle

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days
MAX_CREDENTIAL_LENGTH = 256

# Hash of a random password nobody knows: verified against when the user
# doesn't exist, so "unknown user" and "wrong password" take the same time
# (prevents account enumeration via response timing).
_DUMMY_USER = User(user_id="_", username="_", full_name="_",
                   password_hash=User.hash_password(secrets.token_hex(16)))


class RateLimitedError(Exception):
    """Too many failed login attempts; try again later."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


class MobileAuthService:
    """Issues and verifies mobile login JWTs; resolves user -> homes."""

    def __init__(
        self,
        user_repository: IUserRepository,
        home_repository: IHomeRepository,
        secret: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ):
        env_secret = os.environ.get("MOBILE_JWT_SECRET", "").strip()
        resolved = secret or env_secret
        if not resolved:
            resolved = secrets.token_hex(32)
            logger.warning(
                "⚠ MOBILE_JWT_SECRET is not set — using an ephemeral secret. "
                "Mobile login tokens will be invalidated on every restart. "
                "Set MOBILE_JWT_SECRET in the environment for production."
            )
        elif len(resolved) < 32:
            logger.warning(
                "⚠ MOBILE_JWT_SECRET is shorter than 32 characters — weak signing "
                "secret. Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        self._secret = resolved.encode("utf-8")

        env_ttl = os.environ.get("MOBILE_JWT_TTL_SECONDS", "").strip()
        self._ttl = ttl_seconds or (int(env_ttl) if env_ttl.isdigit() else DEFAULT_TTL_SECONDS)

        self._users = user_repository
        self._homes = home_repository
        self._throttle = LoginThrottle()

    # ---- JWT (HS256, stdlib) -------------------------------------------

    def issue_token(self, user_id: str) -> Dict[str, Any]:
        """Create a signed JWT for user_id. Returns token + expiry info."""
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": user_id, "iat": now, "exp": now + self._ttl}
        signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}." \
                        f"{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
        sig = hmac.new(self._secret, signing_input.encode("ascii"), hashlib.sha256).digest()
        return {
            "token": f"{signing_input}.{_b64url(sig)}",
            "expires_in": self._ttl,
            "expires_at": now + self._ttl,
        }

    def verify_token(self, token: str) -> Optional[str]:
        """Return the user_id (sub) if token is valid and unexpired, else None."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            signing_input = f"{parts[0]}.{parts[1]}"
            expected = hmac.new(self._secret, signing_input.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _b64url_decode(parts[2])):
                return None
            header = json.loads(_b64url_decode(parts[0]))
            if header.get("alg") != "HS256":
                return None
            payload = json.loads(_b64url_decode(parts[1]))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            sub = payload.get("sub")
            return str(sub) if sub else None
        except Exception:
            return None

    # ---- Login + bootstrap ---------------------------------------------

    def login(self, identifier: str, password: str,
              client_ip: Optional[str] = None) -> Optional[User]:
        """Authenticate by email or username. Returns the user or None.

        Raises:
            RateLimitedError: too many recent failures for this identifier
                              or client IP (brute-force lockout).
        """
        # Type/size hardening: JSON bodies can carry numbers, lists, or
        # megabyte strings — reject anything that isn't a sane credential.
        if not isinstance(identifier, str) or not isinstance(password, str):
            return None
        identifier = identifier.strip()
        if not identifier or not password:
            return None
        if len(identifier) > MAX_CREDENTIAL_LENGTH or len(password) > MAX_CREDENTIAL_LENGTH:
            return None

        throttle_keys = (f"id:{identifier.lower()}", f"ip:{client_ip}" if client_ip else "")
        if self._throttle.is_locked(*throttle_keys):
            raise RateLimitedError()

        user = None
        if "@" in identifier:
            # Exact match first, lowercased fallback (emails are stored as
            # typed but users often re-type them with different casing).
            user = self._users.get_by_email(identifier) \
                or self._users.get_by_email(identifier.lower())
        if user is None:
            user = self._users.get_by_username(identifier)

        if user is None:
            # Equalize timing with the wrong-password path (anti-enumeration).
            _DUMMY_USER.check_password(password)
            self._throttle.record_failure(*throttle_keys)
            return None
        if not user.check_password(password):
            self._throttle.record_failure(*throttle_keys)
            return None
        if not user.is_active:
            logger.warning(f"mobile login rejected (inactive): {user.user_id}")
            self._throttle.record_failure(*throttle_keys)
            return None

        self._throttle.record_success(*throttle_keys)
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get_by_id(user_id)

    def change_password(self, user_id: str, current_password: str,
                        new_password: str) -> bool:
        """Change a user's password after verifying the current one.

        Requiring the current password means a stolen (still-valid) token
        alone can't silently lock the real user out.

        Returns False when the current password is wrong or the user is
        missing/inactive.

        Raises:
            ValueError: new password fails the 8-256 char policy.
            RateLimitedError: too many wrong current-password attempts.
        """
        if not isinstance(current_password, str) or not isinstance(new_password, str):
            return False
        if len(current_password) > MAX_CREDENTIAL_LENGTH:
            return False
        if len(new_password) < 8 or len(new_password) > 256:
            raise ValueError("new password must be 8-256 characters")

        throttle_key = f"pw:{user_id}"
        if self._throttle.is_locked(throttle_key):
            raise RateLimitedError()

        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return False
        if not user.check_password(current_password):
            self._throttle.record_failure(throttle_key)
            return False

        user.password_hash = User.hash_password(new_password)
        self._users.update(user)
        self._throttle.record_success(throttle_key)
        logger.info(f"password changed user={user_id}")
        return True

    def bootstrap(self, user: User) -> Dict[str, Any]:
        """The identity payload the app caches on startup.

        `user_ref` == user_id: it is the exact value to send in every
        favorites/enrollment call. `email`/`username` are included so the
        app can attach user identity to feedback reports.
        """
        homes: List[Home] = self._homes.list_by_user(user.user_id, active_only=True)
        return {
            "user_ref": user.user_id,
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "homes": [
                {"home_id": h.home_id, "name": h.name}
                for h in homes
            ],
            # Convenience for the common one-home case: use directly as home_id.
            "default_home_id": homes[0].home_id if homes else None,
        }
