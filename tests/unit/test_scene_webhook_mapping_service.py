"""
Tests for SceneWebhookMappingService
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from app.domain.models import SceneWebhookMapping, Home
from app.services.scene_webhook_mapping_service import SceneWebhookMappingService
from app.repositories.implementations.in_memory_scene_webhook_mapping_repo import InMemorySceneWebhookMappingRepository
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository


@pytest.fixture
def home_repo():
    """Home repository with a sample home."""
    repo = InMemoryHomeRepository()
    repo.add(Home(
        home_id="home_1",
        user_id="user_1",
        name="Test Home",
        ha_url="https://ha.test.com",
        ha_webhook_id="default_webhook",
        created_at=datetime(2026, 1, 1)
    ))
    return repo


@pytest.fixture
def mapping_repo():
    """Fresh scene webhook mapping repository."""
    return InMemorySceneWebhookMappingRepository()


@pytest.fixture
def service(mapping_repo, home_repo):
    """Service with real in-memory repos."""
    return SceneWebhookMappingService(
        mapping_repository=mapping_repo,
        home_repository=home_repo
    )


class TestSceneWebhookMappingService:

    def test_create_mapping(self, service):
        result = service.create_mapping(
            home_id="home_1",
            scene_name="Decorations On",
            webhook_id="decorations_on_123"
        )
        assert result.home_id == "home_1"
        assert result.scene_name == "decorations on"  # normalized to lowercase
        assert result.webhook_id == "decorations_on_123"
        assert result.is_active is True

    def test_create_mapping_home_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.create_mapping(
                home_id="nonexistent",
                scene_name="test",
                webhook_id="test_webhook"
            )

    def test_create_mapping_duplicate(self, service):
        service.create_mapping("home_1", "decorations on", "webhook_1")
        with pytest.raises(ValueError, match="already mapped"):
            service.create_mapping("home_1", "decorations on", "webhook_2")

    def test_get_webhook_for_scene(self, service):
        service.create_mapping("home_1", "decorations on", "decorations_on_123")
        result = service.get_webhook_for_scene("home_1", "decorations on")
        assert result == "decorations_on_123"

    def test_get_webhook_for_scene_case_insensitive(self, service):
        service.create_mapping("home_1", "decorations on", "decorations_on_123")
        result = service.get_webhook_for_scene("home_1", "Decorations On")
        assert result == "decorations_on_123"

    def test_get_webhook_for_scene_not_found(self, service):
        result = service.get_webhook_for_scene("home_1", "nonexistent")
        assert result is None

    def test_list_scenes_for_home(self, service):
        service.create_mapping("home_1", "decorations on", "webhook_1")
        service.create_mapping("home_1", "night scene", "webhook_2")
        results = service.list_scenes_for_home("home_1")
        assert len(results) == 2

    def test_list_all(self, service):
        service.create_mapping("home_1", "decorations on", "webhook_1")
        results = service.list_all()
        assert len(results) == 1

    def test_update_mapping(self, service):
        created = service.create_mapping("home_1", "decorations on", "webhook_1")
        result = service.update_mapping(
            mapping_id=created.id,
            webhook_id="new_webhook_id"
        )
        assert result.webhook_id == "new_webhook_id"

    def test_update_mapping_not_found(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.update_mapping("nonexistent", webhook_id="test")

    def test_delete_mapping(self, service):
        created = service.create_mapping("home_1", "decorations on", "webhook_1")
        result = service.delete_mapping(created.id)
        assert result is True
        assert service.get_webhook_for_scene("home_1", "decorations on") is None

    def test_delete_mapping_not_found(self, service):
        result = service.delete_mapping("nonexistent")
        assert result is False
