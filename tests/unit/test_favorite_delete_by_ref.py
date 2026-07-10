"""
Tests for one-step favorite deletion: DELETE /favorites/{ref} accepts the
favorite's id (original behavior) OR its device_id / entity_id scoped by
(user_ref, home_id) — from query params or the login token.
"""

import json
import os
from unittest.mock import patch

import pytest
from flask import Flask

from app.controllers.voice_auth_controller import VoiceAuthController
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher
from app.middleware.voice_auth_api_key import attach_mobile_api_key_auth
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
BASE = "/api/v1/voice-auth"


def _build_client(with_jwt_middleware=False):
    with patch.dict(os.environ, {"HOME_CONFIGS_JSON": HOME_CFG, "SCENE_CATALOG_JSON": "{}",
                                  "MOBILE_API_KEYS_JSON": ""}):
        dispatcher = HADirectDispatcher.from_env()
        favorites = FavoriteDeviceService(
            favorite_repository=InMemoryFavoriteDeviceRepository(),
            home_validator=dispatcher.has_home,
        )
        controller = VoiceAuthController(
            service=VoiceAuthService(
                enrollment_repo=InMemoryEnrollmentRepository(),
                log_repo=InMemoryChallengeLogRepository(),
                phone_repo=InMemoryPhoneMappingRepository(),
            ),
            dispatcher=dispatcher,
            favorite_service=favorites,
        )
        if with_jwt_middleware:
            # middleware only attempts JWT verification for xx.yy.zz-shaped bearers
            attach_mobile_api_key_auth(
                controller.blueprint,
                token_verifier=lambda t: "u1" if t == "valid.jwt.token" else None,
            )
        app = Flask(__name__)
        app.register_blueprint(controller.blueprint)
        return app.test_client()


@pytest.fixture
def client():
    return _build_client()


def _add(client, entity="scene.movie", user="u1", **extra):
    rv = client.post(f"{BASE}/favorites",
                     json={"user_ref": user, "home_id": "h1",
                           "entity_id": entity, **extra})
    assert rv.status_code == 201
    return rv.get_json()


class TestDeleteByRef:
    def test_delete_by_favorite_id_still_works(self, client):
        fav = _add(client)
        assert client.delete(f"{BASE}/favorites/{fav['id']}").status_code == 204

    def test_delete_by_entity_id_one_step(self, client):
        _add(client, entity="scene.movie")
        rv = client.delete(f"{BASE}/favorites/scene.movie?user_ref=u1&home_id=h1")
        assert rv.status_code == 204
        rv = client.get(f"{BASE}/favorites?user_ref=u1&home_id=h1")
        assert rv.get_json()["count"] == 0

    def test_delete_by_ref_without_scope_404_with_hint(self, client):
        _add(client, entity="scene.movie")
        rv = client.delete(f"{BASE}/favorites/scene.movie")
        assert rv.status_code == 404
        assert "user_ref" in rv.get_json()["error"]  # tells caller how to fix it

    def test_delete_by_ref_wrong_user_404(self, client):
        _add(client, entity="scene.movie", user="u1")
        rv = client.delete(f"{BASE}/favorites/scene.movie?user_ref=other&home_id=h1")
        assert rv.status_code == 404
        # u1's favorite untouched
        rv = client.get(f"{BASE}/favorites?user_ref=u1&home_id=h1")
        assert rv.get_json()["count"] == 1

    def test_delete_scoped_by_login_token(self):
        client = _build_client(with_jwt_middleware=True)
        hdr = {"Authorization": "Bearer valid.jwt.token"}  # token -> user u1
        rv = client.post(f"{BASE}/favorites", headers=hdr,
                         json={"user_ref": "u1", "home_id": "h1",
                               "entity_id": "scene.movie"})
        assert rv.status_code == 201
        # no user_ref query param needed — inferred from the token
        rv = client.delete(f"{BASE}/favorites/scene.movie?home_id=h1", headers=hdr)
        assert rv.status_code == 204

    def test_unknown_ref_scoped_404(self, client):
        rv = client.delete(f"{BASE}/favorites/nothing-here?user_ref=u1&home_id=h1")
        assert rv.status_code == 404
