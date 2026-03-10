"""
Scene webhook mapping service

Business logic for managing scene-to-webhook mappings per home.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional
from app.domain.models import SceneWebhookMapping
from app.repositories.scene_webhook_mapping_repository import ISceneWebhookMappingRepository
from app.repositories.home_repository import IHomeRepository


logger = logging.getLogger(__name__)


class SceneWebhookMappingService:
    """
    Service for managing scene-to-webhook mappings.

    Each home can have multiple scenes, each mapped to a specific
    Home Assistant webhook ID.
    """

    def __init__(
        self,
        mapping_repository: ISceneWebhookMappingRepository,
        home_repository: IHomeRepository
    ):
        self._mapping_repo = mapping_repository
        self._home_repo = home_repository

    def create_mapping(
        self,
        home_id: str,
        scene_name: str,
        webhook_id: str
    ) -> SceneWebhookMapping:
        """
        Create a new scene-to-webhook mapping.

        Args:
            home_id: Home this scene belongs to
            scene_name: Human-friendly scene name
            webhook_id: HA webhook ID for this scene

        Returns:
            Created SceneWebhookMapping

        Raises:
            ValueError: If home doesn't exist or scene already mapped
        """
        if not self._home_repo.exists(home_id):
            raise ValueError(f"Home '{home_id}' not found")

        normalized_name = scene_name.strip().lower()

        mapping = SceneWebhookMapping(
            id=str(uuid.uuid4()),
            home_id=home_id,
            scene_name=normalized_name,
            webhook_id=webhook_id,
            created_at=datetime.now()
        )

        result = self._mapping_repo.add(mapping)
        logger.info(f"Created scene mapping: {normalized_name} -> {webhook_id} for home {home_id}")
        return result

    def get_webhook_for_scene(self, home_id: str, scene_name: str) -> Optional[str]:
        """
        Look up the webhook_id for a given scene at a given home.

        Args:
            home_id: Home identifier
            scene_name: Scene name to look up

        Returns:
            webhook_id or None if not found
        """
        normalized = scene_name.strip().lower()
        mapping = self._mapping_repo.get_by_home_and_scene(home_id, normalized)
        return mapping.webhook_id if mapping else None

    def get_mapping(self, mapping_id: str) -> Optional[SceneWebhookMapping]:
        """Get a mapping by ID."""
        return self._mapping_repo.get_by_id(mapping_id)

    def list_scenes_for_home(self, home_id: str) -> List[SceneWebhookMapping]:
        """List all active scene mappings for a home."""
        return self._mapping_repo.list_by_home(home_id)

    def list_all(self) -> List[SceneWebhookMapping]:
        """List all scene mappings."""
        return self._mapping_repo.list_all()

    def update_mapping(
        self,
        mapping_id: str,
        scene_name: Optional[str] = None,
        webhook_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> SceneWebhookMapping:
        """
        Update an existing scene mapping.

        Args:
            mapping_id: Mapping to update
            scene_name: New scene name (optional)
            webhook_id: New webhook ID (optional)
            is_active: New active status (optional)

        Returns:
            Updated mapping

        Raises:
            ValueError: If mapping not found
        """
        existing = self._mapping_repo.get_by_id(mapping_id)
        if not existing:
            raise ValueError(f"Scene mapping '{mapping_id}' not found")

        updated = SceneWebhookMapping(
            id=existing.id,
            home_id=existing.home_id,
            scene_name=scene_name.strip().lower() if scene_name else existing.scene_name,
            webhook_id=webhook_id if webhook_id else existing.webhook_id,
            is_active=is_active if is_active is not None else existing.is_active,
            created_at=existing.created_at,
            updated_at=datetime.now()
        )

        result = self._mapping_repo.update(updated)
        logger.info(f"Updated scene mapping: {mapping_id}")
        return result

    def delete_mapping(self, mapping_id: str) -> bool:
        """Delete a scene mapping."""
        result = self._mapping_repo.delete(mapping_id)
        if result:
            logger.info(f"Deleted scene mapping: {mapping_id}")
        return result
