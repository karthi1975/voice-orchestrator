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
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.voice_auth_service import VoiceAuthService


@pytest.fixture
def client():
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": "{}", "SCENE_CATALOG_JSON": "{}"}):
        dispatcher = HADirectDispatcher.from_env()
    svc = VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
    )
    controller = VoiceAuthController(service=svc, dispatcher=dispatcher)
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


class TestVapiCallStart:
    def test_unknown_caller(self, client):
        r = client.post("/api/v1/voice-auth/vapi/call-start",
                        json={"message": {"call": {"customer": {"number": "+19999999999"}}}})
        assert r.status_code == 200
        d = r.get_json()
        assert d["assistantOverrides"] == {"variableValues": {}}

    def test_known_caller_sets_overrides(self, client):
        client.post("/api/v1/voice-auth/phone-mappings",
                    json={"phone": "+15551112222",
                          "user_ref": "u1", "home_id": "scott_home",
                          "label": "Scott mobile"})
        r = client.post("/api/v1/voice-auth/vapi/call-start",
                        json={"message": {"call": {"customer": {"number": "+15551112222"}}}})
        d = r.get_json()
        vv = d["assistantOverrides"]["variableValues"]
        assert vv["user_ref"] == "u1"
        assert vv["home_id"] == "scott_home"
        assert vv["caller_label"] == "Scott mobile"
