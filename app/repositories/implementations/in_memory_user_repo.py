"""
In-memory user repository implementation

Thread-safe in-memory storage for User entities.
Suitable for development and single-instance deployments.
"""

from datetime import datetime
from typing import Optional, List, Dict
from threading import Lock
from app.domain.models import User
from app.repositories.user_repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    """
    Thread-safe in-memory user repository.

    Stores users in memory with indexes for quick lookups by username and email.

    Storage structure:
    {
        'user_123': User(...),
        'user_456': User(...)
    }

    Indexes:
    - username_index: {username -> user_id}
    - email_index: {email -> user_id}

    Thread-safety: Uses threading.Lock for all mutations
    """

    def __init__(self):
        """Initialize empty in-memory storage with lock."""
        self._storage: Dict[str, User] = {}
        self._username_index: Dict[str, str] = {}  # username -> user_id
        self._email_index: Dict[str, str] = {}  # email -> user_id
        self._lock = Lock()

    def add(self, user: User) -> User:
        """Add a new user to storage."""
        with self._lock:
            # Check if user_id already exists
            if user.user_id in self._storage:
                raise ValueError(f"User with ID '{user.user_id}' already exists")

            # Check if username already exists
            if user.username in self._username_index:
                raise ValueError(f"Username '{user.username}' already exists")

            # Check if email already exists (if provided)
            if user.email and user.email in self._email_index:
                raise ValueError(f"Email '{user.email}' already exists")

            # Store user
            self._storage[user.user_id] = user

            # Update indexes
            self._username_index[user.username] = user.user_id
            if user.email:
                self._email_index[user.email] = user.user_id

            return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._storage.get(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        user_id = self._username_index.get(username)
        return self._storage.get(user_id) if user_id else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        user_id = self._email_index.get(email)
        return self._storage.get(user_id) if user_id else None

    def update(self, user: User) -> User:
        """Update an existing user."""
        with self._lock:
            if user.user_id not in self._storage:
                raise ValueError(f"User with ID '{user.user_id}' not found")

            old_user = self._storage[user.user_id]

            # If username changed, update index
            if old_user.username != user.username:
                del self._username_index[old_user.username]
                self._username_index[user.username] = user.user_id

            # If email changed, update index
            if old_user.email != user.email:
                if old_user.email:
                    del self._email_index[old_user.email]
                if user.email:
                    self._email_index[user.email] = user.user_id

            # Update storage
            self._storage[user.user_id] = user
            return user

    def delete(self, user_id: str) -> bool:
        """Hard delete a user."""
        with self._lock:
            user = self._storage.get(user_id)
            if not user:
                return False

            # Remove from storage
            del self._storage[user_id]

            # Remove from indexes
            del self._username_index[user.username]
            if user.email:
                del self._email_index[user.email]

            return True

    def list_all(self) -> List[User]:
        """List all users."""
        return sorted(
            self._storage.values(),
            key=lambda u: u.created_at,
            reverse=True
        )

    def list_active(self) -> List[User]:
        """List all active users."""
        return sorted(
            [u for u in self._storage.values() if u.is_active],
            key=lambda u: u.created_at,
            reverse=True
        )

    def exists(self, user_id: str) -> bool:
        """Check if a user exists by ID."""
        return user_id in self._storage

    def exists_by_username(self, username: str) -> bool:
        """Check if a user exists with the given username."""
        return username in self._username_index

    def exists_by_email(self, email: str) -> bool:
        """Check if a user exists with the given email."""
        return email in self._email_index

    def deactivate(self, user_id: str) -> bool:
        """Deactivate a user (soft delete)."""
        with self._lock:
            user = self._storage.get(user_id)
            if not user:
                return False

            # Create updated user with is_active=False
            updated_user = User(
                user_id=user.user_id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                is_active=False,
                created_at=user.created_at
            )
            self._storage[user_id] = updated_user
            return True

    def activate(self, user_id: str) -> bool:
        """Activate a previously deactivated user."""
        with self._lock:
            user = self._storage.get(user_id)
            if not user:
                return False

            # Create updated user with is_active=True
            updated_user = User(
                user_id=user.user_id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                is_active=True,
                created_at=user.created_at
            )
            self._storage[user_id] = updated_user
            return True
