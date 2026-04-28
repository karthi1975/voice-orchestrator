"""Business logic for FavoriteDevice management.

A favorite is a user-pinned HA entity (light, scene, script, switch, etc.)
within one of the user's homes. The service:
  - validates that home_id exists (via IHomeRepository when available)
  - normalizes entity_id (must be "<domain>.<suffix>")
  - keeps unique (user_ref, home_id, entity_id)
  - assigns the next position when adding (caller can override)

The service does NOT verify the entity actually exists in HA — discovery is
the mobile client's responsibility (see /api/v1/voice-auth/automations/discover).
We just store what we're told.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from app.domain.models import FavoriteDevice
from app.repositories.favorite_device_repository import IFavoriteDeviceRepository
from app.repositories.home_repository import IHomeRepository

logger = logging.getLogger(__name__)


class FavoriteDeviceService:
    def __init__(
        self,
        favorite_repository: IFavoriteDeviceRepository,
        home_repository: Optional[IHomeRepository] = None,
    ):
        self._repo = favorite_repository
        self._homes = home_repository

    def add_favorite(
        self,
        user_ref: str,
        home_id: str,
        entity_id: str,
        friendly_name: Optional[str] = None,
        position: Optional[int] = None,
    ) -> FavoriteDevice:
        if not user_ref or not user_ref.strip():
            raise ValueError("user_ref is required")
        if not home_id or not home_id.strip():
            raise ValueError("home_id is required")
        if not entity_id or "." not in entity_id:
            raise ValueError("entity_id must be of the form '<domain>.<suffix>' (e.g. 'light.kitchen')")

        domain, _, suffix = entity_id.partition(".")
        if not domain or not suffix:
            raise ValueError("entity_id must be of the form '<domain>.<suffix>'")

        if self._homes is not None and not self._homes.exists(home_id):
            raise ValueError(f"home '{home_id}' not found")

        # Default friendly_name = suffix; client can override
        label = (friendly_name or suffix).strip()

        if position is None:
            existing = self._repo.list_for_user_home(user_ref, home_id)
            position = (existing[-1].position + 1) if existing else 0

        fav = FavoriteDevice(
            id=str(uuid.uuid4()),
            user_ref=user_ref.strip(),
            home_id=home_id.strip(),
            entity_id=entity_id.strip(),
            friendly_name=label,
            domain=domain,
            position=int(position),
            created_at=datetime.utcnow(),
        )
        out = self._repo.add(fav)
        logger.info(
            f"FAVORITE add user={user_ref} home={home_id} entity={entity_id} pos={out.position}"
        )
        return out

    def list_favorites(self, user_ref: str, home_id: str) -> List[FavoriteDevice]:
        if not user_ref or not home_id:
            raise ValueError("user_ref and home_id are required")
        return self._repo.list_for_user_home(user_ref, home_id)

    def remove_favorite(self, favorite_id: str) -> bool:
        ok = self._repo.delete(favorite_id)
        if ok:
            logger.info(f"FAVORITE delete id={favorite_id}")
        return ok

    def reorder(self, items: List[dict]) -> List[FavoriteDevice]:
        """Bulk-update position for a list of [{id, position}] entries.

        Returns the updated rows in the order supplied. Skips ids that do not
        exist (no exception) — caller can compare counts to detect partial
        success.
        """
        updated: List[FavoriteDevice] = []
        for entry in items:
            fav_id = entry.get("id")
            position = entry.get("position")
            if not fav_id or position is None:
                continue
            row = self._repo.update_position(fav_id, int(position))
            if row:
                updated.append(row)
        logger.info(f"FAVORITE reorder updated_count={len(updated)} requested={len(items)}")
        return updated
