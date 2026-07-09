"""Tier 1 API-key middleware for /api/v1/voice-auth/*.

Reads API keys from environment variables. Two forms accepted (first wins):

  1. Individual env vars (recommended — dodges Docker --env-file quote stripping):
       MOBILE_API_KEY_IOS=sk_ios_abc…
       MOBILE_API_KEY_ANDROID=sk_and_def…
       MOBILE_API_KEY_WEB=sk_web_ghi…
     Any env var matching MOBILE_API_KEY_<LABEL> registers that label.

  2. JSON dict (convenient for local dev):
       MOBILE_API_KEYS_JSON='{"ios":"sk_ios_…","android":"sk_and_…"}'

Every request to the voice_auth_controller blueprint must carry:

    Authorization: Bearer <secret_key>

On success:
  - g.mobile_platform is set to the matching platform label (lowercased)
On failure:
  - 401 { "error": "unauthorized", "code": "UNAUTHORIZED" }
  - timing-safe comparison (no leaking of which keys are known)

If no keys are configured at all, the middleware falls OPEN (allows all)
and logs a prominent warning — fine for local dev, bad for prod.

Tier 2 (implemented): pass a `token_verifier` to also accept JWT login
tokens (from POST /auth/login). A JWT bearer sets g.user_ref from the
token's `sub` claim; static platform keys keep working unchanged, so
existing app builds are undisturbed. The header shape
(`Authorization: Bearer ...`) is identical for both.
"""

import hmac
import json
import logging
import os
from typing import Callable, Dict, Optional

from flask import Blueprint, Response, g, jsonify, request

logger = logging.getLogger(__name__)


def _load_keys() -> Dict[str, str]:
    # Prefer individual MOBILE_API_KEY_<LABEL> vars — robust against Docker
    # --env-file quote stripping.
    keys: Dict[str, str] = {}
    prefix = "MOBILE_API_KEY_"
    for k, v in os.environ.items():
        if k.startswith(prefix) and v:
            label = k[len(prefix):].lower()
            if label:
                keys[label] = v
    if keys:
        return keys

    # Fallback: MOBILE_API_KEYS_JSON={"ios":"…","android":"…"}
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
    return {str(k).lower(): str(v) for k, v in data.items() if v}


def _match_key(presented: str, keys: Dict[str, str]) -> Optional[str]:
    """Timing-safe key comparison. Returns the matching label or None."""
    # Compare against every key so timing doesn't reveal the first-match index.
    matched: Optional[str] = None
    for label, secret in keys.items():
        if hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8")):
            matched = label
    return matched


def _request_values(field: str) -> list:
    """Collect a field's values from query string, form body, and JSON body."""
    values = []
    values.extend(request.args.getlist(field))
    if request.mimetype == "application/x-www-form-urlencoded" or request.form:
        values.extend(request.form.getlist(field))
    body = request.get_json(silent=True)
    if isinstance(body, dict) and field in body:
        values.append(body.get(field))
    return values


def _find_user_ref_mismatch(token_user: str) -> Optional[str]:
    """If the request carries a user_ref that differs from the token's user,
    return the offending value; otherwise None.

    Only enforced for JWT callers — static-key callers are legacy-trusted and
    keep today's behavior. Guards query string, form body, and JSON body.
    """
    for supplied in _request_values("user_ref"):
        if isinstance(supplied, str) and supplied.strip() and supplied.strip() != token_user:
            return supplied.strip()
    return None


def _find_foreign_home(token_user: str,
                       is_home_owner: Callable[[str, str], bool]) -> Optional[str]:
    """If the request names a home_id the token's user does not own, return
    it; otherwise None. JWT callers only — same rationale as user_ref."""
    for supplied in _request_values("home_id"):
        if isinstance(supplied, str) and supplied.strip():
            home_id = supplied.strip()
            if not is_home_owner(token_user, home_id):
                return home_id
    return None


def attach_mobile_api_key_auth(
    blueprint: Blueprint,
    token_verifier: Optional[Callable[[str], Optional[str]]] = None,
    is_home_owner: Optional[Callable[[str, str], bool]] = None,
) -> None:
    """Wire the Bearer-key check onto the given blueprint's before_request hook.

    Call this once, after routes are registered on the blueprint.

    Args:
        token_verifier: optional callable(token) -> user_id | None. When
            provided, a bearer that verifies as a JWT login token is accepted
            and g.user_ref is set from it. Static keys are checked afterwards
            exactly as before, so omitting this keeps the old behavior.
        is_home_owner: optional callable(user_id, home_id) -> bool. When
            provided, JWT callers naming a home_id they do not own get 403.
            Static-key callers are never affected.
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

        # Tier 2: accept a JWT login token as an alternative to the static
        # platform keys. Checked first (cheap, signature-based); on failure we
        # fall through to the static-key path so old app builds are unaffected.
        if token_verifier is not None and presented.count(".") == 2:
            token_user = token_verifier(presented)
            if token_user is not None:
                mismatch = _find_user_ref_mismatch(token_user)
                if mismatch is not None:
                    logger.warning(
                        f"voice_auth 403 user_ref mismatch token={token_user!r} "
                        f"request={mismatch!r} path={request.path}"
                    )
                    return jsonify({
                        "error": "user_ref does not match the authenticated user",
                        "code": "FORBIDDEN",
                    }), 403
                if is_home_owner is not None:
                    foreign = _find_foreign_home(token_user, is_home_owner)
                    if foreign is not None:
                        logger.warning(
                            f"voice_auth 403 foreign home user={token_user!r} "
                            f"home={foreign!r} path={request.path}"
                        )
                        return jsonify({
                            "error": f"home '{foreign}' does not belong to the authenticated user",
                            "code": "FORBIDDEN",
                        }), 403
                g.mobile_platform = "jwt"
                g.user_ref = token_user
                return None

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
