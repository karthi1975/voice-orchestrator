"""
Repository interface for Alexa user mappings

Defines contract for managing Alexa user ID to home ID mappings.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import AlexaUserMapping


class AlexaMappingRepository(ABC):
    """
    Interface for Alexa user mapping persistence.

    Manages CRUD operations for Alexa user to home mappings.
    """

    @abstractmethod
    def create(self, mapping: AlexaUserMapping) -> AlexaUserMapping:
        """
        Create a new Alexa user mapping.

        Args:
            mapping: AlexaUserMapping to create

        Returns:
            Created mapping

        Raises:
            ValueError: If mapping already exists
        """
        pass

    @abstractmethod
    def get_by_alexa_user_id(self, alexa_user_id: str) -> Optional[AlexaUserMapping]:
        """
        Get mapping by Alexa user ID.

        Args:
            alexa_user_id: Amazon user ID

        Returns:
            AlexaUserMapping or None if not found
        """
        pass

    @abstractmethod
    def get_by_home_id(self, home_id: str) -> List[AlexaUserMapping]:
        """
        Get all mappings for a home.

        Args:
            home_id: Home ID

        Returns:
            List of mappings (can be empty)
        """
        pass

    @abstractmethod
    def list_all(self) -> List[AlexaUserMapping]:
        """
        Get all mappings.

        Returns:
            List of all mappings
        """
        pass

    @abstractmethod
    def update(self, mapping: AlexaUserMapping) -> AlexaUserMapping:
        """
        Update an existing mapping.

        Args:
            mapping: AlexaUserMapping with updated values

        Returns:
            Updated mapping

        Raises:
            ValueError: If mapping doesn't exist
        """
        pass

    @abstractmethod
    def delete(self, alexa_user_id: str) -> None:
        """
        Delete a mapping.

        Args:
            alexa_user_id: Alexa user ID to delete

        Raises:
            ValueError: If mapping doesn't exist
        """
        pass

    @abstractmethod
    def exists(self, alexa_user_id: str) -> bool:
        """
        Check if mapping exists.

        Args:
            alexa_user_id: Alexa user ID to check

        Returns:
            True if mapping exists
        """
        pass
