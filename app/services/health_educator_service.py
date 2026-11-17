"""Single sign-on into the health educator portal (SCI Companion).

Every ACTIVE smart home user may open the portal's patient education from
the mobile app without a second account. This backend is the identity
provider: it vouches for the logged-in user with a short-lived ES256
assertion, the portal verifies it with the matching PUBLIC key, creates the
member account on first use and returns its own session tokens, which are
handed to the app. The app then calls the portal directly.

The private key never leaves this server; the portal cannot mint smart home
identities, and no login secret is shared between the two systems.

Config (env):
    HEALTH_EDUCATOR_URL              portal base URL this server calls,
                                     e.g. https://portal.example.org
    HEALTH_EDUCATOR_PUBLIC_URL       base URL the mobile app should call
                                     (defaults to HEALTH_EDUCATOR_URL)
    HEALTH_EDUCATOR_SSO_PRIVATE_KEY  EC P-256 private key, PEM text or the PEM
                                     base64-encoded on one line
    HEALTH_EDUCATOR_SSO_ISSUER       default "smarthome-voice-orchestrator"
    HEALTH_EDUCATOR_SSO_AUDIENCE     default "healtheducator-portal"

Unset URL or key = feature off (the endpoint answers 503 NOT_CONFIGURED).
"""

import base64
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from app.domain.models import User

logger = logging.getLogger(__name__)

ASSERTION_TTL_SECONDS = 60
PORTAL_TIMEOUT_SECONDS = 10
MOBILE_API_PREFIX = "/api/mobile/v1"


class HealthEducatorNotConfigured(Exception):
    """HEALTH_EDUCATOR_URL / HEALTH_EDUCATOR_SSO_PRIVATE_KEY are not set."""


class HealthEducatorUnavailable(Exception):
    """The portal could not be reached or answered with a server error."""


class HealthEducatorRefused(Exception):
    """The portal verified the request but will not sign this user in."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_private_key(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith("-----"):
        raw = base64.b64decode(raw).decode("utf-8")
    key = serialization.load_pem_private_key(raw.replace("\\n", "\n").encode("utf-8"), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise ValueError("HEALTH_EDUCATOR_SSO_PRIVATE_KEY must be an EC P-256 key")
    return key


class HealthEducatorService:
    """Signs identity assertions and trades them for portal sessions."""

    def __init__(
        self,
        portal_url: Optional[str] = None,
        public_url: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        http_post=None,
    ):
        env = os.environ.get
        self._url = (portal_url or env("HEALTH_EDUCATOR_URL", "")).strip().rstrip("/")
        self._public_url = (public_url or env("HEALTH_EDUCATOR_PUBLIC_URL", "")).strip().rstrip("/") \
            or self._url
        self._issuer = issuer or env("HEALTH_EDUCATOR_SSO_ISSUER", "smarthome-voice-orchestrator")
        self._audience = audience or env("HEALTH_EDUCATOR_SSO_AUDIENCE", "healtheducator-portal")
        self._post = http_post or requests.post
        try:
            self._key = _load_private_key(
                private_key_pem or env("HEALTH_EDUCATOR_SSO_PRIVATE_KEY", ""))
        except Exception as e:
            logger.error(f"health educator SSO key could not be loaded: {e}")
            self._key = None
        if self.configured:
            logger.info(f"health educator SSO enabled portal={self._url}")

    @property
    def configured(self) -> bool:
        return bool(self._url and self._key)

    # ---- assertion (ES256 JWS) -----------------------------------------

    def sign_assertion(self, user: User, purpose: str = "login") -> str:
        if not self.configured:
            raise HealthEducatorNotConfigured()
        now = int(time.time())
        claims: Dict[str, Any] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": user.user_id,
            "iat": now,
            "exp": now + ASSERTION_TTL_SECONDS,
            "jti": uuid.uuid4().hex,
            "purpose": purpose,
        }
        if purpose in ("login", "enroll"):
            claims["name"] = user.full_name
            if user.email:
                claims["email"] = user.email
            if user.gender:
                claims["gender"] = user.gender
        header = {"alg": "ES256", "typ": "JWT"}
        signing_input = (
            f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}."
            f"{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
        )
        der = self._key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return f"{signing_input}.{_b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"

    # ---- portal calls ---------------------------------------------------

    def _call(self, path: str, assertion: str):
        try:
            return self._post(
                f"{self._url}{MOBILE_API_PREFIX}/session/{path}",
                json={"assertion": assertion},
                timeout=PORTAL_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            logger.warning(f"health educator portal unreachable: {e}")
            raise HealthEducatorUnavailable() from e

    def open_session(self, user: User) -> Dict[str, Any]:
        """Portal session for an ACTIVE user: tokens + where the app calls.

        Raises:
            HealthEducatorNotConfigured, HealthEducatorUnavailable,
            HealthEducatorRefused
        """
        if not user.is_active:
            raise HealthEducatorRefused()
        resp = self._call("exchange", self.sign_assertion(user, "login"))
        if resp.status_code == 403:
            logger.warning(f"health educator refused user={user.user_id}")
            raise HealthEducatorRefused()
        if resp.status_code != 200:
            logger.warning(f"health educator exchange failed user={user.user_id} "
                           f"status={resp.status_code}")
            raise HealthEducatorUnavailable()
        body = resp.json()
        logger.info(f"health educator session opened user={user.user_id} "
                    f"created={body.get('created')}")
        return {
            "access_token": body["access_token"],
            "refresh_token": body.get("refresh_token"),
            "token_type": "Bearer",
            "expires_in": body.get("expires_in"),
            "base_url": self._public_url,
            "api_prefix": MOBILE_API_PREFIX,
            "user": body.get("user"),
        }

    def enroll(self, user: User) -> Dict[str, Any]:
        """Create/link the user's portal member account WITHOUT a session.

        Unlike open_session, no tokens are minted and the portal records no
        login, so bulk enrollment does not stamp a false "last login" on
        every account. Safe to repeat: an already-enrolled user comes back
        with created=False, linked=False (the portal refreshes gender).

        Raises:
            HealthEducatorNotConfigured, HealthEducatorUnavailable,
            HealthEducatorRefused
        """
        if not user.is_active:
            raise HealthEducatorRefused()
        resp = self._call("enroll", self.sign_assertion(user, "enroll"))
        if resp.status_code == 403:
            logger.warning(f"health educator refused enrollment user={user.user_id}")
            raise HealthEducatorRefused()
        if resp.status_code != 200:
            logger.warning(f"health educator enroll failed user={user.user_id} "
                           f"status={resp.status_code}")
            raise HealthEducatorUnavailable()
        body = resp.json()
        logger.info(f"health educator enrolled user={user.user_id} "
                    f"created={body.get('created')} linked={body.get('linked')}")
        return {
            "username": body.get("username"),
            "gender": body.get("gender"),
            "service_line": body.get("service_line"),
            "created": bool(body.get("created")),
            "linked": bool(body.get("linked")),
        }

    def revoke_sessions(self, user: User) -> bool:
        """Best effort: end the user's portal sessions (deactivated here).

        Never raises - deactivating a smart home user must not fail because
        the portal is down; new sign-ons are already blocked at the source.
        """
        if not self.configured:
            return False
        try:
            resp = self._call("revoke", self.sign_assertion(user, "revoke"))
            ok = resp.status_code == 200
        except Exception:
            ok = False
        if not ok:
            logger.warning(f"health educator revoke failed user={user.user_id}")
        return ok
