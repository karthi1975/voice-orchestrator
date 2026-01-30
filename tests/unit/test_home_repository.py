"""Unit tests for Home repository."""

import pytest
from datetime import datetime
from app.domain.models import Home
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository


class TestHomeRepository:
    """Test suite for Home repository."""

    @pytest.fixture
    def repo(self):
        """Create a fresh repository for each test."""
        return InMemoryHomeRepository()

    @pytest.fixture
    def sample_home(self):
        """Create a sample home for testing."""
        return Home(
            home_id="home_1",
            user_id="user_123",
            name="Main House",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="voice_auth_scene",
            is_active=True,
            created_at=datetime.now()
        )

    def test_add_home(self, repo, sample_home):
        """Test adding a new home."""
        result = repo.add(sample_home)

        assert result.home_id == sample_home.home_id
        assert result.name == sample_home.name
        assert repo.exists(sample_home.home_id)

    def test_add_duplicate_home_id_raises_error(self, repo, sample_home):
        """Test that adding a home with duplicate ID raises error."""
        repo.add(sample_home)

        with pytest.raises(ValueError, match="already exists"):
            repo.add(sample_home)

    def test_get_by_id(self, repo, sample_home):
        """Test retrieving home by ID."""
        repo.add(sample_home)
        result = repo.get_by_id(sample_home.home_id)

        assert result is not None
        assert result.home_id == sample_home.home_id
        assert result.name == sample_home.name

    def test_get_by_id_not_found(self, repo):
        """Test that get_by_id returns None for non-existent home."""
        result = repo.get_by_id("nonexistent")
        assert result is None

    def test_get_by_home_id(self, repo, sample_home):
        """Test retrieving home by home_id (alias)."""
        repo.add(sample_home)
        result = repo.get_by_home_id(sample_home.home_id)

        assert result is not None
        assert result.home_id == sample_home.home_id

    def test_get_by_user_id(self, repo):
        """Test retrieving all homes for a user."""
        home1 = Home(
            home_id="home_1",
            user_id="user_123",
            name="Main House",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1",
            is_active=True
        )
        home2 = Home(
            home_id="home_2",
            user_id="user_123",
            name="Beach House",
            ha_url="https://ha2.homeadapt.us",
            ha_webhook_id="webhook_2",
            is_active=True
        )

        repo.add(home1)
        repo.add(home2)

        homes = repo.get_by_user_id("user_123")

        assert len(homes) == 2
        assert any(h.home_id == "home_1" for h in homes)
        assert any(h.home_id == "home_2" for h in homes)

    def test_update_home(self, repo, sample_home):
        """Test updating a home."""
        repo.add(sample_home)

        updated = Home(
            home_id=sample_home.home_id,
            user_id=sample_home.user_id,
            name="Updated House",
            ha_url="https://updated-ha.homeadapt.us",
            ha_webhook_id="updated_webhook",
            is_active=True,
            created_at=sample_home.created_at
        )

        result = repo.update(updated)

        assert result.name == "Updated House"
        assert result.ha_url == "https://updated-ha.homeadapt.us"
        assert result.updated_at is not None

    def test_update_nonexistent_home_raises_error(self, repo):
        """Test that updating non-existent home raises error."""
        home = Home(
            home_id="nonexistent",
            user_id="user_123",
            name="Test",
            ha_url="https://test.com",
            ha_webhook_id="test",
            is_active=True
        )

        with pytest.raises(ValueError, match="not found"):
            repo.update(home)

    def test_delete_home(self, repo, sample_home):
        """Test deleting a home."""
        repo.add(sample_home)
        result = repo.delete(sample_home.home_id)

        assert result is True
        assert not repo.exists(sample_home.home_id)

    def test_delete_nonexistent_home(self, repo):
        """Test that deleting non-existent home returns False."""
        result = repo.delete("nonexistent")
        assert result is False

    def test_list_all_homes(self, repo):
        """Test listing all homes."""
        home1 = Home(
            home_id="home_1",
            user_id="user_1",
            name="Home 1",
            ha_url="https://ha1.com",
            ha_webhook_id="webhook_1",
            is_active=True
        )
        home2 = Home(
            home_id="home_2",
            user_id="user_2",
            name="Home 2",
            ha_url="https://ha2.com",
            ha_webhook_id="webhook_2",
            is_active=False
        )

        repo.add(home1)
        repo.add(home2)

        homes = repo.list_all()

        assert len(homes) == 2

    def test_list_active_homes(self, repo):
        """Test listing only active homes."""
        home1 = Home(
            home_id="home_1",
            user_id="user_1",
            name="Home 1",
            ha_url="https://ha1.com",
            ha_webhook_id="webhook_1",
            is_active=True
        )
        home2 = Home(
            home_id="home_2",
            user_id="user_2",
            name="Home 2",
            ha_url="https://ha2.com",
            ha_webhook_id="webhook_2",
            is_active=False
        )

        repo.add(home1)
        repo.add(home2)

        homes = repo.list_active()

        assert len(homes) == 1
        assert homes[0].home_id == "home_1"

    def test_list_by_user_active_only(self, repo):
        """Test listing homes for a user with active filter."""
        home1 = Home(
            home_id="home_1",
            user_id="user_123",
            name="Home 1",
            ha_url="https://ha1.com",
            ha_webhook_id="webhook_1",
            is_active=True
        )
        home2 = Home(
            home_id="home_2",
            user_id="user_123",
            name="Home 2",
            ha_url="https://ha2.com",
            ha_webhook_id="webhook_2",
            is_active=False
        )

        repo.add(home1)
        repo.add(home2)

        # Active only
        homes = repo.list_by_user("user_123", active_only=True)
        assert len(homes) == 1
        assert homes[0].home_id == "home_1"

        # All homes
        homes = repo.list_by_user("user_123", active_only=False)
        assert len(homes) == 2

    def test_exists(self, repo, sample_home):
        """Test checking if home exists."""
        assert not repo.exists(sample_home.home_id)

        repo.add(sample_home)

        assert repo.exists(sample_home.home_id)

    def test_exists_for_user(self, repo, sample_home):
        """Test checking if home exists for specific user."""
        repo.add(sample_home)

        assert repo.exists_for_user("user_123", "home_1")
        assert not repo.exists_for_user("user_999", "home_1")
        assert not repo.exists_for_user("user_123", "nonexistent")

    def test_deactivate_home(self, repo, sample_home):
        """Test deactivating a home."""
        repo.add(sample_home)
        result = repo.deactivate(sample_home.home_id)

        assert result is True

        home = repo.get_by_id(sample_home.home_id)
        assert home.is_active is False
        assert home.updated_at is not None

    def test_deactivate_nonexistent_home(self, repo):
        """Test that deactivating non-existent home returns False."""
        result = repo.deactivate("nonexistent")
        assert result is False

    def test_activate_home(self, repo):
        """Test activating a home."""
        home = Home(
            home_id="home_1",
            user_id="user_123",
            name="Test Home",
            ha_url="https://test.com",
            ha_webhook_id="test",
            is_active=False
        )
        repo.add(home)

        result = repo.activate(home.home_id)
        assert result is True

        activated = repo.get_by_id(home.home_id)
        assert activated.is_active is True
        assert activated.updated_at is not None

    def test_activate_nonexistent_home(self, repo):
        """Test that activating non-existent home returns False."""
        result = repo.activate("nonexistent")
        assert result is False

    def test_update_ha_config(self, repo, sample_home):
        """Test updating Home Assistant configuration."""
        repo.add(sample_home)

        result = repo.update_ha_config(
            home_id=sample_home.home_id,
            ha_url="https://new-ha.homeadapt.us",
            ha_webhook_id="new_webhook"
        )

        assert result is True

        home = repo.get_by_id(sample_home.home_id)
        assert home.ha_url == "https://new-ha.homeadapt.us"
        assert home.ha_webhook_id == "new_webhook"
        assert home.updated_at is not None

    def test_update_ha_config_partial(self, repo, sample_home):
        """Test updating only HA URL."""
        repo.add(sample_home)

        result = repo.update_ha_config(
            home_id=sample_home.home_id,
            ha_url="https://new-ha.homeadapt.us"
        )

        assert result is True

        home = repo.get_by_id(sample_home.home_id)
        assert home.ha_url == "https://new-ha.homeadapt.us"
        assert home.ha_webhook_id == "voice_auth_scene"  # Unchanged

    def test_update_ha_config_nonexistent_home(self, repo):
        """Test that updating config for non-existent home returns False."""
        result = repo.update_ha_config("nonexistent", ha_url="https://test.com")
        assert result is False
