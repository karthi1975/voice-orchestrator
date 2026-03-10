"""
Repository interface for scene webhook mappings

Defines contract for managing scene-to-webhook mappings per home.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import SceneWebhookMapping


class ISceneWebhookMappingRepository(ABC):
    """
    Interface for scene webhook mapping persistence.

    Manages CRUD operations for scene-to-webhook mappings.
    """

    @abstractmethod
    def add(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Create a new scene webhook mapping."""
        pass

    @abstractmethod
    def get_by_id(self, mapping_id: str) -> Optional[SceneWebhookMapping]:
        """Get mapping by ID."""
        pass

    @abstractmethod
    def get_by_home_and_scene(self, home_id: str, scene_name: str) -> Optional[SceneWebhookMapping]:
        """Get mapping by home ID and scene name."""
        pass

    @abstractmethod
    def list_by_home(self, home_id: str, active_only: bool = True) -> List[SceneWebhookMapping]:
        """List all mappings for a home."""
        pass

    @abstractmethod
    def list_all(self) -> List[SceneWebhookMapping]:
        """List all mappings."""
        pass

    @abstractmethod
    def update(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Update an existing mapping."""
        pass

    @abstractmethod
    def delete(self, mapping_id: str) -> bool:
        """Delete a mapping by ID."""
        pass

    @abstractmethod
    def exists(self, mapping_id: str) -> bool:
        """Check if a mapping exists."""
        pass
