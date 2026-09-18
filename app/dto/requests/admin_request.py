"""
Admin request DTOs

Data transfer objects for admin API requests.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.dto.base import BaseDTO, require_field, get_field, ValidationError


@dataclass
class CreateUserRequest(BaseDTO):
    """
    Request to create a new user.

    Attributes:
        username: Unique username
        full_name: User's full name
        email: Optional email address
        user_id: Optional explicit user ID (align with an existing mobile
                 user_ref so historical favorites/enrollments stay attached)
        password: Optional plain-text password enabling mobile app login
    """
    username: str
    full_name: str
    email: Optional[str] = None
    user_id: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateUserRequest':
        """Create from dictionary."""
        return cls(
            username=require_field(data, 'username'),
            full_name=require_field(data, 'full_name'),
            email=get_field(data, 'email'),
            user_id=get_field(data, 'user_id'),
            password=get_field(data, 'password')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'username': self.username,
            'full_name': self.full_name
        }
        if self.email:
            result['email'] = self.email
        return result

    def validate(self) -> None:
        """Validate request data."""
        if not self.username or not self.username.strip():
            raise ValidationError("username cannot be empty")
        if not self.full_name or not self.full_name.strip():
            raise ValidationError("full_name cannot be empty")
        if self.email is not None and '@' not in self.email:
            raise ValidationError("email must be valid")


@dataclass
class UpdateUserRequest(BaseDTO):
    """
    Request to update a user.

    Attributes:
        username: New username (optional)
        full_name: New full name (optional)
        email: New email (optional)
    """
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    # default_home_id: absent = leave alone; null = clear; string = set
    default_home_id: Optional[str] = None
    clear_default_home: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UpdateUserRequest':
        """Create from dictionary."""
        has_default = isinstance(data, dict) and 'default_home_id' in data
        raw = data.get('default_home_id') if has_default else None
        return cls(
            username=get_field(data, 'username'),
            full_name=get_field(data, 'full_name'),
            email=get_field(data, 'email'),
            default_home_id=raw.strip() if isinstance(raw, str) and raw.strip() else None,
            clear_default_home=has_default and (raw is None or (isinstance(raw, str) and not raw.strip())),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.username is not None:
            result['username'] = self.username
        if self.full_name is not None:
            result['full_name'] = self.full_name
        if self.email is not None:
            result['email'] = self.email
        return result


@dataclass
class CreateHomeRequest(BaseDTO):
    """
    Request to register a new home.

    Attributes:
        home_id: Unique home identifier
        user_id: Owner user ID
        name: Home name
        ha_url: Home Assistant URL
        ha_webhook_id: HA webhook ID
    """
    home_id: str
    user_id: str
    name: str
    ha_url: str
    ha_webhook_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateHomeRequest':
        """Create from dictionary."""
        def _s(v):
            return v.strip() if isinstance(v, str) else v
        return cls(
            home_id=_s(require_field(data, 'home_id')),
            user_id=_s(require_field(data, 'user_id')),
            name=_s(require_field(data, 'name')),
            ha_url=_s(require_field(data, 'ha_url')),
            ha_webhook_id=_s(require_field(data, 'ha_webhook_id'))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'home_id': self.home_id,
            'user_id': self.user_id,
            'name': self.name,
            'ha_url': self.ha_url,
            'ha_webhook_id': self.ha_webhook_id
        }

    def validate(self) -> None:
        """Validate request data."""
        if not self.home_id or not self.home_id.strip():
            raise ValidationError("home_id cannot be empty")
        if not self.user_id or not self.user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValidationError("name cannot be empty")
        if not self.ha_url or not self.ha_url.strip():
            raise ValidationError("ha_url cannot be empty")
        if not self.ha_webhook_id or not self.ha_webhook_id.strip():
            raise ValidationError("ha_webhook_id cannot be empty")


@dataclass
class UpdateHomeRequest(BaseDTO):
    """
    Request to update a home.

    Attributes:
        name: New name (optional)
        ha_url: New HA URL (optional)
        ha_webhook_id: New webhook ID (optional)
        is_active: New active status (optional)
    """
    name: Optional[str] = None
    ha_url: Optional[str] = None
    ha_webhook_id: Optional[str] = None
    is_active: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UpdateHomeRequest':
        """Create from dictionary."""
        def _s(v):
            return v.strip() if isinstance(v, str) else v
        return cls(
            name=_s(get_field(data, 'name')),
            ha_url=_s(get_field(data, 'ha_url')),
            ha_webhook_id=_s(get_field(data, 'ha_webhook_id')),
            is_active=get_field(data, 'is_active')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.name is not None:
            result['name'] = self.name
        if self.ha_url is not None:
            result['ha_url'] = self.ha_url
        if self.ha_webhook_id is not None:
            result['ha_webhook_id'] = self.ha_webhook_id
        if self.is_active is not None:
            result['is_active'] = self.is_active
        return result


@dataclass
class CreateAlexaMappingRequest(BaseDTO):
    """
    Request to create a new Alexa user mapping.

    Attributes:
        alexa_user_id: Amazon user ID from Alexa
        home_id: Home ID to map to
    """
    alexa_user_id: str
    home_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateAlexaMappingRequest':
        """Create from dictionary."""
        return cls(
            alexa_user_id=require_field(data, 'alexa_user_id'),
            home_id=require_field(data, 'home_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'alexa_user_id': self.alexa_user_id,
            'home_id': self.home_id
        }

    def validate(self) -> None:
        """Validate request data."""
        if not self.alexa_user_id or not self.alexa_user_id.strip():
            raise ValidationError("alexa_user_id cannot be empty")
        if not self.home_id or not self.home_id.strip():
            raise ValidationError("home_id cannot be empty")


@dataclass
class UpdateAlexaMappingRequest(BaseDTO):
    """
    Request to update an Alexa user mapping.

    Attributes:
        home_id: New home ID to map to
    """
    home_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UpdateAlexaMappingRequest':
        """Create from dictionary."""
        return cls(
            home_id=require_field(data, 'home_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'home_id': self.home_id
        }

    def validate(self) -> None:
        """Validate request data."""
        if not self.home_id or not self.home_id.strip():
            raise ValidationError("home_id cannot be empty")


@dataclass
class CreateSceneWebhookMappingRequest(BaseDTO):
    """
    Request to create a new scene webhook mapping.

    Attributes:
        home_id: Home this scene belongs to
        scene_name: Human-friendly scene name
        webhook_id: HA webhook ID for this scene
    """
    home_id: str
    scene_name: str
    webhook_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateSceneWebhookMappingRequest':
        """Create from dictionary."""
        return cls(
            home_id=require_field(data, 'home_id'),
            scene_name=require_field(data, 'scene_name'),
            webhook_id=require_field(data, 'webhook_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'home_id': self.home_id,
            'scene_name': self.scene_name,
            'webhook_id': self.webhook_id
        }

    def validate(self) -> None:
        """Validate request data."""
        if not self.home_id or not self.home_id.strip():
            raise ValidationError("home_id cannot be empty")
        if not self.scene_name or not self.scene_name.strip():
            raise ValidationError("scene_name cannot be empty")
        if not self.webhook_id or not self.webhook_id.strip():
            raise ValidationError("webhook_id cannot be empty")


@dataclass
class UpdateSceneWebhookMappingRequest(BaseDTO):
    """
    Request to update a scene webhook mapping.

    Attributes:
        scene_name: New scene name (optional)
        webhook_id: New webhook ID (optional)
        is_active: New active status (optional)
    """
    scene_name: Optional[str] = None
    webhook_id: Optional[str] = None
    is_active: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UpdateSceneWebhookMappingRequest':
        """Create from dictionary."""
        return cls(
            scene_name=get_field(data, 'scene_name'),
            webhook_id=get_field(data, 'webhook_id'),
            is_active=get_field(data, 'is_active')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.scene_name is not None:
            result['scene_name'] = self.scene_name
        if self.webhook_id is not None:
            result['webhook_id'] = self.webhook_id
        if self.is_active is not None:
            result['is_active'] = self.is_active
        return result


@dataclass
class AddHomeMemberRequest(BaseDTO):
    """
    Request to attach a user to a home (shared home membership).

    Attributes:
        user_id: User to add
        role: "member" (default) or "owner"
    """
    user_id: str
    role: str = "member"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AddHomeMemberRequest':
        """Create from dictionary."""
        def _s(v):
            return v.strip() if isinstance(v, str) else v
        return cls(
            user_id=_s(require_field(data, 'user_id')),
            role=_s(get_field(data, 'role', 'member')) or 'member',
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {'user_id': self.user_id, 'role': self.role}

    def validate(self) -> None:
        """Validate request data."""
        if not self.user_id or not str(self.user_id).strip():
            raise ValidationError("user_id cannot be empty")
        if self.role not in ('member', 'owner'):
            raise ValidationError("role must be 'member' or 'owner'")


@dataclass
class CreateHomeInviteRequest(BaseDTO):
    """
    Request to generate an OTP-style invite code for a home.

    Attributes:
        role: Role granted on redeem ("member" default, or "owner")
        expires_in_hours: Validity window (default 168 = 7 days, max 8760)
        max_uses: How many accounts may redeem it (default 1, max 100)
    """
    role: str = "member"
    expires_in_hours: Optional[int] = None
    max_uses: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateHomeInviteRequest':
        """Create from dictionary (all fields optional)."""
        data = data or {}
        role = get_field(data, 'role', 'member')
        return cls(
            role=(role.strip().lower() if isinstance(role, str) else 'member') or 'member',
            expires_in_hours=get_field(data, 'expires_in_hours', None),
            max_uses=get_field(data, 'max_uses', 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {'role': self.role, 'expires_in_hours': self.expires_in_hours,
                'max_uses': self.max_uses}

    def validate(self) -> None:
        """Validate request data."""
        if self.role not in ('member', 'owner'):
            raise ValidationError("role must be 'member' or 'owner'")
        if self.expires_in_hours is not None:
            if isinstance(self.expires_in_hours, bool) or \
                    not isinstance(self.expires_in_hours, int) or \
                    not 1 <= self.expires_in_hours <= 8760:
                raise ValidationError("expires_in_hours must be an integer 1-8760")
        if isinstance(self.max_uses, bool) or not isinstance(self.max_uses, int) \
                or not 1 <= self.max_uses <= 100:
            raise ValidationError("max_uses must be an integer 1-100")
