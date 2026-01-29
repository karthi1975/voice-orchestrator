"""
Challenge service for voice authentication

Business logic for challenge generation, validation, and lifecycle management.
Depends on repository interface for storage abstraction.
"""

import random
from datetime import datetime
from typing import Optional, Tuple, List
from dataclasses import dataclass

from app.domain.models import Challenge
from app.domain.enums import ClientType, ChallengeStatus
from app.repositories.challenge_repository import IChallengeRepository
from app.utils.text_normalizer import TextNormalizer
from app.utils.time_utils import get_current_time, calculate_expiry_time


@dataclass
class ChallengeSettings:
    """Configuration settings for challenge service."""
    words: List[str]
    numbers: List[str]
    expiry_seconds: int = 60
    max_attempts: int = 3


@dataclass
class ValidationResult:
    """
    Result of challenge validation.

    Attributes:
        is_valid: Whether validation succeeded
        message: Human-readable status message
        intent: Stored intent (if validation succeeded)
        challenge: The challenge that was validated (if found)
    """
    is_valid: bool
    message: str
    intent: Optional[str] = None
    challenge: Optional[Challenge] = None


class ChallengeService:
    """
    Service for managing voice authentication challenges.

    Handles:
    - Challenge generation
    - Challenge validation
    - Expired challenge cleanup
    - Attempt tracking

    Dependencies:
    - IChallengeRepository: Storage abstraction
    - TextNormalizer: Text normalization
    - ChallengeSettings: Configuration
    """

    def __init__(
        self,
        challenge_repository: IChallengeRepository,
        settings: ChallengeSettings,
        text_normalizer: Optional[TextNormalizer] = None
    ):
        """
        Initialize challenge service.

        Args:
            challenge_repository: Repository for challenge storage
            settings: Challenge configuration
            text_normalizer: Text normalizer (creates default if not provided)
        """
        self._repository = challenge_repository
        self._settings = settings
        self._normalizer = text_normalizer or TextNormalizer()

    def generate_challenge_phrase(self) -> str:
        """
        Generate a random challenge phrase.

        Combines a random word and number from configuration.

        Returns:
            Challenge phrase (e.g., "ocean four")

        Examples:
            >>> service.generate_challenge_phrase()
            'mountain seven'
        """
        word = random.choice(self._settings.words)
        number = random.choice(self._settings.numbers)
        return f"{word} {number}"

    def create_challenge(
        self,
        identifier: str,
        client_type: ClientType,
        intent: Optional[str] = None
    ) -> Challenge:
        """
        Create and store a new challenge.

        Args:
            identifier: Unique identifier (session_id or home_id)
            client_type: Type of client requesting challenge
            intent: Optional intent to execute after validation

        Returns:
            Created challenge

        Raises:
            ValueError: If challenge already exists for this identifier
        """
        # Generate challenge phrase
        phrase = self.generate_challenge_phrase()

        # Normalize phrase for consistent storage
        normalized_phrase = self._normalizer.normalize(phrase)

        # Create challenge entity
        current_time = get_current_time()
        expires_at = calculate_expiry_time(
            current_time,
            self._settings.expiry_seconds
        )

        challenge = Challenge(
            identifier=identifier,
            phrase=normalized_phrase,
            client_type=client_type,
            status=ChallengeStatus.PENDING,
            created_at=current_time,
            attempts=0,
            intent=intent,
            expires_at=expires_at
        )

        # Store challenge
        self._repository.add(challenge)

        return challenge

    def validate_challenge(
        self,
        identifier: str,
        spoken_response: str,
        client_type: ClientType
    ) -> ValidationResult:
        """
        Validate spoken response against stored challenge.

        Handles:
        - Challenge lookup
        - Expiry checking
        - Attempt tracking
        - Response normalization and comparison

        Args:
            identifier: Unique identifier
            spoken_response: User's spoken response
            client_type: Type of client

        Returns:
            ValidationResult with status, message, and optional intent
        """
        # Get challenge
        challenge = self._repository.get_by_identifier(identifier, client_type)

        if not challenge:
            return ValidationResult(
                is_valid=False,
                message="No active challenge found. Please start over.",
                intent=None,
                challenge=None
            )

        # Check expiry
        current_time = get_current_time()
        if challenge.is_expired(current_time):
            challenge.mark_expired()
            self._repository.delete_by_identifier(identifier, client_type)
            return ValidationResult(
                is_valid=False,
                message="Challenge expired. Please start over.",
                intent=None,
                challenge=challenge
            )

        # Increment attempts
        challenge.increment_attempts()

        # Check max attempts
        if challenge.attempts > self._settings.max_attempts:
            challenge.mark_failed()
            self._repository.delete_by_identifier(identifier, client_type)
            return ValidationResult(
                is_valid=False,
                message="Maximum attempts exceeded. Please start over.",
                intent=None,
                challenge=challenge
            )

        # Normalize and compare responses
        normalized_response = self._normalizer.normalize(spoken_response)
        expected = challenge.phrase

        if normalized_response == expected:
            # Success - mark validated and clean up
            challenge.mark_validated()
            intent = challenge.intent
            self._repository.delete_by_identifier(identifier, client_type)

            return ValidationResult(
                is_valid=True,
                message="Voice verified successfully",
                intent=intent,
                challenge=challenge
            )
        else:
            # Incorrect response
            remaining = self._settings.max_attempts - challenge.attempts

            if remaining > 0:
                # Update challenge with new attempt count
                self._repository.update(challenge)

                return ValidationResult(
                    is_valid=False,
                    message=f"Incorrect response. {remaining} attempts remaining.",
                    intent=None,
                    challenge=challenge
                )
            else:
                # Max attempts reached
                challenge.mark_failed()
                self._repository.delete_by_identifier(identifier, client_type)

                return ValidationResult(
                    is_valid=False,
                    message="Maximum attempts exceeded. Please start over.",
                    intent=None,
                    challenge=challenge
                )

    def cancel_challenge(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Cancel a pending challenge.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            True if challenge was found and cancelled, False otherwise
        """
        return self._repository.delete_by_identifier(identifier, client_type)

    def get_challenge(
        self,
        identifier: str,
        client_type: ClientType
    ) -> Optional[Challenge]:
        """
        Get challenge by identifier.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            Challenge if found, None otherwise
        """
        return self._repository.get_by_identifier(identifier, client_type)

    def cleanup_expired_challenges(
        self,
        before: Optional[datetime] = None
    ) -> int:
        """
        Clean up expired challenges.

        Args:
            before: Delete challenges expired before this time (defaults to now)

        Returns:
            Number of challenges deleted
        """
        if before is None:
            before = get_current_time()

        return self._repository.delete_expired(before)

    def list_challenges(
        self,
        client_type: Optional[ClientType] = None
    ) -> List[Challenge]:
        """
        List challenges, optionally filtered by client type.

        Args:
            client_type: Optional client type filter

        Returns:
            List of challenges
        """
        if client_type:
            return self._repository.list_by_client_type(client_type)
        return self._repository.list_all()

    def count_challenges(self, client_type: ClientType) -> int:
        """
        Count active challenges for a client type.

        Args:
            client_type: Type of client

        Returns:
            Number of active challenges
        """
        return self._repository.count_by_client_type(client_type)
