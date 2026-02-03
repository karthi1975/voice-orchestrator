"""
SQLAlchemy implementation of Alexa mapping repository

Persists Alexa user mappings to PostgreSQL database.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.alexa_mapping_repository import AlexaMappingRepository
from app.repositories.implementations.sqlalchemy_models import AlexaUserMappingModel
from app.domain.models import AlexaUserMapping


class SQLAlchemyAlexaMappingRepository(AlexaMappingRepository):
    """
    SQLAlchemy implementation of Alexa mapping repository.

    Uses PostgreSQL for persistence via SQLAlchemy ORM.
    """

    def __init__(self, session: Session):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy session
        """
        self._session = session

    def create(self, mapping: AlexaUserMapping) -> AlexaUserMapping:
        """Create a new Alexa user mapping."""
        # Check if already exists
        existing = self._session.get(AlexaUserMappingModel, mapping.alexa_user_id)
        if existing:
            raise ValueError(f"Mapping for Alexa user '{mapping.alexa_user_id}' already exists")

        # Create model and persist
        model = self._to_model(mapping)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def get_by_alexa_user_id(self, alexa_user_id: str) -> Optional[AlexaUserMapping]:
        """Get mapping by Alexa user ID."""
        model = self._session.get(AlexaUserMappingModel, alexa_user_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_by_home_id(self, home_id: str) -> List[AlexaUserMapping]:
        """Get all mappings for a home."""
        models = self._session.query(AlexaUserMappingModel).filter_by(home_id=home_id).all()
        return [self._to_domain(m) for m in models]

    def list_all(self) -> List[AlexaUserMapping]:
        """Get all mappings."""
        models = self._session.query(AlexaUserMappingModel).all()
        return [self._to_domain(m) for m in models]

    def update(self, mapping: AlexaUserMapping) -> AlexaUserMapping:
        """Update an existing mapping."""
        model = self._session.get(AlexaUserMappingModel, mapping.alexa_user_id)
        if not model:
            raise ValueError(f"Mapping for Alexa user '{mapping.alexa_user_id}' not found")

        # Update fields
        model.home_id = mapping.home_id
        model.updated_at = datetime.now()

        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def delete(self, alexa_user_id: str) -> None:
        """Delete a mapping."""
        model = self._session.get(AlexaUserMappingModel, alexa_user_id)
        if not model:
            raise ValueError(f"Mapping for Alexa user '{alexa_user_id}' not found")

        self._session.delete(model)
        self._session.commit()

    def exists(self, alexa_user_id: str) -> bool:
        """Check if mapping exists."""
        model = self._session.get(AlexaUserMappingModel, alexa_user_id)
        return model is not None

    # Helper methods for domain <-> model conversion

    def _to_domain(self, model: AlexaUserMappingModel) -> AlexaUserMapping:
        """Convert SQLAlchemy model to domain entity."""
        return AlexaUserMapping(
            alexa_user_id=model.alexa_user_id,
            home_id=model.home_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, mapping: AlexaUserMapping) -> AlexaUserMappingModel:
        """Convert domain entity to SQLAlchemy model."""
        return AlexaUserMappingModel(
            alexa_user_id=mapping.alexa_user_id,
            home_id=mapping.home_id,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at
        )
