"""
Tests for multi-scene support in Alexa controller

Tests the full flow: SceneActivationIntent -> challenge -> auth -> scene-specific webhook
"""

import pytest
from unittest.mock import MagicMock, patch
from app.controllers.alexa_controller import AlexaController
from app.dto.requests.alexa_request import AlexaRequest
from app.services.authentication_service import AuthenticationService
from app.services.home_automation_service import HomeAutomationService


@pytest.fixture
def mock_auth_service():
    return MagicMock(spec=AuthenticationService)


@pytest.fixture
def mock_ha_service():
    return MagicMock(spec=HomeAutomationService)


@pytest.fixture
def controller(mock_auth_service, mock_ha_service):
    return AlexaController(
        auth_service=mock_auth_service,
        ha_service=mock_ha_service,
        url_prefix='/alexa'
    )


def make_intent_request(intent_name, slots=None, session_id="test_session", user_id="test_user"):
    """Helper to build an Alexa intent request dict."""
    request_data = {
        "session": {
            "sessionId": session_id,
            "user": {"userId": user_id}
        },
        "request": {
            "type": "IntentRequest",
            "intent": {
                "name": intent_name,
                "slots": slots or {}
            }
        }
    }
    return request_data


class TestSceneActivationIntent:

    def test_scene_activation_stores_intent(self, controller, mock_auth_service):
        """SceneActivationIntent should store scene_name in challenge intent field."""
        mock_auth_service.request_authentication.return_value = MagicMock(
            speech_text="Please say the security phrase: ocean four"
        )

        request_data = make_intent_request(
            "SceneActivationIntent",
            slots={"scene_name": {"value": "decorations on"}}
        )
        alexa_request = AlexaRequest.from_dict(request_data)

        response = controller._handle_scene_activation_intent(alexa_request)

        # Verify auth was requested with scene name as intent
        call_args = mock_auth_service.request_authentication.call_args
        auth_request = call_args[0][0]
        assert auth_request.intent == "decorations on"
        assert response.should_end_session is False

    def test_scene_activation_empty_scene_name(self, controller):
        """Missing scene_name slot should prompt user."""
        request_data = make_intent_request(
            "SceneActivationIntent",
            slots={"scene_name": {"value": ""}}
        )
        alexa_request = AlexaRequest.from_dict(request_data)

        response = controller._handle_scene_activation_intent(alexa_request)

        assert "Which scene" in response.speech_text
        assert response.should_end_session is False


class TestNightSceneIntentBackwardCompat:

    def test_night_scene_stores_intent(self, controller, mock_auth_service):
        """NightSceneIntent should now store 'night scene' as intent."""
        mock_auth_service.request_authentication.return_value = MagicMock(
            speech_text="Please say the security phrase: ocean four"
        )

        request_data = make_intent_request("NightSceneIntent")
        alexa_request = AlexaRequest.from_dict(request_data)

        controller._handle_night_scene_intent(alexa_request)

        call_args = mock_auth_service.request_authentication.call_args
        auth_request = call_args[0][0]
        assert auth_request.intent == "night scene"


class TestChallengeResponseWithSceneWebhook:

    @patch.object(AlexaController, '_get_home_id_for_alexa_user')
    @patch.object(AlexaController, '_get_scene_webhook')
    def test_successful_auth_triggers_scene_specific_webhook(
        self, mock_get_webhook, mock_get_home, controller, mock_auth_service, mock_ha_service
    ):
        """After successful auth, should look up scene webhook and trigger it."""
        # Setup
        mock_auth_service.verify_response.return_value = MagicMock(
            is_valid=True,
            intent="decorations on",
            message="Verified"
        )
        mock_get_home.return_value = "scott_home"
        mock_get_webhook.return_value = "decorations_on_1751404299018"
        mock_ha_service.trigger_scene.return_value = MagicMock(
            success=True,
            message="Scene activated"
        )

        request_data = make_intent_request(
            "ChallengeResponseIntent",
            slots={"response": {"value": "ocean four"}}
        )
        alexa_request = AlexaRequest.from_dict(request_data)

        response = controller._handle_challenge_response(alexa_request)

        # Verify scene-specific webhook was used
        mock_get_webhook.assert_called_once_with("scott_home", "decorations on")
        mock_ha_service.trigger_scene.assert_called_once_with(
            scene_id="decorations on",
            home_id="scott_home",
            source='Alexa Voice Authentication',
            webhook_id="decorations_on_1751404299018"
        )
        assert "Decorations On" in response.speech_text
        assert "activated" in response.speech_text

    @patch.object(AlexaController, '_get_home_id_for_alexa_user')
    @patch.object(AlexaController, '_get_scene_webhook')
    def test_fallback_to_default_webhook(
        self, mock_get_webhook, mock_get_home, controller, mock_auth_service, mock_ha_service
    ):
        """If no scene mapping found, webhook_id should be None (falls back to home default)."""
        mock_auth_service.verify_response.return_value = MagicMock(
            is_valid=True,
            intent="night scene",
            message="Verified"
        )
        mock_get_home.return_value = "home_1"
        mock_get_webhook.return_value = None  # No scene-specific mapping
        mock_ha_service.trigger_scene.return_value = MagicMock(
            success=True,
            message="Scene activated"
        )

        request_data = make_intent_request(
            "ChallengeResponseIntent",
            slots={"response": {"value": "ocean four"}}
        )
        alexa_request = AlexaRequest.from_dict(request_data)

        response = controller._handle_challenge_response(alexa_request)

        mock_ha_service.trigger_scene.assert_called_once_with(
            scene_id="night scene",
            home_id="home_1",
            source='Alexa Voice Authentication',
            webhook_id=None
        )
        assert "Night Scene" in response.speech_text

    @patch.object(AlexaController, '_get_home_id_for_alexa_user')
    def test_no_intent_defaults_to_night_scene(
        self, mock_get_home, controller, mock_auth_service, mock_ha_service
    ):
        """If no intent stored in challenge, default to 'night scene'."""
        mock_auth_service.verify_response.return_value = MagicMock(
            is_valid=True,
            intent=None,  # No intent stored
            message="Verified"
        )
        mock_get_home.return_value = "home_1"
        mock_ha_service.trigger_scene.return_value = MagicMock(
            success=True,
            message="Scene activated"
        )

        request_data = make_intent_request(
            "ChallengeResponseIntent",
            slots={"response": {"value": "ocean four"}}
        )
        alexa_request = AlexaRequest.from_dict(request_data)

        with patch.object(AlexaController, '_get_scene_webhook', return_value=None):
            response = controller._handle_challenge_response(alexa_request)

        assert "Night Scene" in response.speech_text
