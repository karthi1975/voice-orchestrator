"""Mobile login + identity endpoints for the SmartHome app.

Mounted at the same base URL as the voice-auth API so mobile keeps a
single BASE:

    POST /api/v1/voice-auth/auth/login   -> JWT + user_ref + home_id(s)
    GET  /api/v1/voice-auth/me           -> user_ref + home_id(s) (JWT required)

This is a separate blueprint from voice_auth_api on purpose:
- /auth/login must be reachable WITHOUT a bearer token,
- the existing static-key middleware on voice_auth_api stays untouched.
"""

import logging
from typing import Any, Tuple

from flask import Blueprint, jsonify, request

from app.services.mobile_auth_service import MobileAuthService, RateLimitedError

logger = logging.getLogger(__name__)


class MobileAuthController:
    """Login + bootstrap endpoints backed by MobileAuthService."""

    def __init__(self, service: MobileAuthService, url_prefix: str = "/api/v1/voice-auth"):
        self._svc = service
        self.blueprint = Blueprint("mobile_auth", __name__, url_prefix=url_prefix)
        self._register_routes()

    def _register_routes(self) -> None:
        self.blueprint.add_url_rule("/auth/login", "mobile_login", self.login, methods=["POST"])
        self.blueprint.add_url_rule("/me", "mobile_me", self.me, methods=["GET"])

    def _bearer(self) -> str:
        hdr = request.headers.get("Authorization", "")
        return hdr[7:].strip() if hdr.lower().startswith("bearer ") else ""

    def login(self) -> Tuple[Any, int]:
        """POST /auth/login {"email": "...", "password": "..."}

        Accepts "email" or "username" as the identifier. On success returns
        the token AND the full identity bootstrap, so app startup is one call:

            { "token": "...", "token_type": "Bearer", "expires_in": 2592000,
              "user_ref": "...", "user_id": "...", "email": "...",
              "homes": [{"home_id": "...", "name": "..."}],
              "default_home_id": "..." }
        """
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({
                "error": "JSON body required",
                "code": "VALIDATION",
            }), 400

        identifier = body.get("email") or body.get("username")
        password = body.get("password")
        if not isinstance(identifier, str) or not isinstance(password, str) \
                or not identifier.strip() or not password:
            return jsonify({
                "error": "email (or username) and password are required",
                "code": "VALIDATION",
            }), 400
        identifier = identifier.strip()

        try:
            user = self._svc.login(identifier, password, client_ip=request.remote_addr)
        except RateLimitedError:
            logger.warning(
                f"mobile login rate-limited identifier={identifier!r} ip={request.remote_addr}"
            )
            return jsonify({
                "error": "Too many failed attempts. Try again later.",
                "code": "RATE_LIMITED",
            }), 429

        if user is None:
            # One generic message — do not reveal which part was wrong.
            logger.warning(
                f"mobile login failed identifier={identifier!r} ip={request.remote_addr}"
            )
            return jsonify({"error": "Invalid credentials", "code": "UNAUTHORIZED"}), 401

        issued = self._svc.issue_token(user.user_id)
        payload = {
            "token": issued["token"],
            "token_type": "Bearer",
            "expires_in": issued["expires_in"],
            **self._svc.bootstrap(user),
        }
        logger.info(f"mobile login ok user={user.user_id}")
        return jsonify(payload), 200

    def me(self) -> Tuple[Any, int]:
        """GET /me — resolve the caller's user_ref/home_id from their JWT.

        Static platform keys are rejected here on purpose: they identify
        only the app platform, not a person, so there is no identity to
        return. The app must log in first.
        """
        token = self._bearer()
        if not token:
            return jsonify({
                "error": "Missing Authorization header. Expected: Bearer <login token>",
                "code": "UNAUTHORIZED",
            }), 401

        user_id = self._svc.verify_token(token)
        if user_id is None:
            return jsonify({
                "error": "Invalid or expired token. POST /auth/login to get a new one.",
                "code": "UNAUTHORIZED",
            }), 401

        user = self._svc.get_user(user_id)
        if user is None or not user.is_active:
            return jsonify({"error": "User not found or inactive", "code": "UNAUTHORIZED"}), 401

        return jsonify(self._svc.bootstrap(user)), 200
