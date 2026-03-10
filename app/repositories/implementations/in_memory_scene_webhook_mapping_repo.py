"""
In-memory scene webhook mapping repository implementation

Thread-safe in-memory storage for SceneWebhookMapping entities.
"""

from datetime import datetime
from typing import Optional, List, Dict
from threading import Lock
from app.domain.models import SceneWebhookMapping
from app.repositories.scene_webhook_mapping_repository import ISceneWebhookMappingRepository


class InMemorySceneWebhookMappingRepository(ISceneWebhookMappingRepository):
    """
    Thread-safe in-memory scene webhook mapping repository.

    Storage: {mapping_id: SceneWebhookMapping}
    Index: {(home_id, scene_name): mapping_id}
    """

    def __init__(self):
        self._storage: Dict[str, SceneWebhookMapping] = {}
        self._home_scene_index: Dict[str, str] = {}  # "home_id:scene_name" -> mapping_id
        self._lock = Lock()

    def add(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Create a new scene webhook mapping."""
        with self._lock:
            index_key = f"{mapping.home_id}:{mapping.scene_name}"
            if index_key in self._home_scene_index:
                raise ValueError(
                    f"Scene '{mapping.scene_name}' already mapped for home '{mapping.home_id}'"
                )
            self._storage[mapping.id] = mapping
            self._home_scene_index[index_key] = mapping.id
            return mapping

    def get_by_id(self, mapping_id: str) -> Optional[SceneWebhookMapping]:
        """Get mapping by ID."""
        return self._storage.get(mapping_id)

    def get_by_home_and_scene(self, home_id: str, scene_name: str) -> Optional[SceneWebhookMapping]:
        """Get active mapping by home ID and scene name."""
        index_key = f"{home_id}:{scene_name}"
        mapping_id = self._home_scene_index.get(index_key)
        if not mapping_id:
            return None
        mapping = self._storage.get(mapping_id)
        if mapping and mapping.is_active:
            return mapping
        return None

    def list_by_home(self, home_id: str, active_only: bool = True) -> List[SceneWebhookMapping]:
        """List all mappings for a home."""
        mappings = [m for m in self._storage.values() if m.home_id == home_id]
        if active_only:
            mappings = [m for m in mappings if m.is_active]
        return sorted(mappings, key=lambda m: m.scene_name)

    def list_all(self) -> List[SceneWebhookMapping]:
        """List all mappings."""
        return sorted(
            self._storage.values(),
            key=lambda m: (m.home_id, m.scene_name)
        )

    def update(self, mapping: SceneWebhookMapping) -> SceneWebhookMapping:
        """Update an existing mapping."""
        with self._lock:
            if mapping.id not in self._storage:
                raise ValueError(f"Scene mapping '{mapping.id}' not found")

            old = self._storage[mapping.id]

            # Update index if scene_name changed
            old_key = f"{old.home_id}:{old.scene_name}"
            new_key = f"{mapping.home_id}:{mapping.scene_name}"
            if old_key != new_key:
                del self._home_scene_index[old_key]
                self._home_scene_index[new_key] = mapping.id

            updated = SceneWebhookMapping(
                id=mapping.id,
                home_id=mapping.home_id,
                scene_name=mapping.scene_name,
                webhook_id=mapping.webhook_id,
                is_active=mapping.is_active,
                created_at=old.created_at,
                updated_at=datetime.now()
            )
            self._storage[mapping.id] = updated
            return updated

    def delete(self, mapping_id: str) -> bool:
        """Delete a mapping by ID."""
        with self._lock:
            mapping = self._storage.get(mapping_id)
            if not mapping:
                return False
            index_key = f"{mapping.home_id}:{mapping.scene_name}"
            del self._storage[mapping_id]
            self._home_scene_index.pop(index_key, None)
            return True

    def exists(self, mapping_id: str) -> bool:
        """Check if a mapping exists."""
        return mapping_id in self._storage
