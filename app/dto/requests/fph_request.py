"""
FutureProof Homes request DTOs

Parse incoming FutureProof Homes API requests.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.dto.base import BaseDTO, require_field, get_field, ValidationError


@dataclass
class FPHAuthRequest(BaseDTO):
    """
    FutureProof Homes authentication request.

    Used for /auth/request endpoint.

    Attributes:
        home_id: Unique home identifier
        intent: Intent to execute after successful authentication
    """
    home_id: str
    intent: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHAuthRequest':
        """
        Parse from JSON.

        Args:
            data: Request JSON

        Returns:
            FPHAuthRequest instance

        Raises:
            ValidationError: If required fields missing
        """
        home_id = require_field(data, "home_id")
        intent = require_field(data, "intent")

        return cls(home_id=home_id, intent=intent)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "home_id": self.home_id,
            "intent": self.intent
        }


@dataclass
class FPHVerifyRequest(BaseDTO):
    """
    FutureProof Homes verification request.

    Used for /auth/verify endpoint.

    Attributes:
        home_id: Unique home identifier
        response: User's spoken response to challenge
    """
    home_id: str
    response: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHVerifyRequest':
        """
        Parse from JSON.

        Args:
            data: Request JSON

        Returns:
            FPHVerifyRequest instance

        Raises:
            ValidationError: If required fields missing
        """
        home_id = require_field(data, "home_id")
        response = require_field(data, "response")

        return cls(home_id=home_id, response=response)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "home_id": self.home_id,
            "response": self.response
        }


@dataclass
class FPHCancelRequest(BaseDTO):
    """
    FutureProof Homes cancel request.

    Used for /auth/cancel endpoint.

    Attributes:
        home_id: Unique home identifier
    """
    home_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHCancelRequest':
        """
        Parse from JSON.

        Args:
            data: Request JSON

        Returns:
            FPHCancelRequest instance

        Raises:
            ValidationError: If required fields missing
        """
        home_id = require_field(data, "home_id")

        return cls(home_id=home_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"home_id": self.home_id}
