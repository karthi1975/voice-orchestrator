"""
In-memory home repository implementation

Thread-safe in-memory storage for Home entities.
Suitable for development and single-instance deployments.
"""

from datetime import datetime
from typing import Optional, List, Dict
from threading import Lock
from app.domain.models import Home
from app.repositories.home_repository import IHomeRepository


class InMemoryHomeRepository(IHomeRepository):
    """
    Thread-safe in-memory home repository.

    Stores homes in memory with indexes for quick lookups by user_id.

    Storage structure:
    {
        'home_1': Home(...),
        'beach_house': Home(...)
    }

    Indexes:
    - user_index: {user_id -> [home_id, home_id, ...]}

    Thread-safety: Uses threading.Lock for all mutations
    """

    def __init__(self):
        """Initialize empty in-memory storage with lock."""
        self._storage: Dict[str, Home] = {}
        self._user_index: Dict[str, List[str]] = {}  # user_id -> [home_ids]
        self._lock = Lock()

    def add(self, home: Home) -> Home:
        """Add a new home to storage."""
        with self._lock:
            # Check if home_id already exists
            if home.home_id in self._storage:
                raise ValueError(f"Home with ID '{home.home_id}' already exists")

            # Store home
            self._storage[home.home_id] = home

            # Update user index
            if home.user_id not in self._user_index:
                self._user_index[home.user_id] = []
            self._user_index[home.user_id].append(home.home_id)

            return home

    def get_by_id(self, home_id: str) -> Optional[Home]:
        """Get home by ID."""
        return self._storage.get(home_id)

    def get_by_home_id(self, home_id: str) -> Optional[Home]:
        """Get home by home_id (alias for get_by_id)."""
        return self.get_by_id(home_id)

    def get_by_user_id(self, user_id: str) -> List[Home]:
        """Get all homes for a specific user."""
        home_ids = self._user_index.get(user_id, [])
        homes = [self._storage[hid] for hid in home_ids if hid in self._storage]
        return sorted(homes, key=lambda h: h.created_at, reverse=True)

    def update(self, home: Home) -> Home:
        """Update an existing home."""
        with self._lock:
            if home.home_id not in self._storage:
                raise ValueError(f"Home with ID '{home.home_id}' not found")

            old_home = self._storage[home.home_id]

            # If user changed, update index
            if old_home.user_id != home.user_id:
                # Remove from old user's index
                if old_home.user_id in self._user_index:
                    self._user_index[old_home.user_id].remove(home.home_id)

                # Add to new user's index
                if home.user_id not in self._user_index:
                    self._user_index[home.user_id] = []
                self._user_index[home.user_id].append(home.home_id)

            # Update updated_at timestamp
            updated_home = Home(
                home_id=home.home_id,
                user_id=home.user_id,
                name=home.name,
                ha_url=home.ha_url,
                ha_webhook_id=home.ha_webhook_id,
                is_active=home.is_active,
                created_at=home.created_at,
                updated_at=datetime.now()
            )

            # Update storage
            self._storage[home.home_id] = updated_home
            return updated_home

    def delete(self, home_id: str) -> bool:
        """Hard delete a home."""
        with self._lock:
            home = self._storage.get(home_id)
            if not home:
                return False

            # Remove from storage
            del self._storage[home_id]

            # Remove from user index
            if home.user_id in self._user_index:
                self._user_index[home.user_id].remove(home_id)

            return True

    def list_all(self) -> List[Home]:
        """List all homes."""
        return sorted(
            self._storage.values(),
            key=lambda h: h.created_at,
            reverse=True
        )

    def list_active(self) -> List[Home]:
        """List all active homes."""
        return sorted(
            [h for h in self._storage.values() if h.is_active],
            key=lambda h: h.created_at,
            reverse=True
        )

    def list_by_user(self, user_id: str, active_only: bool = True) -> List[Home]:
        """List homes for a specific user with optional active filter."""
        home_ids = self._user_index.get(user_id, [])
        homes = [self._storage[hid] for hid in home_ids if hid in self._storage]

        if active_only:
            homes = [h for h in homes if h.is_active]

        return sorted(homes, key=lambda h: h.created_at, reverse=True)

    def exists(self, home_id: str) -> bool:
        """Check if a home exists by ID."""
        return home_id in self._storage

    def exists_for_user(self, user_id: str, home_id: str) -> bool:
        """Check if a specific home exists for a user."""
        home = self._storage.get(home_id)
        return home is not None and home.user_id == user_id

    def deactivate(self, home_id: str) -> bool:
        """Deactivate a home (soft delete)."""
        with self._lock:
            home = self._storage.get(home_id)
            if not home:
                return False

            # Create updated home with is_active=False
            updated_home = Home(
                home_id=home.home_id,
                user_id=home.user_id,
                name=home.name,
                ha_url=home.ha_url,
                ha_webhook_id=home.ha_webhook_id,
                is_active=False,
                created_at=home.created_at,
                updated_at=datetime.now()
            )
            self._storage[home_id] = updated_home
            return True

    def activate(self, home_id: str) -> bool:
        """Activate a previously deactivated home."""
        with self._lock:
            home = self._storage.get(home_id)
            if not home:
                return False

            # Create updated home with is_active=True
            updated_home = Home(
                home_id=home.home_id,
                user_id=home.user_id,
                name=home.name,
                ha_url=home.ha_url,
                ha_webhook_id=home.ha_webhook_id,
                is_active=True,
                created_at=home.created_at,
                updated_at=datetime.now()
            )
            self._storage[home_id] = updated_home
            return True

    def update_ha_config(
        self,
        home_id: str,
        ha_url: Optional[str] = None,
        ha_webhook_id: Optional[str] = None
    ) -> bool:
        """Update Home Assistant configuration for a home."""
        with self._lock:
            home = self._storage.get(home_id)
            if not home:
                return False

            # Create updated home with new HA config
            updated_home = Home(
                home_id=home.home_id,
                user_id=home.user_id,
                name=home.name,
                ha_url=ha_url if ha_url is not None else home.ha_url,
                ha_webhook_id=ha_webhook_id if ha_webhook_id is not None else home.ha_webhook_id,
                is_active=home.is_active,
                created_at=home.created_at,
                updated_at=datetime.now()
            )
            self._storage[home_id] = updated_home
            return True
