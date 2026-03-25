"""
In-memory implementation of OAuth token repository

Used for testing without database dependencies.
"""

from typing import Dict, Optional
from app.repositories.oauth_token_repository import OAuthTokenRepository
from app.domain.models import OAuthToken


class InMemoryOAuthTokenRepository(OAuthTokenRepository):
    """
    In-memory implementation of OAuth token repository.

    Stores tokens in a dictionary for testing purposes.
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._tokens: Dict[str, OAuthToken] = {}

    def save(self, token: OAuthToken) -> OAuthToken:
        """Save an OAuth token."""
        self._tokens[token.id] = token
        return token

    def get_by_access_token(self, access_token: str) -> Optional[OAuthToken]:
        """Get token by access token."""
        for token in self._tokens.values():
            if token.access_token == access_token:
                return token
        return None

    def get_by_refresh_token(self, refresh_token: str) -> Optional[OAuthToken]:
        """Get token by refresh token."""
        for token in self._tokens.values():
            if token.refresh_token == refresh_token:
                return token
        return None

    def get_by_home_id(self, home_id: str) -> Optional[OAuthToken]:
        """Get token by home ID."""
        for token in self._tokens.values():
            if token.home_id == home_id:
                return token
        return None

    def delete_by_home_id(self, home_id: str) -> bool:
        """Delete all tokens for a home."""
        to_delete = [tid for tid, t in self._tokens.items() if t.home_id == home_id]
        for tid in to_delete:
            del self._tokens[tid]
        return len(to_delete) > 0
