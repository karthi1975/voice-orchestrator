"""
Domain models for voice orchestrator

Core business entities that represent the problem domain.
These are pure Python objects with no dependencies on frameworks or infrastructure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from app.domain.enums import ClientType, ChallengeStatus


@dataclass
class Challenge:
    """
    Voice authentication challenge entity.

    Represents a voice challenge-response authentication attempt
    for a specific client (Alexa session or FutureProof Home).

    Attributes:
        identifier: Unique identifier (session_id for Alexa, home_id for FutureProof)
        phrase: The challenge phrase user must repeat (e.g., "ocean four")
        client_type: Type of client requesting authentication
        status: Current status of the challenge
        created_at: When the challenge was created
        attempts: Number of validation attempts made
        intent: Optional intent to execute after successful validation
        expires_at: When the challenge expires (auto-calculated if not provided)
    """
    identifier: str
    phrase: str
    client_type: ClientType
    status: ChallengeStatus
    created_at: datetime
    attempts: int = 0
    intent: Optional[str] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        """Calculate expires_at if not provided."""
        if self.expires_at is None:
            # Default expiry is 60 seconds from creation
            self.expires_at = self.created_at + timedelta(seconds=60)

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if challenge has expired.

        Args:
            current_time: Time to check against (defaults to now)

        Returns:
            True if challenge has expired
        """
        if current_time is None:
            current_time = datetime.now()

        return current_time > self.expires_at

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""
        self.attempts += 1

    def mark_validated(self) -> None:
        """Mark challenge as successfully validated."""
        self.status = ChallengeStatus.VALIDATED

    def mark_expired(self) -> None:
        """Mark challenge as expired."""
        self.status = ChallengeStatus.EXPIRED

    def mark_failed(self) -> None:
        """Mark challenge as failed."""
        self.status = ChallengeStatus.FAILED


@dataclass
class Home:
    """
    Home entity for multi-tenant support.

    Represents a physical home with multiple users and voice devices.
    Future enhancement for Phase 7+ multi-tenancy.

    Attributes:
        home_id: Unique home identifier
        name: Human-readable home name
        created_at: When the home was registered
        is_active: Whether the home is currently active
    """
    home_id: str
    name: str
    created_at: datetime
    is_active: bool = True


@dataclass
class Scene:
    """
    Home automation scene entity.

    Represents a Home Assistant scene that can be triggered
    after successful voice authentication.

    Attributes:
        scene_id: Unique scene identifier
        name: Human-readable scene name
        home_id: Home this scene belongs to
        requires_auth: Whether this scene requires voice authentication
    """
    scene_id: str
    name: str
    home_id: str
    requires_auth: bool = True
