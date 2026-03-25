"""
Smart Home controller for Voice Guardian MCS.

Handles Alexa Smart Home Skill API v3 directives:
- Discovery (returns available scenes as endpoints)
- SceneController Activate/Deactivate
- Authorization AcceptGrant
"""

import logging
from flask import jsonify
from app.controllers.base_controller import BaseController
from app.dto.requests.smarthome_request import SmartHomeDirective
from app.dto.responses.smarthome_response import SmartHomeResponse
from app.services.oauth_service import OAuthService
from app.services.scene_webhook_mapping_service import SceneWebhookMappingService
from app.services.home_automation_service import HomeAutomationService


logger = logging.getLogger(__name__)


class SmartHomeController(BaseController):
    """
    Controller for Alexa Smart Home Skill API v3.

    Handles:
    - Discovery: Returns scenes as Smart Home endpoints
    - Activate/Deactivate: Triggers scenes via Home Assistant
    - AcceptGrant: Account linking acknowledgement
    """

    def __init__(
        self,
        oauth_service: OAuthService,
        scene_mapping_service: SceneWebhookMappingService,
        ha_service: HomeAutomationService,
        home_service=None,
        url_prefix: str = '/alexa/smarthome'
    ):
        """
        Initialize Smart Home controller.

        Args:
            oauth_service: OAuth service for token validation
            scene_mapping_service: Scene webhook mapping service
            ha_service: Home automation service
            home_service: Home service (optional, for future use)
            url_prefix: URL prefix for routes
        """
        super().__init__('alexa_smarthome', url_prefix)
        self.oauth_service = oauth_service
        self.scene_mapping_service = scene_mapping_service
        self.ha_service = ha_service
        self.home_service = home_service

        self._register_routes()

    def _register_routes(self) -> None:
        """Register Smart Home routes."""
        self.blueprint.add_url_rule(
            '',
            'handle_directive',
            self.handle_directive,
            methods=['POST']
        )

    def handle_directive(self):
        """
        Main Smart Home directive handler.

        Routes directives to appropriate handlers based on namespace + name.
        """
        try:
            directive = SmartHomeDirective.from_dict(self.get_request_json())
            logger.info(f"Smart Home directive: {directive.namespace}/{directive.name}")

            # Route based on namespace + name
            if directive.namespace == 'Alexa.Discovery' and directive.name == 'Discover':
                response = self._handle_discovery(directive)

            elif directive.namespace == 'Alexa.SceneController' and directive.name == 'Activate':
                response = self._handle_activate(directive)

            elif directive.namespace == 'Alexa.SceneController' and directive.name == 'Deactivate':
                response = self._handle_deactivate(directive)

            elif directive.namespace == 'Alexa.Authorization' and directive.name == 'AcceptGrant':
                response = self._handle_accept_grant(directive)

            else:
                logger.warning(f"Unsupported directive: {directive.namespace}/{directive.name}")
                response = SmartHomeResponse.error_response(
                    message_id=directive.message_id,
                    error_type='INTERNAL_ERROR',
                    message=f"Unsupported directive: {directive.namespace}/{directive.name}"
                )

            return jsonify(response)

        except Exception as e:
            logger.error(f"Error processing Smart Home directive: {str(e)}", exc_info=True)
            response = SmartHomeResponse.error_response(
                message_id='unknown',
                error_type='INTERNAL_ERROR',
                message=f"Internal error: {str(e)}"
            )
            return jsonify(response), 500

    def _handle_discovery(self, directive: SmartHomeDirective) -> dict:
        """
        Handle Alexa.Discovery/Discover directive.

        Validates the bearer token, retrieves all smarthome-enabled scenes
        for the home, and returns them as Smart Home endpoints.

        Args:
            directive: Parsed Smart Home directive

        Returns:
            Discovery response dict
        """
        # Validate token
        home_id = self.oauth_service.validate_token(directive.bearer_token)
        if not home_id:
            return SmartHomeResponse.error_response(
                message_id=directive.message_id,
                error_type='INVALID_AUTHORIZATION_CREDENTIAL',
                message='Invalid or expired access token'
            )

        # Get all scene mappings for this home
        scenes = self.scene_mapping_service.list_scenes_for_home(home_id)

        # Filter to smarthome_enabled and active scenes
        enabled_scenes = [
            s for s in scenes
            if s.is_active and getattr(s, 'smarthome_enabled', True)
        ]

        # Build endpoints
        endpoints = []
        for scene in enabled_scenes:
            endpoint_id = f"{home_id}:{scene.scene_name}"
            friendly_name = scene.scene_name.replace('_', ' ').title()
            endpoints.append(
                SmartHomeResponse.build_scene_endpoint(
                    endpoint_id=endpoint_id,
                    friendly_name=friendly_name
                )
            )

        logger.info(f"Discovery: {len(endpoints)} endpoints for home {home_id}")
        return SmartHomeResponse.discovery_response(endpoints)

    def _handle_activate(self, directive: SmartHomeDirective) -> dict:
        """
        Handle Alexa.SceneController/Activate directive.

        Validates token, extracts scene from endpoint ID, triggers via HA.

        Args:
            directive: Parsed Smart Home directive

        Returns:
            ActivationStarted response dict
        """
        # Validate token
        home_id = self.oauth_service.validate_token(directive.bearer_token)
        if not home_id:
            return SmartHomeResponse.error_response(
                message_id=directive.message_id,
                error_type='INVALID_AUTHORIZATION_CREDENTIAL',
                message='Invalid or expired access token'
            )

        # Parse endpoint_id to extract scene_name
        try:
            _, scene_name = directive.endpoint_id.split(':', 1)
        except (ValueError, AttributeError):
            return SmartHomeResponse.error_response(
                message_id=directive.message_id,
                error_type='NO_SUCH_ENDPOINT',
                message=f'Invalid endpoint ID: {directive.endpoint_id}'
            )

        # Look up webhook_id for this scene
        webhook_id = self.scene_mapping_service.get_webhook_for_scene(home_id, scene_name)

        # Trigger scene via Home Assistant
        self.ha_service.trigger_scene(
            scene_id=scene_name,
            home_id=home_id,
            source='Alexa Smart Home',
            webhook_id=webhook_id
        )

        return SmartHomeResponse.activation_started(
            message_id=directive.message_id,
            correlation_token=directive.correlation_token,
            endpoint_id=directive.endpoint_id
        )

    def _handle_deactivate(self, directive: SmartHomeDirective) -> dict:
        """
        Handle Alexa.SceneController/Deactivate directive.

        Looks for a corresponding deactivation scene (e.g., "decorations off"
        for "decorations on"). If not found, triggers with deactivate prefix.

        Args:
            directive: Parsed Smart Home directive

        Returns:
            DeactivationStarted response dict
        """
        # Validate token
        home_id = self.oauth_service.validate_token(directive.bearer_token)
        if not home_id:
            return SmartHomeResponse.error_response(
                message_id=directive.message_id,
                error_type='INVALID_AUTHORIZATION_CREDENTIAL',
                message='Invalid or expired access token'
            )

        # Parse endpoint_id to extract scene_name
        try:
            _, scene_name = directive.endpoint_id.split(':', 1)
        except (ValueError, AttributeError):
            return SmartHomeResponse.error_response(
                message_id=directive.message_id,
                error_type='NO_SUCH_ENDPOINT',
                message=f'Invalid endpoint ID: {directive.endpoint_id}'
            )

        # Try to find a deactivation scene
        # Convention: "X on" -> "X off", or "no X"
        deactivate_scene_name = self._find_deactivation_scene(home_id, scene_name)

        if deactivate_scene_name:
            webhook_id = self.scene_mapping_service.get_webhook_for_scene(home_id, deactivate_scene_name)
            self.ha_service.trigger_scene(
                scene_id=deactivate_scene_name,
                home_id=home_id,
                source='Alexa Smart Home',
                webhook_id=webhook_id
            )
        else:
            # No deactivation scene found; trigger original with deactivate prefix
            webhook_id = self.scene_mapping_service.get_webhook_for_scene(home_id, scene_name)
            self.ha_service.trigger_scene(
                scene_id=f"deactivate_{scene_name}",
                home_id=home_id,
                source='Alexa Smart Home',
                webhook_id=webhook_id
            )

        return SmartHomeResponse.deactivation_started(
            message_id=directive.message_id,
            correlation_token=directive.correlation_token,
            endpoint_id=directive.endpoint_id
        )

    def _find_deactivation_scene(self, home_id: str, scene_name: str) -> str:
        """
        Find the deactivation scene for a given scene.

        Looks for common patterns:
        - "X on" -> "X off"
        - "X" -> "no X"

        Args:
            home_id: Home identifier
            scene_name: Original scene name

        Returns:
            Deactivation scene name, or None if not found
        """
        candidates = []

        # "X on" -> "X off"
        if scene_name.endswith(' on'):
            candidates.append(scene_name[:-3] + ' off')

        # Try "no X" variant
        candidates.append(f"no {scene_name}")

        # Check each candidate
        for candidate in candidates:
            webhook_id = self.scene_mapping_service.get_webhook_for_scene(home_id, candidate)
            if webhook_id:
                logger.info(f"Found deactivation scene: {scene_name} -> {candidate}")
                return candidate

        logger.info(f"No deactivation scene found for '{scene_name}', using prefix fallback")
        return None

    def _handle_accept_grant(self, directive: SmartHomeDirective) -> dict:
        """
        Handle Alexa.Authorization/AcceptGrant directive.

        Simply acknowledges the grant. No LWA token exchange needed
        since we manage our own OAuth tokens.

        Args:
            directive: Parsed Smart Home directive

        Returns:
            AcceptGrant.Response dict
        """
        logger.info("AcceptGrant received - acknowledged")
        return SmartHomeResponse.accept_grant_response()
