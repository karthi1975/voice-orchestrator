"""Unit tests for User repository."""

import pytest
from datetime import datetime
from app.domain.models import User
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository


class TestUserRepository:
    """Test suite for User repository."""

    @pytest.fixture
    def repo(self):
        """Create a fresh repository for each test."""
        return InMemoryUserRepository()

    @pytest.fixture
    def sample_user(self):
        """Create a sample user for testing."""
        return User(
            user_id="user_123",
            username="john_doe",
            full_name="John Doe",
            email="john@example.com",
            is_active=True,
            created_at=datetime.now()
        )

    def test_add_user(self, repo, sample_user):
        """Test adding a new user."""
        result = repo.add(sample_user)

        assert result.user_id == sample_user.user_id
        assert result.username == sample_user.username
        assert repo.exists(sample_user.user_id)

    def test_add_duplicate_user_id_raises_error(self, repo, sample_user):
        """Test that adding a user with duplicate ID raises error."""
        repo.add(sample_user)

        with pytest.raises(ValueError, match="already exists"):
            repo.add(sample_user)

    def test_add_duplicate_username_raises_error(self, repo, sample_user):
        """Test that adding a user with duplicate username raises error."""
        repo.add(sample_user)

        duplicate = User(
            user_id="user_456",
            username="john_doe",  # Same username
            full_name="Jane Doe",
            is_active=True
        )

        with pytest.raises(ValueError, match="Username.*already exists"):
            repo.add(duplicate)

    def test_add_duplicate_email_raises_error(self, repo, sample_user):
        """Test that adding a user with duplicate email raises error."""
        repo.add(sample_user)

        duplicate = User(
            user_id="user_456",
            username="jane_doe",
            full_name="Jane Doe",
            email="john@example.com",  # Same email
            is_active=True
        )

        with pytest.raises(ValueError, match="Email.*already exists"):
            repo.add(duplicate)

    def test_get_by_id(self, repo, sample_user):
        """Test retrieving user by ID."""
        repo.add(sample_user)
        result = repo.get_by_id(sample_user.user_id)

        assert result is not None
        assert result.user_id == sample_user.user_id
        assert result.username == sample_user.username

    def test_get_by_id_not_found(self, repo):
        """Test that get_by_id returns None for non-existent user."""
        result = repo.get_by_id("nonexistent")
        assert result is None

    def test_get_by_username(self, repo, sample_user):
        """Test retrieving user by username."""
        repo.add(sample_user)
        result = repo.get_by_username(sample_user.username)

        assert result is not None
        assert result.username == sample_user.username

    def test_get_by_username_not_found(self, repo):
        """Test that get_by_username returns None for non-existent username."""
        result = repo.get_by_username("nonexistent")
        assert result is None

    def test_get_by_email(self, repo, sample_user):
        """Test retrieving user by email."""
        repo.add(sample_user)
        result = repo.get_by_email(sample_user.email)

        assert result is not None
        assert result.email == sample_user.email

    def test_get_by_email_not_found(self, repo):
        """Test that get_by_email returns None for non-existent email."""
        result = repo.get_by_email("nonexistent@example.com")
        assert result is None

    def test_update_user(self, repo, sample_user):
        """Test updating a user."""
        repo.add(sample_user)

        updated = User(
            user_id=sample_user.user_id,
            username="john_updated",
            full_name="John Updated",
            email="john.updated@example.com",
            is_active=True,
            created_at=sample_user.created_at
        )

        result = repo.update(updated)

        assert result.username == "john_updated"
        assert result.full_name == "John Updated"
        assert repo.get_by_username("john_updated") is not None

    def test_update_nonexistent_user_raises_error(self, repo):
        """Test that updating non-existent user raises error."""
        user = User(
            user_id="nonexistent",
            username="test",
            full_name="Test User",
            is_active=True
        )

        with pytest.raises(ValueError, match="not found"):
            repo.update(user)

    def test_delete_user(self, repo, sample_user):
        """Test deleting a user."""
        repo.add(sample_user)
        result = repo.delete(sample_user.user_id)

        assert result is True
        assert not repo.exists(sample_user.user_id)

    def test_delete_nonexistent_user(self, repo):
        """Test that deleting non-existent user returns False."""
        result = repo.delete("nonexistent")
        assert result is False

    def test_list_all_users(self, repo):
        """Test listing all users."""
        user1 = User(user_id="user_1", username="user1", full_name="User 1", is_active=True)
        user2 = User(user_id="user_2", username="user2", full_name="User 2", is_active=False)

        repo.add(user1)
        repo.add(user2)

        users = repo.list_all()

        assert len(users) == 2
        assert any(u.user_id == "user_1" for u in users)
        assert any(u.user_id == "user_2" for u in users)

    def test_list_active_users(self, repo):
        """Test listing only active users."""
        user1 = User(user_id="user_1", username="user1", full_name="User 1", is_active=True)
        user2 = User(user_id="user_2", username="user2", full_name="User 2", is_active=False)

        repo.add(user1)
        repo.add(user2)

        users = repo.list_active()

        assert len(users) == 1
        assert users[0].user_id == "user_1"

    def test_exists(self, repo, sample_user):
        """Test checking if user exists."""
        assert not repo.exists(sample_user.user_id)

        repo.add(sample_user)

        assert repo.exists(sample_user.user_id)

    def test_exists_by_username(self, repo, sample_user):
        """Test checking if username exists."""
        assert not repo.exists_by_username(sample_user.username)

        repo.add(sample_user)

        assert repo.exists_by_username(sample_user.username)

    def test_exists_by_email(self, repo, sample_user):
        """Test checking if email exists."""
        assert not repo.exists_by_email(sample_user.email)

        repo.add(sample_user)

        assert repo.exists_by_email(sample_user.email)

    def test_deactivate_user(self, repo, sample_user):
        """Test deactivating a user."""
        repo.add(sample_user)
        result = repo.deactivate(sample_user.user_id)

        assert result is True

        user = repo.get_by_id(sample_user.user_id)
        assert user.is_active is False

    def test_deactivate_nonexistent_user(self, repo):
        """Test that deactivating non-existent user returns False."""
        result = repo.deactivate("nonexistent")
        assert result is False

    def test_activate_user(self, repo):
        """Test activating a user."""
        user = User(
            user_id="user_123",
            username="test_user",
            full_name="Test User",
            is_active=False
        )
        repo.add(user)

        result = repo.activate(user.user_id)
        assert result is True

        activated = repo.get_by_id(user.user_id)
        assert activated.is_active is True

    def test_activate_nonexistent_user(self, repo):
        """Test that activating non-existent user returns False."""
        result = repo.activate("nonexistent")
        assert result is False
