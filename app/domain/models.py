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
        home_id: Optional home identifier for multi-tenant isolation
        attempts: Number of validation attempts made
        intent: Optional intent to execute after successful validation
        expires_at: When the challenge expires (auto-calculated if not provided)
    """
    identifier: str
    phrase: str
    client_type: ClientType
    status: ChallengeStatus
    created_at: datetime
    home_id: Optional[str] = None
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
class User:
    """
    User entity for multi-tenant support.

    Represents a user who owns one or more homes.

    Attributes:
        user_id: Unique user identifier (UUID)
        username: Unique username
        email: Optional email address
        full_name: User's full name
        is_active: Whether the user account is active
        created_at: When the user was created
    """
    user_id: str
    username: str
    full_name: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    email: Optional[str] = None


@dataclass
class Home:
    """
    Home entity for multi-tenant support.

    Represents a physical home with its own Home Assistant instance.
    Each home belongs to a user and has its own HA URL and webhook configuration.

    Attributes:
        home_id: Unique home identifier (e.g., "home_1", "beach_house")
        user_id: Owner user ID (foreign key to User)
        name: Human-readable home name (e.g., "Main House")
        ha_url: Home Assistant URL for this home (e.g., "https://ha1.homeadapt.us")
        ha_webhook_id: Webhook ID for voice authentication (e.g., "voice_auth_scene")
        is_active: Whether the home is currently active
        created_at: When the home was registered
        updated_at: When the home configuration was last updated
    """
    home_id: str
    user_id: str
    name: str
    ha_url: str
    ha_webhook_id: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


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
