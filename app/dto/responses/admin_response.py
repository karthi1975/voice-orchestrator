"""
Admin response DTOs

Data transfer objects for admin API responses.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from app.dto.base import BaseDTO
from app.domain.models import User, Home


@dataclass
class UserResponse(BaseDTO):
    """
    Response containing user data.

    Attributes:
        user_id: User ID
        username: Username
        full_name: Full name
        email: Email address
        is_active: Active status
        created_at: Creation timestamp
    """
    user_id: str
    username: str
    full_name: str
    email: Optional[str]
    is_active: bool
    created_at: str

    @classmethod
    def from_model(cls, user: User) -> 'UserResponse':
        """
        Create response from User domain model.

        Args:
            user: User domain model

        Returns:
            UserResponse
        """
        return cls(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at.isoformat()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserResponse':
        """Create from dictionary (not typically used for responses)."""
        return cls(
            user_id=data['user_id'],
            username=data['username'],
            full_name=data['full_name'],
            email=data.get('email'),
            is_active=data['is_active'],
            created_at=data['created_at']
        )


@dataclass
class HomeResponse(BaseDTO):
    """
    Response containing home data.

    Attributes:
        home_id: Home ID
        user_id: Owner user ID
        name: Home name
        ha_url: Home Assistant URL
        ha_webhook_id: HA webhook ID
        is_active: Active status
        test_mode: Test mode flag (skips HA integration if True)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    home_id: str
    user_id: str
    name: str
    ha_url: str
    ha_webhook_id: str
    is_active: bool
    test_mode: bool
    created_at: str
    updated_at: Optional[str]

    @classmethod
    def from_model(cls, home: Home) -> 'HomeResponse':
        """
        Create response from Home domain model.

        Args:
            home: Home domain model

        Returns:
            HomeResponse
        """
        return cls(
            home_id=home.home_id,
            user_id=home.user_id,
            name=home.name,
            ha_url=home.ha_url,
            ha_webhook_id=home.ha_webhook_id,
            is_active=home.is_active,
            test_mode=home.test_mode,
            created_at=home.created_at.isoformat(),
            updated_at=home.updated_at.isoformat() if home.updated_at else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'home_id': self.home_id,
            'user_id': self.user_id,
            'name': self.name,
            'ha_url': self.ha_url,
            'ha_webhook_id': self.ha_webhook_id,
            'is_active': self.is_active,
            'test_mode': self.test_mode,
            'created_at': self.created_at
        }
        if self.updated_at:
            result['updated_at'] = self.updated_at
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HomeResponse':
        """Create from dictionary (not typically used for responses)."""
        return cls(
            home_id=data['home_id'],
            user_id=data['user_id'],
            name=data['name'],
            ha_url=data['ha_url'],
            ha_webhook_id=data['ha_webhook_id'],
            is_active=data['is_active'],
            test_mode=data.get('test_mode', False),
            created_at=data['created_at'],
            updated_at=data.get('updated_at')
        )


@dataclass
class UserListResponse(BaseDTO):
    """
    Response containing list of users.

    Attributes:
        users: List of user responses
        total: Total count
    """
    users: List[UserResponse]
    total: int

    @classmethod
    def from_models(cls, users: List[User]) -> 'UserListResponse':
        """
        Create response from list of User models.

        Args:
            users: List of User domain models

        Returns:
            UserListResponse
        """
        return cls(
            users=[UserResponse.from_model(u) for u in users],
            total=len(users)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'users': [u.to_dict() for u in self.users],
            'total': self.total
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserListResponse':
        """Create from dictionary (not typically used for responses)."""
        return cls(
            users=[UserResponse.from_dict(u) for u in data['users']],
            total=data['total']
        )


@dataclass
class HomeListResponse(BaseDTO):
    """
    Response containing list of homes.

    Attributes:
        homes: List of home responses
        total: Total count
    """
    homes: List[HomeResponse]
    total: int

    @classmethod
    def from_models(cls, homes: List[Home]) -> 'HomeListResponse':
        """
        Create response from list of Home models.

        Args:
            homes: List of Home domain models

        Returns:
            HomeListResponse
        """
        return cls(
            homes=[HomeResponse.from_model(h) for h in homes],
            total=len(homes)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'homes': [h.to_dict() for h in self.homes],
            'total': self.total
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HomeListResponse':
        """Create from dictionary (not typically used for responses)."""
        return cls(
            homes=[HomeResponse.from_dict(h) for h in data['homes']],
            total=data['total']
        )


@dataclass
class ErrorResponse(BaseDTO):
    """
    Response for errors.

    Attributes:
        error: Error message
        details: Optional additional details
    """
    error: str
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {'error': self.error}
        if self.details:
            result['details'] = self.details
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorResponse':
        """Create from dictionary."""
        return cls(
            error=data['error'],
            details=data.get('details')
        )
