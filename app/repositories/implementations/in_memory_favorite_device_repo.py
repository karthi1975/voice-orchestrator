"""In-memory FavoriteDevice repository."""

from threading import Lock
from typing import Dict, List, Optional

from app.domain.models import FavoriteDevice
from app.repositories.favorite_device_repository import IFavoriteDeviceRepository


class InMemoryFavoriteDeviceRepository(IFavoriteDeviceRepository):
    def __init__(self):
        self._storage: Dict[str, FavoriteDevice] = {}
        self._unique_index: Dict[str, str] = {}  # "user_ref|home_id|entity_id" -> id
        self._lock = Lock()

    @staticmethod
    def _key(user_ref: str, home_id: str, entity_id: str) -> str:
        return f"{user_ref}|{home_id}|{entity_id}"

    def add(self, favorite: FavoriteDevice) -> FavoriteDevice:
        with self._lock:
            key = self._key(favorite.user_ref, favorite.home_id, favorite.entity_id)
            if key in self._unique_index:
                raise ValueError(
                    f"entity {favorite.entity_id} already favorited for user {favorite.user_ref} in home {favorite.home_id}"
                )
            self._storage[favorite.id] = favorite
            self._unique_index[key] = favorite.id
            return favorite

    def get_by_id(self, favorite_id: str) -> Optional[FavoriteDevice]:
        return self._storage.get(favorite_id)

    def get_by_user_home_entity(
        self, user_ref: str, home_id: str, entity_id: str
    ) -> Optional[FavoriteDevice]:
        fav_id = self._unique_index.get(self._key(user_ref, home_id, entity_id))
        return self._storage.get(fav_id) if fav_id else None

    def list_for_user_home(self, user_ref: str, home_id: str) -> List[FavoriteDevice]:
        items = [
            f for f in self._storage.values()
            if f.user_ref == user_ref and f.home_id == home_id
        ]
        return sorted(items, key=lambda f: (f.position, f.created_at))

    def update_position(self, favorite_id: str, position: int) -> Optional[FavoriteDevice]:
        with self._lock:
            existing = self._storage.get(favorite_id)
            if not existing:
                return None
            existing.position = position
            return existing

    def delete(self, favorite_id: str) -> bool:
        with self._lock:
            existing = self._storage.pop(favorite_id, None)
            if not existing:
                return False
            self._unique_index.pop(
                self._key(existing.user_ref, existing.home_id, existing.entity_id),
                None,
            )
            return True
