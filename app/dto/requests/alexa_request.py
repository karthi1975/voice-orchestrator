"""
Alexa request DTOs

Parse incoming Alexa Skill requests.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.dto.base import BaseDTO, require_nested_field, get_nested_field


@dataclass
class AlexaRequest(BaseDTO):
    """
    Parsed Alexa skill request.

    Attributes:
        request_type: Type of request (LaunchRequest, IntentRequest, SessionEndedRequest)
        intent_name: Name of intent (if IntentRequest)
        session_id: Alexa session identifier
        slots: Intent slot values (if IntentRequest)
        raw_data: Original request data
    """
    request_type: str
    session_id: str
    intent_name: Optional[str] = None
    slots: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlexaRequest':
        """
        Parse Alexa request from JSON.

        Args:
            data: Alexa request JSON

        Returns:
            AlexaRequest instance

        Raises:
            ValidationError: If request is malformed

        Examples:
            >>> data = {
            ...     "request": {"type": "LaunchRequest"},
            ...     "session": {"sessionId": "session_123"}
            ... }
            >>> req = AlexaRequest.from_dict(data)
            >>> req.request_type
            'LaunchRequest'
        """
        # Extract required fields
        request_type = require_nested_field(data, "request", "type")
        session_id = require_nested_field(data, "session", "sessionId")

        # Extract optional fields
        intent_name = None
        slots = None

        if request_type == "IntentRequest":
            intent_name = get_nested_field(data, "request", "intent", "name")
            slots = get_nested_field(data, "request", "intent", "slots", default={})

        return cls(
            request_type=request_type,
            session_id=session_id,
            intent_name=intent_name,
            slots=slots,
            raw_data=data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (returns raw_data)."""
        return self.raw_data or {}

    def get_slot_value(self, slot_name: str, default: Any = None) -> Any:
        """
        Get value from intent slot.

        Args:
            slot_name: Name of slot
            default: Default value if slot not found

        Returns:
            Slot value or default

        Examples:
            >>> req = AlexaRequest(...)
            >>> req.get_slot_value("response", "")
            'ocean four'
        """
        if not self.slots or slot_name not in self.slots:
            return default

        slot = self.slots[slot_name]
        return slot.get("value", default)

    def is_launch_request(self) -> bool:
        """Check if this is a LaunchRequest."""
        return self.request_type == "LaunchRequest"

    def is_intent_request(self, intent_name: Optional[str] = None) -> bool:
        """
        Check if this is an IntentRequest.

        Args:
            intent_name: Optional specific intent to check for

        Returns:
            True if IntentRequest (and matches intent_name if provided)
        """
        if self.request_type != "IntentRequest":
            return False

        if intent_name:
            return self.intent_name == intent_name

        return True

    def is_session_ended_request(self) -> bool:
        """Check if this is a SessionEndedRequest."""
        return self.request_type == "SessionEndedRequest"
