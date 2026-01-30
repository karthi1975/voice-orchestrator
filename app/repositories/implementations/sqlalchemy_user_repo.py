"""
SQLAlchemy implementation of user repository

Provides persistent storage using PostgreSQL.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.models import User
from app.repositories.user_repository import IUserRepository
from app.repositories.implementations.sqlalchemy_models import UserModel


class SQLAlchemyUserRepository(IUserRepository):
    """
    SQLAlchemy-based user repository.

    Implements IUserRepository using SQLAlchemy ORM for
    persistent storage in PostgreSQL.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        self._session = session

    def _to_domain(self, model: UserModel) -> User:
        """
        Convert SQLAlchemy model to domain model.

        Args:
            model: SQLAlchemy UserModel

        Returns:
            Domain User object
        """
        return User(
            user_id=model.user_id,
            username=model.username,
            full_name=model.full_name,
            email=model.email,
            is_active=model.is_active,
            created_at=model.created_at
        )

    def _to_model(self, user: User) -> UserModel:
        """
        Convert domain model to SQLAlchemy model.

        Args:
            user: Domain User object

        Returns:
            SQLAlchemy UserModel
        """
        return UserModel(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at
        )

    def add(self, user: User) -> User:
        """Add a new user to the database."""
        # Check if user_id already exists
        if self.exists(user.user_id):
            raise ValueError(f"User with ID '{user.user_id}' already exists")

        # Check if username already exists
        if self.exists_by_username(user.username):
            raise ValueError(f"Username '{user.username}' already exists")

        # Check if email already exists (if provided)
        if user.email and self.exists_by_email(user.email):
            raise ValueError(f"Email '{user.email}' already exists")

        model = self._to_model(user)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        model = self._session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        stmt = select(UserModel).where(UserModel.username == username)
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(model) if model else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        stmt = select(UserModel).where(UserModel.email == email)
        model = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(model) if model else None

    def update(self, user: User) -> User:
        """Update an existing user."""
        model = self._session.get(UserModel, user.user_id)
        if not model:
            raise ValueError(f"User with ID '{user.user_id}' not found")

        # Update fields
        model.username = user.username
        model.full_name = user.full_name
        model.email = user.email
        model.is_active = user.is_active

        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def delete(self, user_id: str) -> bool:
        """Hard delete a user."""
        model = self._session.get(UserModel, user_id)
        if not model:
            return False

        self._session.delete(model)
        self._session.commit()
        return True

    def list_all(self) -> List[User]:
        """List all users."""
        stmt = select(UserModel).order_by(UserModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def list_active(self) -> List[User]:
        """List all active users."""
        stmt = select(UserModel).where(
            UserModel.is_active == True
        ).order_by(UserModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def exists(self, user_id: str) -> bool:
        """Check if a user exists by ID."""
        return self._session.get(UserModel, user_id) is not None

    def exists_by_username(self, username: str) -> bool:
        """Check if a user exists with the given username."""
        stmt = select(UserModel.user_id).where(UserModel.username == username)
        result = self._session.execute(stmt).scalar_one_or_none()
        return result is not None

    def exists_by_email(self, email: str) -> bool:
        """Check if a user exists with the given email."""
        stmt = select(UserModel.user_id).where(UserModel.email == email)
        result = self._session.execute(stmt).scalar_one_or_none()
        return result is not None

    def deactivate(self, user_id: str) -> bool:
        """Deactivate a user (soft delete)."""
        model = self._session.get(UserModel, user_id)
        if not model:
            return False

        model.is_active = False
        self._session.commit()
        return True

    def activate(self, user_id: str) -> bool:
        """Activate a previously deactivated user."""
        model = self._session.get(UserModel, user_id)
        if not model:
            return False

        model.is_active = True
        self._session.commit()
        return True
