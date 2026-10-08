"""dispatch_direct must not report success for an entity Home Assistant
cannot act on. HA answers 200 to a service call whose entity does not exist
or is unavailable — it simply changes nothing — which is how a 'toggle' of
the wrong entity came back as success while the real device never moved."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.infrastructure.home_assistant.direct_dispatcher import (
    DispatchResult,
    HADirectDispatcher,
    HomeConfig,
)

MOD = "app.infrastructure.home_assistant.direct_dispatcher"


def _resp(status, body=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    if body is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = body
    return r


@pytest.fixture
def dispatcher():
    return HADirectDispatcher(
        {"scott_home": HomeConfig("scott_home", "https://ha.example/", "tok")},
        {},
    )


def test_missing_entity_is_refused_before_any_service_call(dispatcher):
    with patch(f"{MOD}.requests.get", return_value=_resp(404, {"message": "Entity not found."})) as g, \
         patch(f"{MOD}.requests.post") as p:
        r = dispatcher.dispatch_direct("scott_home", "switch", "bat_sgin", action="toggle")
    assert r.success is False
    assert r.code == "ENTITY_NOT_FOUND"
    assert r.entity_id == "switch.bat_sgin"
    assert r.action == "toggle"
    assert "does not exist" in r.message
    g.assert_called_once()
    assert g.call_args[0][0] == "https://ha.example/api/states/switch.bat_sgin"
    p.assert_not_called()


def test_unavailable_entity_is_refused(dispatcher):
    state = {"entity_id": "media_player.lg_webos_tv_ut7000pua", "state": "unavailable"}
    with patch(f"{MOD}.requests.get", return_value=_resp(200, state)), \
         patch(f"{MOD}.requests.post") as p:
        r = dispatcher.dispatch_direct("scott_home", "media_player", "lg_webos_tv_ut7000pua", action="toggle")
    assert r.success is False
    assert r.code == "ENTITY_UNAVAILABLE"
    assert r.entity_id == "media_player.lg_webos_tv_ut7000pua"
    p.assert_not_called()


def test_available_entity_toggles_and_reports_changed_entities(dispatcher):
    state = {"entity_id": "switch.bat_sign", "state": "off"}
    changed = [{"entity_id": "switch.bat_sign", "state": "on"}]
    with patch(f"{MOD}.requests.get", return_value=_resp(200, state)), \
         patch(f"{MOD}.requests.post", return_value=_resp(200, changed)) as p:
        r = dispatcher.dispatch_direct("scott_home", "switch", "bat_sign", action="Toggle")
    assert r.success is True
    assert r.code is None
    assert r.action == "toggle"                       # normalized
    assert r.entity_id == "switch.bat_sign"
    assert r.changed_entities == ["switch.bat_sign"]
    assert p.call_args[0][0] == "https://ha.example/api/services/switch/toggle"
    assert p.call_args[1]["json"] == {"entity_id": "switch.bat_sign"}


def test_accepted_call_with_no_state_change_is_flagged(dispatcher):
    state = {"entity_id": "switch.bat_sign", "state": "off"}
    with patch(f"{MOD}.requests.get", return_value=_resp(200, state)), \
         patch(f"{MOD}.requests.post", return_value=_resp(200, [])):
        r = dispatcher.dispatch_direct("scott_home", "switch", "bat_sign")
    assert r.success is True                          # HA said 2xx; not a hard failure
    assert r.code == "NO_STATE_CHANGE"
    assert r.changed_entities == []
    assert r.action == "turn_on"                      # per-domain default
    assert "no state change" in r.message


def test_default_actions_still_apply(dispatcher):
    state = {"entity_id": "automation.utogglebatsign", "state": "on"}
    with patch(f"{MOD}.requests.get", return_value=_resp(200, state)), \
         patch(f"{MOD}.requests.post", return_value=_resp(200, [{"entity_id": "automation.utogglebatsign"}])) as p:
        r = dispatcher.dispatch_direct("scott_home", "automation", "utogglebatsign")
    assert r.success and r.action == "trigger"
    assert p.call_args[0][0].endswith("/api/services/automation/trigger")


@pytest.mark.parametrize("domain", ["input_button", "button"])
def test_buttons_default_to_press(dispatcher, domain):
    # input_button only supports press; turn_on is a 400 from HA. This is
    # the tap path for helper tiles like input_button.entry_open_door.
    entity = f"{domain}.entry_open_door"
    state = {"entity_id": entity, "state": "2026-10-07T00:00:00+00:00"}
    with patch(f"{MOD}.requests.get", return_value=_resp(200, state)), \
         patch(f"{MOD}.requests.post", return_value=_resp(200, [{"entity_id": entity}])) as p:
        r = dispatcher.dispatch_direct("scott_home", domain, "entry_open_door")
    assert r.success and r.action == "press"
    assert p.call_args[0][0].endswith(f"/api/services/{domain}/press")


def test_precheck_network_error_falls_through_to_service_call(dispatcher):
    with patch(f"{MOD}.requests.get", side_effect=requests.exceptions.ConnectionError("down")), \
         patch(f"{MOD}.requests.post", side_effect=requests.exceptions.ConnectionError("down")):
        r = dispatcher.dispatch_direct("scott_home", "switch", "bat_sign", action="toggle")
    assert r.success is False
    assert r.code == "HA_UNREACHABLE"


def test_precheck_auth_error_lets_service_call_report(dispatcher):
    with patch(f"{MOD}.requests.get", return_value=_resp(401, text="Unauthorized")), \
         patch(f"{MOD}.requests.post", return_value=_resp(401, text="401: Unauthorized")):
        r = dispatcher.dispatch_direct("scott_home", "switch", "bat_sign", action="toggle")
    assert r.success is False
    assert r.code == "HA_ERROR"
    assert r.status_code == 401


def test_unknown_home(dispatcher):
    r = dispatcher.dispatch_direct("nope", "switch", "bat_sign")
    assert r == DispatchResult(False, "Unknown home_id: nope", code="UNKNOWN_HOME")


def test_catalog_dispatch_unchanged_apart_from_codes(dispatcher):
    """The voice/Alexa scene path does not pre-check (it is fed from a curated
    catalog) but still reports what changed."""
    dispatcher._scenes = {"night scene": __import__(MOD, fromlist=["SceneTarget"]).SceneTarget("scene", "night_mode")}
    with patch(f"{MOD}.requests.get") as g, \
         patch(f"{MOD}.requests.post", return_value=_resp(200, [{"entity_id": "light.hall"}])):
        r = dispatcher.dispatch("scott_home", "Night Scene")
    g.assert_not_called()
    assert r.success and r.changed_entities == ["light.hall"] and r.action == "turn_on"


def test_home_config_prefers_db_token_over_env(dispatcher):
    """A token renewed in the portal must be what HA reads use, not the
    stale HOME_CONFIGS_JSON entry (that left /automations on a 401 while
    dispatch worked)."""
    dispatcher.set_credentials_resolver(lambda hid: ("https://ha.example/", "fresh") if hid == "scott_home" else None)
    cfg = dispatcher.home_config("scott_home")
    assert cfg is not None and cfg.ha_token == "fresh"
    # env fallback still works for homes the DB does not know
    dispatcher._homes["legacy"] = HomeConfig("legacy", "https://old.example/", "envtok")
    assert dispatcher.home_config("legacy").ha_token == "envtok"
    assert dispatcher.home_config("nope") is None
