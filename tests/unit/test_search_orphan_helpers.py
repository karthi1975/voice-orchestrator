"""/items/search surfaces device-less helpers by the boards' rule.

A helper that appears as a board tile (orphan entity in HELPER_ORPHAN_DOMAINS,
e.g. Scott's input_button.entry_open_door) must also be findable in search —
otherwise the app can render it but never favorite or look it up.
"""
import json as _json
import os as _os
from unittest.mock import MagicMock, patch as _patch

import pytest
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher
from app.repositories.implementations.in_memory_favorite_device_repo import (
    InMemoryFavoriteDeviceRepository,
)
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.favorite_device_service import FavoriteDeviceService
from app.services.voice_auth_service import VoiceAuthService


class TestSearchOrphanHelpers:

    @pytest.fixture
    def client(self):
        home_cfg = _json.dumps({"h1": {"ha_url": "https://ha.test", "ha_token": "tok"}})
        with _patch.dict(_os.environ, {"HOME_CONFIGS_JSON": home_cfg, "SCENE_CATALOG_JSON": "{}"}):
            dispatcher = HADirectDispatcher.from_env()

        device = MagicMock()
        device.device_id = "dev1"
        device.name = "Deck light"
        device.manufacturer = "TP-Link"
        device.model = "HS200"
        device.area = "Deck"
        device.primary_entity_id = "switch.deck_light"
        device.primary_domain = "switch"
        device.all_entities = ["switch.deck_light", "button.deck_light_restart"]
        device.is_controllable = True

        registry = MagicMock()
        registry.list_devices.return_value = [device]
        registry.get_states.return_value = [
            {"entity_id": "switch.deck_light", "state": "off",
             "attributes": {"friendly_name": "Deck light"}},
            # Orphan press helper — Scott's Entry Door pattern.
            {"entity_id": "input_button.entry_open_door",
             "state": "2026-10-21T16:19:21+00:00",
             "attributes": {"friendly_name": "Entry Door"}},
            # Orphan toggle helper (previously the only admitted domain).
            {"entity_id": "input_boolean.guest_mode", "state": "off",
             "attributes": {"friendly_name": "Guest Mode"}},
            # Device-attached diagnostic button: already skipped as a device
            # entity, must not become a duplicate row.
            {"entity_id": "button.deck_light_restart", "state": "unknown",
             "attributes": {"friendly_name": "Deck light restart"}},
            # Orphan non-controllable domains stay out.
            {"entity_id": "sensor.loose_sensor", "state": "42",
             "attributes": {"friendly_name": "Loose Sensor"}},
            {"entity_id": "automation.open_door", "state": "on",
             "attributes": {"friendly_name": "Entry Door"}},
        ]
        registry.entity_areas.return_value = {
            "switch.deck_light": "Deck",
            "input_button.entry_open_door": "Entry",
        }

        meta = MagicMock()
        meta.get.side_effect = lambda home_id, entity_ids: {
            "input_button.entry_open_door": {"icon": "mdi:door"},
        }

        svc = VoiceAuthService(
            InMemoryEnrollmentRepository(),
            InMemoryChallengeLogRepository(),
            InMemoryPhoneMappingRepository(),
        )
        controller = VoiceAuthController(
            service=svc,
            dispatcher=dispatcher,
            device_registry=registry,
            favorite_service=FavoriteDeviceService(InMemoryFavoriteDeviceRepository()),
            entity_metadata=meta,
        )
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        return app.test_client(), registry

    def _rows(self, c, qs=""):
        r = c.get(f"/api/v1/voice-auth/items/search?home_id=h1&user_ref=u{qs}")
        assert r.status_code == 200
        return r.get_json()["items"]

    def test_orphan_input_button_is_searchable_with_board_area(self, client):
        c, _ = client
        by_id = {r["entity_id"]: r for r in self._rows(c, "&q=entry")}
        row = by_id.get("input_button.entry_open_door")
        assert row is not None
        assert row["kind"] == "entity"
        assert row["domain"] == "input_button"
        assert row["name"] == "Entry Door"
        assert row["area"] == "Entry"          # same placement as the board
        assert row["icon"] == "mdi:door"
        # The automation of the same name still shows alongside it.
        assert "automation.open_door" in by_id

    def test_orphan_input_boolean_still_searchable(self, client):
        c, _ = client
        by_id = {r["entity_id"]: r for r in self._rows(c)}
        assert "input_boolean.guest_mode" in by_id

    def test_device_attached_button_and_stray_sensor_stay_out(self, client):
        c, _ = client
        ids = {r["entity_id"] for r in self._rows(c)}
        assert "button.deck_light_restart" not in ids   # device row covers it
        assert "sensor.loose_sensor" not in ids         # not controllable

    def test_area_lookup_failure_degrades_to_null_area(self, client):
        c, registry = client
        registry.entity_areas.side_effect = RuntimeError("HA down")
        by_id = {r["entity_id"]: r for r in self._rows(c, "&q=entry")}
        row = by_id.get("input_button.entry_open_door")
        assert row is not None and row["area"] is None
