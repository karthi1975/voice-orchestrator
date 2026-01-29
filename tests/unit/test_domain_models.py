"""
Unit tests for domain models

Tests core business entities in isolation without dependencies.
"""

import pytest
from datetime import datetime, timedelta
from app.domain.enums import ClientType, ChallengeStatus
from app.domain.models import Challenge, Home, Scene


@pytest.mark.unit
class TestChallenge:
    """Tests for Challenge domain model."""

    def test_challenge_creation(self, fixed_datetime):
        """Test creating a new challenge."""
        challenge = Challenge(
            identifier="test_session",
            phrase="apple five",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            attempts=0
        )

        assert challenge.identifier == "test_session"
        assert challenge.phrase == "apple five"
        assert challenge.client_type == ClientType.ALEXA
        assert challenge.status == ChallengeStatus.PENDING
        assert challenge.attempts == 0
        assert challenge.intent is None

    def test_challenge_auto_expiry_calculation(self, fixed_datetime):
        """Test that expires_at is auto-calculated if not provided."""
        challenge = Challenge(
            identifier="test_session",
            phrase="apple five",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            attempts=0
        )

        expected_expiry = fixed_datetime + timedelta(seconds=60)
        assert challenge.expires_at == expected_expiry

    def test_challenge_with_explicit_expiry(self, fixed_datetime):
        """Test creating challenge with explicit expiry time."""
        custom_expiry = fixed_datetime + timedelta(seconds=120)
        challenge = Challenge(
            identifier="test_session",
            phrase="apple five",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            expires_at=custom_expiry
        )

        assert challenge.expires_at == custom_expiry

    def test_challenge_is_not_expired(self, sample_challenge, fixed_datetime):
        """Test that a fresh challenge is not expired."""
        # Check 30 seconds after creation
        check_time = fixed_datetime + timedelta(seconds=30)
        assert not sample_challenge.is_expired(check_time)

    def test_challenge_is_expired(self, sample_challenge, fixed_datetime):
        """Test that an old challenge is expired."""
        # Check 90 seconds after creation (past 60 second expiry)
        check_time = fixed_datetime + timedelta(seconds=90)
        assert sample_challenge.is_expired(check_time)

    def test_challenge_is_expired_exact_boundary(self, sample_challenge, fixed_datetime):
        """Test expiry at exact boundary time."""
        # Exactly at expiry time (should be expired)
        check_time = fixed_datetime + timedelta(seconds=60)
        assert not sample_challenge.is_expired(check_time)

        # Just after expiry time (should be expired)
        check_time = fixed_datetime + timedelta(seconds=61)
        assert sample_challenge.is_expired(check_time)

    def test_challenge_increment_attempts(self, sample_challenge):
        """Test incrementing attempt counter."""
        assert sample_challenge.attempts == 0

        sample_challenge.increment_attempts()
        assert sample_challenge.attempts == 1

        sample_challenge.increment_attempts()
        assert sample_challenge.attempts == 2

    def test_challenge_mark_validated(self, sample_challenge):
        """Test marking challenge as validated."""
        assert sample_challenge.status == ChallengeStatus.PENDING

        sample_challenge.mark_validated()
        assert sample_challenge.status == ChallengeStatus.VALIDATED

    def test_challenge_mark_expired(self, sample_challenge):
        """Test marking challenge as expired."""
        assert sample_challenge.status == ChallengeStatus.PENDING

        sample_challenge.mark_expired()
        assert sample_challenge.status == ChallengeStatus.EXPIRED

    def test_challenge_mark_failed(self, sample_challenge):
        """Test marking challenge as failed."""
        assert sample_challenge.status == ChallengeStatus.PENDING

        sample_challenge.mark_failed()
        assert sample_challenge.status == ChallengeStatus.FAILED

    def test_challenge_with_intent(self, futureproof_challenge):
        """Test challenge with intent for FutureProof Homes."""
        assert futureproof_challenge.intent == "night_scene"
        assert futureproof_challenge.client_type == ClientType.FUTUREPROOFHOME

    def test_challenge_client_types(self, fixed_datetime):
        """Test both client types."""
        alexa_challenge = Challenge(
            identifier="session_1",
            phrase="test",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )
        assert alexa_challenge.client_type == ClientType.ALEXA

        fph_challenge = Challenge(
            identifier="home_1",
            phrase="test",
            client_type=ClientType.FUTUREPROOFHOME,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )
        assert fph_challenge.client_type == ClientType.FUTUREPROOFHOME


@pytest.mark.unit
class TestHome:
    """Tests for Home domain model."""

    def test_home_creation(self, sample_home):
        """Test creating a new home."""
        assert sample_home.home_id == "home_1"
        assert sample_home.name == "Test Home"
        assert sample_home.is_active is True

    def test_home_inactive(self, fixed_datetime):
        """Test creating an inactive home."""
        home = Home(
            home_id="home_2",
            name="Inactive Home",
            created_at=fixed_datetime,
            is_active=False
        )
        assert home.is_active is False


@pytest.mark.unit
class TestScene:
    """Tests for Scene domain model."""

    def test_scene_creation(self, sample_scene):
        """Test creating a new scene."""
        assert sample_scene.scene_id == "scene_night"
        assert sample_scene.name == "Night Scene"
        assert sample_scene.home_id == "home_1"
        assert sample_scene.requires_auth is True

    def test_scene_without_auth(self):
        """Test creating a scene that doesn't require auth."""
        scene = Scene(
            scene_id="scene_guest",
            name="Guest Mode",
            home_id="home_1",
            requires_auth=False
        )
        assert scene.requires_auth is False


@pytest.mark.unit
class TestChallengeStatus:
    """Tests for ChallengeStatus enum."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        assert ChallengeStatus.PENDING.value == "pending"
        assert ChallengeStatus.VALIDATED.value == "validated"
        assert ChallengeStatus.EXPIRED.value == "expired"
        assert ChallengeStatus.FAILED.value == "failed"

    def test_status_comparison(self):
        """Test comparing status values."""
        status = ChallengeStatus.PENDING
        assert status == ChallengeStatus.PENDING
        assert status != ChallengeStatus.VALIDATED


@pytest.mark.unit
class TestClientType:
    """Tests for ClientType enum."""

    def test_all_client_types_exist(self):
        """Test that all expected client types are defined."""
        assert ClientType.ALEXA.value == "alexa"
        assert ClientType.FUTUREPROOFHOME.value == "futureproofhome"

    def test_client_type_comparison(self):
        """Test comparing client type values."""
        client = ClientType.ALEXA
        assert client == ClientType.ALEXA
        assert client != ClientType.FUTUREPROOFHOME
