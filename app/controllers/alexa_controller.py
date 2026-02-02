"""
Alexa Skill controller

Thin HTTP layer for Alexa integration.
All business logic delegated to services.
"""

import logging
from flask import request
from app.controllers.base_controller import BaseController
from app.dto.requests.alexa_request import AlexaRequest
from app.dto.responses.alexa_response import AlexaResponse
from app.services.authentication_service import (
    AuthenticationService,
    AuthenticationRequest,
    VerificationRequest
)
from app.services.home_automation_service import HomeAutomationService, SceneTriggerRequest
from app.domain.enums import ClientType


logger = logging.getLogger(__name__)


class AlexaController(BaseController):
    """
    Controller for Alexa Skill integration.

    Handles:
    - Launch requests
    - Intent requests (NightScene, ChallengeResponse, Help, Stop, etc.)
    - Session end requests

    All business logic delegated to AuthenticationService and HomeAutomationService.
    """

    def __init__(
        self,
        auth_service: AuthenticationService,
        ha_service: HomeAutomationService,
        url_prefix: str = '/alexa'
    ):
        """
        Initialize Alexa controller.

        Args:
            auth_service: Authentication service
            ha_service: Home automation service
            url_prefix: URL prefix for routes
        """
        super().__init__('alexa', url_prefix)
        self.auth_service = auth_service
        self.ha_service = ha_service

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all Alexa routes."""
        self.blueprint.add_url_rule(
            '',
            'webhook',
            self.handle_webhook,
            methods=['POST']
        )

    def handle_webhook(self):
        """
        Main Alexa webhook handler.

        Processes all Alexa requests and returns appropriate responses.
        """
        try:
            # Parse request
            request_data = self.get_request_json()
            alexa_request = AlexaRequest.from_dict(request_data)

            logger.info(f"Alexa request: {alexa_request.request_type}")

            # Clean up expired challenges periodically
            self.auth_service.cleanup_expired()

            # Route to appropriate handler
            if alexa_request.is_launch_request():
                response = self._handle_launch()

            elif alexa_request.is_intent_request('NightSceneIntent'):
                response = self._handle_night_scene_intent(alexa_request)

            elif alexa_request.is_intent_request('ChallengeResponseIntent'):
                response = self._handle_challenge_response(alexa_request)

            elif alexa_request.is_intent_request('AMAZON.HelpIntent'):
                response = AlexaResponse.help_response()

            elif alexa_request.is_intent_request('AMAZON.StopIntent') or \
                 alexa_request.is_intent_request('AMAZON.CancelIntent'):
                response = AlexaResponse.stop_response()

            elif alexa_request.is_intent_request('AMAZON.FallbackIntent'):
                response = AlexaResponse.fallback_response()

            elif alexa_request.is_session_ended_request():
                response = AlexaResponse.session_ended_response()

            else:
                # Unknown request type
                response = AlexaResponse(
                    speech_text="I didn't understand that. Please try again.",
                    should_end_session=False
                )

            return self.json_response(response.to_dict())

        except Exception as e:
            logger.error(f"Error processing Alexa request: {str(e)}", exc_info=True)
            response = AlexaResponse.error_response()
            return self.json_response(response.to_dict())

    def _handle_launch(self) -> AlexaResponse:
        """
        Handle skill launch.

        Returns:
            AlexaResponse for launch
        """
        return AlexaResponse.launch_response()

    def _handle_night_scene_intent(self, alexa_request: AlexaRequest) -> AlexaResponse:
        """
        Handle night scene activation request.

        Args:
            alexa_request: Parsed Alexa request

        Returns:
            AlexaResponse with challenge
        """
        # Request authentication
        auth_request = AuthenticationRequest(
            identifier=alexa_request.session_id,
            client_type=ClientType.ALEXA,
            intent=None  # Intent is implicit for Alexa (night scene)
        )

        auth_response = self.auth_service.request_authentication(auth_request)

        # Build Alexa response
        return AlexaResponse(
            speech_text=auth_response.speech_text,
            should_end_session=False
        )

    def _handle_challenge_response(self, alexa_request: AlexaRequest) -> AlexaResponse:
        """
        Handle user's challenge response.

        Args:
            alexa_request: Parsed Alexa request

        Returns:
            AlexaResponse with validation result
        """
        # Extract spoken response from slot
        spoken_response = alexa_request.get_slot_value('response', '')

        logger.info(f"Challenge response: {spoken_response}")

        # Verify response
        verify_request = VerificationRequest(
            identifier=alexa_request.session_id,
            client_type=ClientType.ALEXA,
            spoken_response=spoken_response
        )

        result = self.auth_service.verify_response(verify_request)

        if result.is_valid:
            # Trigger Home Assistant scene
            # TODO: Map alexa_request.user_id to home_id from database
            # For now, use default home from environment or first home
            scene_result = self.ha_service.trigger_scene(
                scene_id='night_scene',
                home_id='karthi_test_home',  # Default for testing
                source='Alexa Voice Authentication'
            )

            if scene_result.success:
                speech = "Voice verified. Night scene activated."
            else:
                speech = f"Voice verified, but scene activation failed: {scene_result.message}"

            return AlexaResponse(
                speech_text=speech,
                should_end_session=True
            )
        else:
            # Validation failed
            speech = f"{result.message} Please try saying night scene again if you want to retry."
            return AlexaResponse(
                speech_text=speech,
                should_end_session=False
            )
