"""
Per-account default home.

- bootstrap resolution rule: stored preference wins while valid, else oldest
- PATCH /me sets / clears it; membership + active checks; auth
- admin PUT /users/{id} accepts default_home_id (set / clear / invalid)
- preference survives profile updates and both repository backends
"""

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.controllers.admin_controller import AdminController
from app.controllers.mobile_auth_controller import MobileAuthController
from app.domain.models import Home, User
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
from app.repositories.implementations.sqlalchemy_home_repo import SQLAlchemyHomeRepository
from app.repositories.implementations.sqlalchemy_models import Base
from app.repositories.implementations.sqlalchemy_user_repo import SQLAlchemyUserRepository
from app.services.home_service import HomeService
from app.services.mobile_auth_service import MobileAuthService
from app.services.user_service import UserService

SECRET = "test-secret-do-not-use"
BASE = "/api/v1/voice-auth"


def _home(home_id, name, user_id="scott_mobile"):
    return Home(home_id=home_id, user_id=user_id, name=name,
                ha_url="https://ha.example.com", ha_webhook_id="wh")


@pytest.fixture(params=["memory", "sqlalchemy"])
def repos(request):
    if request.param == "memory":
        users, homes = InMemoryUserRepository(), InMemoryHomeRepository()
    else:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        users, homes = SQLAlchemyUserRepository(session), SQLAlchemyHomeRepository(session)
    users.add(User(user_id="scott_mobile", username="scott", full_name="Scott",
                   email="scott@example.com", password_hash=User.hash_password("hunter2")))
    users.add(User(user_id="other", username="other", full_name="Other",
                   email="other@example.com", password_hash=User.hash_password("hunter2")))
    homes.add(_home("scott_home", "Scott's House"))       # oldest
    homes.add(_home("ne_qli_1", "NE QLI Office"))
    homes.add(_home("other_home", "Other's House", user_id="other"))
    return users, homes


@pytest.fixture
def svc(repos):
    users, homes = repos
    return MobileAuthService(users, homes, secret=SECRET)


@pytest.fixture
def client(svc):
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(svc).blueprint)
    return app.test_client()


def _token(client, email="scott@example.com"):
    rv = client.post(f"{BASE}/auth/login", json={"email": email, "password": "hunter2"})
    assert rv.status_code == 200
    return rv.get_json()["token"]


class TestResolutionRule:
    def test_no_preference_is_oldest(self, svc, repos):
        users, _ = repos
        assert svc.bootstrap(users.get_by_id("scott_mobile"))["default_home_id"] == "scott_home"

    def test_preference_wins(self, svc, repos):
        users, _ = repos
        svc.set_default_home("scott_mobile", "ne_qli_1")
        assert svc.bootstrap(users.get_by_id("scott_mobile"))["default_home_id"] == "ne_qli_1"

    def test_stale_after_membership_removed_falls_back(self, svc, repos):
        users, homes = repos
        svc.set_default_home("scott_mobile", "ne_qli_1")
        homes.remove_member("ne_qli_1", "scott_mobile")
        assert svc.bootstrap(users.get_by_id("scott_mobile"))["default_home_id"] == "scott_home"
        # ...and comes back when re-added (value was never cleared)
        homes.add_member("ne_qli_1", "scott_mobile")
        assert svc.bootstrap(users.get_by_id("scott_mobile"))["default_home_id"] == "ne_qli_1"

    def test_stale_after_home_deactivated_falls_back(self, svc, repos):
        users, homes = repos
        svc.set_default_home("scott_mobile", "ne_qli_1")
        homes.deactivate("ne_qli_1")
        assert svc.bootstrap(users.get_by_id("scott_mobile"))["default_home_id"] == "scott_home"

    def test_no_homes(self, svc, repos):
        users, homes = repos
        homes.remove_member("other_home", "other")
        assert svc.bootstrap(users.get_by_id("other"))["default_home_id"] is None

    def test_set_rejects_foreign_or_unknown_or_inactive(self, svc, repos):
        _, homes = repos
        with pytest.raises(ValueError):
            svc.set_default_home("scott_mobile", "other_home")
        with pytest.raises(ValueError):
            svc.set_default_home("scott_mobile", "nope")
        homes.deactivate("ne_qli_1")
        with pytest.raises(ValueError):
            svc.set_default_home("scott_mobile", "ne_qli_1")

    def test_clear(self, svc, repos):
        users, _ = repos
        svc.set_default_home("scott_mobile", "ne_qli_1")
        svc.set_default_home("scott_mobile", None)
        assert users.get_by_id("scott_mobile").default_home_id is None

    def test_preference_survives_profile_update(self, svc, repos):
        users, _ = repos
        svc.set_default_home("scott_mobile", "ne_qli_1")
        UserService(user_repository=users).update_user("scott_mobile", full_name="Scott M")
        u = users.get_by_id("scott_mobile")
        assert u.full_name == "Scott M" and u.default_home_id == "ne_qli_1"


class TestPatchMe:
    def test_set_and_readback(self, client):
        tok = _token(client)
        rv = client.patch(f"{BASE}/me", json={"default_home_id": "ne_qli_1"},
                          headers={"Authorization": f"Bearer {tok}"})
        assert rv.status_code == 200, rv.get_json()
        body = rv.get_json()
        assert body["default_home_id"] == "ne_qli_1"
        assert {h["home_id"] for h in body["homes"]} == {"scott_home", "ne_qli_1"}
        assert client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {tok}"}
                          ).get_json()["default_home_id"] == "ne_qli_1"
        # login reflects it too
        rv = client.post(f"{BASE}/auth/login", json={"email": "scott@example.com", "password": "hunter2"})
        assert rv.get_json()["default_home_id"] == "ne_qli_1"

    def test_clear_with_null(self, client):
        tok = _token(client)
        client.patch(f"{BASE}/me", json={"default_home_id": "ne_qli_1"},
                     headers={"Authorization": f"Bearer {tok}"})
        rv = client.patch(f"{BASE}/me", json={"default_home_id": None},
                          headers={"Authorization": f"Bearer {tok}"})
        assert rv.status_code == 200 and rv.get_json()["default_home_id"] == "scott_home"

    def test_foreign_home_400(self, client):
        tok = _token(client)
        rv = client.patch(f"{BASE}/me", json={"default_home_id": "other_home"},
                          headers={"Authorization": f"Bearer {tok}"})
        assert rv.status_code == 400 and rv.get_json()["code"] == "VALIDATION"

    def test_validation(self, client):
        tok = _token(client)
        h = {"Authorization": f"Bearer {tok}"}
        assert client.patch(f"{BASE}/me", json={}, headers=h).status_code == 400
        assert client.patch(f"{BASE}/me", json={"default_home_id": ""}, headers=h).status_code == 400
        assert client.patch(f"{BASE}/me", json={"default_home_id": 42}, headers=h).status_code == 400

    def test_requires_token(self, client):
        assert client.patch(f"{BASE}/me", json={"default_home_id": "ne_qli_1"}).status_code == 401
        assert client.patch(f"{BASE}/me", json={"default_home_id": "ne_qli_1"},
                            headers={"Authorization": "Bearer sk_ios_abc"}).status_code == 401


@pytest.fixture
def admin(repos):
    users, homes = repos
    ctrl = AdminController(
        user_service=UserService(user_repository=users),
        home_service=HomeService(home_repository=homes, user_repository=users),
        alexa_mapping_service=None)
    app = Flask(__name__)
    app.register_blueprint(ctrl.blueprint)
    return app.test_client()


class TestAdminDefaultHome:
    def test_set_and_clear(self, admin, repos):
        users, _ = repos
        rv = admin.put("/admin/users/scott_mobile", json={"default_home_id": "ne_qli_1"})
        assert rv.status_code == 200 and rv.get_json()["default_home_id"] == "ne_qli_1"
        assert users.get_by_id("scott_mobile").default_home_id == "ne_qli_1"
        rv = admin.put("/admin/users/scott_mobile", json={"default_home_id": None})
        assert rv.status_code == 200 and rv.get_json()["default_home_id"] is None

    def test_other_fields_leave_it_alone(self, admin, repos):
        users, _ = repos
        admin.put("/admin/users/scott_mobile", json={"default_home_id": "ne_qli_1"})
        rv = admin.put("/admin/users/scott_mobile", json={"full_name": "Scott M"})
        assert rv.status_code == 200 and rv.get_json()["default_home_id"] == "ne_qli_1"

    def test_not_a_member_400(self, admin):
        rv = admin.put("/admin/users/scott_mobile", json={"default_home_id": "other_home"})
        assert rv.status_code == 400

    def test_unknown_home_404(self, admin):
        assert admin.put("/admin/users/scott_mobile", json={"default_home_id": "nope"}).status_code == 404

    def test_get_user_shows_it(self, admin):
        admin.put("/admin/users/scott_mobile", json={"default_home_id": "ne_qli_1"})
        assert admin.get("/admin/users/scott_mobile").get_json()["default_home_id"] == "ne_qli_1"
