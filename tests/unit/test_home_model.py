"""Unit tests for Home domain model."""

import pytest
from datetime import datetime
from app.domain.models import Home


class TestHomeModel:
    """Test suite for Home domain model."""

    def test_create_home_with_all_fields(self):
        """Test creating a home with all required fields."""
        home_id = "home_1"
        user_id = "user_123"
        name = "Main House"
        ha_url = "https://ha1.homeadapt.us"
        ha_webhook_id = "voice_auth_scene"
        created_at = datetime.now()
        updated_at = datetime.now()

        home = Home(
            home_id=home_id,
            user_id=user_id,
            name=name,
            ha_url=ha_url,
            ha_webhook_id=ha_webhook_id,
            is_active=True,
            created_at=created_at,
            updated_at=updated_at
        )

        assert home.home_id == home_id
        assert home.user_id == user_id
        assert home.name == name
        assert home.ha_url == ha_url
        assert home.ha_webhook_id == ha_webhook_id
        assert home.is_active is True
        assert home.created_at == created_at
        assert home.updated_at == updated_at

    def test_create_home_default_is_active(self):
        """Test that is_active defaults to True."""
        home = Home(
            home_id="beach_house",
            user_id="user_456",
            name="Beach House",
            ha_url="https://beach-ha.homeadapt.us",
            ha_webhook_id="beach_webhook"
        )

        assert home.is_active is True

    def test_create_home_default_created_at(self):
        """Test that created_at is auto-generated if not provided."""
        before = datetime.now()
        home = Home(
            home_id="mountain_cabin",
            user_id="user_789",
            name="Mountain Cabin",
            ha_url="https://mountain-ha.homeadapt.us",
            ha_webhook_id="mountain_webhook"
        )
        after = datetime.now()

        assert before <= home.created_at <= after

    def test_create_home_without_updated_at(self):
        """Test creating a home without updated_at (optional field)."""
        home = Home(
            home_id="city_apartment",
            user_id="user_999",
            name="City Apartment",
            ha_url="https://city-ha.homeadapt.us",
            ha_webhook_id="city_webhook"
        )

        assert home.updated_at is None

    def test_create_inactive_home(self):
        """Test creating an inactive home."""
        home = Home(
            home_id="old_house",
            user_id="user_000",
            name="Old House",
            ha_url="https://old-ha.homeadapt.us",
            ha_webhook_id="old_webhook",
            is_active=False
        )

        assert home.is_active is False

    def test_home_with_different_webhook_ids(self):
        """Test that different homes can have different webhook IDs."""
        home1 = Home(
            home_id="home_1",
            user_id="user_1",
            name="Home 1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        home2 = Home(
            home_id="home_2",
            user_id="user_1",
            name="Home 2",
            ha_url="https://ha2.homeadapt.us",
            ha_webhook_id="webhook_2"
        )

        assert home1.ha_webhook_id != home2.ha_webhook_id
        assert home1.ha_url != home2.ha_url
        assert home1.user_id == home2.user_id  # Same user owns both
