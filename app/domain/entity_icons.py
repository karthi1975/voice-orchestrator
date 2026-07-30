"""Icon and tile-behavior resolution for Home Assistant entities.

Pure functions — no I/O. Callers supply the three inputs; the infrastructure
layer is responsible for fetching them (see HAEntityMetadata).

WHY THIS EXISTS

HA's REST `/api/states` is not enough to icon a tile. Measured against a real
home (204 entities on the default Overview board): 62% carry neither an `icon`
attribute nor a `device_class`. `sensor.deck_light_signal_level` is typical —
icon, device_class and unit are all null over REST, yet HA's own UI shows
`mdi:signal` for it.

The reason is that since HA 2024.2 integrations declare icons in an
`icons.json` *icon translation* file keyed by the entity's `translation_key`,
not as an entity attribute. REST never includes them; the frontend fetches
them separately over the WebSocket API. So the resolution chain has to reach
past REST into the entity registry (for translation_key + platform) and the
icon translations themselves.

RESOLUTION ORDER (first hit wins; `source` says which rung fired)

  1. state       state attribute `icon`     — dynamic, integration-computed
  2. registry    registry `icon`            — the user's own override in HA
  3. integration registry `original_icon`   — legacy static `_attr_icon`
  4. translation icons.json default/state   — the modern path, biggest win
  5. device_class DEVICE_CLASS_ICONS
  6. unit        UNIT_ICONS                 — rescues unit-only sensors
  7. domain      DOMAIN_ICONS
  8. fallback    mdi:help-circle            — should never be reached

Rungs 1-4 are HA's own data, so a tile iconed from them matches what the user
sees in Home Assistant. Rungs 5-7 are ours and only fire where HA itself has
nothing better than a domain default.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Fallback tables
# ---------------------------------------------------------------------------

# device_class -> mdi icon. Covers HA's documented classes for sensor,
# binary_sensor, cover, media_player, switch, button and update.
DEVICE_CLASS_ICONS: Dict[str, str] = {
    # sensor
    "apparent_power": "mdi:flash",
    "aqi": "mdi:air-filter",
    "atmospheric_pressure": "mdi:thermometer-lines",
    "battery": "mdi:battery",
    "carbon_dioxide": "mdi:molecule-co2",
    "carbon_monoxide": "mdi:molecule-co",
    "current": "mdi:current-ac",
    "data_rate": "mdi:transmission-tower",
    "data_size": "mdi:harddisk",
    "date": "mdi:calendar",
    "distance": "mdi:ruler",
    "duration": "mdi:timer-outline",
    "energy": "mdi:lightning-bolt",
    "energy_storage": "mdi:car-battery",
    "enum": "mdi:format-list-bulleted",
    "frequency": "mdi:sine-wave",
    "gas": "mdi:meter-gas",
    "humidity": "mdi:water-percent",
    "illuminance": "mdi:brightness-5",
    "irradiance": "mdi:sun-wireless",
    "moisture": "mdi:water-percent",
    "monetary": "mdi:cash",
    "nitrogen_dioxide": "mdi:molecule",
    "ozone": "mdi:molecule",
    "ph": "mdi:ph",
    "pm1": "mdi:molecule",
    "pm10": "mdi:molecule",
    "pm25": "mdi:molecule",
    "power": "mdi:flash",
    "power_factor": "mdi:angle-acute",
    "precipitation": "mdi:weather-rainy",
    "precipitation_intensity": "mdi:weather-pouring",
    "pressure": "mdi:gauge",
    "reactive_power": "mdi:flash",
    "signal_strength": "mdi:wifi",
    "sound_pressure": "mdi:ear-hearing",
    "speed": "mdi:speedometer",
    "sulphur_dioxide": "mdi:molecule",
    "temperature": "mdi:thermometer",
    "timestamp": "mdi:clock-outline",
    "volatile_organic_compounds": "mdi:molecule",
    "voltage": "mdi:sine-wave",
    "volume": "mdi:car-coolant-level",
    "water": "mdi:water",
    "weight": "mdi:weight",
    "wind_speed": "mdi:weather-windy",
    # binary_sensor
    "battery_charging": "mdi:battery-charging",
    "cold": "mdi:snowflake",
    "connectivity": "mdi:wifi",
    "door": "mdi:door-open",
    "garage_door": "mdi:garage-open",
    "gas_detected": "mdi:gas-cylinder",
    "heat": "mdi:fire",
    "light": "mdi:brightness-5",
    "lock": "mdi:lock-open",
    "motion": "mdi:motion-sensor",
    "moving": "mdi:arrow-right",
    "occupancy": "mdi:home-account",
    "opening": "mdi:square-outline",
    "plug": "mdi:power-plug",
    "presence": "mdi:home",
    "problem": "mdi:alert-circle",
    "running": "mdi:play",
    "safety": "mdi:shield-check",
    "smoke": "mdi:smoke-detector",
    "sound": "mdi:volume-high",
    "tamper": "mdi:hammer-wrench",
    "vibration": "mdi:vibrate",
    "window": "mdi:window-open",
    # cover
    "awning": "mdi:awning-outline",
    "blind": "mdi:blinds",
    "curtain": "mdi:curtains",
    "damper": "mdi:circle",
    "gate": "mdi:gate",
    "shade": "mdi:roller-shade",
    "shutter": "mdi:window-shutter",
    # media_player
    "receiver": "mdi:audio-video",
    "speaker": "mdi:speaker",
    "tv": "mdi:television",
    # switch / button / update
    "outlet": "mdi:power-socket-us",
    "switch": "mdi:toggle-switch",
    "identify": "mdi:crosshairs-question",
    "restart": "mdi:restart",
    "firmware": "mdi:package-up",
}

# unit_of_measurement -> mdi icon. Only consulted when nothing above matched;
# rescues integrations that ship a unit but no device_class (e.g. Venstar's
# thermostat runtime sensors, which report minutes and nothing else).
UNIT_ICONS: Dict[str, str] = {
    "min": "mdi:timer-outline",
    "h": "mdi:timer-outline",
    "s": "mdi:timer-outline",
    "d": "mdi:calendar-range",
    "%": "mdi:percent",
    "steps": "mdi:walk",
    "floors": "mdi:stairs",
    "dB": "mdi:volume-high",
    "dBm": "mdi:wifi",
}

# Last resort before mdi:help-circle. Every HA domain the boards surface can
# hand us gets an entry so the fallback rung never looks broken.
DOMAIN_ICONS: Dict[str, str] = {
    "alarm_control_panel": "mdi:shield-home",
    "automation": "mdi:robot",
    "binary_sensor": "mdi:radiobox-blank",
    "button": "mdi:gesture-tap-button",
    "camera": "mdi:video",
    "climate": "mdi:thermostat",
    "conversation": "mdi:forum-outline",
    "cover": "mdi:window-shutter",
    "device_tracker": "mdi:account",
    "event": "mdi:gesture-double-tap",
    "fan": "mdi:fan",
    "humidifier": "mdi:air-humidifier",
    "image": "mdi:image",
    "input_boolean": "mdi:toggle-switch-outline",
    "input_button": "mdi:gesture-tap-button",
    "input_number": "mdi:ray-vertex",
    "input_select": "mdi:form-dropdown",
    "input_text": "mdi:form-textbox",
    "light": "mdi:lightbulb",
    "lock": "mdi:lock",
    "media_player": "mdi:speaker",
    "number": "mdi:ray-vertex",
    "person": "mdi:account",
    "remote": "mdi:remote",
    "scene": "mdi:palette",
    "script": "mdi:script-text",
    "select": "mdi:form-dropdown",
    "sensor": "mdi:eye",
    "siren": "mdi:bullhorn",
    "sun": "mdi:white-balance-sunny",
    "switch": "mdi:toggle-switch",
    "text": "mdi:form-textbox",
    "todo": "mdi:clipboard-list",
    "update": "mdi:package-up",
    "vacuum": "mdi:robot-vacuum",
    "valve": "mdi:pipe-valve",
    "weather": "mdi:weather-partly-cloudy",
    "zone": "mdi:map-marker-radius",
}

FALLBACK_ICON = "mdi:help-circle"

# Domains a tile can fire through POST /automations/trigger, whose
# HADirectDispatcher.DEFAULT_ACTIONS resolve to turn_on / trigger / unlock.
# Everything else (sensor, number, select, event, update…) renders read-only.
# `number`/`select`/`text` are settable in HA but not through that endpoint,
# so they stay read-only until a set-value action exists.
CONTROLLABLE_DOMAINS = frozenset({
    "automation",
    "button",
    "climate",
    "cover",
    "fan",
    "humidifier",
    "input_boolean",
    "input_button",
    "light",
    "lock",
    "media_player",
    "scene",
    "script",
    "siren",
    "switch",
    "vacuum",
    "valve",
})


def is_controllable(entity_id: str) -> bool:
    """True when tapping the tile can fire something via /automations/trigger."""
    return entity_id.split(".", 1)[0] in CONTROLLABLE_DOMAINS


def _translation_icon(
    domain: str,
    state: Optional[str],
    registry_entry: Dict[str, Any],
    icon_resources: Dict[str, Any],
) -> Optional[str]:
    """Look the entity up in HA's icon translations.

    Shape, as returned by the `frontend/get_icons` WebSocket command:

        resources[platform][domain][translation_key] = {
            "default": "mdi:signal",
            "state": {"on": "mdi:signal-cellular-3", ...},   # optional
        }

    A state-specific icon wins over the default, mirroring the HA frontend.
    """
    platform = registry_entry.get("platform")
    translation_key = registry_entry.get("translation_key")
    if not platform or not translation_key:
        return None
    node = (
        (icon_resources.get(platform) or {})
        .get(domain, {})
        .get(translation_key)
    )
    if not isinstance(node, dict):
        return None
    if state is not None:
        by_state = node.get("state")
        if isinstance(by_state, dict) and by_state.get(state):
            return by_state[state]
    return node.get("default") or None


def resolve_icon(
    entity_id: str,
    *,
    state_attributes: Optional[Dict[str, Any]] = None,
    state: Optional[str] = None,
    registry_entry: Optional[Dict[str, Any]] = None,
    icon_resources: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Resolve one entity's icon. Returns (mdi_icon, source).

    `source` is one of: state, registry, integration, translation,
    device_class, unit, domain, fallback — see the module docstring. It is
    echoed in the API response so a mis-iconed tile can be diagnosed without
    guessing which rung produced it.
    """
    attrs = state_attributes or {}
    entry = registry_entry or {}
    resources = icon_resources or {}
    domain = entity_id.split(".", 1)[0]

    if attrs.get("icon"):
        return attrs["icon"], "state"
    if entry.get("icon"):
        return entry["icon"], "registry"
    if entry.get("original_icon"):
        return entry["original_icon"], "integration"

    translated = _translation_icon(domain, state, entry, resources)
    if translated:
        return translated, "translation"

    device_class = (
        attrs.get("device_class")
        or entry.get("device_class")
        or entry.get("original_device_class")
    )
    if device_class and device_class in DEVICE_CLASS_ICONS:
        return DEVICE_CLASS_ICONS[device_class], "device_class"

    unit = attrs.get("unit_of_measurement")
    if unit and unit in UNIT_ICONS:
        return UNIT_ICONS[unit], "unit"

    if domain in DOMAIN_ICONS:
        return DOMAIN_ICONS[domain], "domain"
    return FALLBACK_ICON, "fallback"
