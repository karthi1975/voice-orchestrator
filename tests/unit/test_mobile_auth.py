"""
Tests for mobile login + identity bootstrap (Tier 2 auth).

Covers:
- JWT issue/verify roundtrip, tampering, expiry
- MobileAuthService.login (email/username, wrong password, inactive, no password)
- POST /auth/login and GET /me endpoints
- voice_auth_api_key middleware: static keys unchanged, JWTs accepted,
  user_ref mismatch rejected
- password_hash survives profile updates (data-continuity regression)
"""

import os
import time

import pytest
from flask import Blueprint, Flask, g, jsonify

from app.controllers.mobile_auth_controller import MobileAuthController
from app.domain.models import Home, User
from app.middleware.voice_auth_api_key import attach_mobile_api_key_auth
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
from app.services.mobile_auth_service import MobileAuthService
from app.services.user_service import UserService


SECRET = "test-secret-do-not-use"


@pytest.fixture
def repos():
    users = InMemoryUserRepository()
    homes = InMemoryHomeRepository()
    users.add(User(
        user_id="scott_mobile",
        username="scott",
        full_name="Scott",
        email="scott@example.com",
        password_hash=User.hash_password("hunter2"),
    ))
    homes.add(Home(
        home_id="scott_home",
        user_id="scott_mobile",
        name="Scott's House",
        ha_url="https://ha.example.com",
        ha_webhook_id="voice_auth_scene",
    ))
    return users, homes


@pytest.fixture
def service(repos):
    users, homes = repos
    return MobileAuthService(users, homes, secret=SECRET)


@pytest.fixture
def client(service):
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(service).blueprint)
    return app.test_client()


# --- JWT ---

class TestToken:
    def test_roundtrip(self, service):
        token = service.issue_token("scott_mobile")["token"]
        assert service.verify_token(token) == "scott_mobile"

    def test_tampered_signature_rejected(self, service):
        token = service.issue_token("scott_mobile")["token"]
        head, payload, sig = token.split(".")
        flipped = ("B" if sig[0] == "A" else "A") + sig[1:]  # guaranteed change
        bad = f"{head}.{payload}.{flipped}"
        assert service.verify_token(bad) is None

    def test_wrong_secret_rejected(self, repos, service):
        users, homes = repos
        other = MobileAuthService(users, homes, secret="other-secret")
        token = other.issue_token("scott_mobile")["token"]
        assert service.verify_token(token) is None

    def test_expired_rejected(self, repos):
        users, homes = repos
        svc = MobileAuthService(users, homes, secret=SECRET, ttl_seconds=-10)
        token = svc.issue_token("scott_mobile")["token"]
        assert svc.verify_token(token) is None

    def test_garbage_rejected(self, service):
        assert service.verify_token("not-a-token") is None
        assert service.verify_token("") is None
        assert service.verify_token("a.b.c") is None


# --- Service login ---

class TestLogin:
    def test_by_email(self, service):
        user = service.login("scott@example.com", "hunter2")
        assert user is not None and user.user_id == "scott_mobile"

    def test_by_username(self, service):
        user = service.login("scott", "hunter2")
        assert user is not None and user.user_id == "scott_mobile"

    def test_wrong_password(self, service):
        assert service.login("scott", "nope") is None

    def test_unknown_user(self, service):
        assert service.login("nobody", "hunter2") is None

    def test_no_password_set(self, repos, service):
        users, _ = repos
        users.add(User(user_id="u2", username="nopw", full_name="No PW"))
        assert service.login("nopw", "anything") is None

    def test_inactive_user_pending(self, repos, service):
        from app.services.mobile_auth_service import PendingApprovalError
        users, _ = repos
        users.deactivate("scott_mobile")
        with pytest.raises(PendingApprovalError):
            service.login("scott", "hunter2")

    def test_inactive_wrong_password_stays_generic(self, repos, service):
        # Wrong password on an inactive account must NOT reveal pending state.
        users, _ = repos
        users.deactivate("scott_mobile")
        assert service.login("scott", "wrong-pass") is None


# --- Endpoints ---

class TestEndpoints:
    def test_login_returns_token_and_bootstrap(self, client):
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": "scott@example.com", "password": "hunter2"})
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["token_type"] == "Bearer"
        assert body["user_ref"] == "scott_mobile"
        assert body["user_id"] == "scott_mobile"
        assert body["email"] == "scott@example.com"
        assert body["default_home_id"] == "scott_home"
        assert body["homes"] == [{"home_id": "scott_home", "name": "Scott's House"}]

    def test_login_bad_credentials(self, client):
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": "scott@example.com", "password": "nope"})
        assert rv.status_code == 401

    def test_login_missing_fields(self, client):
        rv = client.post("/api/v1/voice-auth/auth/login", json={"email": "x"})
        assert rv.status_code == 400

    def test_me_with_token(self, client):
        token = client.post("/api/v1/voice-auth/auth/login",
                            json={"email": "scott@example.com", "password": "hunter2"}
                            ).get_json()["token"]
        rv = client.get("/api/v1/voice-auth/me",
                        headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["user_ref"] == "scott_mobile"
        assert body["email"] == "scott@example.com"
        assert body["default_home_id"] == "scott_home"

    def test_me_without_token(self, client):
        assert client.get("/api/v1/voice-auth/me").status_code == 401

    def test_me_with_static_platform_key_rejected(self, client):
        rv = client.get("/api/v1/voice-auth/me",
                        headers={"Authorization": "Bearer sk_ios_abc"})
        assert rv.status_code == 401


# --- Sign-up (Tier 2: admin approval) ---

class TestSignup:
    def test_signup_creates_pending_account(self, client, repos):
        users, _ = repos
        rv = client.post("/api/v1/voice-auth/auth/signup",
                         json={"email": "New.User@Example.com",
                               "password": "goodpass99", "full_name": "New User"})
        assert rv.status_code == 201
        body = rv.get_json()
        assert body["status"] == "pending_approval"
        assert body["email"] == "new.user@example.com"  # normalized
        user = users.get_by_email("new.user@example.com")
        assert user is not None and user.is_active is False

    def test_pending_account_cannot_login_403(self, client):
        client.post("/api/v1/voice-auth/auth/signup",
                    json={"email": "p@x.com", "password": "goodpass99",
                          "full_name": "P"})
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": "p@x.com", "password": "goodpass99"})
        assert rv.status_code == 403
        assert rv.get_json()["code"] == "PENDING_APPROVAL"

    def test_activated_account_can_login(self, client, repos):
        users, _ = repos
        client.post("/api/v1/voice-auth/auth/signup",
                    json={"email": "a@x.com", "password": "goodpass99",
                          "full_name": "A"})
        users.activate(users.get_by_email("a@x.com").user_id)
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": "a@x.com", "password": "goodpass99"})
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["homes"] == [] and body["default_home_id"] is None

    def test_duplicate_email_409(self, client):
        rv = client.post("/api/v1/voice-auth/auth/signup",
                         json={"email": "scott@example.com",
                               "password": "goodpass99", "full_name": "Imposter"})
        assert rv.status_code == 409
        assert rv.get_json()["code"] == "EMAIL_EXISTS"

    def test_validation_errors_400(self, client):
        for payload in (
            {"email": "not-an-email", "password": "goodpass99", "full_name": "X"},
            {"email": "v@x.com", "password": "short", "full_name": "X"},
            {"email": "v@x.com", "password": "goodpass99", "full_name": ""},
            {"email": 42, "password": "goodpass99", "full_name": "X"},
        ):
            rv = client.post("/api/v1/voice-auth/auth/signup", json=payload)
            assert rv.status_code == 400, payload

    def test_signup_rate_limited_per_ip(self, client):
        for i in range(5):
            client.post("/api/v1/voice-auth/auth/signup",
                        json={"email": f"u{i}@x.com", "password": "goodpass99",
                              "full_name": "U"})
        rv = client.post("/api/v1/voice-auth/auth/signup",
                         json={"email": "u6@x.com", "password": "goodpass99",
                               "full_name": "U"})
        assert rv.status_code == 429

    def test_wrong_password_on_pending_is_generic_401(self, client):
        client.post("/api/v1/voice-auth/auth/signup",
                    json={"email": "q@x.com", "password": "goodpass99",
                          "full_name": "Q"})
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": "q@x.com", "password": "wrong-pass"})
        assert rv.status_code == 401  # no pending-state leak without the password


# --- Change password ---

class TestChangePassword:
    def _token(self, client):
        return client.post("/api/v1/voice-auth/auth/login",
                           json={"email": "scott@example.com", "password": "hunter2"}
                           ).get_json()["token"]

    def test_success_and_old_password_invalidated(self, client, service):
        token = self._token(client)
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"current_password": "hunter2", "new_password": "brandnew99"})
        assert rv.status_code == 204
        assert service.login("scott", "hunter2") is None
        assert service.login("scott", "brandnew99") is not None
        # existing token still valid until expiry
        rv = client.get("/api/v1/voice-auth/me",
                        headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 200

    def test_wrong_current_password_403(self, client):
        token = self._token(client)
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"current_password": "wrong", "new_password": "brandnew99"})
        assert rv.status_code == 403

    def test_weak_new_password_400(self, client):
        token = self._token(client)
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"current_password": "hunter2", "new_password": "short"})
        assert rv.status_code == 400

    def test_no_token_401(self, client):
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         json={"current_password": "hunter2", "new_password": "brandnew99"})
        assert rv.status_code == 401

    def test_non_string_values_400(self, client):
        token = self._token(client)
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"current_password": 1, "new_password": ["x"]})
        assert rv.status_code == 400

    def test_rate_limited_after_failures(self, client):
        token = self._token(client)
        for _ in range(5):
            client.post("/api/v1/voice-auth/auth/change-password",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"current_password": "wrong", "new_password": "brandnew99"})
        rv = client.post("/api/v1/voice-auth/auth/change-password",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"current_password": "hunter2", "new_password": "brandnew99"})
        assert rv.status_code == 429


# --- Middleware: JWT + static keys side by side ---

@pytest.fixture
def guarded_client(service, repos, monkeypatch):
    monkeypatch.setenv("MOBILE_API_KEY_IOS", "sk_ios_testkey")
    _, homes = repos
    app = Flask(__name__)
    bp = Blueprint("voice_auth_api", __name__, url_prefix="/api/v1/voice-auth")

    @bp.route("/whoami", methods=["GET", "POST"])
    def whoami():
        return jsonify({
            "platform": g.mobile_platform,
            "user_ref": getattr(g, "user_ref", None),
        })

    attach_mobile_api_key_auth(bp, token_verifier=service.verify_token,
                               is_home_owner=homes.exists_for_user)
    app.register_blueprint(bp)
    return app.test_client()


class TestMiddleware:
    def test_static_key_still_works(self, guarded_client):
        rv = guarded_client.get("/api/v1/voice-auth/whoami",
                                headers={"Authorization": "Bearer sk_ios_testkey"})
        assert rv.status_code == 200
        assert rv.get_json() == {"platform": "ios", "user_ref": None}

    def test_jwt_accepted_and_sets_user_ref(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.get("/api/v1/voice-auth/whoami",
                                headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 200
        assert rv.get_json() == {"platform": "jwt", "user_ref": "scott_mobile"}

    def test_jwt_matching_user_ref_in_body_allowed(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.post("/api/v1/voice-auth/whoami",
                                 headers={"Authorization": f"Bearer {token}"},
                                 json={"user_ref": "scott_mobile"})
        assert rv.status_code == 200

    def test_jwt_mismatched_user_ref_in_body_forbidden(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.post("/api/v1/voice-auth/whoami",
                                 headers={"Authorization": f"Bearer {token}"},
                                 json={"user_ref": "someone_else"})
        assert rv.status_code == 403

    def test_jwt_mismatched_user_ref_in_query_forbidden(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.get(
            "/api/v1/voice-auth/whoami?user_ref=someone_else",
            headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 403

    def test_bad_bearer_still_401(self, guarded_client):
        rv = guarded_client.get("/api/v1/voice-auth/whoami",
                                headers={"Authorization": "Bearer wrong"})
        assert rv.status_code == 401

    def test_jwt_mismatched_user_ref_in_form_forbidden(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.post("/api/v1/voice-auth/whoami",
                                 headers={"Authorization": f"Bearer {token}"},
                                 data={"user_ref": "someone_else"})
        assert rv.status_code == 403

    def test_jwt_own_home_allowed(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.get("/api/v1/voice-auth/whoami?home_id=scott_home",
                                headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 200

    def test_jwt_foreign_home_forbidden(self, guarded_client, service):
        token = service.issue_token("scott_mobile")["token"]
        rv = guarded_client.get("/api/v1/voice-auth/whoami?home_id=other_home",
                                headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 403
        rv = guarded_client.post("/api/v1/voice-auth/whoami",
                                 headers={"Authorization": f"Bearer {token}"},
                                 json={"home_id": "other_home"})
        assert rv.status_code == 403

    def test_static_key_foreign_home_untouched(self, guarded_client):
        # Legacy trust model: static-key callers are NOT home-gated.
        rv = guarded_client.get("/api/v1/voice-auth/whoami?home_id=other_home",
                                headers={"Authorization": "Bearer sk_ios_testkey"})
        assert rv.status_code == 200


# --- Admin guard ---

class TestAdminGuard:
    @pytest.fixture
    def admin_app(self, monkeypatch):
        monkeypatch.delenv("ADMIN_AUTH_OPEN", raising=False)
        monkeypatch.setenv("ADMIN_API_TOKEN", "admintoken123")
        from app.middleware.admin_auth import attach_admin_auth
        app = Flask(__name__)
        app.secret_key = "test"
        bp = Blueprint("admin", __name__, url_prefix="/admin")

        @bp.route("/users")
        def users():
            return jsonify({"ok": True})

        attach_admin_auth(bp)
        app.register_blueprint(bp)
        return app

    def test_unauthenticated_401(self, admin_app):
        assert admin_app.test_client().get("/admin/users").status_code == 401

    def test_admin_token_allowed(self, admin_app):
        rv = admin_app.test_client().get(
            "/admin/users", headers={"Authorization": "Bearer admintoken123"})
        assert rv.status_code == 200

    def test_wrong_token_401(self, admin_app):
        rv = admin_app.test_client().get(
            "/admin/users", headers={"Authorization": "Bearer nope"})
        assert rv.status_code == 401

    def test_admin_session_allowed(self, admin_app):
        client = admin_app.test_client()
        with client.session_transaction() as sess:
            sess["admin_user"] = "karthi"
        assert client.get("/admin/users").status_code == 200


# --- Data continuity ---

class TestPasswordPersistence:
    def test_profile_update_keeps_password(self, repos):
        users, _ = repos
        svc = UserService(users)
        svc.update_user("scott_mobile", full_name="Scott J")
        assert users.get_by_id("scott_mobile").check_password("hunter2")

    def test_set_password(self, repos):
        users, _ = repos
        svc = UserService(users)
        svc.set_password("scott_mobile", "new-pass")
        user = users.get_by_id("scott_mobile")
        assert user.check_password("new-pass")
        assert not user.check_password("hunter2")

    def test_create_user_with_explicit_id_and_password(self, repos):
        users, _ = repos
        svc = UserService(users)
        user = svc.create_user(username="aaron", full_name="Aaron",
                               user_id="aaron_mobile", password="pw123456")
        assert user.user_id == "aaron_mobile"
        assert users.get_by_id("aaron_mobile").check_password("pw123456")

    def test_short_password_rejected(self, repos):
        users, _ = repos
        svc = UserService(users)
        with pytest.raises(ValueError):
            svc.set_password("scott_mobile", "short")
        with pytest.raises(ValueError):
            svc.create_user(username="x", full_name="X", password="short")


# --- Hardening: edge cases and abuse ---

class TestLoginHardening:
    def test_non_string_credentials_rejected(self, service):
        assert service.login(12345, "hunter2") is None
        assert service.login("scott", {"$gt": ""}) is None
        assert service.login(None, None) is None

    def test_oversized_credentials_rejected(self, service):
        assert service.login("a" * 1000, "hunter2") is None
        assert service.login("scott", "x" * 100_000) is None

    def test_email_case_insensitive_fallback(self, repos):
        users, homes = repos
        svc = MobileAuthService(users, homes, secret=SECRET)
        user = svc.login("Scott@Example.com".lower(), "hunter2")
        assert user is not None

    def test_rate_limit_locks_after_failures(self, service):
        from app.services.mobile_auth_service import RateLimitedError
        for _ in range(5):
            assert service.login("scott", "wrong", client_ip="1.2.3.4") is None
        with pytest.raises(RateLimitedError):
            service.login("scott", "hunter2", client_ip="1.2.3.4")

    def test_rate_limit_endpoint_returns_429(self, client):
        for _ in range(5):
            client.post("/api/v1/voice-auth/auth/login",
                        json={"username": "scott", "password": "wrong"})
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"username": "scott", "password": "hunter2"})
        assert rv.status_code == 429
        assert rv.get_json()["code"] == "RATE_LIMITED"

    def test_success_resets_counter(self, service):
        for _ in range(3):
            service.login("scott", "wrong", client_ip="5.6.7.8")
        assert service.login("scott", "hunter2", client_ip="5.6.7.8") is not None
        for _ in range(3):
            service.login("scott", "wrong", client_ip="5.6.7.8")
        assert service.login("scott", "hunter2", client_ip="5.6.7.8") is not None

    def test_login_non_json_body(self, client):
        rv = client.post("/api/v1/voice-auth/auth/login", data="not json",
                         content_type="text/plain")
        assert rv.status_code == 400

    def test_login_non_string_json_values(self, client):
        rv = client.post("/api/v1/voice-auth/auth/login",
                         json={"email": 123, "password": ["x"]})
        assert rv.status_code == 400
