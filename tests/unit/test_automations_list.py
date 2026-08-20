"""
Tests for GET /automations — the per-home HA automation list for the mobile
app — and the `action` override on POST /automations/trigger.

The list is built from the registry's cached `/api/states` rows (the same
verified surface search_items reads); these tests pin the HTTP contract:
domain filtering, field mapping (enabled/ha_automation_id/is_running), the
q/enabled filters, per-user voice_gated + is_favorited annotation, and the
error statuses shared with the rest of the mobile surface.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.domain.voice_auth_enums import ChallengeType
from app.infrastructure.home_assistant.device_registry import HomeUnreachableError
from app.infrastructure.home_assistant.direct_dispatcher import (
    DispatchResult,
    HADirectDispatcher,
)
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.voice_auth_service import VoiceAuthService

HOME_CFG = json.dumps({"h1": {"ha_url": "https://ha.test", "ha_token": "tok"}})

BASE = "/api/v1/voice-auth"
Q = "user_ref=scott_mobile&home_id=h1"

STATES = [
    {"entity_id": "light.den_lamp", "state": "on", "attributes": {"friendly_name": "Den Lamp"}},
    {
        "entity_id": "automation.lights_off_at_night",
        "state": "on",
        "attributes": {
            "id": "1751405011005",
            "friendly_name": "Lights Off at Night",
            "last_triggered": "2026-08-18T04:00:00+00:00",
            "mode": "single",
            "current": 0,
        },
    },
    {
        "entity_id": "automation.wake_up_morning",
        "state": "off",
        "attributes": {
            "id": "1743855173735",
            "friendly_name": "Wake up Morning",
            "last_triggered": None,
            "mode": "single",
            "current": 1,
        },
    },
    # YAML-defined: no `id` attribute; also no friendly_name -> suffix used
    {"entity_id": "automation.backup_nightly", "state": "on", "attributes": {}},
]


@pytest.fixture
def dispatcher():
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}"}):
        return HADirectDispatcher.from_env()


def _build(dispatcher, *, gated_suffix=None, favorited_entity=None):
    """Test client with a real VoiceAuthService (so the gate flag and the fire
    path share one source of truth), mocked registry states, and mocked
    icon metadata."""
    svc = VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
    )
    enrollment = None
    if gated_suffix:
        # ha_service "automation" is not enrollable directly, but the gate
        # matches on the entity SUFFIX across domains — an enrollment on
        # script.<suffix> gates automation.<suffix> too (see _gate_lookup).
        enrollment = svc.create_enrollment(
            user_ref="scott_mobile", home_id="h1", automation_id=gated_suffix,
            automation_name=gated_suffix, ha_service="script", ha_entity=gated_suffix,
            challenge_type=ChallengeType.VERIFICATION,
        )

    registry = MagicMock()
    registry.get_states.return_value = STATES
    registry.list_devices.return_value = []

    meta = MagicMock()
    meta.get.side_effect = lambda home_id, entity_ids: {
        e: {"icon": "mdi:robot"} for e in entity_ids
    }

    favorites = MagicMock()
    fav_rows = []
    if favorited_entity:
        row = MagicMock()
        row.entity_id = favorited_entity
        row.id = "fav-1"
        fav_rows.append(row)
    favorites.list_favorites.return_value = fav_rows

    controller = VoiceAuthController(
        service=svc,
        dispatcher=dispatcher,
        device_registry=registry,
        entity_metadata=meta,
        favorite_service=favorites,
    )
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    return app.test_client(), controller, registry, enrollment


class TestListAutomations:
    def test_missing_params_400(self, dispatcher):
        client, _, _, _ = _build(dispatcher)
        assert client.get(f"{BASE}/automations?home_id=h1").status_code == 400
        assert client.get(f"{BASE}/automations?user_ref=u").status_code == 400

    def test_unknown_home_404(self, dispatcher):
        client, _, _, _ = _build(dispatcher)
        r = client.get(f"{BASE}/automations?user_ref=u&home_id=nope")
        assert r.status_code == 404

    def test_unreachable_503(self, dispatcher):
        client, _, registry, _ = _build(dispatcher)
        registry.get_states.side_effect = HomeUnreachableError("HA down")
        r = client.get(f"{BASE}/automations?{Q}")
        assert r.status_code == 503
        assert r.get_json()["code"] == "HOME_UNREACHABLE"

    def test_only_automation_domain_sorted_by_name(self, dispatcher):
        client, _, _, _ = _build(dispatcher)
        body = client.get(f"{BASE}/automations?{Q}").get_json()
        assert body["home_id"] == "h1"
        assert body["count"] == 3
        assert [i["entity_id"] for i in body["items"]] == [
            "automation.backup_nightly",       # "backup_nightly" (suffix name)
            "automation.lights_off_at_night",  # "Lights Off at Night"
            "automation.wake_up_morning",      # "Wake up Morning"
        ]
        assert body["gate_check_available"] is True

    def test_field_mapping(self, dispatcher):
        client, _, _, _ = _build(dispatcher)
        items = {i["entity_id"]: i for i in client.get(f"{BASE}/automations?{Q}").get_json()["items"]}

        on = items["automation.lights_off_at_night"]
        assert on["automation_id"] == "lights_off_at_night"
        assert on["ha_automation_id"] == "1751405011005"
        assert on["name"] == "Lights Off at Night"
        assert on["enabled"] is True
        assert on["is_running"] is False
        assert on["mode"] == "single"
        assert on["last_triggered"] == "2026-08-18T04:00:00+00:00"
        assert on["icon"] == "mdi:robot"

        off = items["automation.wake_up_morning"]
        assert off["enabled"] is False
        assert off["is_running"] is True  # current=1: still executing

        yaml_defined = items["automation.backup_nightly"]
        assert yaml_defined["ha_automation_id"] is None
        assert yaml_defined["name"] == "backup_nightly"

    def test_q_and_enabled_filters(self, dispatcher):
        client, _, _, _ = _build(dispatcher)
        body = client.get(f"{BASE}/automations?{Q}&q=night").get_json()
        assert [i["entity_id"] for i in body["items"]] == [
            "automation.backup_nightly", "automation.lights_off_at_night",
        ]
        body = client.get(f"{BASE}/automations?{Q}&enabled=false").get_json()
        assert [i["entity_id"] for i in body["items"]] == ["automation.wake_up_morning"]

    def test_voice_gate_and_favorite_annotation(self, dispatcher):
        client, _, _, enrollment = _build(
            dispatcher,
            gated_suffix="wake_up_morning",
            favorited_entity="automation.lights_off_at_night",
        )
        items = {i["entity_id"]: i for i in client.get(f"{BASE}/automations?{Q}").get_json()["items"]}

        gated = items["automation.wake_up_morning"]
        assert gated["voice_gated"] is True
        assert gated["voice_auth_enrollment_id"] == enrollment.id

        fav = items["automation.lights_off_at_night"]
        assert fav["voice_gated"] is False
        assert fav["is_favorited"] is True
        assert fav["favorite_id"] == "fav-1"

    def test_gate_lookup_failure_flagged_not_fatal(self, dispatcher):
        client, controller, _, _ = _build(dispatcher)
        with patch.object(controller._svc, "active_gate_map", side_effect=RuntimeError("db down")):
            body = client.get(f"{BASE}/automations?{Q}").get_json()
        assert body["count"] == 3
        assert body["gate_check_available"] is False

    def test_metadata_failure_degrades_to_null_icons(self, dispatcher):
        client, controller, _, _ = _build(dispatcher)
        controller._entity_meta.get.side_effect = RuntimeError("HA hiccup")
        body = client.get(f"{BASE}/automations?{Q}").get_json()
        assert body["count"] == 3
        assert all(i["icon"] is None for i in body["items"])


class TestTriggerAutomationAction:
    def _fire(self, dispatcher, body):
        client, controller, _, _ = _build(dispatcher)
        controller._dispatcher = MagicMock()
        controller._dispatcher.dispatch_direct.return_value = DispatchResult(True, "ok", 200, 5)
        r = client.post(f"{BASE}/automations/trigger", json=body)
        return r, controller._dispatcher.dispatch_direct

    def test_default_action_is_domain_default(self, dispatcher):
        r, dispatch = self._fire(dispatcher, {
            "home_id": "h1", "ha_service": "automation", "ha_entity": "wake_up_morning",
        })
        assert r.status_code == 200
        dispatch.assert_called_once_with("h1", "automation", "wake_up_morning", action=None)

    def test_action_override_disables_automation(self, dispatcher):
        r, dispatch = self._fire(dispatcher, {
            "home_id": "h1", "ha_service": "automation", "ha_entity": "wake_up_morning",
            "action": "turn_off",
        })
        assert r.status_code == 200
        dispatch.assert_called_once_with("h1", "automation", "wake_up_morning", action="turn_off")

    def test_homeassistant_domain_rejected_not_silently_ignored(self, dispatcher):
        # entity_id is built as "{service}.{entity}", so ha_service
        # "homeassistant" would target homeassistant.<entity> — which HA
        # 200-OKs and ignores. The API must refuse rather than fake success.
        r, dispatch = self._fire(dispatcher, {
            "home_id": "h1", "ha_service": "homeassistant", "ha_entity": "man_land_lamp",
            "action": "toggle",
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "VALIDATION"
        dispatch.assert_not_called()
