"""
FutureProof Homes controller

Thin HTTP layer for FutureProof Homes integration.
All business logic delegated to services.
"""

import logging
from app.controllers.base_controller import BaseController
from app.dto.requests.fph_request import FPHAuthRequest, FPHVerifyRequest, FPHCancelRequest
from app.dto.responses.fph_response import (
    FPHAuthResponse,
    FPHVerifyResponse,
    FPHCancelResponse,
    FPHErrorResponse
)
from app.services.authentication_service import (
    AuthenticationService,
    AuthenticationRequest,
    VerificationRequest
)
from app.domain.enums import ClientType
from app.services.challenge_service import ChallengeSettings


logger = logging.getLogger(__name__)


class FutureProofHomesController(BaseController):
    """
    Controller for FutureProof Homes integration.

    Endpoints:
    - POST /auth/request - Request voice challenge
    - POST /auth/verify - Verify spoken response
    - POST /auth/cancel - Cancel pending authentication
    - GET /auth/status - Debug status endpoint

    All business logic delegated to AuthenticationService.
    """

    def __init__(
        self,
        auth_service: AuthenticationService,
        challenge_settings: ChallengeSettings,
        url_prefix: str = '/futureproofhome'
    ):
        """
        Initialize FutureProof Homes controller.

        Args:
            auth_service: Authentication service
            challenge_settings: Challenge configuration
            url_prefix: URL prefix for routes
        """
        super().__init__('futureproofhome', url_prefix)
        self.auth_service = auth_service
        self.challenge_settings = challenge_settings

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all FutureProof Homes routes."""
        self.blueprint.add_url_rule(
            '/auth/request',
            'auth_request',
            self.handle_auth_request,
            methods=['POST']
        )

        self.blueprint.add_url_rule(
            '/auth/verify',
            'auth_verify',
            self.handle_auth_verify,
            methods=['POST']
        )

        self.blueprint.add_url_rule(
            '/auth/cancel',
            'auth_cancel',
            self.handle_auth_cancel,
            methods=['POST']
        )

        self.blueprint.add_url_rule(
            '/auth/status',
            'auth_status',
            self.handle_auth_status,
            methods=['GET']
        )

    def handle_auth_request(self):
        """
        Handle authentication request.

        Request: {"home_id": "home_1", "intent": "night_scene"}
        Response: {"status": "challenge", "speech": "...", "challenge": "ocean four"}
        """
        # Parse request (ValidationError will propagate to blueprint error handler)
        request_data = self.get_request_json()
        fph_request = FPHAuthRequest.from_dict(request_data)

        logger.info(f"FPH auth request - home_id: {fph_request.home_id}, intent: {fph_request.intent}")

        # Request authentication
        auth_request = AuthenticationRequest(
            identifier=fph_request.home_id,
            client_type=ClientType.FUTUREPROOFHOME,
            intent=fph_request.intent
        )

        auth_response = self.auth_service.request_authentication(auth_request)

        # Build FPH response
        response = FPHAuthResponse.create(auth_response.challenge_phrase)

        return self.json_response(response.to_dict())

    def handle_auth_verify(self):
        """
        Handle authentication verification.

        Request: {"home_id": "home_1", "response": "ocean four"}
        Success Response: {"status": "approved", "speech": "...", "intent": "night_scene"}
        Denied Response: {"status": "denied", "speech": "...", "reason": "mismatch", "attempts_remaining": 2}
        """
        # Parse request (ValidationError will propagate)
        request_data = self.get_request_json()
        fph_request = FPHVerifyRequest.from_dict(request_data)

        logger.info(f"FPH auth verify - home_id: {fph_request.home_id}, response: {fph_request.response}")

        # Verify response
        verify_request = VerificationRequest(
            identifier=fph_request.home_id,
            client_type=ClientType.FUTUREPROOFHOME,
            spoken_response=fph_request.response
        )

        result = self.auth_service.verify_response(verify_request)

        if result.is_valid:
            # Success
            response = FPHVerifyResponse.approved(result.intent)
            logger.info(f"FPH auth approved - home_id: {fph_request.home_id}, intent: {result.intent}")
        else:
            # Denied - determine reason
            reason, attempts_remaining = self._determine_denial_reason(result.message)

            response = FPHVerifyResponse.denied(
                reason=reason,
                message=result.message,
                attempts_remaining=attempts_remaining
            )

            logger.info(f"FPH auth denied - home_id: {fph_request.home_id}, reason: {reason}")

        return self.json_response(response.to_dict())

    def handle_auth_cancel(self):
        """
        Handle authentication cancellation.

        Request: {"home_id": "home_1"}
        Response: {"status": "cancelled", "speech": "Security check cancelled."}
        """
        # Parse request (ValidationError will propagate)
        request_data = self.get_request_json()
        fph_request = FPHCancelRequest.from_dict(request_data)

        logger.info(f"FPH auth cancel - home_id: {fph_request.home_id}")

        # Cancel authentication
        cancelled = self.auth_service.cancel_authentication(
            fph_request.home_id,
            ClientType.FUTUREPROOFHOME
        )

        response = FPHCancelResponse.create()

        return self.json_response(response.to_dict())

    def handle_auth_status(self):
        """
        Handle authentication status query (debug endpoint).

        Response: {
            "pending_challenges": {...},
            "config": {...},
            "total_pending": 1
        }
        """
        # Get all FutureProof Homes challenges
        from app.domain.enums import ClientType
        challenges = self.auth_service._challenge_service.list_challenges(
            client_type=ClientType.FUTUREPROOFHOME
        )

        pending_challenges = {}
        for challenge in challenges:
            from app.utils.time_utils import seconds_since_creation, get_current_time

            elapsed = seconds_since_creation(challenge.created_at)
            is_expired = challenge.is_expired()

            pending_challenges[challenge.identifier] = {
                "intent": challenge.intent,
                "attempts": challenge.attempts,
                "elapsed_seconds": round(elapsed, 1),
                "expired": is_expired
            }

        response = {
            "pending_challenges": pending_challenges,
            "config": {
                "expiry_seconds": self.challenge_settings.expiry_seconds,
                "max_attempts": self.challenge_settings.max_attempts
            },
            "total_pending": len(pending_challenges)
        }

        return self.json_response(response)

    def _determine_denial_reason(self, message: str) -> tuple[str, int | None]:
        """
        Determine denial reason from validation message.

        Args:
            message: Validation error message

        Returns:
            Tuple of (reason, attempts_remaining)
        """
        message_lower = message.lower()

        if "no active challenge" in message_lower:
            return "no_challenge", None
        elif "expired" in message_lower:
            return "expired", None
        elif "maximum" in message_lower:
            return "max_attempts", None
        else:
            # Mismatch - extract attempts remaining
            attempts_remaining = None
            if "attempts remaining" in message_lower:
                try:
                    # Extract number from message like "2 attempts remaining"
                    parts = message.split()
                    for i, part in enumerate(parts):
                        if part == "attempts" and i > 0:
                            attempts_remaining = int(parts[i-1])
                            break
                except (ValueError, IndexError):
                    pass

            return "mismatch", attempts_remaining
