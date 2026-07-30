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

    def test_registry_and_icons_share_one_connection(self, dispatcher):
        """Both commands go out before either reply is read — connecting and
        authenticating costs more than the commands themselves."""
        frames = AUTH_OK + [
            {"id": 2, "type": "result", "success": True,
             "result": {"resources": {"tplink": {"sensor": {"signal_level": {"default": "mdi:signal"}}}}}},
            {"id": 1, "type": "result", "success": True, "result": [
                {"entity_id": "sensor.deck_light_signal_level", "platform": "tplink",
                 "translation_key": "signal_level", "entity_category": "diagnostic",
                 "options": {"ignored": "bulk"}},
                {"entity_id": None},  # rows without an entity_id are skipped
            ]},
        ]
        client, fake, patcher = _client(dispatcher, frames)
        with patcher:
            registry, resources = client.get_entity_registry_and_icons("h1")
        assert fake.sent[1]["type"] == "config/entity_registry/list"
        assert fake.sent[2]["type"] == "frontend/get_icons"
        assert list(resources) == ["tplink"]
        assert list(registry) == ["sensor.deck_light_signal_level"]
        # Fat fields are dropped before caching
        assert "options" not in registry["sensor.deck_light_signal_level"]
        assert registry["sensor.deck_light_signal_level"]["translation_key"] == "signal_level"

    def test_out_of_order_replies_are_matched_by_id(self, dispatcher):
        """Reply order is not command order; results must still line up."""
        frames = AUTH_OK + [
            {"id": 2, "type": "result", "success": True, "result": {"resources": {}}},
            {"id": 99, "type": "event"},  # unrelated frame in the middle
            {"id": 1, "type": "result", "success": True, "result": []},
        ]
        client, _, patcher = _client(dispatcher, frames)
        with patcher:
            registry, resources = client.get_entity_registry_and_icons("h1")
        assert registry == {} and resources == {}

    def test_registry_uses_the_static_ttl_not_the_dashboard_ttl(self, dispatcher):
        """Dashboards refresh every 30s; the registry must not re-fetch with them."""
        client = HADashboardClient(dispatcher, cache_ttl_seconds=0, static_cache_ttl_seconds=600)
        frames = AUTH_OK + [
            {"id": 1, "type": "result", "success": True, "result": []},
            {"id": 2, "type": "result", "success": True, "result": {"resources": {}}},
        ]
        fake = FakeWS(frames)
        with patch(
            "app.infrastructure.home_assistant.dashboard_client.websocket.create_connection",
            return_value=fake,
        ):
            client.get_entity_registry_and_icons("h1")
            # A second call with no frames left would raise IndexError if it refetched
            assert client.get_entity_registry_and_icons("h1") == ({}, {})


# --- HTTP layer ---------------------------------------------------------------


def _device(area, entities):
    d = MagicMock()
    d.area = area
    d.all_entities = entities
    return d


def _build_http(dispatcher, entity_metadata=None):
    svc = VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
    )
    dash = MagicMock(spec=HADashboardClient)
    registry = MagicMock()
    registry.list_devices.return_value = []
    controller = VoiceAuthController(
        service=svc,
        dispatcher=dispatcher,
        dashboard_client=dash,
        device_registry=registry,
        entity_metadata=entity_metadata,
    )
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    return app.test_client(), dash, registry


@pytest.fixture
def http(dispatcher):
    """No entity_metadata wired — the pre-metadata behavior, still supported."""
    return _build_http(dispatcher)


BASE = "/api/v1/voice-auth"
Q = "user_ref=scott_mobile&home_id=h1"


class TestDashboardEndpoints:
    def test_list_ok(self, http):
        client, dash, _ = http
        dash.list_dashboards.return_value = [{"url_path": None, "title": "Overview"}]
        r = client.get(f"{BASE}/dashboards?{Q}")
        assert r.status_code == 200
        assert r.get_json()["count"] == 1
        dash.list_dashboards.assert_called_once_with("h1")

    def test_missing_params_400(self, http):
        client, _, _ = http
        r = client.get(f"{BASE}/dashboards?home_id=h1")
        assert r.status_code == 400

    def test_unknown_home_404(self, http):
        client, _, _ = http
        r = client.get(f"{BASE}/dashboards?user_ref=u&home_id=nope")
        assert r.status_code == 404

    def test_unreachable_503(self, http):
        client, dash, _ = http
        dash.list_dashboards.side_effect = HomeUnreachableError("HA down")
        r = client.get(f"{BASE}/dashboards?{Q}")
        assert r.status_code == 503
        assert r.get_json()["code"] == "HOME_UNREACHABLE"

    def test_config_extracts_entities_per_view(self, http):
        client, dash, _ = http
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
        client, dash, _ = http
        dash.get_config.return_value = {"title": "Tablet", "views": []}
        r = client.get(f"{BASE}/dashboards/config?{Q}&url_path=tablet&include_config=true")
        assert r.status_code == 200
        dash.get_config.assert_called_once_with("h1", "tablet")
        assert r.get_json()["config"] == {"title": "Tablet", "views": []}

    def test_config_not_configured_409(self, http):
        client, dash, _ = http
        dash.get_config.side_effect = DashboardNotConfiguredError("auto-generated")
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 409
        assert r.get_json()["code"] == "DASHBOARD_NOT_CONFIGURED"

    def test_config_unknown_dashboard_404(self, http):
        client, dash, _ = http
        dash.get_config.side_effect = DashboardNotFoundError("unknown", code="not_found")
        r = client.get(f"{BASE}/dashboards/config?{Q}&url_path=nope")
        assert r.status_code == 404
        assert r.get_json()["code"] == "DASHBOARD_NOT_FOUND"

    def test_config_other_ha_error_502(self, http):
        client, dash, _ = http
        dash.get_config.side_effect = DashboardError("kaboom", code="unknown_error")
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 502
        assert r.get_json()["code"] == "HA_ERROR"

    def test_strategy_dashboard_expands_to_area_views(self, http):
        client, dash, registry = http
        dash.get_config.return_value = {
            "strategy": {
                "type": "original-states",
                "hide_entities_without_area": True,
                "areas": {"hidden": ["bat_cave"], "order": ["office_at_qli"]},
            }
        }
        registry.list_devices.return_value = [
            _device("Bat Cave", ["light.bat_lamp"]),          # hidden -> dropped
            _device("Living Room", ["light.sofa", "sensor.temp"]),
            _device("Office at QLI", ["switch.bat_sign"]),    # ordered first
            _device(None, ["scene.orphan"]),                  # no area -> dropped
            _device("Living Room", ["light.sofa"]),           # duplicate entity deduped
        ]
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["strategy"] == "original-states"
        assert [v["title"] for v in body["views"]] == ["Office at QLI", "Living Room"]
        assert body["views"][0]["entities"] == ["switch.bat_sign"]
        assert body["views"][1]["entities"] == ["light.sofa", "sensor.temp"]
        assert body["entities"] == ["switch.bat_sign", "light.sofa", "sensor.temp"]

    def test_strategy_dashboard_unreachable_registry_503(self, http):
        client, dash, registry = http
        dash.get_config.return_value = {"strategy": {"type": "original-states"}}
        registry.list_devices.side_effect = HomeUnreachableError("HA down")
        r = client.get(f"{BASE}/dashboards/config?{Q}")
        assert r.status_code == 503
        assert r.get_json()["code"] == "HOME_UNREACHABLE"

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


# --- entity_meta and the tile filters -----------------------------------------


META_ROWS = {
    "switch.deck_light": {
        "name": "Deck light", "domain": "switch", "icon": "mdi:toggle-switch",
        "icon_source": "domain", "device_class": None, "unit_of_measurement": None,
        "entity_category": None, "hidden": False, "state": "off", "controllable": True,
    },
    "sensor.deck_light_signal_level": {
        "name": "Deck light Signal level", "domain": "sensor", "icon": "mdi:signal",
        "icon_source": "translation", "device_class": None, "unit_of_measurement": None,
        "entity_category": "diagnostic", "hidden": False, "state": "2", "controllable": False,
    },
    "number.deck_light_turn_off_in": {
        "name": "Deck light Turn off in", "domain": "number", "icon": "mdi:sleep",
        "icon_source": "translation", "device_class": None, "unit_of_measurement": None,
        "entity_category": "config", "hidden": False, "state": "0", "controllable": False,
    },
    "switch.hidden_thing": {
        "name": "Hidden", "domain": "switch", "icon": "mdi:toggle-switch",
        "icon_source": "domain", "device_class": None, "unit_of_measurement": None,
        "entity_category": None, "hidden": True, "state": "on", "controllable": True,
    },
}

ALL_FOUR = list(META_ROWS)


@pytest.fixture
def http_meta(dispatcher):
    meta = MagicMock()
    meta.get.side_effect = lambda home_id, entity_ids: {
        e: META_ROWS[e] for e in entity_ids if e in META_ROWS
    }
    client, dash, registry = _build_http(dispatcher, entity_metadata=meta)
    dash.get_config.return_value = {
        "title": "Deck",
        "views": [{"title": "Deck", "path": "deck",
                   "cards": [{"entities": ALL_FOUR}]}],
    }
    return client, dash, meta


class TestEntityMeta:
    def test_meta_is_returned_per_entity(self, http_meta):
        client, _, _ = http_meta
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert body["entity_meta_available"] is True
        assert body["entity_meta"]["sensor.deck_light_signal_level"]["icon"] == "mdi:signal"
        assert body["entity_meta"]["switch.deck_light"]["controllable"] is True
        # No filter requested -> nothing dropped (back-compat)
        assert body["entities"] == ALL_FOUR
        assert body["entity_count"] == 4

    def test_primary_filter_drops_config_and_diagnostic(self, http_meta):
        client, _, _ = http_meta
        body = client.get(
            f"{BASE}/dashboards/config?{Q}&include_categories=primary"
        ).get_json()
        assert body["entities"] == ["switch.deck_light", "switch.hidden_thing"]
        assert body["entity_count"] == 2
        assert body["views"][0]["entity_count"] == 2
        assert set(body["entity_meta"]) == {"switch.deck_light", "switch.hidden_thing"}

    def test_include_hidden_false(self, http_meta):
        client, _, _ = http_meta
        body = client.get(
            f"{BASE}/dashboards/config?{Q}&include_categories=primary&include_hidden=false"
        ).get_json()
        assert body["entities"] == ["switch.deck_light"]

    def test_multiple_categories(self, http_meta):
        client, _, _ = http_meta
        body = client.get(
            f"{BASE}/dashboards/config?{Q}&include_categories=primary,diagnostic"
        ).get_json()
        assert "sensor.deck_light_signal_level" in body["entities"]
        assert "number.deck_light_turn_off_in" not in body["entities"]

    def test_bad_category_is_a_400_not_a_silent_no_op(self, http_meta):
        client, _, _ = http_meta
        r = client.get(f"{BASE}/dashboards/config?{Q}&include_categories=primary,bogus")
        assert r.status_code == 400
        assert r.get_json()["code"] == "VALIDATION"
        assert "bogus" in r.get_json()["error"]

    def test_metadata_failure_degrades_instead_of_503(self, http_meta):
        """A board with fallback icons beats no board."""
        client, _, meta = http_meta
        meta.get.side_effect = HomeUnreachableError("HA down")
        r = client.get(f"{BASE}/dashboards/config?{Q}&include_categories=primary")
        assert r.status_code == 200
        body = r.get_json()
        assert body["entity_meta_available"] is False
        assert body["entity_meta"] == {}
        # The filter could not be applied, and the response says so rather
        # than pretending these four entities are all primary.
        assert body["entities"] == ALL_FOUR

    def test_absent_metadata_service_reports_unavailable(self, http):
        client, dash, _ = http
        dash.get_config.return_value = {
            "views": [{"title": "V", "cards": [{"entity": "light.a"}]}]
        }
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert body["entity_meta_available"] is False
        assert body["entity_meta"] == {}

    def test_entities_without_metadata_are_kept(self, http_meta):
        """A card referencing an entity HA does not know must not lose its tile."""
        client, dash, _ = http_meta
        dash.get_config.return_value = {
            "views": [{"title": "V", "cards": [{"entities": ["light.ghost", "switch.deck_light"]}]}]
        }
        body = client.get(
            f"{BASE}/dashboards/config?{Q}&include_categories=primary"
        ).get_json()
        assert body["entities"] == ["light.ghost", "switch.deck_light"]


# --- voice_gated: the app must never have to probe for a 409 ------------------


@pytest.fixture
def http_gated(dispatcher):
    """Real VoiceAuthService so the advertised flag and the fire path share
    one source of truth — a mock here would let them drift silently."""
    from app.domain.voice_auth_enums import ChallengeType, EnrollmentStatus

    svc = VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
    )
    lock = svc.create_enrollment(
        user_ref="scott_mobile", home_id="h1", automation_id="yale_yrd226_tsdb",
        automation_name="Yale Lock", ha_service="lock", ha_entity="yale_yrd226_tsdb",
        challenge_type=ChallengeType.STEP_UP,
    )
    paused = svc.create_enrollment(
        user_ref="scott_mobile", home_id="h1", automation_id="main_lights_on",
        automation_name="Main Lights On", ha_service="script", ha_entity="main_lights_on",
        challenge_type=ChallengeType.VERIFICATION,
    )
    svc.update_status(paused.id, EnrollmentStatus.PAUSED)

    meta = MagicMock()
    meta.get.side_effect = lambda home_id, entity_ids: {
        e: {"name": e, "domain": e.split(".")[0], "icon": "mdi:x", "icon_source": "domain",
            "device_class": None, "unit_of_measurement": None, "entity_category": None,
            "hidden": False, "state": "off", "controllable": True}
        for e in entity_ids
    }
    dash = MagicMock(spec=HADashboardClient)
    registry = MagicMock()
    registry.list_devices.return_value = []
    controller = VoiceAuthController(
        service=svc, dispatcher=dispatcher, dashboard_client=dash,
        device_registry=registry, entity_metadata=meta,
    )
    app = Flask(__name__)
    app.register_blueprint(controller.blueprint)
    dash.get_config.return_value = {"views": [{"title": "V", "cards": [{"entities": [
        "lock.yale_yrd226_tsdb",     # ACTIVE enrollment -> gated
        "script.main_lights_on",     # PAUSED enrollment -> NOT gated
        "light.den_lamp",            # no enrollment    -> not gated
        "scene.yale_yrd226_tsdb",    # same suffix, different domain -> gated
    ]}]}]}
    return app.test_client(), controller, lock

class TestBoardTilesAreButtonClicks:
    """A board tile is a button: tapping anything the board returns must fire
    the device, never answer 409. Gated entities are withheld rather than
    badged, and the gate itself is left alone — the lock still needs the
    spoken challenge wherever it IS offered (favorites)."""

    def test_gated_entity_is_not_a_tile(self, http_gated):
        client, _, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert "lock.yale_yrd226_tsdb" not in body["entities"]
        assert "lock.yale_yrd226_tsdb" not in body["entity_meta"]

    def test_withheld_entities_are_reported_not_silently_dropped(self, http_gated):
        client, _, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert sorted(body["gated_excluded"]) == [
            "lock.yale_yrd226_tsdb", "scene.yale_yrd226_tsdb",
        ]
        assert body["gate_check_available"] is True

    def test_every_returned_tile_is_ungated(self, http_gated):
        """The guarantee Aaron builds on."""
        client, controller, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert body["entities"], "sanity: the board is not empty"
        for entity_id in body["entities"]:
            gated, _ = controller._is_voice_gated("scott_mobile", entity_id)
            assert gated is False, entity_id
            assert body["entity_meta"][entity_id]["voice_gated"] is False

    def test_paused_enrollment_still_yields_a_tile(self, http_gated):
        """PAUSED does not gate, so the tile must stay on the board."""
        client, _, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert "script.main_lights_on" in body["entities"]

    def test_view_counts_reflect_the_withheld_tile(self, http_gated):
        client, _, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        view = body["views"][0]
        assert view["entity_count"] == len(view["entities"])
        assert "lock.yale_yrd226_tsdb" not in view["entities"]

    def test_include_gated_puts_them_back_marked(self, http_gated):
        client, _, lock = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}&include_gated=true").get_json()
        meta = body["entity_meta"]
        assert meta["lock.yale_yrd226_tsdb"]["voice_gated"] is True
        assert meta["lock.yale_yrd226_tsdb"]["voice_auth_enrollment_id"] == lock.id
        assert body["gated_excluded"] == []

    def test_gate_keys_on_suffix_exactly_like_the_fire_path(self, http_gated):
        """Same suffix, different domain — the fire path gates it, so the
        board must withhold it too or the tile would 409."""
        client, controller, _ = http_gated
        body = client.get(f"{BASE}/dashboards/config?{Q}&include_gated=true").get_json()
        assert body["entity_meta"]["scene.yale_yrd226_tsdb"]["voice_gated"] is True
        assert controller._is_voice_gated("scott_mobile", "scene.yale_yrd226_tsdb")[0] is True

    def test_flag_agrees_with_the_endpoint_that_returns_409(self, http_gated):
        """The invariant: what the board says matches what the fire path does."""
        client, controller, _ = http_gated
        meta = client.get(
            f"{BASE}/dashboards/config?{Q}&include_gated=true"
        ).get_json()["entity_meta"]
        for entity_id, row in meta.items():
            gated_per_fire_path, _ = controller._is_voice_gated("scott_mobile", entity_id)
            assert row["voice_gated"] == gated_per_fire_path, entity_id

    def test_gate_lookup_failure_is_declared_not_hidden(self, http_gated):
        """If we cannot tell what is gated we must not claim the board is
        safe to render as plain buttons — the 409 handler is still needed."""
        client, controller, _ = http_gated
        with patch.object(controller._svc, "active_gate_map", side_effect=RuntimeError("db down")):
            body = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        assert body["gate_check_available"] is False
        assert "lock.yale_yrd226_tsdb" in body["entities"]  # could not be withheld


# --- GET /voice-gated ---------------------------------------------------------


class TestVoiceGatedEndpoint:
    """One read-only call that answers "which entities 409?" — the
    alternative to firing commands and watching for the status code."""

    def test_lists_every_gated_entity_id(self, http_gated):
        client, _, lock = http_gated
        body = client.get(f"{BASE}/voice-gated?user_ref=scott_mobile").get_json()
        assert body["count"] == 1
        row = body["items"][0]
        assert row["entity_id"] == "lock.yale_yrd226_tsdb"
        assert row["automation_id"] == "yale_yrd226_tsdb"
        assert row["enrollment_id"] == lock.id
        assert row["challenge_type"] == "STEP_UP"

    def test_paused_enrollments_are_excluded(self, http_gated):
        """PAUSED does not 409, so listing it would send users to a voice
        session for a device that would have just worked."""
        client, _, _ = http_gated
        body = client.get(f"{BASE}/voice-gated?user_ref=scott_mobile").get_json()
        assert "script.main_lights_on" not in [i["entity_id"] for i in body["items"]]

    def test_matches_the_fire_path_for_every_row(self, http_gated):
        client, controller, _ = http_gated
        body = client.get(f"{BASE}/voice-gated?user_ref=scott_mobile").get_json()
        for row in body["items"]:
            assert controller._is_voice_gated("scott_mobile", row["entity_id"])[0] is True

    def test_scoped_to_a_home(self, http_gated):
        client, _, _ = http_gated
        assert client.get(
            f"{BASE}/voice-gated?user_ref=scott_mobile&home_id=h1"
        ).get_json()["count"] == 1
        assert client.get(
            f"{BASE}/voice-gated?user_ref=scott_mobile&home_id=other"
        ).get_json()["count"] == 0

    def test_unknown_user_is_empty_not_an_error(self, http_gated):
        client, _, _ = http_gated
        r = client.get(f"{BASE}/voice-gated?user_ref=nobody")
        assert r.status_code == 200
        assert r.get_json()["items"] == []

    def test_user_ref_required(self, http_gated):
        client, _, _ = http_gated
        r = client.get(f"{BASE}/voice-gated")
        assert r.status_code == 400
        assert r.get_json()["code"] == "VALIDATION"

    def test_the_board_and_this_endpoint_agree(self, http_gated):
        """gated_excluded on a board ⊆ what /voice-gated lists."""
        client, _, _ = http_gated
        board = client.get(f"{BASE}/dashboards/config?{Q}").get_json()
        gated = client.get(f"{BASE}/voice-gated?user_ref=scott_mobile").get_json()
        suffixes = {i["automation_id"] for i in gated["items"]}
        for entity_id in board["gated_excluded"]:
            assert entity_id.split(".", 1)[1] in suffixes
