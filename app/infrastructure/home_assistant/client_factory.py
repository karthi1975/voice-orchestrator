"""
HomeAssistant client factory for multi-tenant support

Factory to create and cache HA clients, one per home.
"""

import logging
from typing import Dict, Optional
from app.infrastructure.home_assistant.client import IHomeAssistantClient
from app.infrastructure.home_assistant.webhook_client import WebhookHomeAssistantClient


logger = logging.getLogger(__name__)


class HomeAssistantClientFactory:
    """
    Factory to create and cache HA clients per home.

    Manages multiple Home Assistant client instances, one per home.
    Caches clients for performance and reuses connections.

    Usage:
        factory = HomeAssistantClientFactory(test_mode=False)
        client = factory.get_client(
            home_id="home_1",
            ha_url="https://ha1.homeadapt.us",
            ha_webhook_id="voice_auth_scene"
        )
        result = client.trigger_scene("night_scene")
    """

    def __init__(self, test_mode: bool = False, timeout: int = 10):
        """
        Initialize client factory.

        Args:
            test_mode: If True, clients will simulate responses without calling HA
            timeout: Request timeout in seconds for all clients
        """
        self._clients: Dict[str, IHomeAssistantClient] = {}
        self._test_mode = test_mode
        self._timeout = timeout
        logger.info(f"Initialized HA client factory (test_mode={test_mode})")

    def get_client(
        self,
        home_id: str,
        ha_url: str,
        ha_webhook_id: str
    ) -> IHomeAssistantClient:
        """
        Get or create HA client for a home.

        Creates a new client if one doesn't exist for this home configuration.
        Caches and reuses clients based on home_id + ha_url combination.

        Args:
            home_id: Unique home identifier
            ha_url: Home Assistant base URL
            ha_webhook_id: Webhook ID for voice auth

        Returns:
            IHomeAssistantClient configured for this home

        Examples:
            >>> factory = HomeAssistantClientFactory()
            >>> client = factory.get_client("home_1", "https://ha.local", "webhook_1")
            >>> client.trigger_scene("night_scene")
        """
        # Create cache key from home_id and ha_url
        # This ensures we create new client if HA URL changes for same home
        cache_key = f"{home_id}:{ha_url}"

        if cache_key not in self._clients:
            logger.info(f"Creating new HA client for home '{home_id}' at {ha_url}")

            self._clients[cache_key] = WebhookHomeAssistantClient(
                base_url=ha_url,
                webhook_id=ha_webhook_id,
                test_mode=self._test_mode,
                timeout=self._timeout
            )
        else:
            logger.debug(f"Reusing cached HA client for home '{home_id}'")

        return self._clients[cache_key]

    def clear_cache(self, home_id: Optional[str] = None) -> int:
        """
        Clear cached clients.

        Args:
            home_id: If provided, only clear clients for this home.
                    If None, clear all cached clients.

        Returns:
            Number of clients removed from cache

        Examples:
            >>> factory.clear_cache("home_1")  # Clear specific home
            2
            >>> factory.clear_cache()  # Clear all
            10
        """
        if home_id:
            # Clear specific home's clients
            keys_to_delete = [
                key for key in self._clients
                if key.startswith(f"{home_id}:")
            ]

            for key in keys_to_delete:
                del self._clients[key]
                logger.info(f"Cleared cached client: {key}")

            return len(keys_to_delete)
        else:
            # Clear all clients
            count = len(self._clients)
            self._clients.clear()
            logger.info(f"Cleared all {count} cached clients")
            return count

    def update_client(
        self,
        home_id: str,
        ha_url: str,
        ha_webhook_id: str
    ) -> IHomeAssistantClient:
        """
        Update/recreate client for a home.

        Removes existing cached client and creates a new one.
        Use this when home's HA configuration changes.

        Args:
            home_id: Home identifier
            ha_url: New HA URL
            ha_webhook_id: New webhook ID

        Returns:
            New IHomeAssistantClient instance

        Examples:
            >>> factory.update_client("home_1", "https://new-ha.local", "new_webhook")
        """
        # Clear existing clients for this home
        self.clear_cache(home_id)

        # Create new client
        return self.get_client(home_id, ha_url, ha_webhook_id)

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics

        Examples:
            >>> factory.get_cache_stats()
            {'total_clients': 5, 'unique_homes': 3}
        """
        unique_homes = len(set(
            key.split(':')[0] for key in self._clients.keys()
        ))

        return {
            'total_clients': len(self._clients),
            'unique_homes': unique_homes
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_cache_stats()
        return (
            f"<HomeAssistantClientFactory "
            f"clients={stats['total_clients']} "
            f"homes={stats['unique_homes']} "
            f"test_mode={self._test_mode}>"
        )
