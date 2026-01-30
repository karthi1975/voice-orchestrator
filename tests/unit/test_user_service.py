"""Unit tests for User service."""

import pytest
from datetime import datetime
from app.services.user_service import UserService
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository


class TestUserService:
    """Test suite for User service."""

    @pytest.fixture
    def repo(self):
        """Create a fresh repository for each test."""
        return InMemoryUserRepository()

    @pytest.fixture
    def service(self, repo):
        """Create a user service with in-memory repository."""
        return UserService(repo)

    def test_create_user(self, service):
        """Test creating a new user."""
        user = service.create_user(
            username="john_doe",
            full_name="John Doe",
            email="john@example.com"
        )

        assert user.user_id is not None
        assert user.username == "john_doe"
        assert user.full_name == "John Doe"
        assert user.email == "john@example.com"
        assert user.is_active is True

    def test_create_user_without_email(self, service):
        """Test creating a user without email."""
        user = service.create_user(
            username="jane_doe",
            full_name="Jane Doe"
        )

        assert user.email is None
        assert user.username == "jane_doe"

    def test_create_duplicate_username_raises_error(self, service):
        """Test that creating user with duplicate username raises error."""
        service.create_user("john_doe", "John Doe")

        with pytest.raises(ValueError, match="already exists"):
            service.create_user("john_doe", "Another John")

    def test_create_duplicate_email_raises_error(self, service):
        """Test that creating user with duplicate email raises error."""
        service.create_user("user1", "User One", "test@example.com")

        with pytest.raises(ValueError, match="already exists"):
            service.create_user("user2", "User Two", "test@example.com")

    def test_get_user(self, service):
        """Test getting user by ID."""
        created = service.create_user("john_doe", "John Doe")
        retrieved = service.get_user(created.user_id)

        assert retrieved.user_id == created.user_id
        assert retrieved.username == "john_doe"

    def test_get_user_not_found_raises_error(self, service):
        """Test that getting non-existent user raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.get_user("nonexistent")

    def test_get_by_username(self, service):
        """Test getting user by username."""
        service.create_user("john_doe", "John Doe")
        user = service.get_by_username("john_doe")

        assert user.username == "john_doe"

    def test_get_by_username_not_found_raises_error(self, service):
        """Test that getting user by non-existent username raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.get_by_username("nonexistent")

    def test_get_by_email(self, service):
        """Test getting user by email."""
        service.create_user("john_doe", "John Doe", "john@example.com")
        user = service.get_by_email("john@example.com")

        assert user.email == "john@example.com"

    def test_get_by_email_not_found_raises_error(self, service):
        """Test that getting user by non-existent email raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.get_by_email("nonexistent@example.com")

    def test_list_users_all(self, service):
        """Test listing all users."""
        service.create_user("user1", "User One")
        service.create_user("user2", "User Two")

        users = service.list_users(active_only=False)

        assert len(users) == 2

    def test_list_users_active_only(self, service):
        """Test listing only active users."""
        user1 = service.create_user("user1", "User One")
        service.create_user("user2", "User Two")

        # Deactivate user1
        service.deactivate_user(user1.user_id)

        users = service.list_users(active_only=True)

        assert len(users) == 1
        assert users[0].username == "user2"

    def test_update_user(self, service):
        """Test updating user details."""
        user = service.create_user("john_doe", "John Doe", "john@example.com")

        updated = service.update_user(
            user.user_id,
            username="john_updated",
            full_name="John Updated",
            email="john.updated@example.com"
        )

        assert updated.username == "john_updated"
        assert updated.full_name == "John Updated"
        assert updated.email == "john.updated@example.com"

    def test_update_user_partial(self, service):
        """Test updating only some fields."""
        user = service.create_user("john_doe", "John Doe", "john@example.com")

        updated = service.update_user(
            user.user_id,
            full_name="John Updated"
        )

        assert updated.username == "john_doe"  # Unchanged
        assert updated.full_name == "John Updated"
        assert updated.email == "john@example.com"  # Unchanged

    def test_update_user_not_found_raises_error(self, service):
        """Test that updating non-existent user raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.update_user("nonexistent", full_name="Test")

    def test_deactivate_user(self, service):
        """Test deactivating a user."""
        user = service.create_user("john_doe", "John Doe")

        deactivated = service.deactivate_user(user.user_id)

        assert deactivated.is_active is False

    def test_deactivate_user_not_found_raises_error(self, service):
        """Test that deactivating non-existent user raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.deactivate_user("nonexistent")

    def test_activate_user(self, service):
        """Test activating a deactivated user."""
        user = service.create_user("john_doe", "John Doe")
        service.deactivate_user(user.user_id)

        activated = service.activate_user(user.user_id)

        assert activated.is_active is True

    def test_activate_user_not_found_raises_error(self, service):
        """Test that activating non-existent user raises error."""
        with pytest.raises(ValueError, match="not found"):
            service.activate_user("nonexistent")

    def test_delete_user(self, service):
        """Test deleting a user."""
        user = service.create_user("john_doe", "John Doe")

        result = service.delete_user(user.user_id)

        assert result is True
        assert not service.user_exists(user.user_id)

    def test_delete_nonexistent_user(self, service):
        """Test deleting non-existent user returns False."""
        result = service.delete_user("nonexistent")

        assert result is False

    def test_user_exists(self, service):
        """Test checking if user exists."""
        user = service.create_user("john_doe", "John Doe")

        assert service.user_exists(user.user_id)
        assert not service.user_exists("nonexistent")
