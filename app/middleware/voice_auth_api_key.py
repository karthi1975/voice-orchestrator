"""Tier 1 API-key middleware for /api/v1/voice-auth/*.

Reads MOBILE_API_KEYS_JSON env var, a dict of {platform_label: secret_key}:

    MOBILE_API_KEYS_JSON='{"ios":"sk_ios_abc…","android":"sk_and_def…","web":"sk_web_ghi…"}'

Every request to the voice_auth_controller blueprint must carry:

    Authorization: Bearer <secret_key>

On success:
  - request.mobile_platform is set to the matching platform label
  - audit log lines include the label
On failure:
  - 401 { "error": "unauthorized", "code": "UNAUTHORIZED" }
  - timing-safe comparison (no leaking of which keys are known)

If MOBILE_API_KEYS_JSON is missing or empty, the middleware falls OPEN
(allows all) and logs a prominent warning. This keeps local dev / CI
working without mandatory keys, while production deploys that set the
env get enforcement.

Tier 2 will replace this with JWT-signed `sub=user_ref` claims; the
header shape (`Authorization: Bearer ...`) stays the same, so mobile
clients never change their request code.
"""

import hmac
import json
import logging
import os
from typing import Dict, Optional

from flask import Blueprint, Response, g, jsonify, request

logger = logging.getLogger(__name__)


def _load_keys() -> Dict[str, str]:
    raw = os.environ.get("MOBILE_API_KEYS_JSON") or ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"MOBILE_API_KEYS_JSON: parse error ({e}); treating as empty")
        return {}
    if not isinstance(data, dict):
        logger.error("MOBILE_API_KEYS_JSON: must be a JSON object {label: key}; got %s", type(data).__name__)
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def _match_key(presented: str, keys: Dict[str, str]) -> Optional[str]:
    """Timing-safe key comparison. Returns the matching label or None."""
    # Compare against every key so timing doesn't reveal the first-match index.
    matched: Optional[str] = None
    for label, secret in keys.items():
        if hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8")):
            matched = label
    return matched


def attach_mobile_api_key_auth(blueprint: Blueprint) -> None:
    """Wire the Bearer-key check onto the given blueprint's before_request hook.

    Call this once, after routes are registered on the blueprint.
    """
    keys = _load_keys()

    if not keys:
        logger.warning(
            "⚠ voice_auth API-key middleware is OPEN: MOBILE_API_KEYS_JSON is not set. "
            "All /api/v1/voice-auth/* routes accept any caller. Set the env var to enforce."
        )
    else:
        logger.info(f"voice_auth API-key middleware enforcing: known platforms={list(keys.keys())}")

    @blueprint.before_request
    def _check_bearer() -> Optional[Response]:
        # Always allow CORS preflight — browsers send OPTIONS without auth.
        if request.method == "OPTIONS":
            return None

        # If no keys configured, fall open (dev/local).
        if not keys:
            g.mobile_platform = "UNAUTHENTICATED"
            return None

        auth_hdr = request.headers.get("Authorization", "")
        if not auth_hdr.lower().startswith("bearer "):
            return jsonify({
                "error": "Missing or malformed Authorization header. Expected: Bearer <key>",
                "code": "UNAUTHORIZED",
            }), 401

        presented = auth_hdr[7:].strip()
        if not presented:
            return jsonify({"error": "Empty bearer token", "code": "UNAUTHORIZED"}), 401

        label = _match_key(presented, keys)
        if label is None:
            # Do not echo the key; log a truncated hash-free marker.
            logger.warning(
                f"voice_auth 401 path={request.path} "
                f"ua={request.headers.get('User-Agent','')[:50]!r} "
                f"remote={request.remote_addr}"
            )
            return jsonify({"error": "Invalid API key", "code": "UNAUTHORIZED"}), 401

        g.mobile_platform = label
        # Keep this log quiet — too chatty if on every call, but useful in audit.
        logger.debug(f"voice_auth auth ok platform={label} path={request.path}")
        return None
