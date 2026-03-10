"""
Tests for SceneWebhookMapping repository (in-memory implementation)
"""

import pytest
from datetime import datetime
from app.domain.models import SceneWebhookMapping
from app.repositories.implementations.in_memory_scene_webhook_mapping_repo import InMemorySceneWebhookMappingRepository


@pytest.fixture
def repo():
    """Fresh in-memory repository for each test."""
    return InMemorySceneWebhookMappingRepository()


@pytest.fixture
def mapping():
    """Sample scene webhook mapping."""
    return SceneWebhookMapping(
        id="mapping_1",
        home_id="home_1",
        scene_name="decorations on",
        webhook_id="decorations_on_1751404299018",
        is_active=True,
        created_at=datetime(2026, 3, 4, 12, 0, 0)
    )


@pytest.fixture
def mapping2():
    """Second scene webhook mapping for same home."""
    return SceneWebhookMapping(
        id="mapping_2",
        home_id="home_1",
        scene_name="night scene",
        webhook_id="night_scene_123",
        is_active=True,
        created_at=datetime(2026, 3, 4, 12, 0, 0)
    )


class TestInMemorySceneWebhookMappingRepository:

    def test_add_mapping(self, repo, mapping):
        result = repo.add(mapping)
        assert result.id == "mapping_1"
        assert result.scene_name == "decorations on"
        assert result.webhook_id == "decorations_on_1751404299018"

    def test_add_duplicate_raises(self, repo, mapping):
        repo.add(mapping)
        duplicate = SceneWebhookMapping(
            id="mapping_dup",
            home_id="home_1",
            scene_name="decorations on",
            webhook_id="different_webhook",
            created_at=datetime.now()
        )
        with pytest.raises(ValueError, match="already mapped"):
            repo.add(duplicate)

    def test_get_by_id(self, repo, mapping):
        repo.add(mapping)
        result = repo.get_by_id("mapping_1")
        assert result is not None
        assert result.scene_name == "decorations on"

    def test_get_by_id_not_found(self, repo):
        result = repo.get_by_id("nonexistent")
        assert result is None

    def test_get_by_home_and_scene(self, repo, mapping):
        repo.add(mapping)
        result = repo.get_by_home_and_scene("home_1", "decorations on")
        assert result is not None
        assert result.webhook_id == "decorations_on_1751404299018"

    def test_get_by_home_and_scene_not_found(self, repo, mapping):
        repo.add(mapping)
        result = repo.get_by_home_and_scene("home_1", "nonexistent scene")
        assert result is None

    def test_get_by_home_and_scene_inactive(self, repo):
        inactive = SceneWebhookMapping(
            id="inactive_1",
            home_id="home_1",
            scene_name="old scene",
            webhook_id="old_webhook",
            is_active=False,
            created_at=datetime.now()
        )
        repo.add(inactive)
        result = repo.get_by_home_and_scene("home_1", "old scene")
        assert result is None

    def test_list_by_home(self, repo, mapping, mapping2):
        repo.add(mapping)
        repo.add(mapping2)
        results = repo.list_by_home("home_1")
        assert len(results) == 2
        # Should be sorted by scene_name
        assert results[0].scene_name == "decorations on"
        assert results[1].scene_name == "night scene"

    def test_list_by_home_active_only(self, repo, mapping):
        repo.add(mapping)
        inactive = SceneWebhookMapping(
            id="inactive_2",
            home_id="home_1",
            scene_name="inactive scene",
            webhook_id="inactive_webhook",
            is_active=False,
            created_at=datetime.now()
        )
        repo.add(inactive)
        results = repo.list_by_home("home_1", active_only=True)
        assert len(results) == 1
        assert results[0].scene_name == "decorations on"

    def test_list_all(self, repo, mapping, mapping2):
        repo.add(mapping)
        repo.add(mapping2)
        results = repo.list_all()
        assert len(results) == 2

    def test_update(self, repo, mapping):
        repo.add(mapping)
        updated = SceneWebhookMapping(
            id="mapping_1",
            home_id="home_1",
            scene_name="decorations on",
            webhook_id="new_webhook_id",
            is_active=True,
            created_at=mapping.created_at
        )
        result = repo.update(updated)
        assert result.webhook_id == "new_webhook_id"
        assert result.updated_at is not None

    def test_update_not_found(self, repo):
        nonexistent = SceneWebhookMapping(
            id="nonexistent",
            home_id="home_1",
            scene_name="test",
            webhook_id="test",
            created_at=datetime.now()
        )
        with pytest.raises(ValueError, match="not found"):
            repo.update(nonexistent)

    def test_delete(self, repo, mapping):
        repo.add(mapping)
        result = repo.delete("mapping_1")
        assert result is True
        assert repo.get_by_id("mapping_1") is None

    def test_delete_not_found(self, repo):
        result = repo.delete("nonexistent")
        assert result is False

    def test_exists(self, repo, mapping):
        repo.add(mapping)
        assert repo.exists("mapping_1") is True
        assert repo.exists("nonexistent") is False
