"""User ORM models."""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from .base import Base

class ApiKeyORM(Base):
    """API Key ORM model."""
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["UserORM"] = relationship("UserORM", back_populates="api_keys")

class UserORM(Base):
    """User ORM model."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)
    groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string

    # Relationships
    api_keys: Mapped[List["ApiKeyORM"]] = relationship("ApiKeyORM", back_populates="user", cascade="all, delete-orphan")
