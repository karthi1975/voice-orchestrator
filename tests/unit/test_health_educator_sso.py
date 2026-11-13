"""
Gender on the user profile + single sign-on into the health educator portal.

- gender: admin create / update / clear / invalid; PATCH /me; GET /me; both
  repository backends
- assertion: ES256, verifiable with the public key, carries the profile
- POST /health-educator/session: auth, every active user eligible, portal
  errors mapped, not-configured answers 503
- deactivation ends the user's portal sessions (best effort)
"""

import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.controllers.admin_controller import AdminController
from app.controllers.mobile_auth_controller import MobileAuthController
from app.domain.models import User
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
from app.repositories.implementations.sqlalchemy_home_repo import SQLAlchemyHomeRepository
from app.repositories.implementations.sqlalchemy_models import Base
from app.repositories.implementations.sqlalchemy_user_repo import SQLAlchemyUserRepository
from app.services.health_educator_service import HealthEducatorService
from app.services.home_service import HomeService
from app.services.mobile_auth_service import MobileAuthService
from app.services.user_service import UserService

SECRET = "test-secret-do-not-use"
BASE = "/api/v1/voice-auth"

_KEY = ec.generate_private_key(ec.SECP256R1())
PRIVATE_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()).decode()


def _decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


class FakePortal:
    """Stands in for requests.post; records what the portal was sent."""

    def __init__(self, status_code=200):
        self.status_code = status_code
        self.calls = []

    def __call__(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        return FakeResponse(self.status_code, {
            "access_token": "portal-access", "refresh_token": "portal-refresh",
            "token_type": "bearer", "expires_in": 1800, "created": True,
            "user": {"username": "sh-abc", "service_line": "sci-companion"},
        })


@pytest.fixture(params=["memory", "sqlalchemy"])
def repos(request):
    if request.param == "memory":
        users, homes = InMemoryUserRepository(), InMemoryHomeRepository()
    else:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        users, homes = SQLAlchemyUserRepository(session), SQLAlchemyHomeRepository(session)
    users.add(User(user_id="scott_mobile", username="scott", full_name="Scott Example",
                   email="scott@example.com", password_hash=User.hash_password("hunter2")))
    return users, homes


@pytest.fixture
def portal():
    return FakePortal()


@pytest.fixture
def health(portal):
    return HealthEducatorService(
        portal_url="https://portal.internal/", public_url="https://portal.example.org",
        private_key_pem=PRIVATE_PEM, http_post=portal)


@pytest.fixture
def svc(repos):
    users, homes = repos
    return MobileAuthService(users, homes, secret=SECRET)


@pytest.fixture
def client(svc, health):
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(svc, health_educator=health).blueprint)
    return app.test_client()


@pytest.fixture
def admin(repos, health):
    users, homes = repos
    controller = AdminController(
        user_service=UserService(users), home_service=HomeService(homes, users),
        alexa_mapping_service=None, scene_mapping_service=None)
    controller.set_user_deactivated_hook(health.revoke_sessions)
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    return app.test_client()


def _auth(svc, user_id="scott_mobile"):
    return {"Authorization": f"Bearer {svc.issue_token(user_id)['token']}"}


# ---- gender on the profile ----------------------------------------------

def test_gender_defaults_to_not_specified(client, svc):
    assert client.get(f"{BASE}/me", headers=_auth(svc)).get_json()["gender"] is None


def test_admin_sets_and_clears_gender(admin, repos):
    users, _ = repos
    r = admin.put("/admin/users/scott_mobile", json={"gender": "Male"})
    assert r.status_code == 200 and r.get_json()["gender"] == "male"
    assert users.get_by_id("scott_mobile").gender == "male"

    # an unrelated update leaves it alone
    admin.put("/admin/users/scott_mobile", json={"full_name": "Scott E"})
    assert users.get_by_id("scott_mobile").gender == "male"

    r = admin.put("/admin/users/scott_mobile", json={"gender": None})
    assert r.get_json()["gender"] is None


def test_admin_rejects_unknown_gender(admin, repos):
    users, _ = repos
    assert admin.put("/admin/users/scott_mobile", json={"gender": "other"}).status_code == 400
    assert users.get_by_id("scott_mobile").gender is None


def test_admin_creates_user_with_gender(admin):
    r = admin.post("/admin/users", json={
        "username": "dana", "full_name": "Dana", "email": "dana@example.com",
        "gender": "female"})
    assert r.status_code == 201 and r.get_json()["gender"] == "female"
    listed = admin.get("/admin/users").get_json()["users"]
    assert {u["username"]: u["gender"] for u in listed}["dana"] == "female"


def test_mobile_user_sets_own_gender(client, svc):
    r = client.patch(f"{BASE}/me", json={"gender": "female"}, headers=_auth(svc))
    assert r.status_code == 200 and r.get_json()["gender"] == "female"
    assert client.get(f"{BASE}/me", headers=_auth(svc)).get_json()["gender"] == "female"
    assert client.patch(f"{BASE}/me", json={"gender": "x"}, headers=_auth(svc)).status_code == 400
    assert client.patch(f"{BASE}/me", json={}, headers=_auth(svc)).status_code == 400


# ---- assertion -----------------------------------------------------------

def test_assertion_is_es256_and_verifies_with_the_public_key(health, repos):
    users, _ = repos
    user = users.get_by_id("scott_mobile")
    user.gender = "male"
    header_b64, claims_b64, sig_b64 = health.sign_assertion(user).split(".")
    assert json.loads(_decode(header_b64))["alg"] == "ES256"

    claims = json.loads(_decode(claims_b64))
    assert claims["sub"] == "scott_mobile"
    assert claims["email"] == "scott@example.com"
    assert claims["name"] == "Scott Example"
    assert claims["gender"] == "male"
    assert claims["purpose"] == "login"
    assert claims["aud"] == "healtheducator-portal"
    assert 0 < claims["exp"] - claims["iat"] <= 60 and claims["jti"]

    raw = _decode(sig_b64)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    _KEY.public_key().verify(der, f"{header_b64}.{claims_b64}".encode(), ec.ECDSA(hashes.SHA256()))


def test_each_assertion_has_its_own_id(health, repos):
    user = repos[0].get_by_id("scott_mobile")
    ids = {json.loads(_decode(health.sign_assertion(user).split(".")[1]))["jti"] for _ in range(5)}
    assert len(ids) == 5


# ---- POST /health-educator/session ---------------------------------------

def test_session_requires_a_login_token(client):
    assert client.post(f"{BASE}/health-educator/session").status_code == 401
    r = client.post(f"{BASE}/health-educator/session", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_any_active_user_gets_a_portal_session(client, svc, portal):
    r = client.post(f"{BASE}/health-educator/session", headers=_auth(svc))
    assert r.status_code == 200
    body = r.get_json()
    assert body["access_token"] == "portal-access"
    assert body["refresh_token"] == "portal-refresh"
    assert body["base_url"] == "https://portal.example.org"
    assert body["api_prefix"] == "/api/mobile/v1"
    assert body["user"]["service_line"] == "sci-companion"

    url, sent = portal.calls[0]
    assert url == "https://portal.internal/api/mobile/v1/session/exchange"
    assert json.loads(_decode(sent["assertion"].split(".")[1]))["sub"] == "scott_mobile"


def test_inactive_user_gets_no_session(client, svc, repos, portal):
    users, _ = repos
    headers = _auth(svc)
    users.deactivate("scott_mobile")
    assert client.post(f"{BASE}/health-educator/session", headers=headers).status_code == 401
    assert portal.calls == []


@pytest.mark.parametrize("portal_status,expected,code", [
    (403, 403, "FORBIDDEN"),
    (401, 502, "PORTAL_UNAVAILABLE"),
    (500, 502, "PORTAL_UNAVAILABLE"),
    (503, 502, "PORTAL_UNAVAILABLE"),
])
def test_portal_errors_are_mapped(svc, portal_status, expected, code):
    health = HealthEducatorService(portal_url="https://p", private_key_pem=PRIVATE_PEM,
                                   http_post=FakePortal(portal_status))
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(svc, health_educator=health).blueprint)
    r = app.test_client().post(f"{BASE}/health-educator/session", headers=_auth(svc))
    assert r.status_code == expected and r.get_json()["code"] == code


def test_unreachable_portal_answers_502(svc):
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("down")

    health = HealthEducatorService(portal_url="https://p", private_key_pem=PRIVATE_PEM,
                                   http_post=boom)
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(svc, health_educator=health).blueprint)
    r = app.test_client().post(f"{BASE}/health-educator/session", headers=_auth(svc))
    assert r.status_code == 502


def test_not_configured_answers_503(svc, monkeypatch):
    for name in ("HEALTH_EDUCATOR_URL", "HEALTH_EDUCATOR_SSO_PRIVATE_KEY"):
        monkeypatch.delenv(name, raising=False)
    for health in (None, HealthEducatorService()):
        app = Flask(__name__)
        app.register_blueprint(MobileAuthController(svc, health_educator=health).blueprint)
        r = app.test_client().post(f"{BASE}/health-educator/session", headers=_auth(svc))
        assert r.status_code == 503 and r.get_json()["code"] == "NOT_CONFIGURED"


def test_wrong_curve_or_garbage_key_disables_the_feature():
    assert not HealthEducatorService(portal_url="https://p", private_key_pem="garbage").configured
    p384 = ec.generate_private_key(ec.SECP384R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()
    assert not HealthEducatorService(portal_url="https://p", private_key_pem=p384).configured


def test_base64_encoded_key_is_accepted():
    one_line = base64.b64encode(PRIVATE_PEM.encode()).decode()
    assert HealthEducatorService(portal_url="https://p", private_key_pem=one_line).configured


# ---- deactivation --------------------------------------------------------

def test_deactivating_a_user_revokes_portal_sessions(admin, portal):
    assert admin.delete("/admin/users/scott_mobile").status_code == 200
    url, sent = portal.calls[0]
    assert url.endswith("/api/mobile/v1/session/revoke")
    claims = json.loads(_decode(sent["assertion"].split(".")[1]))
    assert claims["sub"] == "scott_mobile" and claims["purpose"] == "revoke"
    assert "email" not in claims


def test_deactivation_succeeds_when_the_portal_is_down(repos):
    users, homes = repos

    def boom(*a, **k):
        raise RuntimeError("down")

    health = HealthEducatorService(portal_url="https://p", private_key_pem=PRIVATE_PEM,
                                   http_post=boom)
    controller = AdminController(
        user_service=UserService(users), home_service=HomeService(homes, users),
        alexa_mapping_service=None, scene_mapping_service=None)
    controller.set_user_deactivated_hook(health.revoke_sessions)
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    assert app.test_client().delete("/admin/users/scott_mobile").status_code == 200
    assert users.get_by_id("scott_mobile").is_active is False
