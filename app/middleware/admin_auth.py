"""Auth guard for the /admin/* API.

Historically these routes were unauthenticated — anyone who could reach the
server could create/delete users and homes (and, with mobile login, reset a
user's password and take over their account). This guard closes that.

A request is allowed if EITHER:
  - it carries a logged-in admin session (the static admin dashboard flow:
    POST /auth/login sets session['admin_user']), or
  - it carries `Authorization: Bearer <ADMIN_API_TOKEN>` where the token
    matches the ADMIN_API_TOKEN env var (for curl/scripts; timing-safe).

Escape hatch: set ADMIN_AUTH_OPEN=true to restore the old open behavior
(logged loudly; for local dev only).
"""

import hmac
import logging
import os
from typing import Optional

from flask import Blueprint, Response, jsonify, request, session

logger = logging.getLogger(__name__)


def attach_admin_auth(blueprint: Blueprint) -> None:
    """Wire the admin auth check onto the blueprint's before_request hook."""

    if os.environ.get("ADMIN_AUTH_OPEN", "").strip().lower() == "true":
        logger.warning(
            "⚠ ADMIN_AUTH_OPEN=true: /admin/* routes are UNAUTHENTICATED. "
            "Never use this outside local development."
        )
        return

    @blueprint.before_request
    def _check_admin_auth() -> Optional[Response]:
        if request.method == "OPTIONS":
            return None

        # Admin dashboard session (set by POST /auth/login)
        if session.get("admin_user"):
            return None

        # Scripted access via static admin token
        admin_token = os.environ.get("ADMIN_API_TOKEN", "").strip()
        if admin_token:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.lower().startswith("bearer "):
                presented = auth_hdr[7:].strip()
                if presented and hmac.compare_digest(
                    presented.encode("utf-8"), admin_token.encode("utf-8")
                ):
                    return None

        logger.warning(
            f"admin 401 path={request.path} remote={request.remote_addr}"
        )
        return jsonify({
            "error": "Admin authentication required. Log in via /auth/login "
                     "or send Authorization: Bearer <ADMIN_API_TOKEN>.",
            "code": "UNAUTHORIZED",
        }), 401
