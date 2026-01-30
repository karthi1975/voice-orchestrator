"""
User service for multi-tenant user management

Business logic for user creation, updates, and lifecycle management.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from app.domain.models import User
from app.repositories.user_repository import IUserRepository


class UserService:
    """
    Service for managing users in multi-tenant system.

    Handles:
    - User creation with unique username/email validation
    - User retrieval by various criteria
    - User updates
    - User activation/deactivation

    Dependencies:
    - IUserRepository: Storage abstraction
    """

    def __init__(self, user_repository: IUserRepository):
        """
        Initialize user service.

        Args:
            user_repository: Repository for user storage
        """
        self._repository = user_repository

    def create_user(
        self,
        username: str,
        full_name: str,
        email: Optional[str] = None
    ) -> User:
        """
        Create a new user.

        Args:
            username: Unique username
            full_name: User's full name
            email: Optional email address

        Returns:
            Created user

        Raises:
            ValueError: If username or email already exists
        """
        # Generate unique user ID
        user_id = str(uuid.uuid4())

        # Create user domain model
        user = User(
            user_id=user_id,
            username=username,
            full_name=full_name,
            email=email,
            is_active=True,
            created_at=datetime.now()
        )

        # Persist to repository
        return self._repository.add(user)

    def get_user(self, user_id: str) -> User:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User

        Raises:
            ValueError: If user not found
        """
        user = self._repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID '{user_id}' not found")
        return user

    def get_by_username(self, username: str) -> User:
        """
        Get user by username.

        Args:
            username: Username

        Returns:
            User

        Raises:
            ValueError: If user not found
        """
        user = self._repository.get_by_username(username)
        if not user:
            raise ValueError(f"User with username '{username}' not found")
        return user

    def get_by_email(self, email: str) -> User:
        """
        Get user by email.

        Args:
            email: Email address

        Returns:
            User

        Raises:
            ValueError: If user not found
        """
        user = self._repository.get_by_email(email)
        if not user:
            raise ValueError(f"User with email '{email}' not found")
        return user

    def list_users(self, active_only: bool = False) -> List[User]:
        """
        List all users.

        Args:
            active_only: If True, only return active users

        Returns:
            List of users
        """
        if active_only:
            return self._repository.list_active()
        return self._repository.list_all()

    def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        email: Optional[str] = None
    ) -> User:
        """
        Update user details.

        Args:
            user_id: User ID
            username: New username (optional)
            full_name: New full name (optional)
            email: New email (optional)

        Returns:
            Updated user

        Raises:
            ValueError: If user not found or new username/email already exists
        """
        # Get existing user
        user = self.get_user(user_id)

        # Update fields if provided
        if username is not None:
            # Check if new username is available
            if username != user.username and self._repository.exists_by_username(username):
                raise ValueError(f"Username '{username}' already exists")
            user = User(
                user_id=user.user_id,
                username=username,
                full_name=full_name if full_name is not None else user.full_name,
                email=email if email is not None else user.email,
                is_active=user.is_active,
                created_at=user.created_at
            )
        elif full_name is not None or email is not None:
            user = User(
                user_id=user.user_id,
                username=user.username,
                full_name=full_name if full_name is not None else user.full_name,
                email=email if email is not None else user.email,
                is_active=user.is_active,
                created_at=user.created_at
            )

        return self._repository.update(user)

    def deactivate_user(self, user_id: str) -> User:
        """
        Deactivate a user (soft delete).

        Args:
            user_id: User ID

        Returns:
            Deactivated user

        Raises:
            ValueError: If user not found
        """
        if not self._repository.deactivate(user_id):
            raise ValueError(f"User with ID '{user_id}' not found")

        return self.get_user(user_id)

    def activate_user(self, user_id: str) -> User:
        """
        Activate a previously deactivated user.

        Args:
            user_id: User ID

        Returns:
            Activated user

        Raises:
            ValueError: If user not found
        """
        if not self._repository.activate(user_id):
            raise ValueError(f"User with ID '{user_id}' not found")

        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> bool:
        """
        Permanently delete a user.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        return self._repository.delete(user_id)

    def user_exists(self, user_id: str) -> bool:
        """
        Check if user exists.

        Args:
            user_id: User ID

        Returns:
            True if user exists, False otherwise
        """
        return self._repository.exists(user_id)
