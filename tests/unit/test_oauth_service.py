"""Unit tests for OAuth service."""

import pytest
from datetime import datetime, timedelta
from app.services.oauth_service import OAuthService
from app.repositories.implementations.in_memory_oauth_token_repo import InMemoryOAuthTokenRepository
from app.domain.models import OAuthToken


class TestOAuthService:
    """Test suite for OAuth service."""

    @pytest.fixture
    def repo(self):
        """Create a fresh repository for each test."""
        return InMemoryOAuthTokenRepository()

    @pytest.fixture
    def service(self, repo):
        """Create an OAuth service with in-memory repository."""
        return OAuthService(repo)

    def test_create_token(self, service):
        """Test creating a new OAuth token."""
        token = service.create_token("home_1", amazon_user_id="amzn1.user.test")

        assert token.home_id == "home_1"
        assert token.amazon_user_id == "amzn1.user.test"
        assert token.token_type == "bearer"
        assert token.access_token is not None
        assert token.refresh_token is not None
        assert token.id is not None
        # Expires roughly 365 days from now
        assert token.expires_at > datetime.now() + timedelta(days=364)

    def test_create_token_without_amazon_user_id(self, service):
        """Test creating a token without Amazon user ID."""
        token = service.create_token("home_1")
        assert token.home_id == "home_1"
        assert token.amazon_user_id is None

    def test_create_token_generates_unique_tokens(self, service):
        """Test that each call generates unique tokens."""
        token1 = service.create_token("home_1")
        token2 = service.create_token("home_2")

        assert token1.id != token2.id
        assert token1.access_token != token2.access_token
        assert token1.refresh_token != token2.refresh_token

    def test_validate_token_valid(self, service):
        """Test validating a valid token returns home_id."""
        token = service.create_token("home_1")
        result = service.validate_token(token.access_token)
        assert result == "home_1"

    def test_validate_token_not_found(self, service):
        """Test validating non-existent token returns None."""
        result = service.validate_token("nonexistent-token")
        assert result is None

    def test_validate_token_expired(self, service, repo):
        """Test validating expired token returns None."""
        # Create a token that's already expired
        expired_token = OAuthToken(
            id="expired-1",
            home_id="home_1",
            access_token="expired-access",
            refresh_token="expired-refresh",
            token_type="bearer",
            expires_at=datetime.now() - timedelta(days=1),
            amazon_user_id=None,
            created_at=datetime.now() - timedelta(days=366),
            updated_at=None
        )
        repo.save(expired_token)

        result = service.validate_token("expired-access")
        assert result is None

    def test_refresh_access_token(self, service):
        """Test refreshing an access token."""
        original = service.create_token("home_1", amazon_user_id="amzn1.user.test")
        original_refresh = original.refresh_token

        new_token = service.refresh_access_token(original_refresh)

        assert new_token is not None
        assert new_token.home_id == "home_1"
        assert new_token.amazon_user_id == "amzn1.user.test"
        assert new_token.access_token != original.access_token
        assert new_token.refresh_token != original.refresh_token

        # Old token should no longer be valid
        assert service.validate_token(original.access_token) is None

    def test_refresh_access_token_not_found(self, service):
        """Test refreshing with invalid refresh token returns None."""
        result = service.refresh_access_token("nonexistent-refresh")
        assert result is None

    def test_revoke_tokens(self, service):
        """Test revoking all tokens for a home."""
        token = service.create_token("home_1")

        result = service.revoke_tokens("home_1")
        assert result is True

        # Token should no longer be valid
        assert service.validate_token(token.access_token) is None

    def test_revoke_tokens_not_found(self, service):
        """Test revoking tokens for non-existent home returns False."""
        result = service.revoke_tokens("nonexistent-home")
        assert result is False
