"""
Shared-home membership + OTP-style invite codes.

Covers:
- home repositories (in-memory + SQLAlchemy/sqlite): owner auto-membership,
  add/remove/list members, list_by_user / exists_for_user honour membership
- HomeInviteService: generate, normalise, validate, redeem, expiry,
  max_uses, revoke
- POST /auth/signup with invite_code (active + logged in), bad code, lockout
- POST /auth/redeem-invite for an existing account
- /admin/homes/{id}/members and /admin/homes/{id}/invites endpoints
- login bootstrap lists a shared home for BOTH users
"""

from datetime import datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.controllers.admin_controller import AdminController
from app.controllers.mobile_auth_controller import MobileAuthController
from app.domain.models import Home, User
from app.repositories.implementations.in_memory_home_invite_repo import (
    InMemoryHomeInviteRepository)
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
from app.repositories.implementations.sqlalchemy_home_invite_repo import (
    SQLAlchemyHomeInviteRepository)
from app.repositories.implementations.sqlalchemy_home_repo import SQLAlchemyHomeRepository
from app.repositories.implementations.sqlalchemy_models import Base
from app.repositories.implementations.sqlalchemy_user_repo import SQLAlchemyUserRepository
from app.services.home_invite_service import (HomeInviteService, InvalidInviteError,
                                              normalize_code)
from app.services.home_service import HomeService
from app.services.mobile_auth_service import MobileAuthService
from app.services.user_service import UserService

SECRET = "test-secret-do-not-use"


def _home(home_id="scott_home", user_id="scott_mobile", name="Scott's House"):
    return Home(home_id=home_id, user_id=user_id, name=name,
                ha_url="https://ha.example.com", ha_webhook_id="voice_auth_scene")


def _user(user_id, email=None, active=True, password="hunter2"):
    return User(user_id=user_id, username=user_id, full_name=user_id.title(),
                email=email or f"{user_id}@example.com", is_active=active,
                password_hash=User.hash_password(password))


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

@pytest.fixture(params=["memory", "sqlalchemy"])
def repos(request):
    """(users, homes, invites) for both storage backends."""
    if request.param == "memory":
        users, homes, invites = (InMemoryUserRepository(), InMemoryHomeRepository(),
                                 InMemoryHomeInviteRepository())
    else:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        users, homes, invites = (SQLAlchemyUserRepository(session),
                                 SQLAlchemyHomeRepository(session),
                                 SQLAlchemyHomeInviteRepository(session))
    users.add(_user("scott_mobile", "scott@example.com"))
    users.add(_user("aaron"))
    homes.add(_home())
    homes.add(_home("ne_qli_1", "scott_mobile", "NE QLI Office"))
    return users, homes, invites


class TestMembershipRepository:
    def test_registering_owner_is_a_member(self, repos):
        _, homes, _ = repos
        members = homes.list_members("scott_home")
        assert [(m.user_id, m.role) for m in members] == [("scott_mobile", "owner")]
        assert homes.exists_for_user("scott_mobile", "scott_home")

    def test_add_member_makes_home_visible_to_second_user(self, repos):
        _, homes, _ = repos
        assert homes.list_by_user("aaron") == []
        assert not homes.exists_for_user("aaron", "scott_home")

        m = homes.add_member("scott_home", "aaron")
        assert m.role == "member"
        assert [h.home_id for h in homes.list_by_user("aaron")] == ["scott_home"]
        assert homes.exists_for_user("aaron", "scott_home")
        # Owner still sees it too — sharing, not transfer.
        assert {h.home_id for h in homes.list_by_user("scott_mobile")} == {"scott_home", "ne_qli_1"}

    def test_add_member_is_idempotent_and_updates_role(self, repos):
        _, homes, _ = repos
        homes.add_member("scott_home", "aaron")
        homes.add_member("scott_home", "aaron", role="owner")
        members = homes.list_members("scott_home")
        assert len(members) == 2
        assert next(m for m in members if m.user_id == "aaron").role == "owner"

    def test_remove_member(self, repos):
        _, homes, _ = repos
        homes.add_member("scott_home", "aaron")
        assert homes.remove_member("scott_home", "aaron") is True
        assert homes.remove_member("scott_home", "aaron") is False
        assert not homes.exists_for_user("aaron", "scott_home")
        assert homes.list_by_user("aaron") == []

    def test_removing_owner_membership_hides_home(self, repos):
        """Membership is the single source of truth (legacy column ignored)."""
        _, homes, _ = repos
        assert homes.remove_member("scott_home", "scott_mobile") is True
        assert not homes.exists_for_user("scott_mobile", "scott_home")
        assert [h.home_id for h in homes.list_by_user("scott_mobile")] == ["ne_qli_1"]

    def test_add_member_unknown_home(self, repos):
        _, homes, _ = repos
        with pytest.raises(ValueError):
            homes.add_member("nope", "aaron")

    def test_inactive_home_hidden_by_default(self, repos):
        _, homes, _ = repos
        homes.add_member("scott_home", "aaron")
        homes.deactivate("scott_home")
        assert homes.list_by_user("aaron") == []
        assert [h.home_id for h in homes.list_by_user("aaron", active_only=False)] == ["scott_home"]

    def test_delete_home_drops_members_and_invites(self, repos):
        users, homes, invites = repos
        homes.add_member("scott_home", "aaron")
        svc = HomeInviteService(invites, homes, users)
        inv = svc.create_invite("scott_home")
        assert homes.delete("scott_home") is True
        assert homes.list_by_user("aaron") == []
        if isinstance(homes, SQLAlchemyHomeRepository):
            assert invites.list_by_home("scott_home") == []  # FK rows cascaded
        # Either way the orphaned code can no longer be redeemed.
        with pytest.raises(InvalidInviteError):
            svc.validate(inv.code)


# ---------------------------------------------------------------------------
# HomeInviteService
# ---------------------------------------------------------------------------

@pytest.fixture
def svc(repos):
    users, homes, invites = repos
    return HomeInviteService(invites, homes, users)


class TestNormalizeCode:
    def test_strips_separators_and_case(self):
        assert normalize_code(" k7qx-4mrp ") == "K7QX4MRP"
        assert normalize_code("K7QX 4MRP") == "K7QX4MRP"
        assert normalize_code(None) == ""
        assert normalize_code(42) == ""


class TestInviteService:
    def test_create_defaults(self, svc):
        inv = svc.create_invite("scott_home", created_by="karthi")
        assert len(inv.code) == 8 and inv.code.isupper()
        assert not set(inv.code) & set("0O1I")
        assert inv.display_code == f"{inv.code[:4]}-{inv.code[4:]}"
        assert inv.max_uses == 1 and inv.use_count == 0 and inv.role == "member"
        assert inv.status() == "active"
        assert timedelta(days=6, hours=23) < (inv.expires_at - inv.created_at) <= timedelta(days=7)
        assert inv.created_by == "karthi"

    def test_create_validation(self, svc):
        with pytest.raises(ValueError):
            svc.create_invite("nope")
        with pytest.raises(ValueError):
            svc.create_invite("scott_home", role="admin")
        with pytest.raises(ValueError):
            svc.create_invite("scott_home", max_uses=0)
        with pytest.raises(ValueError):
            svc.create_invite("scott_home", expires_in_hours=0)

    def test_redeem_attaches_and_consumes(self, svc, repos):
        _, homes, _ = repos
        inv = svc.create_invite("scott_home")
        member = svc.redeem(inv.display_code.lower(), "aaron")  # typed sloppily
        assert member.home_id == "scott_home" and member.role == "member"
        assert homes.exists_for_user("aaron", "scott_home")
        again = svc.get_invite(inv.code)
        assert again.use_count == 1 and again.status() == "exhausted"
        with pytest.raises(InvalidInviteError) as ei:
            svc.redeem(inv.code, "scott_mobile")
        assert ei.value.reason == "exhausted"

    def test_multi_use_code(self, svc):
        inv = svc.create_invite("scott_home", max_uses=2)
        svc.redeem(inv.code, "aaron")
        svc.redeem(inv.code, "scott_mobile")
        assert svc.get_invite(inv.code).status() == "exhausted"

    def test_unknown_code(self, svc):
        with pytest.raises(InvalidInviteError) as ei:
            svc.validate("ZZZZ-ZZZZ")
        assert ei.value.reason == "unknown"

    def test_expired_code(self, svc, repos):
        _, _, invites = repos
        inv = svc.create_invite("scott_home", expires_in_hours=1)
        inv.expires_at = datetime.now() - timedelta(seconds=1)
        invites.update(inv)
        with pytest.raises(InvalidInviteError) as ei:
            svc.validate(inv.code)
        assert ei.value.reason == "expired"

    def test_revoke(self, svc):
        inv = svc.create_invite("scott_home")
        revoked = svc.revoke_invite(inv.display_code)
        assert revoked.status() == "revoked" and revoked.revoked_at is not None
        with pytest.raises(InvalidInviteError) as ei:
            svc.redeem(inv.code, "aaron")
        assert ei.value.reason == "revoked"
        with pytest.raises(ValueError):
            svc.revoke_invite("NOPE-NOPE")

    def test_inactive_home(self, svc, repos):
        _, homes, _ = repos
        inv = svc.create_invite("scott_home")
        homes.deactivate("scott_home")
        with pytest.raises(InvalidInviteError) as ei:
            svc.validate(inv.code)
        assert ei.value.reason == "home_inactive"

    def test_owner_role_invite(self, svc):
        inv = svc.create_invite("scott_home", role="owner")
        assert svc.redeem(inv.code, "aaron").role == "owner"

    def test_list_invites(self, svc):
        svc.create_invite("scott_home")
        svc.create_invite("scott_home")
        assert len(svc.list_invites("scott_home")) == 2
        assert svc.list_invites("ne_qli_1") == []
        with pytest.raises(ValueError):
            svc.list_invites("nope")


# ---------------------------------------------------------------------------
# Mobile endpoints: sign-up with code, redeem, shared bootstrap
# ---------------------------------------------------------------------------

@pytest.fixture
def mobile(repos):
    users, homes, invites = repos
    invite_svc = HomeInviteService(invites, homes, users)
    auth = MobileAuthService(users, homes, secret=SECRET, invite_service=invite_svc)
    app = Flask(__name__)
    app.register_blueprint(MobileAuthController(auth).blueprint)
    return app.test_client(), auth, invite_svc


BASE = "/api/v1/voice-auth"


class TestSignupWithInvite:
    def test_valid_code_creates_active_logged_in_member(self, mobile, repos):
        client, auth, invite_svc = mobile
        users, homes, _ = repos
        inv = invite_svc.create_invite("scott_home")
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "Aaron.New@Example.com", "password": "goodpass99",
            "full_name": "Aaron", "invite_code": inv.display_code.lower()})
        assert rv.status_code == 201, rv.get_json()
        body = rv.get_json()
        assert body["status"] == "active"
        assert auth.verify_token(body["token"]) == body["user_id"]
        assert body["homes"] == [{"home_id": "scott_home", "name": "Scott's House"}]
        assert body["default_home_id"] == "scott_home"
        user = users.get_by_email("aaron.new@example.com")
        assert user.is_active is True
        assert homes.exists_for_user(user.user_id, "scott_home")
        # ...and they can log in straight away
        rv = client.post(f"{BASE}/auth/login",
                         json={"email": "aaron.new@example.com", "password": "goodpass99"})
        assert rv.status_code == 200 and rv.get_json()["default_home_id"] == "scott_home"

    def test_bad_code_creates_nothing(self, mobile, repos):
        client, _, _ = mobile
        users, _, _ = repos
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "x@example.com", "password": "goodpass99",
            "full_name": "X", "invite_code": "ZZZZ-ZZZZ"})
        assert rv.status_code == 400
        body = rv.get_json()
        assert body["code"] == "INVALID_INVITE" and body["reason"] == "unknown"
        assert users.get_by_email("x@example.com") is None

    def test_used_code_rejected(self, mobile):
        client, _, invite_svc = mobile
        inv = invite_svc.create_invite("scott_home")
        ok = client.post(f"{BASE}/auth/signup", json={
            "email": "a1@example.com", "password": "goodpass99",
            "full_name": "A1", "invite_code": inv.code})
        assert ok.status_code == 201
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "a2@example.com", "password": "goodpass99",
            "full_name": "A2", "invite_code": inv.code})
        assert rv.status_code == 400 and rv.get_json()["reason"] == "exhausted"

    def test_no_code_still_pending(self, mobile, repos):
        client, _, _ = mobile
        users, _, _ = repos
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "p@example.com", "password": "goodpass99", "full_name": "P"})
        assert rv.status_code == 201 and rv.get_json()["status"] == "pending_approval"
        assert users.get_by_email("p@example.com").is_active is False

    def test_empty_code_treated_as_absent(self, mobile):
        client, _, _ = mobile
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "e@example.com", "password": "goodpass99",
            "full_name": "E", "invite_code": "   "})
        assert rv.status_code == 201 and rv.get_json()["status"] == "pending_approval"

    def test_duplicate_email_with_valid_code_does_not_consume_it(self, mobile):
        client, _, invite_svc = mobile
        inv = invite_svc.create_invite("scott_home")
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "scott@example.com", "password": "goodpass99",
            "full_name": "Imposter", "invite_code": inv.code})
        assert rv.status_code == 409
        assert invite_svc.get_invite(inv.code).use_count == 0

    def test_code_guessing_locked_out(self, mobile):
        client, _, _ = mobile
        for i in range(5):
            client.post(f"{BASE}/auth/signup", json={
                "email": f"g{i}@example.com", "password": "goodpass99",
                "full_name": "G", "invite_code": "AAAA-AAA2"})
        rv = client.post(f"{BASE}/auth/signup", json={
            "email": "g9@example.com", "password": "goodpass99",
            "full_name": "G", "invite_code": "AAAA-AAA2"})
        assert rv.status_code == 429

    def test_invites_disabled_server(self, repos):
        users, homes, _ = repos
        auth = MobileAuthService(users, homes, secret=SECRET)  # no invite service
        app = Flask(__name__)
        app.register_blueprint(MobileAuthController(auth).blueprint)
        rv = app.test_client().post(f"{BASE}/auth/signup", json={
            "email": "d@example.com", "password": "goodpass99",
            "full_name": "D", "invite_code": "K7QX-4MRP"})
        assert rv.status_code == 400 and rv.get_json()["code"] == "VALIDATION"


class TestRedeemInvite:
    def _login(self, client, email="aaron@example.com"):
        rv = client.post(f"{BASE}/auth/login", json={"email": email, "password": "hunter2"})
        assert rv.status_code == 200
        return rv.get_json()["token"]

    def test_redeem_adds_home_to_existing_account(self, mobile):
        client, _, invite_svc = mobile
        token = self._login(client)
        inv = invite_svc.create_invite("ne_qli_1")
        rv = client.post(f"{BASE}/auth/redeem-invite", json={"invite_code": inv.display_code},
                         headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 200, rv.get_json()
        body = rv.get_json()
        assert body["homes"] == [{"home_id": "ne_qli_1", "name": "NE QLI Office"}]
        assert body["default_home_id"] == "ne_qli_1"
        # /me agrees
        rv = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
        assert rv.get_json()["default_home_id"] == "ne_qli_1"

    def test_requires_token(self, mobile):
        client, _, _ = mobile
        rv = client.post(f"{BASE}/auth/redeem-invite", json={"invite_code": "K7QX-4MRP"})
        assert rv.status_code == 401

    def test_bad_code(self, mobile):
        client, _, _ = mobile
        token = self._login(client)
        rv = client.post(f"{BASE}/auth/redeem-invite", json={"invite_code": "ZZZZ-ZZZZ"},
                         headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 400 and rv.get_json()["code"] == "INVALID_INVITE"

    def test_missing_code(self, mobile):
        client, _, _ = mobile
        token = self._login(client)
        rv = client.post(f"{BASE}/auth/redeem-invite", json={},
                         headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 400 and rv.get_json()["code"] == "VALIDATION"

    def test_lockout_after_bad_codes(self, mobile):
        client, _, _ = mobile
        token = self._login(client)
        for _ in range(5):
            client.post(f"{BASE}/auth/redeem-invite", json={"invite_code": "ZZZZ-ZZZZ"},
                        headers={"Authorization": f"Bearer {token}"})
        rv = client.post(f"{BASE}/auth/redeem-invite", json={"invite_code": "ZZZZ-ZZZZ"},
                         headers={"Authorization": f"Bearer {token}"})
        assert rv.status_code == 429


class TestSharedBootstrap:
    def test_both_users_see_shared_home_at_login(self, mobile, repos):
        client, _, _ = mobile
        _, homes, _ = repos
        homes.add_member("scott_home", "aaron")
        homes.add_member("ne_qli_1", "aaron")
        for email in ("scott@example.com", "aaron@example.com"):
            rv = client.post(f"{BASE}/auth/login", json={"email": email, "password": "hunter2"})
            assert rv.status_code == 200
            body = rv.get_json()
            assert {h["home_id"] for h in body["homes"]} == {"scott_home", "ne_qli_1"}
            assert body["default_home_id"] == "scott_home"  # oldest first, stable


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def admin(repos):
    users, homes, invites = repos
    invite_svc = HomeInviteService(invites, homes, users)
    ctrl = AdminController(
        user_service=UserService(user_repository=users),
        home_service=HomeService(home_repository=homes, user_repository=users),
        alexa_mapping_service=None,
        scene_mapping_service=None,
        invite_service=invite_svc,
    )
    app = Flask(__name__)
    app.register_blueprint(ctrl.blueprint)
    return app.test_client(), invite_svc


class TestAdminMembers:
    def test_list_members(self, admin):
        client, _ = admin
        rv = client.get("/admin/homes/scott_home/members")
        assert rv.status_code == 200
        body = rv.get_json()
        assert body["count"] == 1
        m = body["members"][0]
        assert m["user_id"] == "scott_mobile" and m["role"] == "owner"
        assert m["email"] == "scott@example.com" and m["username"] == "scott_mobile"

    def test_list_members_unknown_home(self, admin):
        client, _ = admin
        assert client.get("/admin/homes/nope/members").status_code == 404

    def test_add_member(self, admin, repos):
        client, _ = admin
        _, homes, _ = repos
        rv = client.post("/admin/homes/scott_home/members", json={"user_id": "aaron"})
        assert rv.status_code == 201
        assert rv.get_json()["role"] == "member"
        assert homes.exists_for_user("aaron", "scott_home")
        assert client.get("/admin/homes/scott_home/members").get_json()["count"] == 2

    def test_add_member_errors(self, admin):
        client, _ = admin
        assert client.post("/admin/homes/scott_home/members",
                           json={"user_id": "ghost"}).status_code == 400
        assert client.post("/admin/homes/nope/members",
                           json={"user_id": "aaron"}).status_code == 404
        assert client.post("/admin/homes/scott_home/members",
                           json={"user_id": "aaron", "role": "boss"}).status_code == 400
        assert client.post("/admin/homes/scott_home/members", json={}).status_code == 400

    def test_remove_member(self, admin):
        client, _ = admin
        client.post("/admin/homes/scott_home/members", json={"user_id": "aaron"})
        rv = client.delete("/admin/homes/scott_home/members/aaron")
        assert rv.status_code == 200 and rv.get_json()["removed"] is True
        assert client.delete("/admin/homes/scott_home/members/aaron").status_code == 404
        assert client.delete("/admin/homes/nope/members/aaron").status_code == 404

    def test_user_homes_endpoint_reflects_membership(self, admin):
        client, _ = admin
        client.post("/admin/homes/scott_home/members", json={"user_id": "aaron"})
        rv = client.get("/admin/users/aaron/homes")
        assert [h["home_id"] for h in rv.get_json()["homes"]] == ["scott_home"]


class TestAdminInvites:
    def test_create_defaults(self, admin):
        client, _ = admin
        rv = client.post("/admin/homes/scott_home/invites")
        assert rv.status_code == 201, rv.get_json()
        body = rv.get_json()
        assert len(body["code"]) == 9 and body["code"][4] == "-"
        assert body["status"] == "active" and body["max_uses"] == 1
        assert body["use_count"] == 0 and body["role"] == "member"
        assert body["expires_at"] is not None and body["created_by"] == "admin"

    def test_create_custom(self, admin):
        client, _ = admin
        rv = client.post("/admin/homes/scott_home/invites",
                         json={"role": "owner", "expires_in_hours": 48, "max_uses": 5},
                         headers={"X-Admin-User": "karthi"})
        assert rv.status_code == 201
        body = rv.get_json()
        assert body["role"] == "owner" and body["max_uses"] == 5
        assert body["created_by"] == "karthi"

    def test_create_errors(self, admin):
        client, _ = admin
        assert client.post("/admin/homes/nope/invites").status_code == 404
        assert client.post("/admin/homes/scott_home/invites",
                           json={"max_uses": 0}).status_code == 400
        assert client.post("/admin/homes/scott_home/invites",
                           json={"expires_in_hours": "soon"}).status_code == 400
        assert client.post("/admin/homes/scott_home/invites",
                           json={"role": "god"}).status_code == 400

    def test_list_and_status_filter(self, admin, repos):
        client, invite_svc = admin
        a = client.post("/admin/homes/scott_home/invites").get_json()["code"]
        b = client.post("/admin/homes/scott_home/invites").get_json()["code"]
        invite_svc.redeem(b, "aaron")
        rv = client.get("/admin/homes/scott_home/invites")
        assert rv.status_code == 200 and rv.get_json()["count"] == 2
        active = client.get("/admin/homes/scott_home/invites?status=active").get_json()
        assert [i["code"] for i in active["invites"]] == [a]
        assert client.get("/admin/homes/nope/invites").status_code == 404

    def test_revoke(self, admin):
        client, _ = admin
        code = client.post("/admin/homes/scott_home/invites").get_json()["code"]
        rv = client.delete(f"/admin/invites/{code}")
        assert rv.status_code == 200 and rv.get_json()["status"] == "revoked"
        assert client.delete(f"/admin/invites/{code}").status_code == 200  # idempotent
        assert client.delete("/admin/invites/ZZZZ-ZZZZ").status_code == 404

    def test_invites_disabled_503(self, repos):
        users, homes, _ = repos
        ctrl = AdminController(
            user_service=UserService(user_repository=users),
            home_service=HomeService(home_repository=homes, user_repository=users),
            alexa_mapping_service=None)
        app = Flask(__name__)
        app.register_blueprint(ctrl.blueprint)
        assert app.test_client().post("/admin/homes/scott_home/invites").status_code == 503
