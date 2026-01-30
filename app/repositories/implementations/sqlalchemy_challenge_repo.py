"""
SQLAlchemy implementation of challenge repository

Provides persistent storage using PostgreSQL.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.domain.models import Challenge
from app.domain.enums import ClientType, ChallengeStatus
from app.repositories.challenge_repository import IChallengeRepository
from app.repositories.implementations.sqlalchemy_models import ChallengeModel


class SQLAlchemyChallengeRepository(IChallengeRepository):
    """
    SQLAlchemy-based challenge repository.
    
    Implements IChallengeRepository using SQLAlchemy ORM for
    persistent storage in PostgreSQL.
    """
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self._session = session
    
    def _to_domain(self, model: ChallengeModel) -> Challenge:
        """
        Convert SQLAlchemy model to domain model.
        
        Args:
            model: SQLAlchemy ChallengeModel
            
        Returns:
            Domain Challenge object
        """
        return Challenge(
            identifier=model.identifier,
            phrase=model.phrase,
            client_type=model.client_type,
            status=model.status,
            created_at=model.created_at,
            attempts=model.attempts,
            intent=model.intent,
            expires_at=model.expires_at
        )
    
    def _to_model(self, challenge: Challenge) -> ChallengeModel:
        """
        Convert domain model to SQLAlchemy model.
        
        Args:
            challenge: Domain Challenge object
            
        Returns:
            SQLAlchemy ChallengeModel
        """
        # Generate ID from identifier and client_type
        model_id = f"{challenge.identifier}_{challenge.client_type.value}"
        
        return ChallengeModel(
            id=model_id,
            identifier=challenge.identifier,
            phrase=challenge.phrase,
            client_type=challenge.client_type,
            status=challenge.status,
            created_at=challenge.created_at,
            attempts=challenge.attempts,
            intent=challenge.intent,
            expires_at=challenge.expires_at
        )
    
    def add(self, challenge: Challenge) -> Challenge:
        """Add a new challenge to the database."""
        model = self._to_model(challenge)
        
        # Check if already exists
        existing = self._session.get(ChallengeModel, model.id)
        if existing:
            raise ValueError(
                f"Challenge already exists for identifier '{challenge.identifier}' "
                f"and client type '{challenge.client_type.value}'"
            )
        
        self._session.add(model)
        self._session.commit()
        
        return challenge
    
    def get_by_id(self, challenge_id: str) -> Optional[Challenge]:
        """Get challenge by ID (not used in this implementation)."""
        model = self._session.get(ChallengeModel, challenge_id)
        return self._to_domain(model) if model else None
    
    def get_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> Optional[Challenge]:
        """Get challenge by identifier and client type."""
        model_id = f"{identifier}_{client_type.value}"
        model = self._session.get(ChallengeModel, model_id)
        return self._to_domain(model) if model else None
    
    def update(self, challenge: Challenge) -> Challenge:
        """Update existing challenge."""
        model_id = f"{challenge.identifier}_{challenge.client_type.value}"
        model = self._session.get(ChallengeModel, model_id)
        
        if not model:
            raise ValueError(
                f"Challenge not found for identifier '{challenge.identifier}' "
                f"and client type '{challenge.client_type.value}'"
            )
        
        # Update fields
        model.phrase = challenge.phrase
        model.status = challenge.status
        model.attempts = challenge.attempts
        model.intent = challenge.intent
        model.expires_at = challenge.expires_at
        
        self._session.commit()
        
        return challenge
    
    def delete(self, entity_id: str) -> bool:
        """
        Delete a challenge by entity ID.

        Args:
            entity_id: Challenge ID (format: identifier_clienttype)

        Returns:
            True if challenge was found and deleted, False otherwise
        """
        model = self._session.get(ChallengeModel, entity_id)

        if model:
            self._session.delete(model)
            self._session.commit()
            return True

        return False
    
    def delete_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """Delete challenge by identifier and client type."""
        model_id = f"{identifier}_{client_type.value}"
        model = self._session.get(ChallengeModel, model_id)
        
        if model:
            self._session.delete(model)
            self._session.commit()
            return True
        
        return False
    
    def list_all(self) -> List[Challenge]:
        """List all challenges."""
        stmt = select(ChallengeModel)
        models = self._session.scalars(stmt).all()
        return [self._to_domain(model) for model in models]
    
    def list_by_client_type(self, client_type: ClientType) -> List[Challenge]:
        """List challenges by client type."""
        stmt = select(ChallengeModel).where(
            ChallengeModel.client_type == client_type
        )
        models = self._session.scalars(stmt).all()
        return [self._to_domain(model) for model in models]
    
    def exists(self, entity_id: str) -> bool:
        """
        Check if challenge exists by entity ID.

        Args:
            entity_id: Challenge ID (format: identifier_clienttype)

        Returns:
            True if challenge exists, False otherwise
        """
        model = self._session.get(ChallengeModel, entity_id)
        return model is not None

    def exists_for_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """Check if challenge exists."""
        model_id = f"{identifier}_{client_type.value}"
        model = self._session.get(ChallengeModel, model_id)
        return model is not None

    def delete_expired(self, before: datetime) -> int:
        """Delete expired challenges."""
        stmt = delete(ChallengeModel).where(
            ChallengeModel.expires_at < before
        )
        result = self._session.execute(stmt)
        self._session.commit()
        return result.rowcount
    
    def count_by_client_type(self, client_type: ClientType) -> int:
        """Count challenges by client type."""
        stmt = select(ChallengeModel).where(
            ChallengeModel.client_type == client_type
        )
        return len(self._session.scalars(stmt).all())
    
    def clear_all(self) -> None:
        """Clear all challenges (for testing)."""
        stmt = delete(ChallengeModel)
        self._session.execute(stmt)
        self._session.commit()
