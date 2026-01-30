"""
SQLAlchemy implementation of home repository

Provides persistent storage using PostgreSQL.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.models import Home
from app.repositories.home_repository import IHomeRepository
from app.repositories.implementations.sqlalchemy_models import HomeModel


class SQLAlchemyHomeRepository(IHomeRepository):
    """
    SQLAlchemy-based home repository.

    Implements IHomeRepository using SQLAlchemy ORM for
    persistent storage in PostgreSQL.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        self._session = session

    def _to_domain(self, model: HomeModel) -> Home:
        """
        Convert SQLAlchemy model to domain model.

        Args:
            model: SQLAlchemy HomeModel

        Returns:
            Domain Home object
        """
        return Home(
            home_id=model.home_id,
            user_id=model.user_id,
            name=model.name,
            ha_url=model.ha_url,
            ha_webhook_id=model.ha_webhook_id,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, home: Home) -> HomeModel:
        """
        Convert domain model to SQLAlchemy model.

        Args:
            home: Domain Home object

        Returns:
            SQLAlchemy HomeModel
        """
        return HomeModel(
            home_id=home.home_id,
            user_id=home.user_id,
            name=home.name,
            ha_url=home.ha_url,
            ha_webhook_id=home.ha_webhook_id,
            is_active=home.is_active,
            created_at=home.created_at,
            updated_at=home.updated_at
        )

    def add(self, home: Home) -> Home:
        """Add a new home to the database."""
        # Check if home_id already exists
        if self.exists(home.home_id):
            raise ValueError(f"Home with ID '{home.home_id}' already exists")

        model = self._to_model(home)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def get_by_id(self, home_id: str) -> Optional[Home]:
        """Get home by ID."""
        model = self._session.get(HomeModel, home_id)
        return self._to_domain(model) if model else None

    def get_by_home_id(self, home_id: str) -> Optional[Home]:
        """Get home by home_id (alias for get_by_id)."""
        return self.get_by_id(home_id)

    def get_by_user_id(self, user_id: str) -> List[Home]:
        """Get all homes for a specific user."""
        stmt = select(HomeModel).where(
            HomeModel.user_id == user_id
        ).order_by(HomeModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def update(self, home: Home) -> Home:
        """Update an existing home."""
        model = self._session.get(HomeModel, home.home_id)
        if not model:
            raise ValueError(f"Home with ID '{home.home_id}' not found")

        # Update fields
        model.name = home.name
        model.ha_url = home.ha_url
        model.ha_webhook_id = home.ha_webhook_id
        model.is_active = home.is_active
        model.updated_at = datetime.now()

        self._session.commit()
        self._session.refresh(model)

        return self._to_domain(model)

    def delete(self, home_id: str) -> bool:
        """Hard delete a home."""
        model = self._session.get(HomeModel, home_id)
        if not model:
            return False

        self._session.delete(model)
        self._session.commit()
        return True

    def list_all(self) -> List[Home]:
        """List all homes."""
        stmt = select(HomeModel).order_by(HomeModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def list_active(self) -> List[Home]:
        """List all active homes."""
        stmt = select(HomeModel).where(
            HomeModel.is_active == True
        ).order_by(HomeModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def list_by_user(self, user_id: str, active_only: bool = True) -> List[Home]:
        """List homes for a specific user with optional active filter."""
        stmt = select(HomeModel).where(HomeModel.user_id == user_id)

        if active_only:
            stmt = stmt.where(HomeModel.is_active == True)

        stmt = stmt.order_by(HomeModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [self._to_domain(model) for model in models]

    def exists(self, home_id: str) -> bool:
        """Check if a home exists by ID."""
        return self._session.get(HomeModel, home_id) is not None

    def exists_for_user(self, user_id: str, home_id: str) -> bool:
        """Check if a specific home exists for a user."""
        stmt = select(HomeModel).where(
            HomeModel.user_id == user_id,
            HomeModel.home_id == home_id
        )
        result = self._session.execute(stmt).scalar_one_or_none()
        return result is not None

    def deactivate(self, home_id: str) -> bool:
        """Deactivate a home (soft delete)."""
        model = self._session.get(HomeModel, home_id)
        if not model:
            return False

        model.is_active = False
        model.updated_at = datetime.now()
        self._session.commit()
        return True

    def activate(self, home_id: str) -> bool:
        """Activate a previously deactivated home."""
        model = self._session.get(HomeModel, home_id)
        if not model:
            return False

        model.is_active = True
        model.updated_at = datetime.now()
        self._session.commit()
        return True

    def update_ha_config(
        self,
        home_id: str,
        ha_url: Optional[str] = None,
        ha_webhook_id: Optional[str] = None
    ) -> bool:
        """Update Home Assistant configuration for a home."""
        model = self._session.get(HomeModel, home_id)
        if not model:
            return False

        # Update provided fields
        if ha_url is not None:
            model.ha_url = ha_url
        if ha_webhook_id is not None:
            model.ha_webhook_id = ha_webhook_id

        model.updated_at = datetime.now()
        self._session.commit()
        return True
