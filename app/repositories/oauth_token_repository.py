"""
Repository interface for OAuth tokens

Defines contract for managing OAuth2 tokens used in Smart Home API authorization.
"""

from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models import OAuthToken


class OAuthTokenRepository(ABC):
    """
    Interface for OAuth token persistence.

    Manages CRUD operations for OAuth2 tokens issued during
    Alexa account linking.
    """

    @abstractmethod
    def save(self, token: OAuthToken) -> OAuthToken:
        """
        Save an OAuth token.

        Args:
            token: OAuthToken to save

        Returns:
            Saved token
        """
        pass

    @abstractmethod
    def get_by_access_token(self, access_token: str) -> Optional[OAuthToken]:
        """
        Get token by access token.

        Args:
            access_token: OAuth2 access token

        Returns:
            OAuthToken or None if not found
        """
        pass

    @abstractmethod
    def get_by_refresh_token(self, refresh_token: str) -> Optional[OAuthToken]:
        """
        Get token by refresh token.

        Args:
            refresh_token: OAuth2 refresh token

        Returns:
            OAuthToken or None if not found
        """
        pass

    @abstractmethod
    def get_by_home_id(self, home_id: str) -> Optional[OAuthToken]:
        """
        Get token by home ID.

        Args:
            home_id: Home ID

        Returns:
            OAuthToken or None if not found
        """
        pass

    @abstractmethod
    def delete_by_home_id(self, home_id: str) -> bool:
        """
        Delete all tokens for a home.

        Args:
            home_id: Home ID whose tokens to delete

        Returns:
            True if any tokens were deleted, False otherwise
        """
        pass
