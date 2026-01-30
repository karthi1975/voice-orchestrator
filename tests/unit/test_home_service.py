"""Unit tests for Home service."""

import pytest
from datetime import datetime
from app.services.home_service import HomeService
from app.services.user_service import UserService
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository


class TestHomeService:
    """Test suite for Home service."""

    @pytest.fixture
    def user_repo(self):
        """Create a fresh user repository for each test."""
        return InMemoryUserRepository()

    @pytest.fixture
    def home_repo(self):
        """Create a fresh home repository for each test."""
        return InMemoryHomeRepository()

    @pytest.fixture
    def user_service(self, user_repo):
        """Create a user service."""
        return UserService(user_repo)

    @pytest.fixture
    def service(self, home_repo, user_repo):
        """Create a home service with in-memory repositories."""
        return HomeService(home_repo, user_repo)

    @pytest.fixture
    def sample_user(self, user_service):
        """Create a sample user for testing."""
        return user_service.create_user("john_doe", "John Doe")

    def test_register_home(self, service, sample_user):
        """Test registering a new home."""
        home = service.register_home(
            home_id="home_1",
            user_id=sample_user.user_id,
            name="Main House",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="voice_auth_scene"
        )

        assert home.home_id == "home_1"
        assert home.user_id == sample_user.user_id
        assert home.name == "Main House"
        assert home.ha_url == "https://ha1.homeadapt.us"
        assert home.ha_webhook_id == "voice_auth_scene"
        assert home.is_active is True

    def test_register_home_user_not_found_raises_error(self, service):
        """Test that registering home with non-existent user raises error."""
        with pytest.raises(ValueError, match="User.*not found"):
            service.register_home(
                home_id="home_1",
                user_id="nonexistent",
                name="Test Home",
                ha_url="https://test.com",
                ha_webhook_id="test"
            )

    def test_register_duplicate_home_id_raises_error(self, service, sample_user):
        """Test that registering home with duplicate ID raises error."""
        service.register_home(
            home_id="home_1",
            user_id=sample_user.user_id,
            name="Home 1",
            ha_url="https://ha1.com",
            ha_webhook_id="webhook_1"
        )

        with pytest.raises(ValueError, match="already exists"):
            service.register_home(
                home_id="home_1",
                user_id=sample_user.user_id,
                name="Home 2",
                ha_url="https://ha2.com",
                ha_webhook_id="webhook_2"
            )

    def test_get_home(self, service, sample_user):
        """Test getting home by ID."""
        created = service.register_home(
            home_id="home_1",
            user_id=sample_user.user_id,
            name="Main House",
            ha_url="https://ha1.com",
            ha_webhook_id="webhook_1"
        )

        retrieved = service.get_home("home_1")

        assert retrieved.home_id == created.home_id
        assert retrieved.name == "Main House"

    def test_get_home_not_found_raises_error(self, service):
        """Test that getting non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.get_home("nonexistent")

    def test_get_user_homes(self, service, sample_user):
        """Test getting all homes for a user."""
        service.register_home("home_1", sample_user.user_id, "Home 1", "https://ha1.com", "webhook_1")
        service.register_home("home_2", sample_user.user_id, "Home 2", "https://ha2.com", "webhook_2")

        homes = service.get_user_homes(sample_user.user_id)

        assert len(homes) == 2
        assert any(h.home_id == "home_1" for h in homes)
        assert any(h.home_id == "home_2" for h in homes)

    def test_get_user_homes_active_only(self, service, sample_user):
        """Test getting only active homes for a user."""
        service.register_home("home_1", sample_user.user_id, "Home 1", "https://ha1.com", "webhook_1")
        home2 = service.register_home("home_2", sample_user.user_id, "Home 2", "https://ha2.com", "webhook_2")

        # Deactivate home2
        service.deactivate_home(home2.home_id)

        homes = service.get_user_homes(sample_user.user_id, active_only=True)

        assert len(homes) == 1
        assert homes[0].home_id == "home_1"

    def test_list_homes_all(self, service, sample_user, user_service):
        """Test listing all homes."""
        user2 = user_service.create_user("jane_doe", "Jane Doe")

        service.register_home("home_1", sample_user.user_id, "Home 1", "https://ha1.com", "webhook_1")
        service.register_home("home_2", user2.user_id, "Home 2", "https://ha2.com", "webhook_2")

        homes = service.list_homes(active_only=False)

        assert len(homes) == 2

    def test_list_homes_active_only(self, service, sample_user):
        """Test listing only active homes."""
        home1 = service.register_home("home_1", sample_user.user_id, "Home 1", "https://ha1.com", "webhook_1")
        service.register_home("home_2", sample_user.user_id, "Home 2", "https://ha2.com", "webhook_2")

        # Deactivate home1
        service.deactivate_home(home1.home_id)

        homes = service.list_homes(active_only=True)

        assert len(homes) == 1
        assert homes[0].home_id == "home_2"

    def test_update_home(self, service, sample_user):
        """Test updating home details."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Old Name",
            "https://old.com", "old_webhook"
        )

        updated = service.update_home(
            home.home_id,
            name="New Name",
            ha_url="https://new.com",
            ha_webhook_id="new_webhook"
        )

        assert updated.name == "New Name"
        assert updated.ha_url == "https://new.com"
        assert updated.ha_webhook_id == "new_webhook"
        assert updated.updated_at is not None

    def test_update_home_partial(self, service, sample_user):
        """Test updating only some fields."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Old Name",
            "https://old.com", "old_webhook"
        )

        updated = service.update_home(
            home.home_id,
            name="New Name"
        )

        assert updated.name == "New Name"
        assert updated.ha_url == "https://old.com"  # Unchanged
        assert updated.ha_webhook_id == "old_webhook"  # Unchanged

    def test_update_home_not_found_raises_error(self, service):
        """Test that updating non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.update_home("nonexistent", name="Test")

    def test_deactivate_home(self, service, sample_user):
        """Test deactivating a home."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )

        deactivated = service.deactivate_home(home.home_id)

        assert deactivated.is_active is False

    def test_deactivate_home_not_found_raises_error(self, service):
        """Test that deactivating non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.deactivate_home("nonexistent")

    def test_activate_home(self, service, sample_user):
        """Test activating a deactivated home."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )
        service.deactivate_home(home.home_id)

        activated = service.activate_home(home.home_id)

        assert activated.is_active is True

    def test_activate_home_not_found_raises_error(self, service):
        """Test that activating non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.activate_home("nonexistent")

    def test_delete_home(self, service, sample_user):
        """Test deleting a home."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )

        result = service.delete_home(home.home_id)

        assert result is True
        assert not service.home_exists(home.home_id)

    def test_delete_nonexistent_home(self, service):
        """Test deleting non-existent home returns False."""
        result = service.delete_home("nonexistent")

        assert result is False

    def test_get_ha_config(self, service, sample_user):
        """Test getting HA configuration for a home."""
        service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://ha.homeadapt.us", "voice_webhook"
        )

        ha_url, ha_webhook_id = service.get_ha_config("home_1")

        assert ha_url == "https://ha.homeadapt.us"
        assert ha_webhook_id == "voice_webhook"

    def test_get_ha_config_inactive_home_raises_error(self, service, sample_user):
        """Test that getting HA config for inactive home raises error."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )
        service.deactivate_home(home.home_id)

        with pytest.raises(ValueError, match="not active"):
            service.get_ha_config(home.home_id)

    def test_get_ha_config_not_found_raises_error(self, service):
        """Test that getting HA config for non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.get_ha_config("nonexistent")

    def test_update_ha_config(self, service, sample_user):
        """Test updating HA configuration."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://old.com", "old_webhook"
        )

        updated = service.update_ha_config(
            home.home_id,
            ha_url="https://new.com",
            ha_webhook_id="new_webhook"
        )

        assert updated.ha_url == "https://new.com"
        assert updated.ha_webhook_id == "new_webhook"

    def test_update_ha_config_not_found_raises_error(self, service):
        """Test that updating HA config for non-existent home raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.update_ha_config("nonexistent", ha_url="https://test.com")

    def test_home_exists(self, service, sample_user):
        """Test checking if home exists."""
        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )

        assert service.home_exists(home.home_id)
        assert not service.home_exists("nonexistent")

    def test_validate_home_access(self, service, sample_user, user_service):
        """Test validating user access to home."""
        user2 = user_service.create_user("jane_doe", "Jane Doe")

        home = service.register_home(
            "home_1", sample_user.user_id, "Test Home",
            "https://test.com", "test"
        )

        assert service.validate_home_access(sample_user.user_id, home.home_id)
        assert not service.validate_home_access(user2.user_id, home.home_id)
        assert not service.validate_home_access(sample_user.user_id, "nonexistent")
