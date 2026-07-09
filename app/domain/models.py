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
        password_hash: Hashed login password for mobile app login (None = login disabled)
    """
    user_id: str
    username: str
    full_name: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    email: Optional[str] = None
    password_hash: Optional[str] = None

    def check_password(self, password: str) -> bool:
        """Verify a plain-text password against the stored hash."""
        if not self.password_hash:
            return False
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plain-text password (pbkdf2:sha256, same scheme as AdminUser)."""
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method='pbkdf2:sha256')


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
        test_mode: If True, skip Home Assistant integration (for testing)
        created_at: When the home was registered
        updated_at: When the home configuration was last updated
    """
    home_id: str
    user_id: str
    name: str
    ha_url: str
    ha_webhook_id: str
    is_active: bool = True
    test_mode: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


@dataclass
class SceneWebhookMapping:
    """
    Maps a scene name to a Home Assistant webhook ID for a specific home.

    Each home can have multiple scenes, each with its own HA webhook endpoint.
    When a user activates a scene via Alexa, the system looks up the webhook_id
    for that scene at that home and calls the corresponding HA webhook.

    Attributes:
        id: Unique mapping identifier (UUID)
        home_id: Home this scene belongs to
        scene_name: Human-friendly scene name (e.g., "decorations on", "night scene")
        webhook_id: HA webhook ID for this scene (e.g., "decorations_on_1751404299018")
        is_active: Whether this scene mapping is active
        created_at: When the mapping was created
        updated_at: When the mapping was last updated
    """
    id: str
    home_id: str
    scene_name: str
    webhook_id: str
    is_active: bool = True
    smarthome_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


@dataclass
class AlexaUserMapping:
    """
    Alexa user to home mapping entity.

    Maps Amazon Alexa user IDs to home IDs for multi-tenant support.
    Allows multiple Alexa users to use the skill with their own homes.

    Attributes:
        alexa_user_id: Amazon user ID from Alexa (can be very long, up to 500 chars)
        home_id: Home this Alexa user is mapped to
        created_at: When the mapping was created
        updated_at: When the mapping was last updated
    """
    alexa_user_id: str
    home_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


@dataclass
class FavoriteDevice:
    """
    A user's favorited Home Assistant item — device, scene, script, automation,
    or raw entity — pinned for quick access on the mobile dashboard.

    `entity_id` is always populated (it's the trigger target). For favorites
    added at the device level, `entity_id` holds the device's resolved primary
    entity, and `device_id` plus `kind="device"` capture the original intent.

    The (user_ref, home_id, entity_id) tuple is unique — favoriting "Den Lamp"
    as a device and `light.den_lamp` as an entity collide on the resolved
    entity_id, which is correct (they activate the same HA service call).

    Attributes:
        id: Unique row identifier (UUID).
        user_ref: External user reference (matches enrollments.user_ref).
        home_id: Home this favorite lives in.
        entity_id: HA entity_id used at trigger time. Always "<domain>.<suffix>".
        friendly_name: Human-friendly label cached at add-time.
        domain: HA domain extracted from entity_id, e.g. "light", "scene", "lock".
        kind: One of {"device","entity","scene","script","automation"}.
              Captures user intent at add-time and drives the mobile UI.
        device_id: HA device_registry id (32-char hex), if favorited as device.
        primary_entity_id: same as entity_id for device favorites; null otherwise.
                           Stored for clarity / future-compat.
        position: Sort order within (user_ref, home_id); lower = earlier.
        created_at: When the favorite was added.
    """
    id: str
    user_ref: str
    home_id: str
    entity_id: str
    friendly_name: str
    domain: str
    kind: str = "entity"
    device_id: Optional[str] = None
    primary_entity_id: Optional[str] = None
    position: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class OAuthToken:
    """
    OAuth token entity for Smart Home API authorization.

    Stores OAuth2 tokens issued during Alexa account linking,
    used to authenticate Smart Home API directive requests.

    Attributes:
        id: Unique token identifier (UUID)
        home_id: Home this token is associated with
        access_token: OAuth2 access token
        refresh_token: OAuth2 refresh token
        token_type: Token type (default: bearer)
        expires_at: When the access token expires
        amazon_user_id: Optional Amazon user ID from account linking
        created_at: When the token was created
        updated_at: When the token was last updated
    """
    id: str
    home_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime = field(default_factory=datetime.now)
    amazon_user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
