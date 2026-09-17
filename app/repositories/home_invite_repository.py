"""
Home invite repository interface

Storage for OTP-style invite codes that attach a user to a home.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import HomeInvite


class IHomeInviteRepository(ABC):
    """CRUD for HomeInvite. Codes are stored canonical (see HomeInviteService)."""

    @abstractmethod
    def add(self, invite: HomeInvite) -> HomeInvite:
        """Persist a new invite. Raises ValueError when the code already exists."""

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[HomeInvite]:
        """Look up an invite by its canonical code."""

    @abstractmethod
    def list_by_home(self, home_id: str) -> List[HomeInvite]:
        """All invites ever generated for a home, newest first."""

    @abstractmethod
    def update(self, invite: HomeInvite) -> HomeInvite:
        """Persist use_count / revoked_at changes. Raises ValueError when missing."""
