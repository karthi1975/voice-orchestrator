"""Unit tests for HomeAssistant client factory."""

import pytest
from app.infrastructure.home_assistant.client_factory import HomeAssistantClientFactory
from app.infrastructure.home_assistant.webhook_client import WebhookHomeAssistantClient


class TestHomeAssistantClientFactory:
    """Test suite for HA client factory."""

    @pytest.fixture
    def factory(self):
        """Create a fresh factory for each test."""
        return HomeAssistantClientFactory(test_mode=True)

    def test_factory_initialization(self):
        """Test factory initialization."""
        factory = HomeAssistantClientFactory(test_mode=True, timeout=20)

        assert factory._test_mode is True
        assert factory._timeout == 20
        assert len(factory._clients) == 0

    def test_get_client_creates_new_client(self, factory):
        """Test that get_client creates a new client."""
        client = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        assert client is not None
        assert isinstance(client, WebhookHomeAssistantClient)

    def test_get_client_caches_client(self, factory):
        """Test that get_client caches and reuses clients."""
        client1 = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        client2 = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        # Should return same cached instance
        assert client1 is client2

    def test_get_client_different_homes(self, factory):
        """Test that different homes get different clients."""
        client1 = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        client2 = factory.get_client(
            home_id="home_2",
            ha_url="https://ha2.homeadapt.us",
            ha_webhook_id="webhook_2"
        )

        # Should be different instances
        assert client1 is not client2

    def test_get_client_same_home_different_url(self, factory):
        """Test that changing URL creates new client."""
        client1 = factory.get_client(
            home_id="home_1",
            ha_url="https://old.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        client2 = factory.get_client(
            home_id="home_1",
            ha_url="https://new.homeadapt.us",
            ha_webhook_id="webhook_1"
        )

        # Should be different instances due to URL change
        assert client1 is not client2

    def test_clear_cache_specific_home(self, factory):
        """Test clearing cache for specific home."""
        # Create clients for multiple homes
        factory.get_client("home_1", "https://ha1.com", "webhook_1")
        factory.get_client("home_1", "https://ha1-alt.com", "webhook_1")
        factory.get_client("home_2", "https://ha2.com", "webhook_2")

        # Clear home_1's clients
        removed = factory.clear_cache("home_1")

        assert removed == 2
        assert len(factory._clients) == 1

    def test_clear_cache_all(self, factory):
        """Test clearing all cached clients."""
        # Create multiple clients
        factory.get_client("home_1", "https://ha1.com", "webhook_1")
        factory.get_client("home_2", "https://ha2.com", "webhook_2")
        factory.get_client("home_3", "https://ha3.com", "webhook_3")

        # Clear all
        removed = factory.clear_cache()

        assert removed == 3
        assert len(factory._clients) == 0

    def test_clear_cache_empty(self, factory):
        """Test clearing empty cache."""
        removed = factory.clear_cache()

        assert removed == 0

    def test_update_client(self, factory):
        """Test updating client for a home."""
        # Create initial client
        client1 = factory.get_client("home_1", "https://old.com", "old_webhook")

        # Update client
        client2 = factory.update_client("home_1", "https://new.com", "new_webhook")

        # Should be different instance
        assert client1 is not client2

        # Old client should be cleared
        stats = factory.get_cache_stats()
        assert stats['total_clients'] == 1

    def test_get_cache_stats(self, factory):
        """Test getting cache statistics."""
        # Initially empty
        stats = factory.get_cache_stats()
        assert stats['total_clients'] == 0
        assert stats['unique_homes'] == 0

        # Add some clients
        factory.get_client("home_1", "https://ha1.com", "webhook_1")
        factory.get_client("home_1", "https://ha1-alt.com", "webhook_1")
        factory.get_client("home_2", "https://ha2.com", "webhook_2")

        stats = factory.get_cache_stats()
        assert stats['total_clients'] == 3
        assert stats['unique_homes'] == 2

    def test_client_configuration(self, factory):
        """Test that created clients have correct configuration."""
        client = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="voice_webhook"
        )

        # Verify client configuration
        assert isinstance(client, WebhookHomeAssistantClient)
        assert client.base_url == "https://ha1.homeadapt.us"
        assert client.webhook_id == "voice_webhook"
        assert client.test_mode is True  # Factory was created with test_mode=True

    def test_factory_repr(self, factory):
        """Test factory string representation."""
        factory.get_client("home_1", "https://ha1.com", "webhook_1")
        factory.get_client("home_2", "https://ha2.com", "webhook_2")

        repr_str = repr(factory)

        assert "HomeAssistantClientFactory" in repr_str
        assert "clients=2" in repr_str
        assert "homes=2" in repr_str
        assert "test_mode=True" in repr_str

    def test_multiple_clients_can_trigger_scenes(self, factory):
        """Test that multiple clients can trigger scenes independently."""
        client1 = factory.get_client("home_1", "https://ha1.com", "webhook_1")
        client2 = factory.get_client("home_2", "https://ha2.com", "webhook_2")

        # Both should be able to trigger scenes (in test mode)
        result1 = client1.trigger_scene("night_scene")
        result2 = client2.trigger_scene("morning_scene")

        assert result1.success is True
        assert result2.success is True
        assert result1.scene_id == "night_scene"
        assert result2.scene_id == "morning_scene"
