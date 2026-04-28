"""Repository interface for FavoriteDevice persistence."""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import FavoriteDevice


class IFavoriteDeviceRepository(ABC):
    @abstractmethod
    def add(self, favorite: FavoriteDevice) -> FavoriteDevice:
        """Insert a new favorite. Raises ValueError if (user_ref, home_id, entity_id) already exists."""

    @abstractmethod
    def get_by_id(self, favorite_id: str) -> Optional[FavoriteDevice]:
        """Return one favorite or None."""

    @abstractmethod
    def get_by_user_home_entity(
        self, user_ref: str, home_id: str, entity_id: str
    ) -> Optional[FavoriteDevice]:
        """Return the favorite for this (user, home, entity) triple, if any."""

    @abstractmethod
    def list_for_user_home(self, user_ref: str, home_id: str) -> List[FavoriteDevice]:
        """Return all favorites for (user_ref, home_id), ordered by position then created_at."""

    @abstractmethod
    def update_position(self, favorite_id: str, position: int) -> Optional[FavoriteDevice]:
        """Set position on a favorite. Returns updated row or None if not found."""

    @abstractmethod
    def delete(self, favorite_id: str) -> bool:
        """Delete by id. Returns True if a row was removed."""
