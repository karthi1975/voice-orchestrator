"""HADeviceRegistry.entity_areas: the per-entity area map that lets
device-less helpers (Scott's Entry Door pattern) appear on area boards.

The template now renders {entity: [device_id, area]} in one call; these
tests pin the parsing rules:
  - device-attached entities keep their resolved area
  - orphan (device-less) entities qualify only in controllable domains
  - orphans with no area, and non-controllable orphans, are excluded
  - the map is cached and served stale alongside devices during an outage
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests as real_requests

from app.infrastructure.home_assistant.device_registry import HADeviceRegistry
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher

HOME_CFG = json.dumps({"h1": {"ha_url": "https://ha.test", "ha_token": "tok"}})


def _resp(status, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else []
    r.text = json.dumps(body) if body is not None else "[]"
    return r


def _registry():
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}"}):
        dispatcher = HADirectDispatcher.from_env()
    return HADeviceRegistry(dispatcher, cache_ttl_seconds=0)


STATES = _resp(200, [
    {"entity_id": "switch.relay"},          # device-attached
    {"entity_id": "sensor.relay_power"},    # device-attached, no area override
    {"entity_id": "input_boolean.entry_door"},  # orphan helper with area
    {"entity_id": "cover.entry_door_virtual"},  # orphan helper with area
    {"entity_id": "input_button.press_to_open"},  # orphan press helper with area
    {"entity_id": "sensor.random_stat"},    # orphan NON-controllable with area
    {"entity_id": "automation.open_door"},  # orphan automation with area
    {"entity_id": "input_boolean.scratch"},  # orphan helper, NO area
])
ENT_MAP = _resp(200, {
    "switch.relay": ["dev1", "Hidden Devices"],
    "sensor.relay_power": ["dev1", "Hidden Devices"],
    "input_boolean.entry_door": ["", "Entry Area"],
    "cover.entry_door_virtual": ["", "Entry Area"],
    "input_button.press_to_open": ["", "Entry Area"],
    "sensor.random_stat": ["", "Entry Area"],
    "automation.open_door": ["", "Entry Area"],
    "input_boolean.scratch": ["", ""],
})
ATTRS = _resp(200, {"dev1": ["Shelly Relay", "Shelly", "1PM", "Hidden Devices"]})


class TestEntityAreas:
    def _fetch(self, reg):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=STATES), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ENT_MAP, ATTRS]):
            return reg.entity_areas("h1")

    def test_orphan_helper_with_area_included(self):
        areas = self._fetch(_registry())
        assert areas["input_boolean.entry_door"] == "Entry Area"
        assert areas["cover.entry_door_virtual"] == "Entry Area"

    def test_device_attached_entities_keep_resolved_area(self):
        areas = self._fetch(_registry())
        assert areas["switch.relay"] == "Hidden Devices"
        assert areas["sensor.relay_power"] == "Hidden Devices"

    def test_orphan_input_button_included(self):
        # The real Scott case: input_button.entry_open_door — a press
        # helper, not in PRIMARY_DOMAINS but a deliberate user-created
        # control (HELPER_ORPHAN_DOMAINS admits it).
        areas = self._fetch(_registry())
        assert areas["input_button.press_to_open"] == "Entry Area"

    def test_non_controllable_orphan_excluded(self):
        areas = self._fetch(_registry())
        assert "sensor.random_stat" not in areas

    def test_orphan_automation_excluded(self):
        # Automations stay off the boards even with an area assigned —
        # agreed policy; the helper is the user-facing control.
        areas = self._fetch(_registry())
        assert "automation.open_door" not in areas

    def test_orphan_without_area_excluded(self):
        areas = self._fetch(_registry())
        assert "input_boolean.scratch" not in areas

    def test_devices_unaffected_by_orphans(self):
        reg = _registry()
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=STATES), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ENT_MAP, ATTRS]):
            devices = reg.list_devices("h1")
        assert [d.device_id for d in devices] == ["dev1"]
        assert devices[0].area == "Hidden Devices"
        assert "input_boolean.entry_door" not in devices[0].all_entities

    def test_entity_area_override_beats_device_area(self):
        # An entity reassigned to its own area resolves there, not at the
        # device's area — the template's area_name(entity) already did the
        # resolution; we must not overwrite it with the device area.
        reg = _registry()
        ent_map = _resp(200, {"switch.relay": ["dev1", "Porch"]})
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(200, [{"entity_id": "switch.relay"}])), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ent_map, ATTRS]):
            areas = reg.entity_areas("h1")
        assert areas["switch.relay"] == "Porch"

    def test_stale_cache_serves_area_map_through_outage(self):
        reg = _registry()  # ttl 0 = always refetch
        areas = self._fetch(reg)
        assert "input_boolean.entry_door" in areas

        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   side_effect=real_requests.exceptions.ConnectionError("down")):
            stale = reg.entity_areas("h1")
        assert stale == areas

    def test_only_helpers_no_devices_still_returns_map(self):
        reg = _registry()
        states = _resp(200, [{"entity_id": "input_boolean.entry_door"}])
        ent_map = _resp(200, {"input_boolean.entry_door": ["", "Entry Area"]})
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=states), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ent_map]):
            areas = reg.entity_areas("h1")
        assert areas == {"input_boolean.entry_door": "Entry Area"}
        # and list_devices from the same (ttl-0, so refetched) pipeline is empty
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=states), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ent_map]):
            assert reg.list_devices("h1") == []
