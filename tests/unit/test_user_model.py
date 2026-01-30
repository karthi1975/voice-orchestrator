"""Unit tests for User domain model."""

import pytest
from datetime import datetime
from app.domain.models import User


class TestUserModel:
    """Test suite for User domain model."""

    def test_create_user_with_all_fields(self):
        """Test creating a user with all fields."""
        user_id = "user_123"
        username = "john_doe"
        full_name = "John Doe"
        email = "john@example.com"
        created_at = datetime.now()

        user = User(
            user_id=user_id,
            username=username,
            full_name=full_name,
            email=email,
            is_active=True,
            created_at=created_at
        )

        assert user.user_id == user_id
        assert user.username == username
        assert user.full_name == full_name
        assert user.email == email
        assert user.is_active is True
        assert user.created_at == created_at

    def test_create_user_without_email(self):
        """Test creating a user without email (optional field)."""
        user = User(
            user_id="user_456",
            username="jane_smith",
            full_name="Jane Smith",
            is_active=True
        )

        assert user.email is None
        assert user.username == "jane_smith"

    def test_create_user_default_is_active(self):
        """Test that is_active defaults to True."""
        user = User(
            user_id="user_789",
            username="bob_jones",
            full_name="Bob Jones"
        )

        assert user.is_active is True

    def test_create_user_default_created_at(self):
        """Test that created_at is auto-generated if not provided."""
        before = datetime.now()
        user = User(
            user_id="user_999",
            username="alice_wonder",
            full_name="Alice Wonder"
        )
        after = datetime.now()

        assert before <= user.created_at <= after

    def test_create_inactive_user(self):
        """Test creating an inactive user."""
        user = User(
            user_id="user_000",
            username="inactive_user",
            full_name="Inactive User",
            is_active=False
        )

        assert user.is_active is False
