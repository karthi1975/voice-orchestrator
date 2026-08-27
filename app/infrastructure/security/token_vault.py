"""Encrypt-at-rest vault for per-home Home Assistant tokens.

Fernet (AES-128-CBC + HMAC) symmetric encryption. Key sources, in order:

  1. HA_TOKEN_KEY env var — a Fernet key (44-char urlsafe base64).
     Generate with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     RECOMMENDED in production: survives SECRET_KEY rotation.
  2. Derived from SECRET_KEY (sha256 -> urlsafe b64). Works out of the box,
     but rotating SECRET_KEY then orphans stored tokens (logged warning).

Ciphertexts are prefixed "fv1:" so plaintext/legacy values are recognizable.
"""
import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_PREFIX = "fv1:"


class TokenVault:
    """Encrypts/decrypts HA long-lived tokens for DB storage."""

    def __init__(self, key: Optional[str] = None):
        key = (key or os.environ.get("HA_TOKEN_KEY", "")).strip()
        if key:
            self._fernet = Fernet(key.encode())
            self._derived = False
        else:
            secret = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
            digest = hashlib.sha256(("ha-token-vault:" + secret).encode()).digest()
            self._fernet = Fernet(base64.urlsafe_b64encode(digest))
            self._derived = True
            logger.warning(
                "TokenVault: HA_TOKEN_KEY not set — deriving key from SECRET_KEY. "
                "Set HA_TOKEN_KEY so token storage survives SECRET_KEY rotation."
            )

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Encrypt a token. None/empty -> None (means: no token stored)."""
        if not plaintext or not plaintext.strip():
            return None
        return _PREFIX + self._fernet.encrypt(plaintext.strip().encode()).decode()

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt a stored value. Returns None on missing/undecryptable."""
        if not ciphertext:
            return None
        raw = ciphertext[len(_PREFIX):] if ciphertext.startswith(_PREFIX) else ciphertext
        try:
            return self._fernet.decrypt(raw.encode()).decode()
        except (InvalidToken, ValueError):
            logger.error(
                "TokenVault: could not decrypt stored token (wrong HA_TOKEN_KEY "
                "or rotated SECRET_KEY?) — treating as absent"
            )
            return None

    @staticmethod
    def hint(plaintext: Optional[str]) -> Optional[str]:
        """Non-secret display hint: last 4 chars."""
        if not plaintext or len(plaintext) < 8:
            return None
        return "…" + plaintext[-4:]
