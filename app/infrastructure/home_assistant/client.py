"""
Home Assistant client interface

Abstract interface for Home Assistant integration.
Allows swapping implementations (webhook, REST API, WebSocket, etc.).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SceneTriggerResult:
    """
    Result of triggering a scene.

    Attributes:
        success: Whether the trigger succeeded
        message: Human-readable status message
        scene_id: Scene that was triggered
        details: Optional additional details
    """
    success: bool
    message: str
    scene_id: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ConnectionTestResult:
    """
    Result of testing Home Assistant connection.

    Attributes:
        success: Whether connection succeeded
        message: Human-readable status message
        details: Optional additional details (version, etc.)
    """
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class IHomeAssistantClient(ABC):
    """
    Interface for Home Assistant integration.

    Defines operations for interacting with Home Assistant.
    Implementations can use webhooks, REST API, WebSocket, etc.
    """

    @abstractmethod
    def trigger_scene(
        self,
        scene_id: str,
        source: str = "Voice Authentication"
    ) -> SceneTriggerResult:
        """
        Trigger a Home Assistant scene.

        Args:
            scene_id: Scene identifier to trigger
            source: Source of the trigger (for logging)

        Returns:
            SceneTriggerResult with success status and message

        Examples:
            >>> client = WebhookHomeAssistantClient(...)
            >>> result = client.trigger_scene("night_scene")
            >>> print(result.success)
            True
        """
        pass

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """
        Test connection to Home Assistant.

        Returns:
            ConnectionTestResult with success status

        Examples:
            >>> client = WebhookHomeAssistantClient(...)
            >>> result = client.test_connection()
            >>> print(result.message)
            'Connected to Home Assistant'
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if Home Assistant is available.

        Returns:
            True if HA is reachable, False otherwise

        Examples:
            >>> client = WebhookHomeAssistantClient(...)
            >>> client.is_available()
            True
        """
        pass
