"""
Tests for HomeUnreachableError: when a home's Home Assistant is down or
rejecting our token, the API must say so (503 HOME_UNREACHABLE) instead of
the misleading 400 "device not found" — and entity favorites must keep
working (degraded, without device enrichment).

Covers registry, service, and HTTP layers.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests as real_requests
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.infrastructure.home_assistant.device_registry import (
    HADeviceRegistry,
    HomeUnreachableError,
)
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

HOME_CFG = json.dumps({"h1": {"ha_url": "https://ha.test", "ha_token": "tok"}})


def _resp(status, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else []
    r.text = json.dumps(body) if body is not None else "[]"
    return r


@pytest.fixture
def registry():
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}"}):
        dispatcher = HADirectDispatcher.from_env()
    return HADeviceRegistry(dispatcher, cache_ttl_seconds=0)


# --- Registry layer ---

class TestRegistry:
    def test_network_error_raises(self, registry):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   side_effect=real_requests.exceptions.ConnectionError("boom")):
            with pytest.raises(HomeUnreachableError):
                registry.list_devices("h1")

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_rejection_names_the_token(self, registry, status):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(status)):
            with pytest.raises(HomeUnreachableError) as exc:
                registry.list_devices("h1")
        assert "token" in str(exc.value)
        assert str(status) in str(exc.value)

    def test_server_error_raises(self, registry):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(502)):
            with pytest.raises(HomeUnreachableError):
                registry.list_devices("h1")

    def test_template_failure_raises(self, registry):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(200, [{"entity_id": "switch.a"}])), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   return_value=_resp(500)):
            with pytest.raises(HomeUnreachableError):
                registry.list_devices("h1")

    def test_healthy_fetch_then_stale_cache_on_outage(self):
        with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}"}):
            dispatcher = HADirectDispatcher.from_env()
        reg = HADeviceRegistry(dispatcher, cache_ttl_seconds=0)  # ttl 0 = always refetch

        states = _resp(200, [{"entity_id": "switch.a"}])
        ent_map = _resp(200, {"switch.a": "dev1"})
        attrs = _resp(200, {"dev1": ["Device A", "Acme", "M1", "Cave"]})
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=states), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ent_map, attrs]):
            devices = reg.list_devices("h1")
        assert len(devices) == 1 and devices[0].device_id == "dev1"

        # HA now down: stale cache is served instead of raising
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(401)):
            devices2 = reg.list_devices("h1")
        assert [d.device_id for d in devices2] == ["dev1"]

    def test_get_device_propagates(self, registry):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(401)):
            with pytest.raises(HomeUnreachableError):
                registry.get_device("h1", "whatever")

    def test_device_id_for_entity_degrades_to_none(self, registry):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(401)):
            assert registry.device_id_for_entity("h1", "switch.a") is None


# --- Service layer ---

class TestService:
    @pytest.fixture
    def svc(self, registry):
        return FavoriteDeviceService(
            favorite_repository=InMemoryFavoriteDeviceRepository(),
            home_validator=lambda h: h == "h1",
            device_registry=registry,
        )

    def test_device_favorite_raises_when_ha_down(self, svc):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(401)):
            with pytest.raises(HomeUnreachableError):
                svc.add_favorite(user_ref="u", home_id="h1", device_id="dev1")

    def test_entity_favorite_still_works_when_ha_down(self, svc):
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=_resp(401)):
            result = svc.add_favorite(user_ref="u", home_id="h1",
                                      entity_id="scene.movie_night")
        assert result.favorite.entity_id == "scene.movie_night"
        assert result.favorite.device_id is None  # enrichment degraded


# --- HTTP layer ---

@pytest.fixture
def client(registry):
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}",
                                  "MOBILE_API_KEYS_JSON": ""}):
        dispatcher = HADirectDispatcher.from_env()
        favorites = FavoriteDeviceService(
            favorite_repository=InMemoryFavoriteDeviceRepository(),
            home_validator=dispatcher.has_home,
            device_registry=registry,
        )
        controller = VoiceAuthController(
            service=VoiceAuthService(
                enrollment_repo=InMemoryEnrollmentRepository(),
                log_repo=InMemoryChallengeLogRepository(),
                phone_repo=InMemoryPhoneMappingRepository(),
            ),
            dispatcher=dispatcher,
            favorite_service=favorites,
            device_registry=registry,
        )
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        return app.test_client()


class TestHttp:
    def _down(self):
        return patch("app.infrastructure.home_assistant.device_registry.requests.get",
                     return_value=_resp(401))

    def test_create_favorite_by_device_503(self, client):
        with self._down():
            rv = client.post("/api/v1/voice-auth/favorites",
                             json={"user_ref": "u", "home_id": "h1", "device_id": "dev1"})
        assert rv.status_code == 503
        body = rv.get_json()
        assert body["code"] == "HOME_UNREACHABLE"
        assert "token" in body["error"]

    def test_create_favorite_by_entity_still_201(self, client):
        with self._down():
            rv = client.post("/api/v1/voice-auth/favorites",
                             json={"user_ref": "u", "home_id": "h1",
                                   "entity_id": "scene.movie_night"})
        assert rv.status_code == 201

    def test_devices_discover_503(self, client):
        with self._down():
            rv = client.get("/api/v1/voice-auth/devices/discover?home_id=h1")
        assert rv.status_code == 503
        assert rv.get_json()["code"] == "HOME_UNREACHABLE"

    def test_items_search_503(self, client):
        with self._down():
            rv = client.get("/api/v1/voice-auth/items/search?home_id=h1&q=x")
        assert rv.status_code == 503
        assert rv.get_json()["code"] == "HOME_UNREACHABLE"

    def test_unknown_home_still_400_not_503(self, client):
        with self._down():
            rv = client.post("/api/v1/voice-auth/favorites",
                             json={"user_ref": "u", "home_id": "nope", "device_id": "d"})
        assert rv.status_code == 400  # home validation fires before registry

    def test_genuinely_missing_device_still_400(self, client):
        states = _resp(200, [{"entity_id": "switch.a"}])
        ent_map = _resp(200, {"switch.a": "dev1"})
        attrs = _resp(200, {"dev1": ["Device A", "", "", ""]})
        with patch("app.infrastructure.home_assistant.device_registry.requests.get",
                   return_value=states), \
             patch("app.infrastructure.home_assistant.device_registry.requests.post",
                   side_effect=[ent_map, attrs, ent_map, attrs]):
            rv = client.post("/api/v1/voice-auth/favorites",
                             json={"user_ref": "u", "home_id": "h1",
                                   "device_id": "not_a_real_device"})
        assert rv.status_code == 400
        assert "not found" in rv.get_json()["error"]
