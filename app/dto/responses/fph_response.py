"""
FutureProof Homes response DTOs

Build FutureProof Homes API responses.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.dto.base import BaseDTO


@dataclass
class FPHAuthResponse(BaseDTO):
    """
    FutureProof Homes authentication response.

    Response for /auth/request endpoint.

    Attributes:
        status: Response status ("challenge")
        speech: Text for voice assistant to speak
        challenge: The challenge phrase user must repeat
    """
    status: str
    speech: str
    challenge: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON response."""
        return {
            "status": self.status,
            "speech": self.speech,
            "challenge": self.challenge
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHAuthResponse':
        """Parse from JSON."""
        return cls(
            status=data.get("status", ""),
            speech=data.get("speech", ""),
            challenge=data.get("challenge", "")
        )

    @classmethod
    def create(cls, challenge_phrase: str) -> 'FPHAuthResponse':
        """
        Create auth response from challenge phrase.

        Args:
            challenge_phrase: Challenge phrase to include

        Returns:
            FPHAuthResponse
        """
        return cls(
            status="challenge",
            speech=f"Security check. Please say: {challenge_phrase}",
            challenge=challenge_phrase
        )


@dataclass
class FPHVerifyResponse(BaseDTO):
    """
    FutureProof Homes verification response.

    Response for /auth/verify endpoint.

    Attributes:
        status: Response status ("approved" or "denied")
        speech: Text for voice assistant to speak
        intent: Intent to execute (if approved)
        reason: Denial reason (if denied)
        attempts_remaining: Attempts remaining (if denied with mismatch)
    """
    status: str
    speech: str
    intent: Optional[str] = None
    reason: Optional[str] = None
    attempts_remaining: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON response."""
        result = {
            "status": self.status,
            "speech": self.speech
        }

        if self.intent is not None:
            result["intent"] = self.intent

        if self.reason is not None:
            result["reason"] = self.reason

        if self.attempts_remaining is not None:
            result["attempts_remaining"] = self.attempts_remaining

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHVerifyResponse':
        """Parse from JSON."""
        return cls(
            status=data.get("status", ""),
            speech=data.get("speech", ""),
            intent=data.get("intent"),
            reason=data.get("reason"),
            attempts_remaining=data.get("attempts_remaining")
        )

    @classmethod
    def approved(cls, intent: str) -> 'FPHVerifyResponse':
        """
        Create approved response.

        Args:
            intent: Intent to execute

        Returns:
            FPHVerifyResponse with approved status
        """
        return cls(
            status="approved",
            speech="Voice verified.",
            intent=intent
        )

    @classmethod
    def denied(cls, reason: str, message: str, attempts_remaining: Optional[int] = None) -> 'FPHVerifyResponse':
        """
        Create denied response.

        Args:
            reason: Denial reason (no_challenge, expired, max_attempts, mismatch)
            message: Human-readable message
            attempts_remaining: Attempts remaining (for mismatch only)

        Returns:
            FPHVerifyResponse with denied status
        """
        return cls(
            status="denied",
            speech=message,
            reason=reason,
            attempts_remaining=attempts_remaining
        )


@dataclass
class FPHCancelResponse(BaseDTO):
    """
    FutureProof Homes cancel response.

    Response for /auth/cancel endpoint.

    Attributes:
        status: Response status ("cancelled")
        speech: Text for voice assistant to speak
    """
    status: str
    speech: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON response."""
        return {
            "status": self.status,
            "speech": self.speech
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHCancelResponse':
        """Parse from JSON."""
        return cls(
            status=data.get("status", ""),
            speech=data.get("speech", "")
        )

    @classmethod
    def create(cls) -> 'FPHCancelResponse':
        """Create cancel response."""
        return cls(
            status="cancelled",
            speech="Security check cancelled."
        )


@dataclass
class FPHErrorResponse(BaseDTO):
    """
    FutureProof Homes error response.

    Attributes:
        error: Error message
    """
    error: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON response."""
        return {"error": self.error}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FPHErrorResponse':
        """Parse from JSON."""
        return cls(error=data.get("error", ""))

    @classmethod
    def create(cls, message: str) -> 'FPHErrorResponse':
        """Create error response."""
        return cls(error=message)
