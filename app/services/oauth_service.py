"""
OAuth service for Smart Home API authorization

Manages OAuth2 token lifecycle for Alexa account linking
and Smart Home API directive authentication.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from app.domain.models import OAuthToken
from app.repositories.oauth_token_repository import OAuthTokenRepository


class OAuthService:
    """
    Service for OAuth2 token management.

    Handles token creation, validation, refresh, and revocation
    for Smart Home API authorization.
    """

    def __init__(self, oauth_token_repository: OAuthTokenRepository):
        """
        Initialize OAuth service.

        Args:
            oauth_token_repository: Repository for token persistence
        """
        self._repo = oauth_token_repository

    def create_token(self, home_id: str, amazon_user_id: Optional[str] = None) -> OAuthToken:
        """
        Create a new OAuth token for a home.

        Generates UUID-based access and refresh tokens with a 365-day expiry
        (long-lived for smart home use).

        Args:
            home_id: Home ID to associate the token with
            amazon_user_id: Optional Amazon user ID from account linking

        Returns:
            Newly created OAuthToken
        """
        now = datetime.now()
        token = OAuthToken(
            id=str(uuid.uuid4()),
            home_id=home_id,
            access_token=str(uuid.uuid4()),
            refresh_token=str(uuid.uuid4()),
            token_type="bearer",
            expires_at=now + timedelta(days=365),
            amazon_user_id=amazon_user_id,
            created_at=now,
            updated_at=None
        )
        return self._repo.save(token)

    def validate_token(self, access_token: str) -> Optional[str]:
        """
        Validate an access token and return the associated home ID.

        Args:
            access_token: OAuth2 access token to validate

        Returns:
            home_id if token is valid, None if token is invalid or expired
        """
        token = self._repo.get_by_access_token(access_token)
        if token is None:
            return None

        # Check if expired
        if datetime.now() > token.expires_at:
            return None

        return token.home_id

    def refresh_access_token(self, refresh_token_str: str) -> Optional[OAuthToken]:
        """
        Refresh an access token using a refresh token.

        Deletes the old token and creates a new one with the same home ID.

        Args:
            refresh_token_str: OAuth2 refresh token

        Returns:
            New OAuthToken if refresh token is valid, None otherwise
        """
        token = self._repo.get_by_refresh_token(refresh_token_str)
        if token is None:
            return None

        home_id = token.home_id
        amazon_user_id = token.amazon_user_id

        # Delete old token
        self._repo.delete_by_home_id(home_id)

        # Create new token with same home_id
        return self.create_token(home_id, amazon_user_id)

    def revoke_tokens(self, home_id: str) -> bool:
        """
        Revoke all tokens for a home.

        Args:
            home_id: Home ID whose tokens to revoke

        Returns:
            True if any tokens were deleted, False otherwise
        """
        return self._repo.delete_by_home_id(home_id)
