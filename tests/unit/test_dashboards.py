"""
Tests for the HA dashboards feature:

  - extract_entity_ids: pulls entity_ids out of arbitrary Lovelace configs
    (nested cards, sections layout, entities lists, badges).
  - HADashboardClient: WebSocket handshake, command/result matching,
    auth_invalid -> HomeUnreachableError, config_not_found ->
    DashboardNotConfiguredError, default-Overview synthesis.
  - HTTP layer: GET /dashboards and GET /dashboards/config status codes
    and payload shape.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.infrastructure.home_assistant.dashboard_client import (
    DashboardError,
    DashboardNotConfiguredError,
    DashboardNotFoundError,
    HADashboardClient,
    extract_entity_ids,
)
from app.infrastructure.home_assistant.device_registry import HomeUnreachableError
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.voice_auth_service import VoiceAuthService

HOME_CFG = json.dumps({"h1": {"ha_url": "https://ha.test", "ha_token": "tok"}})


@pytest.fixture
def dispatcher():
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}"}):
        return HADirectDispatcher.from_env()


# --- extract_entity_ids ------------------------------------------------------


class TestExtractEntityIds:
    def test_flat_card_entity(self):
        assert extract_entity_ids({"type": "light", "entity": "light.lamp"}) == ["light.lamp"]

    def test_entities_list_of_strings_and_dicts(self):
        card = {
            "type": "entities",
            "entities": [
                "switch.bat_sign",
                {"entity": "light.man_land_lamp", "name": "Lamp"},
            ],
        }
        assert extract_entity_ids(card) == ["switch.bat_sign", "light.man_land_lamp"]

    def test_nested_stack_and_sections(self):
        view = {
            "type": "sections",
            "badges": ["sensor.temp"],
            "sections": [
                {
                    "cards": [
                        {"type": "vertical-stack", "cards": [
                            {"entity": "climate.hvac"},
                            {"type": "conditional",
                             "conditions": [{"entity": "binary_sensor.motion", "state": "on"}],
                             "card": {"entity": "camera.front", "camera_image": "camera.front"}},
                        ]},
                    ]
                }
            ],
        }
        assert extract_entity_ids(view) == [
            "sensor.temp", "climate.hvac", "binary_sensor.motion", "camera.front",
        ]

    def test_dedupes_and_ignores_non_entity_strings(self):
        card = {
            "entities": ["light.a", "light.a", "not an entity", "weird..thing"],
            "title": "switch.this_is_a_title_not_ref",  # 'title' is not an entity key
        }
        assert extract_entity_ids(card) == ["light.a"]

    def test_empty(self):
        assert extract_entity_ids({}) == []
        assert extract_entity_ids(None) == []


# --- HADashboardClient (fake WebSocket) --------------------------------------


class FakeWS:
    """Scripted HA WebSocket: replays `frames` in order, records sends."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.closed = False

    def recv(self):
        return json.dumps(self.frames.pop(0))

    def send(self, data):
        self.sent.append(json.loads(data))

    def close(self):
        self.closed = True


def _client(dispatcher, frames):
    fake = FakeWS(frames)
    client = HADashboardClient(dispatcher, cache_ttl_seconds=0)
    patcher = patch(
        "app.infrastructure.home_assistant.dashboard_client.websocket.create_connection",
        return_value=fake,
    )
    return client, fake, patcher


AUTH_OK = [{"type": "auth_required"}, {"type": "auth_ok"}]


class TestDashboardClient:
    def test_list_prepends_default_overview(self, dispatcher):
        frames = AUTH_OK + [
            {"id": 1, "type": "result", "success": True,
             "result": [{"url_path": "tablet", "title": "Tablet", "mode": "storage"}]},
        ]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher:
            items = client.list_dashboards("h1")
        assert items[0]["url_path"] is None
        assert items[0]["is_default"] is True
        assert items[1]["url_path"] == "tablet"
        assert fake.sent[0] == {"type": "auth", "access_token": "tok"}
        assert fake.sent[1] == {"type": "lovelace/dashboards/list", "id": 1}
        assert fake.closed

    def test_get_config_sends_url_path_and_skips_event_frames(self, dispatcher):
        frames = AUTH_OK + [
            {"id": 99, "type": "event"},  # unrelated frame must be skipped
            {"id": 1, "type": "result", "success": True, "result": {"views": []}},
        ]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher:
            cfg = client.get_config("h1", "tablet")
        assert cfg == {"views": []}
        assert fake.sent[1] == {"type": "lovelace/config", "url_path": "tablet", "id": 1}

    def test_auth_invalid_names_the_token(self, dispatcher):
        frames = [{"type": "auth_required"}, {"type": "auth_invalid", "message": "nope"}]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher, pytest.raises(HomeUnreachableError) as exc:
            client.list_dashboards("h1")
        assert "token" in str(exc.value)

    def test_connection_error_is_home_unreachable(self, dispatcher):
        client = HADashboardClient(dispatcher, cache_ttl_seconds=0)
        with patch(
            "app.infrastructure.home_assistant.dashboard_client.websocket.create_connection",
            side_effect=OSError("boom"),
        ), pytest.raises(HomeUnreachableError):
            client.list_dashboards("h1")

    def test_config_not_found_maps_to_not_configured(self, dispatcher):
        frames = AUTH_OK + [
            {"id": 1, "type": "result", "success": False,
             "error": {"code": "config_not_found", "message": "Config not found."}},
        ]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher, pytest.raises(DashboardNotConfiguredError):
            client.get_config("h1", None)

    def test_not_found_maps_to_dashboard_not_found(self, dispatcher):
        frames = AUTH_OK + [
            {"id": 1, "type": "result", "success": False,
             "error": {"code": "not_found", "message": "Unknown dashboard"}},
        ]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher, pytest.raises(DashboardNotFoundError):
            client.get_config("h1", "nope")

    def test_unknown_home_is_unreachable(self, dispatcher):
        client = HADashboardClient(dispatcher, cache_ttl_seconds=0)
        with pytest.raises(HomeUnreachableError):
            client.list_dashboards("no_such_home")

    def test_stale_cache_served_through_outage(self, dispatcher):
        client = HADashboardClient(dispatcher, cache_ttl_seconds=0)
        good = FakeWS(AUTH_OK + [{"id": 1, "type": "result", "success": True, "result": []}])
        with patch(
            "app.infrastructure.home_assistant.dashboard_client.websocket.create_connection",
            return_value=good,
        ):
            first = client.list_dashboards("h1")
        with patch(
            "app.infrastructure.home_assistant.dashboard_client.websocket.create_connection",
            side_effect=OSError("down"),
        ):
            assert client.list_dashboards("h1") == first


# --- HTTP layer ---------------------------------------------------------------


@pytest.fixture
def http(dispatcher):
    svc = VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
    )
    dash = MagicMock(spec=HADashboardClient)
    controller = VoiceAuthController(service=svc, dispatcher=dispatcher, dashboard_client=dash)
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    return app.test_client(), dash


BASE = "/api/v1/voice-auth"
Q = "user_ref=scott_mobile&home_id=h1"


class TestDashboardEndpoints:
    def test_list_ok(self, http):
        client, dash = http
        dash.list_dashboards.return_value = [{"url_path": None, "title": "Overview"}]
        r = client.get(f"{BASE}/dashboards?{Q}")
        assert r.status_code == 200
        assert r.get_json()["count"] == 1
        dash.list_dashboards.assert_called_once_with("h1")

    def test_missing_params_400(self, http):
        client, _ = http
        r = client.get(f"{BASE}/dashboards?home_id=h1")
        assert r.status_code == 400

    def test_unknown_home_404(self, http):
        client, _ = http
        r = client.get(f"{BASE}/dashboards?user_ref=u&home_id=nope")
        assert r.status_code == 404

    def test_unreachable_503(self, http):
        client, dash = http
        dash.list_dashboards.side_effect = HomeUnreachableError("HA down")
        r = client.get(f"{BASE}/dashboards?{Q}")
        assert r.status_code == 503
        assert r.get_json()["code"] == "HOME_UNREACHABLE"

    def test_config_extracts_entities_per_view(self, http):
        client, dash = http
        dash.get_config.return_value = {
            "title": "Home",
            "views": [
                {"title": "Main", "path": "main", "cards": [
                    {"entity": "light.man_land_lamp"},
                    {"entities": ["switch.bat_sign"]},
                ]},
                {"title": "Empty", "cards": []},
            ],
        }
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 200
        body = r.get_json()
        dash.get_config.assert_called_once_with("h1", None)
        assert body["view_count"] == 2
        assert body["views"][0]["entities"] == ["light.man_land_lamp", "switch.bat_sign"]
        assert body["entities"] == ["light.man_land_lamp", "switch.bat_sign"]
        assert "config" not in body  # only with include_config=true

    def test_config_include_config_and_url_path(self, http):
        client, dash = http
        dash.get_config.return_value = {"title": "Tablet", "views": []}
        r = client.get(f"{BASE}/dashboards/config?{Q}&url_path=tablet&include_config=true")
        assert r.status_code == 200
        dash.get_config.assert_called_once_with("h1", "tablet")
        assert r.get_json()["config"] == {"title": "Tablet", "views": []}

    def test_config_not_configured_409(self, http):
        client, dash = http
        dash.get_config.side_effect = DashboardNotConfiguredError("auto-generated")
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 409
        assert r.get_json()["code"] == "DASHBOARD_NOT_CONFIGURED"

    def test_config_unknown_dashboard_404(self, http):
        client, dash = http
        dash.get_config.side_effect = DashboardNotFoundError("unknown", code="not_found")
        r = client.get(f"{BASE}/dashboards/config?{Q}&url_path=nope")
        assert r.status_code == 404
        assert r.get_json()["code"] == "DASHBOARD_NOT_FOUND"

    def test_config_other_ha_error_502(self, http):
        client, dash = http
        dash.get_config.side_effect = DashboardError("kaboom", code="unknown_error")
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 502
        assert r.get_json()["code"] == "HA_ERROR"

    def test_not_wired_503(self, dispatcher):
        svc = VoiceAuthService(
            enrollment_repo=InMemoryEnrollmentRepository(),
            log_repo=InMemoryChallengeLogRepository(),
            phone_repo=InMemoryPhoneMappingRepository(),
        )
        controller = VoiceAuthController(service=svc, dispatcher=dispatcher)
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        r = app.test_client().get(f"{BASE}/dashboards?{Q}")
        assert r.status_code == 503
        assert r.get_json()["code"] == "NOT_CONFIGURED"
