"""
SQLAlchemy database models

Maps domain models to database tables.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.enums import ClientType, ChallengeStatus


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


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
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_identifier_client_type', 'identifier', 'client_type'),
        Index('idx_client_type_status', 'client_type', 'status'),
        Index('idx_expires_at_status', 'expires_at', 'status'),
    )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<ChallengeModel(id={self.id}, identifier={self.identifier}, client_type={self.client_type})>"
