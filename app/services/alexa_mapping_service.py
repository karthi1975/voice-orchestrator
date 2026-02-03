"""
Alexa mapping service

Business logic for managing Alexa user to home mappings.
"""

import logging
from typing import List, Optional
from datetime import datetime
from app.repositories.alexa_mapping_repository import AlexaMappingRepository
from app.repositories.home_repository import IHomeRepository
from app.domain.models import AlexaUserMapping


logger = logging.getLogger(__name__)


class AlexaMappingService:
    """
    Service for managing Alexa user mappings.

    Handles business logic for:
    - Creating/updating/deleting mappings
    - Validating home exists before creating mapping
    - Looking up home_id for Alexa user
    """

    def __init__(
        self,
        mapping_repository: AlexaMappingRepository,
        home_repository: IHomeRepository
    ):
        """
        Initialize service.

        Args:
            mapping_repository: Repository for Alexa mappings
            home_repository: Repository for homes (to validate home_id)
        """
        self._mapping_repo = mapping_repository
        self._home_repo = home_repository

    def create_mapping(
        self,
        alexa_user_id: str,
        home_id: str
    ) -> AlexaUserMapping:
        """
        Create a new Alexa user mapping.

        Args:
            alexa_user_id: Amazon user ID
            home_id: Home ID to map to

        Returns:
            Created mapping

        Raises:
            ValueError: If mapping already exists or home_id doesn't exist
        """
        # Validate home exists
        home = self._home_repo.get_by_id(home_id)
        if not home:
            raise ValueError(f"Home '{home_id}' not found")

        # Check if mapping already exists
        if self._mapping_repo.exists(alexa_user_id):
            raise ValueError(f"Mapping for Alexa user '{alexa_user_id}' already exists")

        # Create mapping
        mapping = AlexaUserMapping(
            alexa_user_id=alexa_user_id,
            home_id=home_id,
            created_at=datetime.now()
        )

        created = self._mapping_repo.create(mapping)
        logger.info(f"Created Alexa mapping: {alexa_user_id} -> {home_id}")

        return created

    def get_mapping(self, alexa_user_id: str) -> Optional[AlexaUserMapping]:
        """
        Get mapping by Alexa user ID.

        Args:
            alexa_user_id: Amazon user ID

        Returns:
            Mapping or None if not found
        """
        return self._mapping_repo.get_by_alexa_user_id(alexa_user_id)

    def get_home_id(self, alexa_user_id: str) -> Optional[str]:
        """
        Get home_id for an Alexa user.

        Convenience method for quick lookups.

        Args:
            alexa_user_id: Amazon user ID

        Returns:
            home_id or None if not mapped
        """
        mapping = self._mapping_repo.get_by_alexa_user_id(alexa_user_id)
        return mapping.home_id if mapping else None

    def list_all_mappings(self) -> List[AlexaUserMapping]:
        """
        Get all Alexa mappings.

        Returns:
            List of all mappings
        """
        return self._mapping_repo.list_all()

    def list_mappings_for_home(self, home_id: str) -> List[AlexaUserMapping]:
        """
        Get all Alexa users mapped to a home.

        Args:
            home_id: Home ID

        Returns:
            List of mappings for this home
        """
        return self._mapping_repo.get_by_home_id(home_id)

    def update_mapping(
        self,
        alexa_user_id: str,
        new_home_id: str
    ) -> AlexaUserMapping:
        """
        Update an existing mapping to a new home.

        Args:
            alexa_user_id: Amazon user ID
            new_home_id: New home ID to map to

        Returns:
            Updated mapping

        Raises:
            ValueError: If mapping doesn't exist or new_home_id doesn't exist
        """
        # Validate new home exists
        home = self._home_repo.get_by_id(new_home_id)
        if not home:
            raise ValueError(f"Home '{new_home_id}' not found")

        # Get existing mapping
        existing = self._mapping_repo.get_by_alexa_user_id(alexa_user_id)
        if not existing:
            raise ValueError(f"Mapping for Alexa user '{alexa_user_id}' not found")

        # Update mapping
        existing.home_id = new_home_id
        existing.updated_at = datetime.now()

        updated = self._mapping_repo.update(existing)
        logger.info(f"Updated Alexa mapping: {alexa_user_id} -> {new_home_id}")

        return updated

    def delete_mapping(self, alexa_user_id: str) -> None:
        """
        Delete an Alexa user mapping.

        Args:
            alexa_user_id: Amazon user ID

        Raises:
            ValueError: If mapping doesn't exist
        """
        if not self._mapping_repo.exists(alexa_user_id):
            raise ValueError(f"Mapping for Alexa user '{alexa_user_id}' not found")

        self._mapping_repo.delete(alexa_user_id)
        logger.info(f"Deleted Alexa mapping for user: {alexa_user_id}")
