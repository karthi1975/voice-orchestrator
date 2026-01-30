"""
Home repository interface

Defines specialized operations for Home entity storage and retrieval.
Extends base repository with home-specific queries.
"""

from abc import abstractmethod
from typing import Optional, List
from app.domain.models import Home
from app.repositories.base import IRepository


class IHomeRepository(IRepository[Home]):
    """
    Home repository interface.

    Specialized repository for Home entities with domain-specific queries
    for home management in multi-tenant system.

    Extends IRepository[Home] with:
    - User home lookups
    - Active home filtering
    - HA configuration retrieval
    """

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> List[Home]:
        """
        Get all homes for a specific user.

        Args:
            user_id: User ID to search for

        Returns:
            List of homes owned by the user (may be empty)
        """
        pass

    @abstractmethod
    def get_by_home_id(self, home_id: str) -> Optional[Home]:
        """
        Get home by home_id.

        This is an alias for get_by_id() but makes the intent clearer
        in business logic.

        Args:
            home_id: Home ID to search for

        Returns:
            Home if found, None otherwise
        """
        pass

    @abstractmethod
    def list_active(self) -> List[Home]:
        """
        List all active homes.

        Returns:
            List of active homes (is_active=True), may be empty
        """
        pass

    @abstractmethod
    def list_by_user(self, user_id: str, active_only: bool = True) -> List[Home]:
        """
        List homes for a specific user with optional active filter.

        Args:
            user_id: User ID to filter by
            active_only: If True, only return active homes

        Returns:
            List of homes (may be empty)
        """
        pass

    @abstractmethod
    def exists_for_user(self, user_id: str, home_id: str) -> bool:
        """
        Check if a specific home exists for a user.

        Args:
            user_id: User ID
            home_id: Home ID

        Returns:
            True if home exists and belongs to user, False otherwise
        """
        pass

    @abstractmethod
    def deactivate(self, home_id: str) -> bool:
        """
        Deactivate a home (soft delete).

        Sets is_active to False instead of deleting the record.

        Args:
            home_id: ID of home to deactivate

        Returns:
            True if home was found and deactivated, False otherwise
        """
        pass

    @abstractmethod
    def activate(self, home_id: str) -> bool:
        """
        Activate a previously deactivated home.

        Sets is_active to True.

        Args:
            home_id: ID of home to activate

        Returns:
            True if home was found and activated, False otherwise
        """
        pass

    @abstractmethod
    def update_ha_config(
        self,
        home_id: str,
        ha_url: Optional[str] = None,
        ha_webhook_id: Optional[str] = None
    ) -> bool:
        """
        Update Home Assistant configuration for a home.

        Args:
            home_id: ID of home to update
            ha_url: New HA URL (optional)
            ha_webhook_id: New webhook ID (optional)

        Returns:
            True if home was found and updated, False otherwise
        """
        pass
