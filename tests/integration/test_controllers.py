"""
Integration tests for controllers

Tests HTTP layer with full dependency injection.
"""

import pytest
import json
from app import create_app


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.mark.integration
class TestAlexaController:
    """Integration tests for Alexa controller."""

    def test_launch_request(self, client):
        """Test Alexa launch request."""
        request_data = {
            "request": {"type": "LaunchRequest"},
            "session": {"sessionId": "test_session_123"}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['version'] == '1.0'
        assert 'Home security activated' in data['response']['outputSpeech']['text']
        assert data['response']['shouldEndSession'] is False

    def test_night_scene_intent(self, client):
        """Test night scene intent generates challenge."""
        request_data = {
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "NightSceneIntent"}
            },
            "session": {"sessionId": "test_session_456"}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        speech = data['response']['outputSpeech']['text']
        assert 'Security check required' in speech
        assert 'Please say:' in speech
        assert data['response']['shouldEndSession'] is False

    def test_challenge_response_success(self, client):
        """Test successful challenge response."""
        session_id = "test_session_789"

        # First, request challenge
        request_data = {
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "NightSceneIntent"}
            },
            "session": {"sessionId": session_id}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        # Extract challenge from response
        speech = response.get_json()['response']['outputSpeech']['text']
        challenge = speech.split('Please say: ')[1]

        # Now respond with correct challenge
        response_data = {
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "ChallengeResponseIntent",
                    "slots": {
                        "response": {"value": challenge}
                    }
                }
            },
            "session": {"sessionId": session_id}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(response_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        speech = data['response']['outputSpeech']['text']
        assert 'Voice verified' in speech
        assert data['response']['shouldEndSession'] is True

    def test_help_intent(self, client):
        """Test help intent."""
        request_data = {
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "AMAZON.HelpIntent"}
            },
            "session": {"sessionId": "test_session"}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        speech = data['response']['outputSpeech']['text']
        assert 'voice authentication' in speech.lower()
        assert data['response']['shouldEndSession'] is False

    def test_stop_intent(self, client):
        """Test stop intent."""
        request_data = {
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "AMAZON.StopIntent"}
            },
            "session": {"sessionId": "test_session"}
        }

        response = client.post(
            '/alexa',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert 'Goodbye' in data['response']['outputSpeech']['text']
        assert data['response']['shouldEndSession'] is True


@pytest.mark.integration
class TestFutureProofHomesController:
    """Integration tests for FutureProof Homes controller."""

    def test_auth_request(self, client):
        """Test authentication request."""
        request_data = {
            "home_id": "home_1",
            "intent": "night_scene"
        }

        response = client.post(
            '/futureproofhome/auth/request',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'challenge'
        assert 'Security check' in data['speech']
        assert 'challenge' in data
        assert len(data['challenge'].split()) == 2  # Should be "word number"

    def test_auth_verify_success(self, client):
        """Test successful authentication verification."""
        home_id = "home_2"

        # First, request auth
        request_data = {
            "home_id": home_id,
            "intent": "night_scene"
        }

        response = client.post(
            '/futureproofhome/auth/request',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        challenge = response.get_json()['challenge']

        # Now verify with correct response
        verify_data = {
            "home_id": home_id,
            "response": challenge
        }

        response = client.post(
            '/futureproofhome/auth/verify',
            data=json.dumps(verify_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'approved'
        assert data['intent'] == 'night_scene'
        assert 'verified' in data['speech'].lower()

    def test_auth_verify_failure(self, client):
        """Test failed authentication verification."""
        home_id = "home_3"

        # Request auth
        request_data = {
            "home_id": home_id,
            "intent": "night_scene"
        }

        client.post(
            '/futureproofhome/auth/request',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        # Verify with wrong response
        verify_data = {
            "home_id": home_id,
            "response": "wrong phrase"
        }

        response = client.post(
            '/futureproofhome/auth/verify',
            data=json.dumps(verify_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'denied'
        assert data['reason'] == 'mismatch'
        assert data['attempts_remaining'] == 2

    def test_auth_cancel(self, client):
        """Test authentication cancellation."""
        home_id = "home_4"

        # Request auth
        request_data = {
            "home_id": home_id,
            "intent": "night_scene"
        }

        client.post(
            '/futureproofhome/auth/request',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        # Cancel
        cancel_data = {"home_id": home_id}

        response = client.post(
            '/futureproofhome/auth/cancel',
            data=json.dumps(cancel_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['status'] == 'cancelled'
        assert 'cancelled' in data['speech'].lower()

    def test_auth_status(self, client):
        """Test authentication status endpoint."""
        # Create a few challenges
        for i in range(2):
            request_data = {
                "home_id": f"home_{i}",
                "intent": "night_scene"
            }
            client.post(
                '/futureproofhome/auth/request',
                data=json.dumps(request_data),
                content_type='application/json'
            )

        # Get status
        response = client.get('/futureproofhome/auth/status')

        assert response.status_code == 200
        data = response.get_json()

        assert 'pending_challenges' in data
        assert 'config' in data
        assert 'total_pending' in data
        assert data['total_pending'] >= 2

    def test_missing_required_field(self, client):
        """Test error handling for missing required field."""
        request_data = {
            "intent": "night_scene"
            # Missing home_id
        }

        response = client.post(
            '/futureproofhome/auth/request',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'home_id' in data['error'].lower()
