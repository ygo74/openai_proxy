"""SQLAlchemy ORM models for rate limiting."""
from typing import List, ClassVar, Optional
from datetime import datetime, time
from sqlalchemy import String, Integer, Boolean, DateTime, Time, ForeignKey, Enum as SQLEnum, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum
from .base import Base


class ScopeTypeEnum(str, enum.Enum):
    """Enum for rate limit scope types."""
    GLOBAL = "global"
    MODEL = "model"
    GROUP_MODEL = "group_model"


class RateLimitORM(Base):
    """SQLAlchemy ORM model for rate_limits table.

    Represents rate limit configuration for a specific scope (global, model, or group/model).
    Each rate limit can have multiple time windows with different thresholds.

    Table: rate_limits
    Relationships: One-to-many with rate_limit_windows
    Indexes: (scope_type, scope_id) unique, scope_type, enabled
    """

    __tablename__ = "rate_limits"

    # Exclude inherited base class columns (we use created_at/updated_at instead)
    created: ClassVar[Optional[Mapped[datetime]]] = None  # type: ignore
    updated: ClassVar[Optional[Mapped[datetime]]] = None  # type: ignore

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Scope identification
    scope_type: Mapped[ScopeTypeEnum] = mapped_column(
        SQLEnum(ScopeTypeEnum, name="scope_type_enum", create_constraint=True),
        nullable=False,
        index=True
    )
    scope_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,  # NULL for global scope
        index=True
    )

    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    windows: Mapped[List["RateLimitWindowORM"]] = relationship(
        "RateLimitWindowORM",
        back_populates="rate_limit",
        cascade="all, delete-orphan",
        lazy="joined"  # Eager load windows with rate limit
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            'scope_type',
            'scope_id',
            name='uq_rate_limit_scope'
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimitORM(id={self.id}, scope_type={self.scope_type.value}, "
            f"scope_id={self.scope_id}, enabled={self.enabled}, "
            f"windows_count={len(self.windows)})>"
        )


class RateLimitWindowORM(Base):
    """SQLAlchemy ORM model for rate_limit_windows table.

    Represents time-based windows for rate limiting with request/token thresholds.
    Each window belongs to a parent RateLimitORM.

    Table: rate_limit_windows
    Relationships: Many-to-one with rate_limits
    """

    __tablename__ = "rate_limit_windows"

    # Exclude inherited base class columns (no timestamps needed for windows)
    created: ClassVar[Optional[Mapped[datetime]]] = None  # type: ignore
    updated: ClassVar[Optional[Mapped[datetime]]] = None  # type: ignore

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to parent rate limit
    rate_limit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rate_limits.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Time range
    from_time: Mapped[time] = mapped_column(Time, nullable=False)
    to_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Limits
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    rate_limit: Mapped["RateLimitORM"] = relationship(
        "RateLimitORM",
        back_populates="windows"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint('max_requests >= -1', name='ck_max_requests_valid'),
        CheckConstraint('max_tokens >= -1', name='ck_max_tokens_valid'),
        CheckConstraint('to_time > from_time', name='ck_time_ordering'),
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimitWindowORM(id={self.id}, "
            f"from_time={self.from_time}, to_time={self.to_time}, "
            f"max_requests={self.max_requests}, max_tokens={self.max_tokens})>"
        )
