"""
Challenge repository interface

Defines specialized operations for Challenge entity storage and retrieval.
Extends base repository with challenge-specific queries.
"""

from abc import abstractmethod
from datetime import datetime
from typing import Optional, List
from app.domain.models import Challenge
from app.domain.enums import ClientType
from app.repositories.base import IRepository


class IChallengeRepository(IRepository[Challenge]):
    """
    Challenge repository interface.

    Specialized repository for Challenge entities with domain-specific queries
    for voice authentication workflows.

    Extends IRepository[Challenge] with:
    - Client type filtering
    - Identifier + client type lookups
    - Expired challenge cleanup
    """

    @abstractmethod
    def get_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> Optional[Challenge]:
        """
        Get challenge by identifier and client type.

        Identifier semantics vary by client:
        - Alexa: session_id
        - FutureProof Homes: home_id

        Args:
            identifier: Unique identifier (session_id or home_id)
            client_type: Type of client (Alexa or FutureProof Homes)

        Returns:
            Challenge if found, None otherwise
        """
        pass

    @abstractmethod
    def delete_by_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Delete challenge by identifier and client type.

        Args:
            identifier: Unique identifier (session_id or home_id)
            client_type: Type of client (Alexa or FutureProof Homes)

        Returns:
            True if challenge was found and deleted, False otherwise
        """
        pass

    @abstractmethod
    def list_by_client_type(self, client_type: ClientType) -> List[Challenge]:
        """
        List all challenges for a specific client type.

        Args:
            client_type: Type of client to filter by

        Returns:
            List of challenges for the client type (may be empty)
        """
        pass

    @abstractmethod
    def delete_expired(self, before: datetime) -> int:
        """
        Delete all challenges that expired before the given time.

        Used for periodic cleanup of stale challenges.

        Args:
            before: Delete challenges that expired before this time

        Returns:
            Number of challenges deleted
        """
        pass

    @abstractmethod
    def count_by_client_type(self, client_type: ClientType) -> int:
        """
        Count challenges for a specific client type.

        Args:
            client_type: Type of client to count

        Returns:
            Number of challenges for this client type
        """
        pass

    @abstractmethod
    def exists_for_identifier(
        self,
        identifier: str,
        client_type: ClientType
    ) -> bool:
        """
        Check if a challenge exists for given identifier and client type.

        Args:
            identifier: Unique identifier to check
            client_type: Type of client

        Returns:
            True if challenge exists, False otherwise
        """
        pass
