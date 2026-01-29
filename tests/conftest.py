"""
Shared pytest fixtures and configuration

Fixtures available to all tests across the test suite.
"""

import pytest
from datetime import datetime, timedelta
from app.domain.enums import ClientType, ChallengeStatus
from app.domain.models import Challenge, Home, Scene


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for testing time-dependent logic."""
    return datetime(2026, 1, 29, 12, 0, 0)


@pytest.fixture
def sample_challenge(fixed_datetime):
    """Sample challenge for testing."""
    return Challenge(
        identifier="test_session_123",
        phrase="ocean four",
        client_type=ClientType.ALEXA,
        status=ChallengeStatus.PENDING,
        created_at=fixed_datetime,
        attempts=0,
        intent=None,
        expires_at=fixed_datetime + timedelta(seconds=60)
    )


@pytest.fixture
def expired_challenge(fixed_datetime):
    """Expired challenge for testing."""
    created_time = fixed_datetime - timedelta(seconds=90)
    return Challenge(
        identifier="expired_session_456",
        phrase="sunset two",
        client_type=ClientType.ALEXA,
        status=ChallengeStatus.PENDING,
        created_at=created_time,
        attempts=0,
        expires_at=created_time + timedelta(seconds=60)
    )


@pytest.fixture
def futureproof_challenge(fixed_datetime):
    """FutureProof Homes challenge for testing."""
    return Challenge(
        identifier="home_1",
        phrase="mountain seven",
        client_type=ClientType.FUTUREPROOFHOME,
        status=ChallengeStatus.PENDING,
        created_at=fixed_datetime,
        attempts=0,
        intent="night_scene",
        expires_at=fixed_datetime + timedelta(seconds=60)
    )


@pytest.fixture
def sample_home(fixed_datetime):
    """Sample home for testing."""
    return Home(
        home_id="home_1",
        name="Test Home",
        created_at=fixed_datetime,
        is_active=True
    )


@pytest.fixture
def sample_scene():
    """Sample scene for testing."""
    return Scene(
        scene_id="scene_night",
        name="Night Scene",
        home_id="home_1",
        requires_auth=True
    )
