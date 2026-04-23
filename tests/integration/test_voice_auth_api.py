"""Integration tests for the /api/v1/voice-auth REST surface.

Uses Flask's test client. Touches in-memory repos only (no DB, no VAPI, no HA).
Verifies the HTTP shape, status codes, and error envelopes the mobile team
will consume.
"""

import json
import os
from unittest.mock import patch

import pytest
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher
from app.middleware.voice_auth_api_key import attach_mobile_api_key_auth
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.voice_auth_service import VoiceAuthService


@pytest.fixture
def client():
    # Exercise with middleware OPEN (MOBILE_API_KEYS_JSON unset) — same as
    # production when Tier 1 is not yet configured. Auth-specific tests below
    # mount a fresh blueprint with keys configured.
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": "{}", "SCENE_CATALOG_JSON": "{}",
                                  "MOBILE_API_KEYS_JSON": ""}):
        dispatcher = HADirectDispatcher.from_env()
        svc = VoiceAuthService(
            enrollment_repo=InMemoryEnrollmentRepository(),
            log_repo=InMemoryChallengeLogRepository(),
            phone_repo=InMemoryPhoneMappingRepository(),
        )
        controller = VoiceAuthController(service=svc, dispatcher=dispatcher)
        attach_mobile_api_key_auth(controller.blueprint)
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        return app.test_client()


@pytest.fixture
def client_authed():
    """Client with MOBILE_API_KEYS_JSON enforced (for auth-specific tests)."""
    with patch.dict(os.environ, {
        "HOME_CONFIGS_JSON": "{}", "SCENE_CATALOG_JSON": "{}",
        "MOBILE_API_KEYS_JSON": '{"ios":"sk_ios_good","android":"sk_and_good"}',
    }):
        dispatcher = HADirectDispatcher.from_env()
        svc = VoiceAuthService(
            enrollment_repo=InMemoryEnrollmentRepository(),
            log_repo=InMemoryChallengeLogRepository(),
            phone_repo=InMemoryPhoneMappingRepository(),
        )
        controller = VoiceAuthController(service=svc, dispatcher=dispatcher)
        attach_mobile_api_key_auth(controller.blueprint)
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        return app.test_client()


def _seed(client, **overrides):
    body = {
        "user_ref": "u1",
        "home_id": "scott_home",
        "automation_name": "Decorations On",
        "ha_service": "scene",
        "ha_entity": "decorations_on",
    }
    body.update(overrides)
    return client.post("/api/v1/voice-auth/enrollments", json=body)


class TestEnrollmentCreate:
    def test_201(self, client):
        r = _seed(client)
        assert r.status_code == 201
        d = r.get_json()
        assert d["automation_id"] == "decorations_on"
        assert d["status"] == "ACTIVE"

    def test_validation_error(self, client):
        r = _seed(client, ha_service="not_a_real_domain")
        assert r.status_code == 400
        assert r.get_json()["code"] == "VALIDATION"

    def test_idempotent(self, client):
        a = _seed(client).get_json()
        b = _seed(client).get_json()
        assert a["id"] == b["id"]


class TestEnrollmentList:
    def test_missing_user_ref(self, client):
        r = client.get("/api/v1/voice-auth/enrollments")
        assert r.status_code == 400

    def test_empty(self, client):
        r = client.get("/api/v1/voice-auth/enrollments?user_ref=nobody")
        assert r.status_code == 200
        assert r.get_json() == {"items": [], "count": 0}

    def test_after_seed(self, client):
        _seed(client)
        r = client.get("/api/v1/voice-auth/enrollments?user_ref=u1")
        assert r.status_code == 200
        assert r.get_json()["count"] == 1

    def test_status_filter(self, client):
        _seed(client)
        r = client.get("/api/v1/voice-auth/enrollments?user_ref=u1&status=paused")
        assert r.status_code == 200
        assert r.get_json()["count"] == 0


class TestCheck:
    def test_missing_params(self, client):
        assert client.get("/api/v1/voice-auth/check").status_code == 400

    def test_not_exists(self, client):
        r = client.get("/api/v1/voice-auth/check?user_ref=u1&automation_id=x")
        assert r.status_code == 404
        assert r.get_json() == {"exists": False, "enrollment_required": True}

    def test_exists(self, client):
        _seed(client)
        r = client.get("/api/v1/voice-auth/check?user_ref=u1&automation_id=decorations_on")
        assert r.status_code == 200
        d = r.get_json()
        assert d["exists"] is True
        assert d["status"] == "ACTIVE"
        assert d["cooldown_remaining_seconds"] == 0
        assert d["attempts_remaining"] == 3


class TestStatusPatch:
    def test_pause_then_resume(self, client):
        eid = _seed(client).get_json()["id"]
        r = client.patch(f"/api/v1/voice-auth/enrollments/{eid}/status",
                         json={"status": "PAUSED"})
        assert r.status_code == 200 and r.get_json()["status"] == "PAUSED"

        r2 = client.patch(f"/api/v1/voice-auth/enrollments/{eid}/status",
                          json={"status": "ACTIVE"})
        assert r2.status_code == 200 and r2.get_json()["status"] == "ACTIVE"

    def test_revoke_then_reactivate_409(self, client):
        eid = _seed(client).get_json()["id"]
        client.patch(f"/api/v1/voice-auth/enrollments/{eid}/status",
                     json={"status": "REVOKED"})
        r = client.patch(f"/api/v1/voice-auth/enrollments/{eid}/status",
                         json={"status": "ACTIVE"})
        assert r.status_code == 409

    def test_nonexistent_404(self, client):
        r = client.patch("/api/v1/voice-auth/enrollments/nope/status",
                         json={"status": "PAUSED"})
        assert r.status_code == 404


class TestPhoneMappings:
    def test_create_list_lookup_delete(self, client):
        r = client.post("/api/v1/voice-auth/phone-mappings",
                        json={"phone": "+1 (555) 000-0001",
                              "user_ref": "u1", "home_id": "scott_home",
                              "label": "Scott's mobile"})
        assert r.status_code == 201
        mid = r.get_json()["id"]

        r2 = client.get("/api/v1/voice-auth/phone-lookup?phone=+15550000001")
        assert r2.status_code == 200
        assert r2.get_json()["user_ref"] == "u1"

        r3 = client.get("/api/v1/voice-auth/phone-mappings?user_ref=u1")
        assert r3.get_json()["count"] == 1

        r4 = client.delete(f"/api/v1/voice-auth/phone-mappings/{mid}")
        assert r4.status_code == 204

        r5 = client.get("/api/v1/voice-auth/phone-lookup?phone=+15550000001")
        assert r5.status_code == 404

    def test_invalid_phone(self, client):
        r = client.post("/api/v1/voice-auth/phone-mappings",
                        json={"phone": "abc", "user_ref": "u1", "home_id": "scott_home"})
        assert r.status_code == 400


class TestTier1Auth:
    """Middleware tests — requires client_authed fixture (keys enforced)."""

    def _enroll_body(self):
        return {
            "user_ref": "u1", "home_id": "scott_home",
            "automation_name": "X", "ha_service": "scene", "ha_entity": "x",
        }

    def test_missing_header_401(self, client_authed):
        r = client_authed.post("/api/v1/voice-auth/enrollments", json=self._enroll_body())
        assert r.status_code == 401
        assert r.get_json()["code"] == "UNAUTHORIZED"

    def test_malformed_header_401(self, client_authed):
        r = client_authed.post("/api/v1/voice-auth/enrollments",
                               json=self._enroll_body(),
                               headers={"Authorization": "Basic abc"})
        assert r.status_code == 401

    def test_wrong_key_401(self, client_authed):
        r = client_authed.post("/api/v1/voice-auth/enrollments",
                               json=self._enroll_body(),
                               headers={"Authorization": "Bearer sk_wrong"})
        assert r.status_code == 401

    def test_ios_key_passes(self, client_authed):
        r = client_authed.post("/api/v1/voice-auth/enrollments",
                               json=self._enroll_body(),
                               headers={"Authorization": "Bearer sk_ios_good"})
        assert r.status_code == 201

    def test_android_key_passes(self, client_authed):
        r = client_authed.post("/api/v1/voice-auth/enrollments",
                               json=self._enroll_body(),
                               headers={"Authorization": "Bearer sk_and_good"})
        assert r.status_code == 201

    def test_empty_keys_config_falls_open(self, client):
        # client fixture has MOBILE_API_KEYS_JSON="" — no header required
        r = client.post("/api/v1/voice-auth/enrollments",
                        json=self._enroll_body())
        assert r.status_code == 201
