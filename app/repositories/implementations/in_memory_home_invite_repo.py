"""In-memory home invite repository (dev / tests)."""

from dataclasses import replace
from threading import Lock
from typing import Dict, List, Optional

from app.domain.models import HomeInvite
from app.repositories.home_invite_repository import IHomeInviteRepository


class InMemoryHomeInviteRepository(IHomeInviteRepository):
    def __init__(self):
        self._storage: Dict[str, HomeInvite] = {}
        self._lock = Lock()

    def add(self, invite: HomeInvite) -> HomeInvite:
        with self._lock:
            if invite.code in self._storage:
                raise ValueError(f"Invite code '{invite.code}' already exists")
            self._storage[invite.code] = invite
            return invite

    def get_by_code(self, code: str) -> Optional[HomeInvite]:
        inv = self._storage.get(code)
        return replace(inv) if inv else None

    def list_by_home(self, home_id: str) -> List[HomeInvite]:
        return sorted((replace(i) for i in self._storage.values() if i.home_id == home_id),
                      key=lambda i: i.created_at, reverse=True)

    def update(self, invite: HomeInvite) -> HomeInvite:
        with self._lock:
            if invite.code not in self._storage:
                raise ValueError(f"Invite code '{invite.code}' not found")
            self._storage[invite.code] = invite
            return invite
