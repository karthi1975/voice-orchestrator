"""
Webhook-based Home Assistant client

Implementation of IHomeAssistantClient using webhooks.
"""

import logging
import requests
from datetime import datetime
from typing import Dict, Any
from app.infrastructure.home_assistant.client import (
    IHomeAssistantClient,
    SceneTriggerResult,
    ConnectionTestResult
)


logger = logging.getLogger(__name__)


class WebhookHomeAssistantClient(IHomeAssistantClient):
    """
    Home Assistant client using webhook integration.

    Sends scene trigger requests to HA via webhook.
    Suitable for simple automation triggers.
    """

    def __init__(
        self,
        base_url: str,
        webhook_id: str,
        test_mode: bool = False,
        timeout: int = 10
    ):
        """
        Initialize webhook client.

        Args:
            base_url: Home Assistant base URL (e.g., "http://homeassistant.local:8123")
            webhook_id: Webhook ID for voice auth (e.g., "voice_auth_scene")
            test_mode: If True, simulates responses without calling HA
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.webhook_id = webhook_id
        self.test_mode = test_mode
        self.timeout = timeout

    def trigger_scene(
        self,
        scene_id: str,
        source: str = "Voice Authentication"
    ) -> SceneTriggerResult:
        """
        Trigger scene via webhook.

        Args:
            scene_id: Scene to trigger
            source: Source of trigger

        Returns:
            SceneTriggerResult
        """
        if self.test_mode:
            return self._simulate_scene_trigger(scene_id, source)

        try:
            # Build webhook URL
            webhook_url = f"{self.base_url}/api/webhook/{self.webhook_id}"

            # Build payload
            payload = {
                "scene": scene_id,
                "source": source,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Triggering HA scene: {scene_id} via webhook")

            # Send webhook request
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=self.timeout
            )

            # Check response
            if response.status_code == 200:
                logger.info(f"Scene {scene_id} triggered successfully")
                return SceneTriggerResult(
                    success=True,
                    message=f"Scene '{scene_id}' activated successfully",
                    scene_id=scene_id,
                    details={'status_code': response.status_code}
                )
            else:
                logger.warning(
                    f"Scene trigger failed: HTTP {response.status_code}",
                    extra={'scene_id': scene_id, 'status_code': response.status_code}
                )
                return SceneTriggerResult(
                    success=False,
                    message=f"Scene trigger failed (HTTP {response.status_code})",
                    scene_id=scene_id,
                    details={'status_code': response.status_code}
                )

        except requests.exceptions.Timeout:
            logger.error(f"Timeout triggering scene {scene_id}")
            return SceneTriggerResult(
                success=False,
                message="Home Assistant request timed out",
                scene_id=scene_id
            )

        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error triggering scene {scene_id}")
            return SceneTriggerResult(
                success=False,
                message="Cannot connect to Home Assistant",
                scene_id=scene_id
            )

        except Exception as e:
            logger.error(f"Error triggering scene {scene_id}: {str(e)}", exc_info=True)
            return SceneTriggerResult(
                success=False,
                message=f"Error triggering scene: {str(e)}",
                scene_id=scene_id
            )

    def test_connection(self) -> ConnectionTestResult:
        """
        Test connection to Home Assistant.

        Returns:
            ConnectionTestResult
        """
        if self.test_mode:
            return ConnectionTestResult(
                success=True,
                message="Running in TEST MODE (Home Assistant connection disabled)",
                details={'test_mode': True}
            )

        try:
            # Try to reach HA API
            api_url = f"{self.base_url}/api/"

            logger.debug(f"Testing HA connection: {api_url}")

            response = requests.get(api_url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                message = data.get('message', 'Connected to Home Assistant')

                logger.info("Home Assistant connection successful")

                return ConnectionTestResult(
                    success=True,
                    message=message,
                    details={'status_code': response.status_code}
                )
            else:
                logger.warning(f"HA connection test failed: HTTP {response.status_code}")
                return ConnectionTestResult(
                    success=False,
                    message=f"Home Assistant returned HTTP {response.status_code}",
                    details={'status_code': response.status_code}
                )

        except requests.exceptions.Timeout:
            logger.error("HA connection test timed out")
            return ConnectionTestResult(
                success=False,
                message="Connection to Home Assistant timed out"
            )

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Home Assistant")
            return ConnectionTestResult(
                success=False,
                message="Cannot connect to Home Assistant - check if it's running"
            )

        except Exception as e:
            logger.error(f"Error testing HA connection: {str(e)}", exc_info=True)
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {str(e)}"
            )

    def is_available(self) -> bool:
        """
        Check if Home Assistant is available.

        Returns:
            True if available
        """
        result = self.test_connection()
        return result.success

    def _simulate_scene_trigger(self, scene_id: str, source: str) -> SceneTriggerResult:
        """
        Simulate scene trigger for testing.

        Args:
            scene_id: Scene ID
            source: Source

        Returns:
            SceneTriggerResult (simulated success)
        """
        logger.info(
            f"[TEST MODE] Simulating scene trigger",
            extra={'scene_id': scene_id, 'source': source}
        )

        return SceneTriggerResult(
            success=True,
            message=f"[TEST MODE] Scene '{scene_id}' activated successfully",
            scene_id=scene_id,
            details={'test_mode': True}
        )
