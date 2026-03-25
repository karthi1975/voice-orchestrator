"""
SQLAlchemy implementation of OAuth token repository

Persists OAuth tokens to PostgreSQL database.
"""

from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.oauth_token_repository import OAuthTokenRepository
from app.repositories.implementations.sqlalchemy_models import OAuthTokenModel
from app.domain.models import OAuthToken


class SQLAlchemyOAuthTokenRepository(OAuthTokenRepository):
    """
    SQLAlchemy implementation of OAuth token repository.

    Uses PostgreSQL for persistence via SQLAlchemy ORM.
    """

    def __init__(self, session: Session):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy session
        """
        self._session = session

    def save(self, token: OAuthToken) -> OAuthToken:
        """Save an OAuth token."""
        # Check if token with this ID already exists
        existing = self._session.get(OAuthTokenModel, token.id)
        if existing:
            # Update existing token
            existing.home_id = token.home_id
            existing.access_token = token.access_token
            existing.refresh_token = token.refresh_token
            existing.token_type = token.token_type
            existing.expires_at = token.expires_at
            existing.amazon_user_id = token.amazon_user_id
            existing.updated_at = token.updated_at
        else:
            # Create new token
            model = self._to_model(token)
            self._session.add(model)

        self._session.commit()

        # Re-fetch to return the persisted state
        saved = self._session.get(OAuthTokenModel, token.id)
        return self._to_domain(saved)

    def get_by_access_token(self, access_token: str) -> Optional[OAuthToken]:
        """Get token by access token."""
        model = self._session.query(OAuthTokenModel).filter_by(
            access_token=access_token
        ).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_refresh_token(self, refresh_token: str) -> Optional[OAuthToken]:
        """Get token by refresh token."""
        model = self._session.query(OAuthTokenModel).filter_by(
            refresh_token=refresh_token
        ).first()
        if not model:
            return None
        return self._to_domain(model)

    def get_by_home_id(self, home_id: str) -> Optional[OAuthToken]:
        """Get token by home ID."""
        model = self._session.query(OAuthTokenModel).filter_by(
            home_id=home_id
        ).first()
        if not model:
            return None
        return self._to_domain(model)

    def delete_by_home_id(self, home_id: str) -> bool:
        """Delete all tokens for a home."""
        count = self._session.query(OAuthTokenModel).filter_by(
            home_id=home_id
        ).delete()
        self._session.commit()
        return count > 0

    # Helper methods for domain <-> model conversion

    def _to_domain(self, model: OAuthTokenModel) -> OAuthToken:
        """Convert SQLAlchemy model to domain entity."""
        return OAuthToken(
            id=model.id,
            home_id=model.home_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_type=model.token_type,
            expires_at=model.expires_at,
            amazon_user_id=model.amazon_user_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, token: OAuthToken) -> OAuthTokenModel:
        """Convert domain entity to SQLAlchemy model."""
        return OAuthTokenModel(
            id=token.id,
            home_id=token.home_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            token_type=token.token_type,
            expires_at=token.expires_at,
            amazon_user_id=token.amazon_user_id,
            created_at=token.created_at,
            updated_at=token.updated_at
        )
