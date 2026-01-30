"""
User repository interface

Defines specialized operations for User entity storage and retrieval.
Extends base repository with user-specific queries.
"""

from abc import abstractmethod
from typing import Optional, List
from app.domain.models import User
from app.repositories.base import IRepository


class IUserRepository(IRepository[User]):
    """
    User repository interface.

    Specialized repository for User entities with domain-specific queries
    for user management in multi-tenant system.

    Extends IRepository[User] with:
    - Username lookups
    - Email lookups
    - Active user filtering
    """

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Unique username to search for

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: Email address to search for

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    def list_active(self) -> List[User]:
        """
        List all active users.

        Returns:
            List of active users (is_active=True), may be empty
        """
        pass

    @abstractmethod
    def exists_by_username(self, username: str) -> bool:
        """
        Check if a user exists with the given username.

        Args:
            username: Username to check

        Returns:
            True if username exists, False otherwise
        """
        pass

    @abstractmethod
    def exists_by_email(self, email: str) -> bool:
        """
        Check if a user exists with the given email.

        Args:
            email: Email to check

        Returns:
            True if email exists, False otherwise
        """
        pass

    @abstractmethod
    def deactivate(self, user_id: str) -> bool:
        """
        Deactivate a user (soft delete).

        Sets is_active to False instead of deleting the record.

        Args:
            user_id: ID of user to deactivate

        Returns:
            True if user was found and deactivated, False otherwise
        """
        pass

    @abstractmethod
    def activate(self, user_id: str) -> bool:
        """
        Activate a previously deactivated user.

        Sets is_active to True.

        Args:
            user_id: ID of user to activate

        Returns:
            True if user was found and activated, False otherwise
        """
        pass
