"""
Unit tests for repository implementations

Tests repository layer in isolation with no external dependencies.
"""

import pytest
from datetime import datetime, timedelta
from app.domain.models import Challenge
from app.domain.enums import ClientType, ChallengeStatus
from app.repositories.implementations.in_memory_challenge_repo import InMemoryChallengeRepository


@pytest.mark.unit
class TestInMemoryChallengeRepository:
    """Tests for InMemoryChallengeRepository."""

    @pytest.fixture
    def repo(self):
        """Fresh repository instance for each test."""
        return InMemoryChallengeRepository()

    @pytest.fixture
    def alexa_challenge(self, fixed_datetime):
        """Sample Alexa challenge."""
        return Challenge(
            identifier="session_123",
            phrase="ocean four",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )

    @pytest.fixture
    def fph_challenge(self, fixed_datetime):
        """Sample FutureProof Homes challenge."""
        return Challenge(
            identifier="home_1",
            phrase="mountain seven",
            client_type=ClientType.FUTUREPROOFHOME,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            intent="night_scene"
        )

    def test_add_challenge(self, repo, alexa_challenge):
        """Test adding a new challenge."""
        result = repo.add(alexa_challenge)

        assert result == alexa_challenge
        assert repo.exists_for_identifier("session_123", ClientType.ALEXA)

    def test_add_duplicate_challenge_raises_error(self, repo, alexa_challenge):
        """Test that adding duplicate challenge raises ValueError."""
        repo.add(alexa_challenge)

        with pytest.raises(ValueError, match="Challenge already exists"):
            repo.add(alexa_challenge)

    def test_get_by_identifier(self, repo, alexa_challenge):
        """Test retrieving challenge by identifier and client type."""
        repo.add(alexa_challenge)

        result = repo.get_by_identifier("session_123", ClientType.ALEXA)

        assert result is not None
        assert result.identifier == "session_123"
        assert result.phrase == "ocean four"

    def test_get_by_identifier_not_found(self, repo):
        """Test get_by_identifier returns None when not found."""
        result = repo.get_by_identifier("nonexistent", ClientType.ALEXA)
        assert result is None

    def test_get_by_identifier_wrong_client_type(self, repo, alexa_challenge):
        """Test that challenges are isolated by client type."""
        repo.add(alexa_challenge)

        # Same identifier, different client type
        result = repo.get_by_identifier("session_123", ClientType.FUTUREPROOFHOME)
        assert result is None

    def test_client_type_isolation(self, repo, alexa_challenge, fph_challenge):
        """Test that Alexa and FutureProof Homes challenges are isolated."""
        repo.add(alexa_challenge)
        repo.add(fph_challenge)

        alexa_result = repo.get_by_identifier("session_123", ClientType.ALEXA)
        fph_result = repo.get_by_identifier("home_1", ClientType.FUTUREPROOFHOME)

        assert alexa_result is not None
        assert fph_result is not None
        assert alexa_result.client_type == ClientType.ALEXA
        assert fph_result.client_type == ClientType.FUTUREPROOFHOME

    def test_update_challenge(self, repo, alexa_challenge):
        """Test updating an existing challenge."""
        repo.add(alexa_challenge)

        # Update attempts
        alexa_challenge.increment_attempts()
        repo.update(alexa_challenge)

        result = repo.get_by_identifier("session_123", ClientType.ALEXA)
        assert result.attempts == 1

    def test_update_nonexistent_challenge_raises_error(self, repo, alexa_challenge):
        """Test that updating nonexistent challenge raises ValueError."""
        with pytest.raises(ValueError, match="Challenge not found"):
            repo.update(alexa_challenge)

    def test_delete_by_identifier(self, repo, alexa_challenge):
        """Test deleting challenge by identifier and client type."""
        repo.add(alexa_challenge)

        result = repo.delete_by_identifier("session_123", ClientType.ALEXA)

        assert result is True
        assert not repo.exists_for_identifier("session_123", ClientType.ALEXA)

    def test_delete_by_identifier_not_found(self, repo):
        """Test deleting nonexistent challenge returns False."""
        result = repo.delete_by_identifier("nonexistent", ClientType.ALEXA)
        assert result is False

    def test_list_all_empty(self, repo):
        """Test listing challenges when repository is empty."""
        result = repo.list_all()
        assert result == []

    def test_list_all_with_challenges(self, repo, alexa_challenge, fph_challenge):
        """Test listing all challenges across client types."""
        repo.add(alexa_challenge)
        repo.add(fph_challenge)

        result = repo.list_all()

        assert len(result) == 2
        assert alexa_challenge in result
        assert fph_challenge in result

    def test_list_by_client_type(self, repo, alexa_challenge, fph_challenge, fixed_datetime):
        """Test listing challenges filtered by client type."""
        repo.add(alexa_challenge)
        repo.add(fph_challenge)

        # Add another Alexa challenge
        alexa_challenge_2 = Challenge(
            identifier="session_456",
            phrase="sunset two",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )
        repo.add(alexa_challenge_2)

        alexa_challenges = repo.list_by_client_type(ClientType.ALEXA)
        fph_challenges = repo.list_by_client_type(ClientType.FUTUREPROOFHOME)

        assert len(alexa_challenges) == 2
        assert len(fph_challenges) == 1
        assert all(c.client_type == ClientType.ALEXA for c in alexa_challenges)
        assert all(c.client_type == ClientType.FUTUREPROOFHOME for c in fph_challenges)

    def test_exists_for_identifier(self, repo, alexa_challenge):
        """Test checking if challenge exists."""
        assert not repo.exists_for_identifier("session_123", ClientType.ALEXA)

        repo.add(alexa_challenge)

        assert repo.exists_for_identifier("session_123", ClientType.ALEXA)

    def test_delete_expired_challenges(self, repo, fixed_datetime):
        """Test deleting expired challenges."""
        # Add fresh challenge (not expired)
        fresh_challenge = Challenge(
            identifier="session_fresh",
            phrase="fresh challenge",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            expires_at=fixed_datetime + timedelta(seconds=60)
        )
        repo.add(fresh_challenge)

        # Add expired challenge
        expired_time = fixed_datetime - timedelta(seconds=90)
        expired_challenge = Challenge(
            identifier="session_expired",
            phrase="expired challenge",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=expired_time,
            expires_at=expired_time + timedelta(seconds=60)
        )
        repo.add(expired_challenge)

        # Delete challenges expired before current time
        current_time = fixed_datetime + timedelta(seconds=30)
        deleted_count = repo.delete_expired(current_time)

        assert deleted_count == 1
        assert repo.exists_for_identifier("session_fresh", ClientType.ALEXA)
        assert not repo.exists_for_identifier("session_expired", ClientType.ALEXA)

    def test_delete_expired_multiple_client_types(self, repo, fixed_datetime):
        """Test deleting expired challenges across client types."""
        # Add expired Alexa challenge
        expired_time = fixed_datetime - timedelta(seconds=90)
        expired_alexa = Challenge(
            identifier="session_expired",
            phrase="expired",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=expired_time,
            expires_at=expired_time + timedelta(seconds=60)
        )
        repo.add(expired_alexa)

        # Add expired FPH challenge
        expired_fph = Challenge(
            identifier="home_expired",
            phrase="expired",
            client_type=ClientType.FUTUREPROOFHOME,
            status=ChallengeStatus.PENDING,
            created_at=expired_time,
            expires_at=expired_time + timedelta(seconds=60)
        )
        repo.add(expired_fph)

        # Add fresh FPH challenge
        fresh_fph = Challenge(
            identifier="home_fresh",
            phrase="fresh",
            client_type=ClientType.FUTUREPROOFHOME,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime,
            expires_at=fixed_datetime + timedelta(seconds=60)
        )
        repo.add(fresh_fph)

        current_time = fixed_datetime + timedelta(seconds=30)
        deleted_count = repo.delete_expired(current_time)

        assert deleted_count == 2
        assert not repo.exists_for_identifier("session_expired", ClientType.ALEXA)
        assert not repo.exists_for_identifier("home_expired", ClientType.FUTUREPROOFHOME)
        assert repo.exists_for_identifier("home_fresh", ClientType.FUTUREPROOFHOME)

    def test_count_by_client_type(self, repo, alexa_challenge, fph_challenge, fixed_datetime):
        """Test counting challenges by client type."""
        assert repo.count_by_client_type(ClientType.ALEXA) == 0
        assert repo.count_by_client_type(ClientType.FUTUREPROOFHOME) == 0

        repo.add(alexa_challenge)
        assert repo.count_by_client_type(ClientType.ALEXA) == 1
        assert repo.count_by_client_type(ClientType.FUTUREPROOFHOME) == 0

        repo.add(fph_challenge)
        assert repo.count_by_client_type(ClientType.ALEXA) == 1
        assert repo.count_by_client_type(ClientType.FUTUREPROOFHOME) == 1

        # Add another Alexa challenge
        alexa_challenge_2 = Challenge(
            identifier="session_456",
            phrase="test",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )
        repo.add(alexa_challenge_2)

        assert repo.count_by_client_type(ClientType.ALEXA) == 2
        assert repo.count_by_client_type(ClientType.FUTUREPROOFHOME) == 1

    def test_clear_all(self, repo, alexa_challenge, fph_challenge):
        """Test clearing all challenges."""
        repo.add(alexa_challenge)
        repo.add(fph_challenge)

        assert len(repo.list_all()) == 2

        repo.clear_all()

        assert len(repo.list_all()) == 0
        assert repo.count_by_client_type(ClientType.ALEXA) == 0
        assert repo.count_by_client_type(ClientType.FUTUREPROOFHOME) == 0

    def test_same_identifier_different_client_types(self, repo, fixed_datetime):
        """Test that same identifier can exist for different client types."""
        # Create challenges with same identifier but different client types
        alexa_challenge = Challenge(
            identifier="test_id",
            phrase="alexa phrase",
            client_type=ClientType.ALEXA,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )

        fph_challenge = Challenge(
            identifier="test_id",
            phrase="fph phrase",
            client_type=ClientType.FUTUREPROOFHOME,
            status=ChallengeStatus.PENDING,
            created_at=fixed_datetime
        )

        repo.add(alexa_challenge)
        repo.add(fph_challenge)

        alexa_result = repo.get_by_identifier("test_id", ClientType.ALEXA)
        fph_result = repo.get_by_identifier("test_id", ClientType.FUTUREPROOFHOME)

        assert alexa_result is not None
        assert fph_result is not None
        assert alexa_result.phrase == "alexa phrase"
        assert fph_result.phrase == "fph phrase"
