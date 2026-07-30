"""Tests for entity icon resolution and tile metadata.

Two layers:
  - resolve_icon: the pure fallback chain (app/domain/entity_icons.py)
  - HAEntityMetadata: the join of registry + icon translations + states

The fixtures mirror shapes taken from a real home, so `sensor.*_signal_level`
here is the actual TP-Link entity that has no icon, no device_class and no
unit over REST, and whose icon only exists in HA's icon translations.
"""

import pytest

from app.domain.entity_icons import (
    DEVICE_CLASS_ICONS,
    DOMAIN_ICONS,
    FALLBACK_ICON,
    is_controllable,
    resolve_icon,
)
from app.infrastructure.home_assistant.entity_metadata import HAEntityMetadata


# Shape of frontend/get_icons -> result.resources
ICONS = {
    "tplink": {
        "sensor": {"signal_level": {"default": "mdi:signal"}},
        "switch": {"led": {"default": "mdi:led-off", "state": {"on": "mdi:led-on"}}},
    },
    "sonos": {"binary_sensor": {"microphone": {"default": "mdi:microphone"}}},
}


class TestResolveIcon:
    def test_state_attribute_icon_wins(self):
        assert resolve_icon(
            "sensor.battery",
            state_attributes={"icon": "mdi:battery-70", "device_class": "battery"},
            registry_entry={"icon": "mdi:nope"},
        ) == ("mdi:battery-70", "state")

    def test_registry_override_beats_integration_default(self):
        assert resolve_icon(
            "light.lamp",
            registry_entry={"icon": "mdi:custom", "original_icon": "mdi:builtin"},
        ) == ("mdi:custom", "registry")

    def test_integration_original_icon(self):
        assert resolve_icon(
            "light.lamp", registry_entry={"original_icon": "mdi:builtin"}
        ) == ("mdi:builtin", "integration")

    def test_icon_translation_is_the_only_source_for_signal_level(self):
        """The case that motivated all this: nothing in REST, icon in icons.json."""
        icon, source = resolve_icon(
            "sensor.deck_light_signal_level",
            state_attributes={},  # no icon, no device_class, no unit
            registry_entry={"platform": "tplink", "translation_key": "signal_level"},
            icon_resources=ICONS,
        )
        assert (icon, source) == ("mdi:signal", "translation")

    def test_translation_state_variant_beats_default(self):
        entry = {"platform": "tplink", "translation_key": "led"}
        assert resolve_icon(
            "switch.plug_led", state="on", registry_entry=entry, icon_resources=ICONS
        ) == ("mdi:led-on", "translation")
        assert resolve_icon(
            "switch.plug_led", state="off", registry_entry=entry, icon_resources=ICONS
        ) == ("mdi:led-off", "translation")

    def test_translation_miss_falls_through(self):
        """A translation_key the integration does not publish must not stick."""
        icon, source = resolve_icon(
            "sensor.thing",
            state_attributes={"device_class": "temperature"},
            registry_entry={"platform": "tplink", "translation_key": "not_published"},
            icon_resources=ICONS,
        )
        assert (icon, source) == (DEVICE_CLASS_ICONS["temperature"], "device_class")

    def test_device_class_from_registry_when_state_has_none(self):
        assert resolve_icon(
            "binary_sensor.door", registry_entry={"original_device_class": "door"}
        ) == (DEVICE_CLASS_ICONS["door"], "device_class")

    def test_unit_rescues_sensors_with_no_device_class(self):
        """Venstar runtime sensors: minutes and nothing else to go on."""
        assert resolve_icon(
            "sensor.thermostat_cooling_stage_1_runtime",
            state_attributes={"unit_of_measurement": "min"},
        ) == ("mdi:timer-outline", "unit")

    def test_domain_fallback(self):
        assert resolve_icon("light.den_lamp") == (DOMAIN_ICONS["light"], "domain")
        assert resolve_icon("lock.yale") == (DOMAIN_ICONS["lock"], "domain")

    def test_unknown_domain_hits_the_floor(self):
        assert resolve_icon("wildcard.thing") == (FALLBACK_ICON, "fallback")

    def test_no_inputs_at_all_never_raises(self):
        icon, source = resolve_icon("switch.x")
        assert icon.startswith("mdi:") and source == "domain"


class TestIsControllable:
    @pytest.mark.parametrize("entity_id", [
        "light.a", "switch.a", "lock.a", "scene.a", "script.a",
        "automation.a", "climate.a", "media_player.a", "button.a",
    ])
    def test_controllable(self, entity_id):
        assert is_controllable(entity_id)

    @pytest.mark.parametrize("entity_id", [
        "sensor.a", "binary_sensor.a", "number.a", "select.a",
        "event.a", "update.a", "device_tracker.a",
    ])
    def test_read_only(self, entity_id):
        """number/select are settable in HA but not via /automations/trigger."""
        assert not is_controllable(entity_id)


# --- HAEntityMetadata ---------------------------------------------------------


class FakeDashboards:
    def __init__(self, registry, icons=ICONS):
        self._registry = registry
        self._icons = icons
        self.calls = 0

    def get_entity_registry_and_icons(self, home_id):
        self.calls += 1
        return self._registry, self._icons


class FakeRegistry:
    def __init__(self, states):
        self._states = states

    def get_states(self, home_id):
        return self._states


@pytest.fixture
def metadata():
    registry = {
        "sensor.deck_light_signal_level": {
            "platform": "tplink",
            "translation_key": "signal_level",
            "entity_category": "diagnostic",
        },
        "switch.deck_light": {"platform": "tplink", "entity_category": None},
        "switch.hidden_thing": {"platform": "tplink", "hidden_by": "user"},
        "number.deck_light_turn_off_in": {
            "platform": "tplink",
            "translation_key": "auto_off_minutes",
            "entity_category": "config",
        },
    }
    states = [
        {"entity_id": "sensor.deck_light_signal_level", "state": "2",
         "attributes": {"friendly_name": "Deck light Signal level"}},
        {"entity_id": "switch.deck_light", "state": "off",
         "attributes": {"friendly_name": "Deck light"}},
        {"entity_id": "switch.hidden_thing", "state": "on", "attributes": {}},
        {"entity_id": "number.deck_light_turn_off_in", "state": "0", "attributes": {}},
    ]
    return HAEntityMetadata(FakeDashboards(registry), FakeRegistry(states))


class TestEntityMetadata:
    def test_joins_all_three_sources(self, metadata):
        meta = metadata.get("h1", ["sensor.deck_light_signal_level"])
        row = meta["sensor.deck_light_signal_level"]
        assert row["name"] == "Deck light Signal level"       # from states
        assert row["icon"] == "mdi:signal"                    # from icon translations
        assert row["icon_source"] == "translation"
        assert row["entity_category"] == "diagnostic"         # from registry
        assert row["state"] == "2"
        assert row["controllable"] is False

    def test_controllable_switch(self, metadata):
        row = metadata.get("h1", ["switch.deck_light"])["switch.deck_light"]
        assert row["controllable"] is True
        assert row["entity_category"] is None
        assert row["icon"] == DOMAIN_ICONS["switch"]

    def test_hidden_flag(self, metadata):
        rows = metadata.get("h1", ["switch.hidden_thing", "switch.deck_light"])
        assert rows["switch.hidden_thing"]["hidden"] is True
        assert rows["switch.deck_light"]["hidden"] is False

    def test_name_falls_back_to_suffix(self, metadata):
        row = metadata.get("h1", ["switch.hidden_thing"])["switch.hidden_thing"]
        assert row["name"] == "hidden_thing"

    def test_default_covers_whole_home(self, metadata):
        assert len(metadata.get("h1")) == 4

    def test_entity_absent_from_ha_still_gets_a_usable_record(self, metadata):
        """A board can reference an entity HA no longer knows. Render it
        anyway rather than dropping a tile the dashboard asks for."""
        row = metadata.get("h1", ["light.does_not_exist"])["light.does_not_exist"]
        assert row["name"] == "does_not_exist"
        assert row["icon"] == DOMAIN_ICONS["light"]
        assert row["state"] is None
        assert row["entity_category"] is None

    def test_malformed_entity_id_dropped(self, metadata):
        assert metadata.get("h1", ["no_dot_here"]) == {}


# --- /items/search icons ------------------------------------------------------


class TestSearchIcons:
    """Search rows carry the same resolved icon the boards surface uses, so a
    search result and a board tile never disagree about a device."""

    @pytest.fixture
    def client(self):
        import json as _json
        import os as _os
        from unittest.mock import MagicMock, patch as _patch

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
        device.all_entities = ["switch.deck_light", "sensor.deck_light_signal_level"]
        device.is_controllable = True

        registry = MagicMock()
        registry.list_devices.return_value = [device]
        registry.get_states.return_value = [
            {"entity_id": "switch.deck_light", "state": "off",
             "attributes": {"friendly_name": "Deck light"}},
            {"entity_id": "scene.good_night", "state": "unknown",
             "attributes": {"friendly_name": "Good Night"}},
        ]

        meta = MagicMock()
        meta.get.side_effect = lambda home_id, entity_ids: {
            "switch.deck_light": {"icon": "mdi:toggle-switch"},
            "scene.good_night": {"icon": "mdi:palette"},
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
        return app.test_client(), meta, svc

    def test_rows_carry_icons(self, client):
        c, _, _ = client
        rows = c.get("/api/v1/voice-auth/items/search?home_id=h1&user_ref=u").get_json()["items"]
        by_id = {r["entity_id"]: r for r in rows}
        assert by_id["switch.deck_light"]["icon"] == "mdi:toggle-switch"   # device row
        assert by_id["scene.good_night"]["icon"] == "mdi:palette"          # activation row

    def test_metadata_failure_leaves_icons_null_but_search_works(self, client):
        c, meta, _ = client
        meta.get.side_effect = RuntimeError("HA down")
        r = c.get("/api/v1/voice-auth/items/search?home_id=h1&user_ref=u")
        assert r.status_code == 200
        assert all(row["icon"] is None for row in r.get_json()["items"])

    def test_rows_carry_the_voice_gate(self, client):
        """Search is a tile surface too — it must not require a probe either."""
        from app.domain.voice_auth_enums import ChallengeType

        c, _, svc = client
        svc.create_enrollment(
            user_ref="u", home_id="h1", automation_id="good_night",
            automation_name="Good Night", ha_service="scene", ha_entity="good_night",
            challenge_type=ChallengeType.VERIFICATION,
        )
        rows = c.get("/api/v1/voice-auth/items/search?home_id=h1&user_ref=u").get_json()["items"]
        by_id = {r["entity_id"]: r for r in rows}
        assert by_id["scene.good_night"]["voice_gated"] is True
        assert by_id["switch.deck_light"]["voice_gated"] is False

    def test_anonymous_search_reports_nothing_gated(self, client):
        """Gating is per-user; with no user_ref there is no honest answer, so
        the rows say false rather than guessing."""
        c, _, _ = client
        rows = c.get("/api/v1/voice-auth/items/search?home_id=h1").get_json()["items"]
        assert all(r["voice_gated"] is False for r in rows)
