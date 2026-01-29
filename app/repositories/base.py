"""
Base repository interfaces

Defines generic repository patterns following Repository Pattern.
Enables swapping storage implementations (in-memory, database, etc.) without
changing business logic.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

# Generic type for repository entities
T = TypeVar('T')


class IRepository(ABC, Generic[T]):
    """
    Generic repository interface.

    Defines common CRUD operations that all repositories should implement.
    Following Repository Pattern for clean data access abstraction.

    Type parameter T: The entity type this repository manages
    """

    @abstractmethod
    def add(self, entity: T) -> T:
        """
        Add a new entity to the repository.

        Args:
            entity: Entity to add

        Returns:
            The added entity (may include generated IDs, timestamps, etc.)

        Raises:
            ValueError: If entity already exists or validation fails
        """
        pass

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Retrieve an entity by its unique identifier.

        Args:
            entity_id: Unique identifier for the entity

        Returns:
            The entity if found, None otherwise
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: Entity with updated values

        Returns:
            The updated entity

        Raises:
            ValueError: If entity doesn't exist
        """
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by its identifier.

        Args:
            entity_id: Unique identifier for the entity to delete

        Returns:
            True if entity was found and deleted, False otherwise
        """
        pass

    @abstractmethod
    def list_all(self) -> List[T]:
        """
        Retrieve all entities.

        Returns:
            List of all entities (may be empty)
        """
        pass

    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists.

        Args:
            entity_id: Unique identifier to check

        Returns:
            True if entity exists, False otherwise
        """
        pass
