"""
SQLAlchemy implementation of scene webhook mapping repository

Persists scene webhook mappings to PostgreSQL database.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.scene_webhook_mapping_repository import ISceneWebhookMappingRepository
from app.repositories.implementations.sqlalchemy_models import SceneWebhookMappingModel
from app.domain.models import SceneWebhookMapping


class SQLAlchemySceneWebhookMappingRepository(ISceneWebhookMappingRepository):
    """
    SQLAlchemy implementation of scene webhook mapping repository.

    Uses PostgreSQL for persistence via SQLAlchemy ORM.
    """

    def __init__(self, session: Session):
        self._session = session

    def add(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Create a new scene webhook mapping."""
        existing = self.get_by_home_and_scene(mapping.home_id, mapping.scene_name)
        if existing:
            raise ValueError(
                f"Scene '{mapping.scene_name}' already mapped for home '{mapping.home_id}'"
            )

        model = self._to_model(mapping)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, mapping_id: str) -> Optional[SceneWebhookMapping]:
        """Get mapping by ID."""
        model = self._session.get(SceneWebhookMappingModel, mapping_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_by_home_and_scene(self, home_id: str, scene_name: str) -> Optional[SceneWebhookMapping]:
        """Get active mapping by home ID and scene name."""
        model = self._session.query(SceneWebhookMappingModel).filter_by(
            home_id=home_id,
            scene_name=scene_name,
            is_active=True
        ).first()
        if not model:
            return None
        return self._to_domain(model)

    def list_by_home(self, home_id: str, active_only: bool = True) -> List[SceneWebhookMapping]:
        """List all mappings for a home."""
        query = self._session.query(SceneWebhookMappingModel).filter_by(home_id=home_id)
        if active_only:
            query = query.filter_by(is_active=True)
        models = query.order_by(SceneWebhookMappingModel.scene_name).all()
        return [self._to_domain(m) for m in models]

    def list_all(self) -> List[SceneWebhookMapping]:
        """List all mappings."""
        models = self._session.query(SceneWebhookMappingModel).order_by(
            SceneWebhookMappingModel.home_id,
            SceneWebhookMappingModel.scene_name
        ).all()
        return [self._to_domain(m) for m in models]

    def update(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Update an existing mapping."""
        model = self._session.get(SceneWebhookMappingModel, mapping.id)
        if not model:
            raise ValueError(f"Scene mapping '{mapping.id}' not found")

        model.scene_name = mapping.scene_name
        model.webhook_id = mapping.webhook_id
        model.is_active = mapping.is_active
        model.updated_at = datetime.now()

        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def delete(self, mapping_id: str) -> bool:
        """Delete a mapping by ID."""
        model = self._session.get(SceneWebhookMappingModel, mapping_id)
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def exists(self, mapping_id: str) -> bool:
        """Check if a mapping exists."""
        model = self._session.get(SceneWebhookMappingModel, mapping_id)
        return model is not None

    def _to_domain(self, model: SceneWebhookMappingModel) -> SceneWebhookMapping:
        """Convert SQLAlchemy model to domain entity."""
        return SceneWebhookMapping(
            id=model.id,
            home_id=model.home_id,
            scene_name=model.scene_name,
            webhook_id=model.webhook_id,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, mapping: SceneWebhookMapping) -> SceneWebhookMappingModel:
        """Convert domain entity to SQLAlchemy model."""
        return SceneWebhookMappingModel(
            id=mapping.id,
            home_id=mapping.home_id,
            scene_name=mapping.scene_name,
            webhook_id=mapping.webhook_id,
            is_active=mapping.is_active,
            created_at=mapping.created_at,
            updated_at=mapping.updated_at
        )
