"""
SQLAlchemy database models

Maps domain models to database tables.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum, Index, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.enums import ClientType, ChallengeStatus


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class UserModel(Base):
    """
    SQLAlchemy model for User entity.

    Maps to 'users' table in database.
    """
    __tablename__ = 'users'

    # Primary key
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # User fields
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserModel(user_id={self.user_id}, username={self.username})>"


class HomeModel(Base):
    """
    SQLAlchemy model for Home entity.

    Maps to 'homes' table in database.
    """
    __tablename__ = 'homes'

    # Primary key
    home_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey('users.user_id'),
        nullable=False,
        index=True
    )

    # Home fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ha_url: Mapped[str] = mapped_column(String(500), nullable=False)
    ha_webhook_id: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Composite indexes
    __table_args__ = (
        Index('idx_homes_user_id', 'user_id'),
        Index('idx_homes_is_active', 'is_active'),
        Index('idx_user_home_unique', 'user_id', 'home_id', unique=True),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<HomeModel(home_id={self.home_id}, name={self.name})>"


class ChallengeModel(Base):
    """
    SQLAlchemy model for Challenge entity.

    Maps to 'challenges' table in database.
    """
    __tablename__ = 'challenges'

    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Challenge fields
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phrase: Mapped[str] = mapped_column(String(100), nullable=False)
    client_type: Mapped[ClientType] = mapped_column(
        SQLEnum(ClientType, native_enum=False, length=50),
        nullable=False,
        index=True
    )
    status: Mapped[ChallengeStatus] = mapped_column(
        SQLEnum(ChallengeStatus, native_enum=False, length=50),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Multi-tenant support
    home_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey('homes.home_id'),
        nullable=True,  # Allow NULL for backward compatibility
        index=True
    )

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_identifier_client_type', 'identifier', 'client_type'),
        Index('idx_client_type_status', 'client_type', 'status'),
        Index('idx_expires_at_status', 'expires_at', 'status'),
        Index('idx_challenges_home_id', 'home_id'),
        Index('idx_challenges_home_status', 'home_id', 'status'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ChallengeModel(id={self.id}, identifier={self.identifier}, client_type={self.client_type})>"
