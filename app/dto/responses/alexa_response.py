"""
Alexa response DTOs

Build Alexa Skill responses.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from app.dto.base import BaseDTO


@dataclass
class AlexaResponse(BaseDTO):
    """
    Alexa skill response builder.

    Attributes:
        speech_text: Text for Alexa to speak
        should_end_session: Whether to end the session after response
        card_title: Optional card title
        card_content: Optional card content
    """
    speech_text: str
    should_end_session: bool = True
    card_title: Optional[str] = None
    card_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Build Alexa response JSON.

        Returns:
            Alexa-formatted response dictionary

        Examples:
            >>> response = AlexaResponse("Hello", should_end_session=False)
            >>> data = response.to_dict()
            >>> data['response']['outputSpeech']['text']
            'Hello'
        """
        response_obj = {
            'version': '1.0',
            'response': {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': self.speech_text
                },
                'shouldEndSession': self.should_end_session
            }
        }

        # Add card if provided
        if self.card_title or self.card_content:
            response_obj['response']['card'] = {
                'type': 'Simple',
                'title': self.card_title or 'Voice Authentication',
                'content': self.card_content or self.speech_text
            }

        return response_obj

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlexaResponse':
        """
        Parse from Alexa response JSON (rarely needed).

        Args:
            data: Alexa response JSON

        Returns:
            AlexaResponse instance
        """
        speech_text = data.get('response', {}).get('outputSpeech', {}).get('text', '')
        should_end_session = data.get('response', {}).get('shouldEndSession', True)

        card = data.get('response', {}).get('card', {})
        card_title = card.get('title')
        card_content = card.get('content')

        return cls(
            speech_text=speech_text,
            should_end_session=should_end_session,
            card_title=card_title,
            card_content=card_content
        )

    @classmethod
    def launch_response(cls) -> 'AlexaResponse':
        """
        Build launch response.

        Returns:
            AlexaResponse for skill launch
        """
        return cls(
            speech_text="Home security activated. Say night scene to begin.",
            should_end_session=False
        )

    @classmethod
    def help_response(cls) -> 'AlexaResponse':
        """
        Build help response.

        Returns:
            AlexaResponse for help intent
        """
        speech = (
            "This skill controls your Home Assistant with voice authentication. "
            "Say night scene, then repeat the security phrase I give you. "
            "What would you like to do?"
        )
        return cls(
            speech_text=speech,
            should_end_session=False
        )

    @classmethod
    def stop_response(cls) -> 'AlexaResponse':
        """
        Build stop/cancel response.

        Returns:
            AlexaResponse for stop intent
        """
        return cls(
            speech_text="Home security deactivated. Goodbye.",
            should_end_session=True
        )

    @classmethod
    def fallback_response(cls) -> 'AlexaResponse':
        """
        Build fallback response.

        Returns:
            AlexaResponse for fallback intent
        """
        speech = (
            "I didn't understand. You can say night scene to activate the night scene. "
            "What would you like to do?"
        )
        return cls(
            speech_text=speech,
            should_end_session=False
        )

    @classmethod
    def session_ended_response(cls) -> 'AlexaResponse':
        """
        Build session ended response.

        Returns:
            AlexaResponse for session end
        """
        return cls(
            speech_text="",
            should_end_session=True
        )

    @classmethod
    def error_response(cls, message: str = "Sorry, there was an error processing your request.") -> 'AlexaResponse':
        """
        Build error response.

        Args:
            message: Error message to speak

        Returns:
            AlexaResponse for error
        """
        return cls(
            speech_text=message,
            should_end_session=True
        )
