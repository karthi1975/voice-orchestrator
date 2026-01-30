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
    """
    username: str
    full_name: str
    email: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateUserRequest':
        """Create from dictionary."""
        return cls(
            username=require_field(data, 'username'),
            full_name=require_field(data, 'full_name'),
            email=get_field(data, 'email')
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UpdateUserRequest':
        """Create from dictionary."""
        return cls(
            username=get_field(data, 'username'),
            full_name=get_field(data, 'full_name'),
            email=get_field(data, 'email')
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
        return cls(
            home_id=require_field(data, 'home_id'),
            user_id=require_field(data, 'user_id'),
            name=require_field(data, 'name'),
            ha_url=require_field(data, 'ha_url'),
            ha_webhook_id=require_field(data, 'ha_webhook_id')
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
        return cls(
            name=get_field(data, 'name'),
            ha_url=get_field(data, 'ha_url'),
            ha_webhook_id=get_field(data, 'ha_webhook_id'),
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
