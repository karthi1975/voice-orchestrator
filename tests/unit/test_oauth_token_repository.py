"""Unit tests for OAuth token repository."""

import pytest
from datetime import datetime, timedelta
from app.repositories.implementations.in_memory_oauth_token_repo import InMemoryOAuthTokenRepository
from app.domain.models import OAuthToken


class TestInMemoryOAuthTokenRepository:
    """Test suite for in-memory OAuth token repository."""

    @pytest.fixture
    def repo(self):
        """Create a fresh repository for each test."""
        return InMemoryOAuthTokenRepository()

    @pytest.fixture
    def sample_token(self):
        """Create a sample OAuth token."""
        now = datetime.now()
        return OAuthToken(
            id="token-1",
            home_id="home_1",
            access_token="access-abc-123",
            refresh_token="refresh-def-456",
            token_type="bearer",
            expires_at=now + timedelta(days=365),
            amazon_user_id="amzn1.user.test123",
            created_at=now,
            updated_at=None
        )

    def test_save_and_get_by_access_token(self, repo, sample_token):
        """Test saving a token and retrieving by access token."""
        repo.save(sample_token)
        result = repo.get_by_access_token("access-abc-123")
        assert result is not None
        assert result.id == "token-1"
        assert result.home_id == "home_1"
        assert result.access_token == "access-abc-123"

    def test_get_by_access_token_not_found(self, repo):
        """Test retrieving non-existent access token returns None."""
        result = repo.get_by_access_token("nonexistent")
        assert result is None

    def test_get_by_refresh_token(self, repo, sample_token):
        """Test retrieving by refresh token."""
        repo.save(sample_token)
        result = repo.get_by_refresh_token("refresh-def-456")
        assert result is not None
        assert result.id == "token-1"

    def test_get_by_refresh_token_not_found(self, repo):
        """Test retrieving non-existent refresh token returns None."""
        result = repo.get_by_refresh_token("nonexistent")
        assert result is None

    def test_get_by_home_id(self, repo, sample_token):
        """Test retrieving by home ID."""
        repo.save(sample_token)
        result = repo.get_by_home_id("home_1")
        assert result is not None
        assert result.id == "token-1"

    def test_get_by_home_id_not_found(self, repo):
        """Test retrieving non-existent home ID returns None."""
        result = repo.get_by_home_id("nonexistent")
        assert result is None

    def test_delete_by_home_id(self, repo, sample_token):
        """Test deleting tokens by home ID."""
        repo.save(sample_token)
        result = repo.delete_by_home_id("home_1")
        assert result is True
        assert repo.get_by_home_id("home_1") is None

    def test_delete_by_home_id_not_found(self, repo):
        """Test deleting tokens for non-existent home returns False."""
        result = repo.delete_by_home_id("nonexistent")
        assert result is False

    def test_save_overwrites_existing(self, repo, sample_token):
        """Test that saving a token with same ID overwrites."""
        repo.save(sample_token)

        updated = OAuthToken(
            id="token-1",
            home_id="home_1",
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            token_type="bearer",
            expires_at=sample_token.expires_at,
            amazon_user_id="amzn1.user.test123",
            created_at=sample_token.created_at,
            updated_at=datetime.now()
        )
        repo.save(updated)

        result = repo.get_by_access_token("new-access-token")
        assert result is not None
        assert result.access_token == "new-access-token"

        # Old access token should not be found
        assert repo.get_by_access_token("access-abc-123") is None
