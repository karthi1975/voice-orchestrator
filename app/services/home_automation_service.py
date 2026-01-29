"""
Home automation service for Home Assistant integration

Service layer for interacting with Home Assistant.
Will use IHomeAssistantClient interface in Phase 5.
"""

from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SceneTriggerRequest:
    """
    Request to trigger a Home Assistant scene.

    Attributes:
        scene_id: Scene identifier to trigger
        source: Source of the trigger (e.g., "Alexa Voice Auth")
    """
    scene_id: str
    source: str = "Voice Authentication"


@dataclass
class SceneTriggerResult:
    """
    Result of scene trigger operation.

    Attributes:
        success: Whether trigger succeeded
        message: Human-readable status message
        scene_id: Scene that was triggered
    """
    success: bool
    message: str
    scene_id: str


class HomeAutomationService:
    """
    Service for Home Assistant integration.

    Provides high-level operations for:
    - Triggering scenes
    - Testing connectivity
    - Future: Device control, status queries

    Phase 5 will inject IHomeAssistantClient interface.
    For now, uses legacy home_assistant module for backward compatibility.
    """

    def __init__(self, ha_client=None):
        """
        Initialize home automation service.

        Args:
            ha_client: Home Assistant client (optional, will use legacy if not provided)
        """
        self._ha_client = ha_client

    def trigger_scene(self, request: SceneTriggerRequest) -> SceneTriggerResult:
        """
        Trigger a Home Assistant scene.

        Args:
            request: Scene trigger request

        Returns:
            SceneTriggerResult with success status and message

        Examples:
            >>> req = SceneTriggerRequest(scene_id="night_scene")
            >>> result = service.trigger_scene(req)
            >>> print(result.success)
            True
        """
        # Phase 5: Use injected HA client
        # For now, use legacy module for backward compatibility
        if self._ha_client:
            # Use injected client (Phase 5)
            return self._trigger_via_client(request)
        else:
            # Use legacy module (backward compatibility)
            return self._trigger_via_legacy(request)

    def _trigger_via_legacy(self, request: SceneTriggerRequest) -> SceneTriggerResult:
        """
        Trigger scene using legacy home_assistant module.

        Args:
            request: Scene trigger request

        Returns:
            SceneTriggerResult
        """
        # Import legacy module
        try:
            from home_assistant import trigger_scene

            success, message = trigger_scene(request.scene_id)

            return SceneTriggerResult(
                success=success,
                message=message,
                scene_id=request.scene_id
            )
        except ImportError:
            return SceneTriggerResult(
                success=False,
                message="Home Assistant module not available",
                scene_id=request.scene_id
            )

    def _trigger_via_client(self, request: SceneTriggerRequest) -> SceneTriggerResult:
        """
        Trigger scene using injected HA client (Phase 5).

        Args:
            request: Scene trigger request

        Returns:
            SceneTriggerResult
        """
        # Use injected client (returns infrastructure SceneTriggerResult)
        client_result = self._ha_client.trigger_scene(
            scene_id=request.scene_id,
            source=request.source
        )

        # Convert to service SceneTriggerResult
        return SceneTriggerResult(
            success=client_result.success,
            message=client_result.message,
            scene_id=request.scene_id
        )

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to Home Assistant.

        Returns:
            Tuple of (success, message)

        Examples:
            >>> success, message = service.test_connection()
            >>> print(message)
            'Running in TEST MODE'
        """
        if self._ha_client:
            # Use injected client (Phase 5)
            result = self._ha_client.test_connection()
            return result.success, result.message
        else:
            # Use legacy module
            try:
                from home_assistant import test_connection
                return test_connection()
            except ImportError:
                return False, "Home Assistant module not available"
