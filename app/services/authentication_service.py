"""
Authentication service for orchestrating voice auth flows

High-level service that coordinates challenge-response authentication
for different client types (Alexa, FutureProof Homes).
"""

from typing import Optional, Tuple
from dataclasses import dataclass

from app.domain.enums import ClientType
from app.services.challenge_service import ChallengeService, ValidationResult


@dataclass
class AuthenticationRequest:
    """
    Request to start authentication flow.

    Attributes:
        identifier: Unique identifier (session_id or home_id)
        client_type: Type of client requesting auth
        intent: Optional intent to execute after successful auth
    """
    identifier: str
    client_type: ClientType
    intent: Optional[str] = None


@dataclass
class AuthenticationResponse:
    """
    Response from authentication request.

    Attributes:
        challenge_phrase: The phrase user must repeat
        speech_text: Text for voice assistant to speak
    """
    challenge_phrase: str
    speech_text: str


@dataclass
class VerificationRequest:
    """
    Request to verify spoken response.

    Attributes:
        identifier: Unique identifier
        client_type: Type of client
        spoken_response: User's spoken response to challenge
    """
    identifier: str
    client_type: ClientType
    spoken_response: str


class AuthenticationService:
    """
    Service for orchestrating voice authentication flows.

    Provides high-level operations for:
    - Starting authentication (generating challenges)
    - Verifying responses
    - Cancelling authentication

    Depends on:
    - ChallengeService: For challenge generation and validation
    """

    def __init__(self, challenge_service: ChallengeService):
        """
        Initialize authentication service.

        Args:
            challenge_service: Challenge service for core operations
        """
        self._challenge_service = challenge_service

    def request_authentication(
        self,
        request: AuthenticationRequest
    ) -> AuthenticationResponse:
        """
        Start authentication flow by generating a challenge.

        Args:
            request: Authentication request with identifier and client type

        Returns:
            AuthenticationResponse with challenge phrase and speech text

        Examples:
            >>> req = AuthenticationRequest("session_123", ClientType.ALEXA)
            >>> response = service.request_authentication(req)
            >>> print(response.speech_text)
            'Security check required. Please say: ocean four'
        """
        # Create challenge
        challenge = self._challenge_service.create_challenge(
            identifier=request.identifier,
            client_type=request.client_type,
            intent=request.intent
        )

        # Build response based on client type
        if request.client_type == ClientType.ALEXA:
            speech = f"Security check required. Please say: {challenge.phrase}"
        elif request.client_type == ClientType.FUTUREPROOFHOME:
            speech = f"Security check. Please say: {challenge.phrase}"
        else:
            speech = f"Please say: {challenge.phrase}"

        return AuthenticationResponse(
            challenge_phrase=challenge.phrase,
            speech_text=speech
        )

    def verify_response(
        self,
        request: VerificationRequest
    ) -> ValidationResult:
        """
        Verify user's spoken response against challenge.

        Args:
            request: Verification request with identifier and response

        Returns:
            ValidationResult with success status, message, and optional intent

        Examples:
            >>> req = VerificationRequest("session_123", ClientType.ALEXA, "ocean four")
            >>> result = service.verify_response(req)
            >>> print(result.is_valid)
            True
        """
        return self._challenge_service.validate_challenge(
            identifier=request.identifier,
            spoken_response=request.spoken_response,
            client_type=request.client_type
        )

    def cancel_authentication(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Cancel pending authentication.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            True if authentication was found and cancelled

        Examples:
            >>> service.cancel_authentication("session_123", ClientType.ALEXA)
            True
        """
        return self._challenge_service.cancel_challenge(identifier, client_type)

    def cleanup_expired(self) -> int:
        """
        Clean up expired challenges.

        Should be called periodically to prevent memory leaks.

        Returns:
            Number of challenges cleaned up

        Examples:
            >>> count = service.cleanup_expired()
            >>> print(f"Cleaned up {count} expired challenges")
        """
        return self._challenge_service.cleanup_expired_challenges()

    def get_authentication_status(
        self,
        identifier: str,
        client_type: ClientType
    ) -> Optional[dict]:
        """
        Get status of pending authentication.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            Status dict if challenge exists, None otherwise

        Examples:
            >>> status = service.get_authentication_status("home_1", ClientType.FUTUREPROOFHOME)
            >>> if status:
            ...     print(f"Attempts: {status['attempts']}")
        """
        challenge = self._challenge_service.get_challenge(identifier, client_type)

        if not challenge:
            return None

        return {
            'identifier': challenge.identifier,
            'client_type': challenge.client_type.value,
            'status': challenge.status.value,
            'attempts': challenge.attempts,
            'intent': challenge.intent,
            'created_at': challenge.created_at.isoformat(),
            'expires_at': challenge.expires_at.isoformat()
        }
