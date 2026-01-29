"""
Unit tests for service layer

Tests business logic with mocked dependencies (repositories).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.domain.models import Challenge
from app.domain.enums import ClientType, ChallengeStatus
from app.services.challenge_service import ChallengeService, ChallengeSettings, ValidationResult
from app.services.authentication_service import (
    AuthenticationService,
    AuthenticationRequest,
    VerificationRequest
)
from app.services.home_automation_service import (
    HomeAutomationService,
    SceneTriggerRequest
)
from app.utils.text_normalizer import TextNormalizer


@pytest.fixture
def challenge_settings():
    """Sample challenge settings for testing."""
    return ChallengeSettings(
        words=["ocean", "mountain", "sunset"],
        numbers=["one", "two", "three", "four", "five"],
        expiry_seconds=60,
        max_attempts=3
    )


@pytest.fixture
def mock_repository():
    """Mock challenge repository."""
    return Mock()


@pytest.fixture
def challenge_service(mock_repository, challenge_settings):
    """Challenge service with mocked repository."""
    return ChallengeService(
        challenge_repository=mock_repository,
        settings=challenge_settings
    )


@pytest.fixture
def auth_service(challenge_service):
    """Authentication service with challenge service."""
    return AuthenticationService(challenge_service=challenge_service)


@pytest.mark.unit
class TestChallengeService:
    """Tests for ChallengeService."""

    def test_generate_challenge_phrase(self, challenge_service, challenge_settings):
        """Test challenge phrase generation."""
        phrase = challenge_service.generate_challenge_phrase()

        # Should be "word number" format
        parts = phrase.split()
        assert len(parts) == 2

        word, number = parts
        assert word in challenge_settings.words
        assert number in challenge_settings.numbers

    def test_create_challenge(self, challenge_service, mock_repository, fixed_datetime):
        """Test creating a new challenge."""
        mock_repository.add.return_value = Mock()

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            challenge = challenge_service.create_challenge(
                identifier="session_123",
                client_type=ClientType.ALEXA,
                intent=None
            )

        # Verify repository.add was called
        mock_repository.add.assert_called_once()

        # Verify challenge properties
        called_challenge = mock_repository.add.call_args[0][0]
        assert called_challenge.identifier == "session_123"
        assert called_challenge.client_type == ClientType.ALEXA
        assert called_challenge.status == ChallengeStatus.PENDING
        assert called_challenge.attempts == 0

    def test_create_challenge_with_intent(self, challenge_service, mock_repository, fixed_datetime):
        """Test creating challenge with intent."""
        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            challenge_service.create_challenge(
                identifier="home_1",
                client_type=ClientType.FUTUREPROOFHOME,
                intent="night_scene"
            )

        called_challenge = mock_repository.add.call_args[0][0]
        assert called_challenge.intent == "night_scene"

    def test_validate_challenge_success(
        self,
        challenge_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test successful challenge validation."""
        # Mock repository to return challenge
        mock_repository.get_by_identifier.return_value = sample_challenge

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = challenge_service.validate_challenge(
                identifier="test_session_123",
                spoken_response="ocean four",
                client_type=ClientType.ALEXA
            )

        assert result.is_valid is True
        assert result.message == "Voice verified successfully"
        assert result.challenge is not None

        # Should delete challenge after success
        mock_repository.delete_by_identifier.assert_called_once_with(
            "test_session_123",
            ClientType.ALEXA
        )

    def test_validate_challenge_no_challenge_found(self, challenge_service, mock_repository):
        """Test validation when no challenge exists."""
        mock_repository.get_by_identifier.return_value = None

        result = challenge_service.validate_challenge(
            identifier="nonexistent",
            spoken_response="ocean four",
            client_type=ClientType.ALEXA
        )

        assert result.is_valid is False
        assert "No active challenge" in result.message

    def test_validate_challenge_expired(
        self,
        challenge_service,
        mock_repository,
        expired_challenge,
        fixed_datetime
    ):
        """Test validation with expired challenge."""
        mock_repository.get_by_identifier.return_value = expired_challenge

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = challenge_service.validate_challenge(
                identifier="expired_session_456",
                spoken_response="sunset two",
                client_type=ClientType.ALEXA
            )

        assert result.is_valid is False
        assert "expired" in result.message.lower()
        assert expired_challenge.status == ChallengeStatus.EXPIRED

        # Should delete expired challenge
        mock_repository.delete_by_identifier.assert_called_once()

    def test_validate_challenge_incorrect_response(
        self,
        challenge_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test validation with incorrect response."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = challenge_service.validate_challenge(
                identifier="test_session_123",
                spoken_response="wrong phrase",
                client_type=ClientType.ALEXA
            )

        assert result.is_valid is False
        assert "Incorrect response" in result.message
        assert "2 attempts remaining" in result.message

        # Should update challenge with incremented attempts
        mock_repository.update.assert_called_once()

    def test_validate_challenge_max_attempts_exceeded(
        self,
        challenge_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test validation when max attempts exceeded."""
        # Set challenge to have 3 attempts already
        sample_challenge.attempts = 3
        mock_repository.get_by_identifier.return_value = sample_challenge

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = challenge_service.validate_challenge(
                identifier="test_session_123",
                spoken_response="wrong phrase",
                client_type=ClientType.ALEXA
            )

        assert result.is_valid is False
        assert "Maximum attempts exceeded" in result.message

        # Should delete challenge
        mock_repository.delete_by_identifier.assert_called_once()

    def test_validate_challenge_normalization(
        self,
        challenge_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test that response normalization works."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        # Try with digit instead of word
        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = challenge_service.validate_challenge(
                identifier="test_session_123",
                spoken_response="ocean 4",  # digit instead of "four"
                client_type=ClientType.ALEXA
            )

        assert result.is_valid is True

    def test_cancel_challenge(self, challenge_service, mock_repository):
        """Test cancelling a challenge."""
        mock_repository.delete_by_identifier.return_value = True

        result = challenge_service.cancel_challenge(
            identifier="session_123",
            client_type=ClientType.ALEXA
        )

        assert result is True
        mock_repository.delete_by_identifier.assert_called_once_with(
            "session_123",
            ClientType.ALEXA
        )

    def test_get_challenge(self, challenge_service, mock_repository, sample_challenge):
        """Test getting a challenge."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        result = challenge_service.get_challenge(
            identifier="test_session_123",
            client_type=ClientType.ALEXA
        )

        assert result == sample_challenge

    def test_cleanup_expired_challenges(
        self,
        challenge_service,
        mock_repository,
        fixed_datetime
    ):
        """Test cleaning up expired challenges."""
        mock_repository.delete_expired.return_value = 5

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            count = challenge_service.cleanup_expired_challenges()

        assert count == 5
        mock_repository.delete_expired.assert_called_once_with(fixed_datetime)

    def test_list_challenges_all(self, challenge_service, mock_repository):
        """Test listing all challenges."""
        mock_challenges = [Mock(), Mock()]
        mock_repository.list_all.return_value = mock_challenges

        result = challenge_service.list_challenges()

        assert result == mock_challenges
        mock_repository.list_all.assert_called_once()

    def test_list_challenges_by_client_type(self, challenge_service, mock_repository):
        """Test listing challenges filtered by client type."""
        mock_challenges = [Mock()]
        mock_repository.list_by_client_type.return_value = mock_challenges

        result = challenge_service.list_challenges(client_type=ClientType.ALEXA)

        assert result == mock_challenges
        mock_repository.list_by_client_type.assert_called_once_with(ClientType.ALEXA)

    def test_count_challenges(self, challenge_service, mock_repository):
        """Test counting challenges."""
        mock_repository.count_by_client_type.return_value = 3

        count = challenge_service.count_challenges(ClientType.FUTUREPROOFHOME)

        assert count == 3
        mock_repository.count_by_client_type.assert_called_once_with(ClientType.FUTUREPROOFHOME)


@pytest.mark.unit
class TestAuthenticationService:
    """Tests for AuthenticationService."""

    def test_request_authentication_alexa(self, auth_service, mock_repository, fixed_datetime):
        """Test requesting authentication for Alexa."""
        mock_repository.add.return_value = Mock()

        request = AuthenticationRequest(
            identifier="session_123",
            client_type=ClientType.ALEXA,
            intent=None
        )

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            response = auth_service.request_authentication(request)

        assert response.challenge_phrase is not None
        assert "Security check required" in response.speech_text
        assert response.challenge_phrase in response.speech_text

    def test_request_authentication_futureproofhome(
        self,
        auth_service,
        mock_repository,
        fixed_datetime
    ):
        """Test requesting authentication for FutureProof Homes."""
        mock_repository.add.return_value = Mock()

        request = AuthenticationRequest(
            identifier="home_1",
            client_type=ClientType.FUTUREPROOFHOME,
            intent="night_scene"
        )

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            response = auth_service.request_authentication(request)

        assert response.challenge_phrase is not None
        assert "Security check" in response.speech_text

    def test_verify_response_success(
        self,
        auth_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test successful response verification."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        request = VerificationRequest(
            identifier="test_session_123",
            client_type=ClientType.ALEXA,
            spoken_response="ocean four"
        )

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = auth_service.verify_response(request)

        assert result.is_valid is True

    def test_verify_response_failure(
        self,
        auth_service,
        mock_repository,
        sample_challenge,
        fixed_datetime
    ):
        """Test failed response verification."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        request = VerificationRequest(
            identifier="test_session_123",
            client_type=ClientType.ALEXA,
            spoken_response="wrong phrase"
        )

        with patch('app.services.challenge_service.get_current_time', return_value=fixed_datetime):
            result = auth_service.verify_response(request)

        assert result.is_valid is False

    def test_cancel_authentication(self, auth_service, mock_repository):
        """Test cancelling authentication."""
        mock_repository.delete_by_identifier.return_value = True

        result = auth_service.cancel_authentication("session_123", ClientType.ALEXA)

        assert result is True

    def test_cleanup_expired(self, auth_service, mock_repository):
        """Test cleanup of expired challenges."""
        mock_repository.delete_expired.return_value = 3

        count = auth_service.cleanup_expired()

        assert count == 3

    def test_get_authentication_status(
        self,
        auth_service,
        mock_repository,
        sample_challenge
    ):
        """Test getting authentication status."""
        mock_repository.get_by_identifier.return_value = sample_challenge

        status = auth_service.get_authentication_status("test_session_123", ClientType.ALEXA)

        assert status is not None
        assert status['identifier'] == sample_challenge.identifier
        assert status['status'] == ChallengeStatus.PENDING.value
        assert status['attempts'] == 0

    def test_get_authentication_status_not_found(self, auth_service, mock_repository):
        """Test getting status when no challenge exists."""
        mock_repository.get_by_identifier.return_value = None

        status = auth_service.get_authentication_status("nonexistent", ClientType.ALEXA)

        assert status is None


@pytest.mark.unit
class TestHomeAutomationService:
    """Tests for HomeAutomationService."""

    def test_trigger_scene_via_legacy(self):
        """Test triggering scene via legacy module."""
        service = HomeAutomationService(ha_client=None)

        with patch('home_assistant.trigger_scene') as mock_trigger:
            mock_trigger.return_value = (True, "Scene activated")

            request = SceneTriggerRequest(scene_id="night_scene")
            result = service.trigger_scene(request)

        assert result.success is True
        assert result.scene_id == "night_scene"
        mock_trigger.assert_called_once_with("night_scene")

    def test_trigger_scene_via_client(self):
        """Test triggering scene via injected client."""
        from app.infrastructure.home_assistant.client import SceneTriggerResult as InfraResult

        mock_client = Mock()
        mock_client.trigger_scene.return_value = InfraResult(
            success=True,
            message='Scene activated',
            scene_id='night_scene'
        )

        service = HomeAutomationService(ha_client=mock_client)

        request = SceneTriggerRequest(scene_id="night_scene", source="Test")
        result = service.trigger_scene(request)

        assert result.success is True
        mock_client.trigger_scene.assert_called_once_with(
            scene_id="night_scene",
            source="Test"
        )

    def test_test_connection_via_legacy(self):
        """Test connection test via legacy module."""
        service = HomeAutomationService(ha_client=None)

        with patch('home_assistant.test_connection') as mock_test:
            mock_test.return_value = (True, "Connected")

            success, message = service.test_connection()

        assert success is True
        mock_test.assert_called_once()

    def test_test_connection_via_client(self):
        """Test connection test via injected client."""
        from app.infrastructure.home_assistant.client import ConnectionTestResult

        mock_client = Mock()
        mock_client.test_connection.return_value = ConnectionTestResult(
            success=True,
            message="Connected"
        )

        service = HomeAutomationService(ha_client=mock_client)

        success, message = service.test_connection()

        assert success is True
        mock_client.test_connection.assert_called_once()


@pytest.mark.unit
class TestTextNormalizer:
    """Tests for TextNormalizer utility."""

    def test_normalize_digits(self):
        """Test digit to word normalization."""
        normalizer = TextNormalizer()

        assert normalizer.normalize("ocean 4") == "ocean four"
        assert normalizer.normalize("mountain 7") == "mountain seven"

    def test_normalize_homophones(self):
        """Test homophone normalization."""
        normalizer = TextNormalizer()

        assert normalizer.normalize("ocean for") == "ocean four"
        assert normalizer.normalize("mountain to") == "mountain two"
        assert normalizer.normalize("mountain too") == "mountain two"

    def test_normalize_case(self):
        """Test case normalization."""
        normalizer = TextNormalizer()

        assert normalizer.normalize("OCEAN FOUR") == "ocean four"
        assert normalizer.normalize("Ocean Four") == "ocean four"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        normalizer = TextNormalizer()

        assert normalizer.normalize("  ocean   four  ") == "ocean four"
        assert normalizer.normalize("ocean\tfour") == "ocean four"
