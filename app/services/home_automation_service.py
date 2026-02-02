"""
Home automation service for Home Assistant integration

Service layer for interacting with Home Assistant with multi-tenant support.
"""

from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SceneTriggerRequest:
    """
    Request to trigger a Home Assistant scene.

    Attributes:
        scene_id: Scene identifier to trigger
        home_id: Home identifier for multi-tenant routing
        source: Source of the trigger (e.g., "Alexa Voice Auth")
    """
    scene_id: str
    home_id: Optional[str] = None
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
    Service for Home Assistant integration with multi-tenant support.

    Provides high-level operations for:
    - Triggering scenes across multiple homes
    - Testing connectivity
    - Future: Device control, status queries

    Dependencies:
    - HomeService: Get home HA configuration
    - HomeAssistantClientFactory: Get HA client per home
    """

    def __init__(
        self,
        home_service=None,
        client_factory=None,
        legacy_client=None
    ):
        """
        Initialize home automation service.

        Args:
            home_service: HomeService for looking up home config (multi-tenant)
            client_factory: HomeAssistantClientFactory for multi-tenant support
            legacy_client: Legacy single HA client for backward compatibility
        """
        self._home_service = home_service
        self._client_factory = client_factory
        self._legacy_client = legacy_client

    def trigger_scene(
        self,
        scene_id: str,
        home_id: Optional[str] = None,
        source: str = "Voice Authentication"
    ) -> SceneTriggerResult:
        """
        Trigger a Home Assistant scene.

        Args:
            scene_id: Scene identifier to trigger
            home_id: Home identifier (required for multi-tenant, optional for legacy)
            source: Source of the trigger

        Returns:
            SceneTriggerResult with success status and message

        Raises:
            ValueError: If home_id is required but not provided, or home not found

        Examples:
            >>> # Multi-tenant usage
            >>> result = service.trigger_scene("night_scene", home_id="home_1")

            >>> # Legacy usage (backward compatible)
            >>> result = service.trigger_scene("night_scene")
        """
        # Multi-tenant mode: use factory and home service
        if self._client_factory and self._home_service:
            if not home_id:
                raise ValueError("home_id is required for multi-tenant mode")

            return self._trigger_via_factory(scene_id, home_id, source)

        # Legacy mode: use single client
        elif self._legacy_client:
            return self._trigger_via_legacy_client(scene_id, source)

        # Fallback: use legacy module
        else:
            return self._trigger_via_legacy_module(scene_id)

    def _trigger_via_factory(
        self,
        scene_id: str,
        home_id: str,
        source: str
    ) -> SceneTriggerResult:
        """
        Trigger scene using client factory (multi-tenant).

        Args:
            scene_id: Scene to trigger
            home_id: Home identifier
            source: Source of trigger

        Returns:
            SceneTriggerResult
        """
        try:
            # Get home to check test_mode
            home = self._home_service.get_home(home_id)

            # If in test mode, skip HA and return success
            if home.test_mode:
                return SceneTriggerResult(
                    success=True,
                    message=f"[TEST MODE] Scene '{scene_id}' triggered successfully (Home Assistant skipped)",
                    scene_id=scene_id
                )

            # Get home HA configuration
            ha_url, ha_webhook_id = self._home_service.get_ha_config(home_id)

            # Get client for this home
            client = self._client_factory.get_client(
                home_id=home_id,
                ha_url=ha_url,
                ha_webhook_id=ha_webhook_id
            )

            # Trigger scene
            client_result = client.trigger_scene(
                scene_id=scene_id,
                source=source
            )

            # Convert to service result
            return SceneTriggerResult(
                success=client_result.success,
                message=client_result.message,
                scene_id=scene_id
            )

        except Exception as e:
            return SceneTriggerResult(
                success=False,
                message=f"Failed to trigger scene: {str(e)}",
                scene_id=scene_id
            )

    def _trigger_via_legacy_client(
        self,
        scene_id: str,
        source: str
    ) -> SceneTriggerResult:
        """
        Trigger scene using legacy single client.

        Args:
            scene_id: Scene to trigger
            source: Source of trigger

        Returns:
            SceneTriggerResult
        """
        client_result = self._legacy_client.trigger_scene(
            scene_id=scene_id,
            source=source
        )

        return SceneTriggerResult(
            success=client_result.success,
            message=client_result.message,
            scene_id=scene_id
        )

    def _trigger_via_legacy_module(self, scene_id: str) -> SceneTriggerResult:
        """
        Trigger scene using legacy home_assistant module.

        Args:
            scene_id: Scene to trigger

        Returns:
            SceneTriggerResult
        """
        try:
            from home_assistant import trigger_scene

            success, message = trigger_scene(scene_id)

            return SceneTriggerResult(
                success=success,
                message=message,
                scene_id=scene_id
            )
        except ImportError:
            return SceneTriggerResult(
                success=False,
                message="Home Assistant module not available",
                scene_id=scene_id
            )

    def test_connection(self, home_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Test connection to Home Assistant.

        Args:
            home_id: Optional home identifier for multi-tenant mode

        Returns:
            Tuple of (success, message)

        Examples:
            >>> success, message = service.test_connection(home_id="home_1")
            >>> print(message)
            'Connected to Home Assistant'
        """
        # Multi-tenant mode
        if self._client_factory and self._home_service and home_id:
            try:
                ha_url, ha_webhook_id = self._home_service.get_ha_config(home_id)
                client = self._client_factory.get_client(home_id, ha_url, ha_webhook_id)
                result = client.test_connection()
                return result.success, result.message
            except Exception as e:
                return False, f"Connection test failed: {str(e)}"

        # Legacy single client
        elif self._legacy_client:
            result = self._legacy_client.test_connection()
            return result.success, result.message

        # Legacy module
        else:
            try:
                from home_assistant import test_connection
                return test_connection()
            except ImportError:
                return False, "Home Assistant module not available"
