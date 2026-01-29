"""
In-memory challenge repository implementation

Thread-safe in-memory storage for Challenge entities.
Suitable for development and single-instance deployments.

For production multi-instance deployments, use SQLAlchemy or Redis implementations.
"""

import time
from datetime import datetime
from typing import Optional, List, Dict
from threading import Lock
from app.domain.models import Challenge
from app.domain.enums import ClientType, ChallengeStatus
from app.repositories.challenge_repository import IChallengeRepository


class InMemoryChallengeRepository(IChallengeRepository):
    """
    Thread-safe in-memory challenge repository.

    Stores challenges in memory with separate namespaces per client type.
    Uses composite key (identifier + client_type) for lookups.

    Storage structure:
    {
        'alexa': {
            'session_123': Challenge(...),
            'session_456': Challenge(...)
        },
        'futureproofhome': {
            'home_1': Challenge(...),
            'home_2': Challenge(...)
        }
    }

    Thread-safety: Uses threading.Lock for all mutations
    """

    def __init__(self):
        """Initialize empty in-memory storage with lock."""
        self._storage: Dict[str, Dict[str, Challenge]] = {
            ClientType.ALEXA.value: {},
            ClientType.FUTUREPROOFHOME.value: {}
        }
        self._lock = Lock()

    def add(self, entity: Challenge) -> Challenge:
        """
        Add a new challenge to storage.

        Args:
            entity: Challenge to add

        Returns:
            The added challenge

        Raises:
            ValueError: If challenge already exists for this identifier + client type
        """
        with self._lock:
            client_storage = self._storage[entity.client_type.value]

            if entity.identifier in client_storage:
                raise ValueError(
                    f"Challenge already exists for {entity.client_type.value} "
                    f"identifier '{entity.identifier}'"
                )

            client_storage[entity.identifier] = entity
            return entity

    def get_by_id(self, entity_id: str) -> Optional[Challenge]:
        """
        Get challenge by entity ID.

        Note: For challenges, use get_by_identifier() instead as it requires
        both identifier and client_type. This method is provided for interface
        compliance but is not recommended.

        Args:
            entity_id: Challenge identifier (ambiguous without client_type)

        Returns:
            First matching challenge across all client types, None if not found
        """
        # Search across all client types (not ideal, use get_by_identifier)
        for client_storage in self._storage.values():
            if entity_id in client_storage:
                return client_storage[entity_id]
        return None

    def get_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> Optional[Challenge]:
        """
        Get challenge by identifier and client type.

        Preferred method for challenge lookups.

        Args:
            identifier: Unique identifier (session_id or home_id)
            client_type: Type of client

        Returns:
            Challenge if found, None otherwise
        """
        client_storage = self._storage[client_type.value]
        return client_storage.get(identifier)

    def update(self, entity: Challenge) -> Challenge:
        """
        Update an existing challenge.

        Args:
            entity: Challenge with updated values

        Returns:
            The updated challenge

        Raises:
            ValueError: If challenge doesn't exist
        """
        with self._lock:
            client_storage = self._storage[entity.client_type.value]

            if entity.identifier not in client_storage:
                raise ValueError(
                    f"Challenge not found for {entity.client_type.value} "
                    f"identifier '{entity.identifier}'"
                )

            client_storage[entity.identifier] = entity
            return entity

    def delete(self, entity_id: str) -> bool:
        """
        Delete challenge by entity ID.

        Note: Use delete_by_identifier() for better clarity.

        Args:
            entity_id: Challenge identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            for client_storage in self._storage.values():
                if entity_id in client_storage:
                    del client_storage[entity_id]
                    return True
            return False

    def delete_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Delete challenge by identifier and client type.

        Preferred method for challenge deletion.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            client_storage = self._storage[client_type.value]

            if identifier in client_storage:
                del client_storage[identifier]
                return True
            return False

    def list_all(self) -> List[Challenge]:
        """
        List all challenges across all client types.

        Returns:
            List of all challenges (may be empty)
        """
        all_challenges = []
        for client_storage in self._storage.values():
            all_challenges.extend(client_storage.values())
        return all_challenges

    def list_by_client_type(self, client_type: ClientType) -> List[Challenge]:
        """
        List all challenges for a specific client type.

        Args:
            client_type: Type of client to filter by

        Returns:
            List of challenges for the client type (may be empty)
        """
        client_storage = self._storage[client_type.value]
        return list(client_storage.values())

    def exists(self, entity_id: str) -> bool:
        """
        Check if a challenge exists by entity ID.

        Args:
            entity_id: Challenge identifier

        Returns:
            True if exists, False otherwise
        """
        for client_storage in self._storage.values():
            if entity_id in client_storage:
                return True
        return False

    def exists_for_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Check if a challenge exists for given identifier and client type.

        Args:
            identifier: Unique identifier
            client_type: Type of client

        Returns:
            True if exists, False otherwise
        """
        client_storage = self._storage[client_type.value]
        return identifier in client_storage

    def delete_expired(self, before: datetime) -> int:
        """
        Delete all challenges that expired before the given time.

        Args:
            before: Delete challenges expired before this time

        Returns:
            Number of challenges deleted
        """
        deleted_count = 0

        with self._lock:
            for client_storage in self._storage.values():
                expired_identifiers = [
                    identifier
                    for identifier, challenge in client_storage.items()
                    if challenge.is_expired(before)
                ]

                for identifier in expired_identifiers:
                    del client_storage[identifier]
                    deleted_count += 1

        return deleted_count

    def count_by_client_type(self, client_type: ClientType) -> int:
        """
        Count challenges for a specific client type.

        Args:
            client_type: Type of client to count

        Returns:
            Number of challenges for this client type
        """
        client_storage = self._storage[client_type.value]
        return len(client_storage)

    def clear_all(self) -> None:
        """
        Clear all challenges from storage.

        Useful for testing. Not part of interface.
        """
        with self._lock:
            for client_storage in self._storage.values():
                client_storage.clear()
