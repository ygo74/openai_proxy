# Data Model Design: Rate Limiting System

**Project:** FastAPI OpenAI RAG Proxy
**Feature:** Multi-level Rate Limiting System
**Date:** 2025-12-06
**Phase:** Phase 1 Design
**Input:** [research.md](./research.md), [spec.md](./spec.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Domain Models](#domain-models)
3. [ORM Models](#orm-models)
4. [Mappers](#mappers)
5. [Repository Interfaces](#repository-interfaces)
6. [Value Objects & Enums](#value-objects--enums)
7. [API Models (Request/Response)](#api-models-requestresponse)
8. [Database Schema](#database-schema)
9. [Entity Relationships](#entity-relationships)
10. [Validation Rules](#validation-rules)

---

## Overview

The rate limiting system follows **onion architecture** with strict separation between domain models (pure business logic), ORM models (database representation), and API models (HTTP contracts).

**Key Principles:**
- Domain models are Pydantic-based, immutable, with no database dependencies
- ORM models use SQLAlchemy with explicit table mappings
- Mappers handle bidirectional conversion between domain ↔ ORM
- API models are separate for request/response validation
- Repositories abstract data access via protocols in domain layer

**Entities:**
- `RateLimit`: Configuration for a specific scope (global/model/group-model)
- `RateLimitWindow`: Time-based window with request/token thresholds
- `RateLimitUsage`: Runtime counter tracking for active enforcement
- `RateLimitErrorResponse`: Structured HTTP 429 error details

---

## Domain Models

Domain models live in `src/ygo74/fastapi_openai_rag/domain/models/` with **zero external dependencies** (no SQLAlchemy, no FastAPI, no Redis).

### 1. RateLimitWindow

**File:** `domain/models/rate_limit.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import time

class RateLimitWindow(BaseModel):
    """Time-based window for rate limit enforcement.

    Represents a specific time range (e.g., 00:00-08:00) with associated
    request and token limits. Multiple windows can be defined for different
    time periods within a day.

    Attributes:
        id: Unique identifier (None for new windows)
        from_time: Window start time (HH:MM:SS format)
        to_time: Window end time (HH:MM:SS format)
        max_requests: Maximum requests allowed in this window (0 = unlimited)
        max_tokens: Maximum tokens allowed in this window (0 = unlimited)

    Validation:
        - At least one limit (requests or tokens) must be > 0
        - from_time must be before to_time
        - Both limits cannot be 0 simultaneously
    """

    id: Optional[int] = Field(default=None, description="Database primary key")
    from_time: time = Field(description="Window start time (00:00:00 to 23:59:59)")
    to_time: time = Field(description="Window end time (00:00:00 to 23:59:59)")
    max_requests: int = Field(ge=0, description="Max requests in window (0 = unlimited)")
    max_tokens: int = Field(ge=0, description="Max tokens in window (0 = unlimited)")

    @field_validator('max_requests', 'max_tokens')
    @classmethod
    def validate_at_least_one_limit(cls, v: int, info) -> int:
        """Ensure at least one of max_requests or max_tokens is set."""
        if info.data.get('max_requests', 0) == 0 and info.data.get('max_tokens', 0) == 0:
            raise ValueError("At least one limit (requests or tokens) must be greater than 0")
        return v

    @field_validator('to_time')
    @classmethod
    def validate_time_range(cls, to_time: time, info) -> time:
        """Ensure from_time is before to_time."""
        from_time = info.data.get('from_time')
        if from_time and to_time <= from_time:
            raise ValueError(f"to_time ({to_time}) must be after from_time ({from_time})")
        return to_time

    def is_active_at(self, check_time: time) -> bool:
        """Check if this window is active at the given time.

        Args:
            check_time: Time to check against window bounds

        Returns:
            True if check_time falls within [from_time, to_time)
        """
        return self.from_time <= check_time < self.to_time

    class Config:
        """Pydantic configuration."""
        frozen = False  # Allow field updates for admin API
        json_schema_extra = {
            "example": {
                "id": 1,
                "from_time": "00:00:00",
                "to_time": "08:00:00",
                "max_requests": 100,
                "max_tokens": 50000
            }
        }
```

### 2. RateLimit

**File:** `domain/models/rate_limit.py`

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

class RateLimit(BaseModel):
    """Rate limit configuration for a specific scope.

    Defines rate limiting rules that apply to a particular scope (global,
    model, or group/model combination). Each rate limit contains one or more
    time windows with specific request/token thresholds.

    Attributes:
        id: Unique identifier (None for new limits)
        scope_type: Level of rate limit application
        scope_id: Identifier for model or group+model (None for global)
        windows: List of time windows with limits
        enabled: Whether this rate limit is active
        created_at: Timestamp when limit was created
        updated_at: Timestamp when limit was last modified

    Scope Types:
        - global: Applies to all requests (scope_id must be None)
        - model: Applies to all requests for a specific model (scope_id = model technical name)
        - group_model: Applies to specific group+model combo (scope_id = "group_name:model_name")

    Validation:
        - At least one window required when enabled=True
        - scope_id must be None for global scope
        - scope_id must be set for model/group_model scopes
        - group_model scope_id must follow "group:model" format
    """

    id: Optional[int] = Field(default=None, description="Database primary key")
    scope_type: Literal["global", "model", "group_model"] = Field(
        description="Type of scope for this rate limit"
    )
    scope_id: Optional[str] = Field(
        default=None,
        description="Identifier for model or group+model (None for global)"
    )
    windows: List[RateLimitWindow] = Field(
        default_factory=list,
        description="Time windows with rate limits"
    )
    enabled: bool = Field(default=True, description="Whether limit is active")
    created_at: Optional[str] = Field(default=None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="ISO 8601 update timestamp")

    @field_validator('scope_id')
    @classmethod
    def validate_scope_id(cls, v: Optional[str], info) -> Optional[str]:
        """Validate scope_id based on scope_type."""
        scope_type = info.data.get('scope_type')

        if scope_type == 'global':
            if v is not None:
                raise ValueError("Global scope must have scope_id=None")
        elif scope_type in ('model', 'group_model'):
            if not v:
                raise ValueError(f"{scope_type} scope requires scope_id to be set")
            if scope_type == 'group_model' and ':' not in v:
                raise ValueError("group_model scope_id must follow 'group_name:model_name' format")

        return v

    @field_validator('windows')
    @classmethod
    def validate_windows(cls, v: List[RateLimitWindow], info) -> List[RateLimitWindow]:
        """Ensure at least one window when enabled."""
        enabled = info.data.get('enabled', True)
        if enabled and not v:
            raise ValueError("At least one window required when rate limit is enabled")
        return v

    def get_active_window(self, current_time: time) -> Optional[RateLimitWindow]:
        """Get the active window for the current time.

        Args:
            current_time: Current time to check against windows

        Returns:
            Active RateLimitWindow or None if no window matches
        """
        for window in self.windows:
            if window.is_active_at(current_time):
                return window
        return None

    @property
    def scope_identifier(self) -> str:
        """Get canonical scope identifier for cache/counter keys.

        Returns:
            String in format "{scope_type}:{scope_id}" or "global" for global scope
        """
        if self.scope_type == 'global':
            return 'global'
        return f"{self.scope_type}:{self.scope_id}"

    class Config:
        """Pydantic configuration."""
        frozen = False
        json_schema_extra = {
            "example": {
                "id": 1,
                "scope_type": "model",
                "scope_id": "gpt-4",
                "windows": [
                    {
                        "from_time": "00:00:00",
                        "to_time": "23:59:59",
                        "max_requests": 1000,
                        "max_tokens": 500000
                    }
                ],
                "enabled": True,
                "created_at": "2025-12-06T10:30:00Z",
                "updated_at": "2025-12-06T10:30:00Z"
            }
        }
```

### 3. RateLimitUsage

**File:** `domain/models/rate_limit.py`

```python
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal

class RateLimitUsage(BaseModel):
    """Runtime tracking of rate limit consumption.

    Tracks current request and token usage for a specific scope within
    a time window. Used for enforcement decisions and remaining quota
    calculations.

    This is typically stored in Redis or in-memory cache, not in the database.
    It represents ephemeral state that resets with each window transition.

    Attributes:
        scope_identifier: Canonical scope ID (e.g., "model:gpt-4")
        metric: Type of metric being tracked (requests or tokens)
        window_start: UNIX timestamp when current window started
        window_duration: Window duration in seconds
        current_count: Current usage count (requests or tokens)
        limit: Maximum allowed in this window (0 = unlimited)

    Methods:
        is_exceeded: Check if limit has been exceeded
        remaining: Calculate remaining quota
        reset_at: Get UNIX timestamp when window resets
    """

    scope_identifier: str = Field(description="Scope ID (global, model:name, group_model:g:m)")
    metric: Literal["requests", "tokens"] = Field(description="Metric being tracked")
    window_start: int = Field(description="UNIX timestamp of window start")
    window_duration: int = Field(gt=0, description="Window duration in seconds")
    current_count: int = Field(ge=0, default=0, description="Current usage count")
    limit: int = Field(ge=0, description="Maximum allowed (0 = unlimited)")

    def is_exceeded(self) -> bool:
        """Check if the rate limit has been exceeded.

        Returns:
            True if current_count >= limit (and limit > 0), False otherwise
        """
        if self.limit == 0:  # 0 means unlimited
            return False
        return self.current_count >= self.limit

    def remaining(self) -> int:
        """Calculate remaining quota in this window.

        Returns:
            Number of requests/tokens remaining (0 if exceeded or unlimited)
        """
        if self.limit == 0:  # Unlimited
            return 0  # Convention: 0 indicates unlimited
        remaining = self.limit - self.current_count
        return max(0, remaining)

    def reset_at(self) -> int:
        """Get UNIX timestamp when this window resets.

        Returns:
            UNIX timestamp of window end
        """
        return self.window_start + self.window_duration

    def increment(self, amount: int = 1) -> int:
        """Increment usage counter.

        Args:
            amount: Amount to increment (default 1 for requests)

        Returns:
            New current_count value
        """
        self.current_count += amount
        return self.current_count

    class Config:
        """Pydantic configuration."""
        frozen = False  # Allow mutation for counter increments
        json_schema_extra = {
            "example": {
                "scope_identifier": "model:gpt-4",
                "metric": "requests",
                "window_start": 1701936000,
                "window_duration": 3600,
                "current_count": 87,
                "limit": 100
            }
        }
```

### 4. RateLimitErrorResponse

**File:** `domain/models/rate_limit.py`

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any

class RateLimitErrorDetails(BaseModel):
    """Detailed information about rate limit violation.

    Attributes:
        scope_type: Which scope was violated (global/model/group_model)
        scope_id: Specific scope identifier (None for global)
        limit_type: Which metric was exceeded (requests/tokens)
        limit: The configured limit value
        window_seconds: Window duration in seconds
        retry_after_seconds: Seconds until window resets
        current_usage: Current usage count (optional)
    """

    scope_type: Literal["global", "model", "group_model"] = Field(
        description="Type of scope that triggered rate limit"
    )
    scope_id: Optional[str] = Field(
        default=None,
        description="Specific model or group/model identifier"
    )
    limit_type: Literal["requests", "tokens"] = Field(
        description="Which metric exceeded the limit"
    )
    limit: int = Field(ge=0, description="The configured maximum value")
    window_seconds: int = Field(gt=0, description="Duration of rate limit window")
    retry_after_seconds: int = Field(ge=0, description="Seconds until limit resets")
    current_usage: Optional[int] = Field(
        default=None,
        description="Current usage count (optional for debugging)"
    )

class RateLimitErrorResponse(BaseModel):
    """OpenAI-compatible HTTP 429 error response body.

    Structured error response matching OpenAI API format for client
    compatibility. Used by exception handler to generate HTTP 429 responses.

    Attributes:
        error: Error object containing message, type, code, and details

    Response Headers (not in this model, set by exception handler):
        - Retry-After: Seconds until reset
        - X-RateLimit-Limit-Requests: Max requests allowed
        - X-RateLimit-Limit-Tokens: Max tokens allowed
        - X-RateLimit-Remaining-Requests: Requests remaining
        - X-RateLimit-Remaining-Tokens: Tokens remaining
        - X-RateLimit-Reset-Requests: UNIX timestamp of reset
        - X-RateLimit-Reset-Tokens: UNIX timestamp of reset
    """

    class ErrorObject(BaseModel):
        """Error details object."""
        message: str = Field(description="Human-readable error message")
        type: Literal["rate_limit_exceeded"] = Field(
            default="rate_limit_exceeded",
            description="Error type constant"
        )
        param: Optional[str] = Field(
            default=None,
            description="Parameter that caused error (always None for rate limits)"
        )
        code: str = Field(description="Machine-readable error code")
        details: RateLimitErrorDetails = Field(description="Rate limit violation details")

    error: ErrorObject = Field(description="Error information")

    @classmethod
    def from_usage(
        cls,
        usage: RateLimitUsage,
        scope_type: str,
        scope_id: Optional[str] = None
    ) -> "RateLimitErrorResponse":
        """Create error response from RateLimitUsage.

        Args:
            usage: Usage object that exceeded limit
            scope_type: Type of scope (global/model/group_model)
            scope_id: Specific scope identifier

        Returns:
            Formatted RateLimitErrorResponse
        """
        scope_display = f"{scope_type}" if scope_type == "global" else f"{scope_type} '{scope_id}'"
        message = f"Rate limit exceeded for {scope_display}: {usage.metric} limit of {usage.limit} per {usage.window_duration}s"

        retry_after = usage.reset_at() - int(datetime.now().timestamp())

        return cls(
            error=cls.ErrorObject(
                message=message,
                code=f"{scope_type}_rate_limit_exceeded",
                details=RateLimitErrorDetails(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    limit_type=usage.metric,
                    limit=usage.limit,
                    window_seconds=usage.window_duration,
                    retry_after_seconds=max(0, retry_after),
                    current_usage=usage.current_count
                )
            )
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": {
                    "message": "Rate limit exceeded for model 'gpt-4': requests limit of 100 per 3600s",
                    "type": "rate_limit_exceeded",
                    "param": None,
                    "code": "model_rate_limit_exceeded",
                    "details": {
                        "scope_type": "model",
                        "scope_id": "gpt-4",
                        "limit_type": "requests",
                        "limit": 100,
                        "window_seconds": 3600,
                        "retry_after_seconds": 1234,
                        "current_usage": 102
                    }
                }
            }
        }
```

---

## ORM Models

ORM models live in `src/ygo74/fastapi_openai_rag/infrastructure/db/models/` and use SQLAlchemy for database mapping.

### 1. RateLimitWindowORM

**File:** `infrastructure/db/models/rate_limit_orm.py`

```python
from sqlalchemy import Column, Integer, Time, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .base import Base

class RateLimitWindowORM(Base):
    """SQLAlchemy ORM model for rate_limit_windows table.

    Represents time-based windows for rate limiting with request/token thresholds.
    Each window belongs to a parent RateLimitORM.

    Table: rate_limit_windows
    Relationships: Many-to-one with rate_limits
    """

    __tablename__ = "rate_limit_windows"

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
    from_time: Mapped[Time] = mapped_column(Time, nullable=False)
    to_time: Mapped[Time] = mapped_column(Time, nullable=False)

    # Limits
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    rate_limit: Mapped["RateLimitORM"] = relationship(
        "RateLimitORM",
        back_populates="windows"
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimitWindowORM(id={self.id}, "
            f"from_time={self.from_time}, to_time={self.to_time}, "
            f"max_requests={self.max_requests}, max_tokens={self.max_tokens})>"
        )
```

### 2. RateLimitORM

**File:** `infrastructure/db/models/rate_limit_orm.py`

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from typing import List
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
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
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
```

---

## Mappers

Mappers handle bidirectional conversion between domain models and ORM models. Located in `infrastructure/db/mappers/`.

### RateLimitMapper

**File:** `infrastructure/db/mappers/rate_limit_mapper.py`

```python
from typing import List, Optional
from datetime import datetime, time as datetime_time
from ....domain.models.rate_limit import RateLimit, RateLimitWindow
from ..models.rate_limit_orm import RateLimitORM, RateLimitWindowORM, ScopeTypeEnum

class RateLimitMapper:
    """Mapper for converting between RateLimit domain model and RateLimitORM.

    Handles bidirectional mapping including nested RateLimitWindow objects.
    """

    @staticmethod
    def to_domain(orm: RateLimitORM) -> RateLimit:
        """Convert ORM model to domain model.

        Args:
            orm: SQLAlchemy RateLimitORM instance

        Returns:
            RateLimit domain model
        """
        return RateLimit(
            id=orm.id,
            scope_type=orm.scope_type.value,
            scope_id=orm.scope_id,
            windows=[
                RateLimitWindowMapper.to_domain(window_orm)
                for window_orm in orm.windows
            ],
            enabled=orm.enabled,
            created_at=orm.created_at.isoformat() if orm.created_at else None,
            updated_at=orm.updated_at.isoformat() if orm.updated_at else None
        )

    @staticmethod
    def to_orm(domain: RateLimit, existing_orm: Optional[RateLimitORM] = None) -> RateLimitORM:
        """Convert domain model to ORM model.

        Args:
            domain: RateLimit domain model
            existing_orm: Optional existing ORM instance to update

        Returns:
            RateLimitORM instance ready for database persistence
        """
        if existing_orm:
            # Update existing ORM
            orm = existing_orm
            orm.scope_type = ScopeTypeEnum(domain.scope_type)
            orm.scope_id = domain.scope_id
            orm.enabled = domain.enabled

            # Update windows (clear and recreate)
            orm.windows.clear()
            for window_domain in domain.windows:
                window_orm = RateLimitWindowMapper.to_orm(window_domain)
                orm.windows.append(window_orm)
        else:
            # Create new ORM
            orm = RateLimitORM(
                id=domain.id,
                scope_type=ScopeTypeEnum(domain.scope_type),
                scope_id=domain.scope_id,
                enabled=domain.enabled,
                windows=[
                    RateLimitWindowMapper.to_orm(window_domain)
                    for window_domain in domain.windows
                ]
            )

        return orm

    @staticmethod
    def to_domain_list(orm_list: List[RateLimitORM]) -> List[RateLimit]:
        """Convert list of ORM models to domain models.

        Args:
            orm_list: List of RateLimitORM instances

        Returns:
            List of RateLimit domain models
        """
        return [RateLimitMapper.to_domain(orm) for orm in orm_list]


class RateLimitWindowMapper:
    """Mapper for converting between RateLimitWindow domain model and RateLimitWindowORM."""

    @staticmethod
    def to_domain(orm: RateLimitWindowORM) -> RateLimitWindow:
        """Convert ORM model to domain model.

        Args:
            orm: SQLAlchemy RateLimitWindowORM instance

        Returns:
            RateLimitWindow domain model
        """
        return RateLimitWindow(
            id=orm.id,
            from_time=orm.from_time,
            to_time=orm.to_time,
            max_requests=orm.max_requests,
            max_tokens=orm.max_tokens
        )

    @staticmethod
    def to_orm(domain: RateLimitWindow, existing_orm: Optional[RateLimitWindowORM] = None) -> RateLimitWindowORM:
        """Convert domain model to ORM model.

        Args:
            domain: RateLimitWindow domain model
            existing_orm: Optional existing ORM instance to update

        Returns:
            RateLimitWindowORM instance
        """
        if existing_orm:
            # Update existing
            orm = existing_orm
            orm.from_time = domain.from_time
            orm.to_time = domain.to_time
            orm.max_requests = domain.max_requests
            orm.max_tokens = domain.max_tokens
        else:
            # Create new
            orm = RateLimitWindowORM(
                id=domain.id,
                from_time=domain.from_time,
                to_time=domain.to_time,
                max_requests=domain.max_requests,
                max_tokens=domain.max_tokens
            )

        return orm
```

---

## Repository Interfaces

Repository protocols define data access contracts in the domain layer. Implementations live in infrastructure.

### IRateLimitRepository

**File:** `domain/repositories/rate_limit_repository.py`

```python
from typing import Protocol, Optional, List
from ..models.rate_limit import RateLimit

class IRateLimitRepository(Protocol):
    """Protocol for rate limit data access.

    Defines contract for persisting and retrieving rate limit configurations.
    Implementations in infrastructure layer (SQLAlchemy, in-memory mock, etc.).
    """

    def get_by_id(self, rate_limit_id: int) -> Optional[RateLimit]:
        """Retrieve rate limit by ID.

        Args:
            rate_limit_id: Unique identifier

        Returns:
            RateLimit if found, None otherwise
        """
        ...

    def get_by_scope(self, scope_type: str, scope_id: Optional[str] = None) -> Optional[RateLimit]:
        """Retrieve rate limit for specific scope.

        Args:
            scope_type: Type of scope (global/model/group_model)
            scope_id: Scope identifier (None for global)

        Returns:
            RateLimit if found, None otherwise
        """
        ...

    def get_all(self, enabled_only: bool = False) -> List[RateLimit]:
        """Retrieve all rate limits.

        Args:
            enabled_only: If True, return only enabled limits

        Returns:
            List of all RateLimit configurations
        """
        ...

    def get_by_model(self, model_technical_name: str) -> List[RateLimit]:
        """Get all rate limits affecting a specific model.

        Includes model-level and all group/model limits for this model.

        Args:
            model_technical_name: Technical name of the model

        Returns:
            List of applicable RateLimit configurations
        """
        ...

    def create(self, rate_limit: RateLimit) -> RateLimit:
        """Create new rate limit configuration.

        Args:
            rate_limit: RateLimit to create (id should be None)

        Returns:
            Created RateLimit with assigned ID

        Raises:
            EntityAlreadyExistsError: If scope already has a limit
        """
        ...

    def update(self, rate_limit: RateLimit) -> RateLimit:
        """Update existing rate limit configuration.

        Args:
            rate_limit: RateLimit with updated fields (id required)

        Returns:
            Updated RateLimit

        Raises:
            EntityNotFoundError: If rate limit ID not found
        """
        ...

    def delete(self, rate_limit_id: int) -> bool:
        """Delete rate limit configuration.

        Args:
            rate_limit_id: ID of rate limit to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    def upsert(self, rate_limit: RateLimit) -> RateLimit:
        """Create or update rate limit for a scope.

        If a rate limit already exists for this scope, update it.
        Otherwise, create a new one.

        Args:
            rate_limit: RateLimit to upsert

        Returns:
            Created or updated RateLimit
        """
        ...
```

---

## Value Objects & Enums

### ScopeType

**File:** `domain/models/rate_limit.py`

```python
from typing import Literal

# Type alias for scope types (used in domain models)
ScopeType = Literal["global", "model", "group_model"]

# Helper functions for scope manipulation
def parse_group_model_scope(scope_id: str) -> tuple[str, str]:
    """Parse group/model scope ID into components.

    Args:
        scope_id: Scope ID in format "group_name:model_name"

    Returns:
        Tuple of (group_name, model_name)

    Raises:
        ValueError: If format is invalid
    """
    if ':' not in scope_id:
        raise ValueError(f"Invalid group_model scope_id format: {scope_id}")
    parts = scope_id.split(':', 1)
    return parts[0], parts[1]

def build_group_model_scope(group_name: str, model_name: str) -> str:
    """Build group/model scope ID.

    Args:
        group_name: Name of the group
        model_name: Technical name of the model

    Returns:
        Scope ID in format "group_name:model_name"
    """
    return f"{group_name}:{model_name}"
```

### MetricType

**File:** `domain/models/rate_limit.py`

```python
from typing import Literal

# Type alias for metric types
MetricType = Literal["requests", "tokens"]
```

---

## API Models (Request/Response)

API models for HTTP endpoints, separate from domain models. Located in `interfaces/api/models/`.

### CreateRateLimitRequest

**File:** `interfaces/api/models/rate_limit_api.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
from datetime import time

class TimeWindowRequest(BaseModel):
    """Request model for creating a time window."""
    from_time: str = Field(description="Window start time (HH:MM:SS)")
    to_time: str = Field(description="Window end time (HH:MM:SS)")
    max_requests: int = Field(ge=0, description="Max requests (0 = unlimited)")
    max_tokens: int = Field(ge=0, description="Max tokens (0 = unlimited)")

    @field_validator('from_time', 'to_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time string format."""
        try:
            # Parse to validate format
            time.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid time format: {v}. Expected HH:MM:SS")
        return v

class CreateRateLimitRequest(BaseModel):
    """Request model for creating rate limits via admin API."""
    scope_type: Literal["model", "group_model"] = Field(
        description="Scope type (global not allowed via API)"
    )
    scope_id: str = Field(description="Model name or group:model identifier")
    windows: List[TimeWindowRequest] = Field(
        min_length=1,
        description="Time windows with limits"
    )
    enabled: bool = Field(default=True, description="Enable limit immediately")

    class Config:
        json_schema_extra = {
            "example": {
                "scope_type": "model",
                "scope_id": "gpt-4",
                "windows": [
                    {
                        "from_time": "00:00:00",
                        "to_time": "23:59:59",
                        "max_requests": 1000,
                        "max_tokens": 500000
                    }
                ],
                "enabled": True
            }
        }
```

### RateLimitResponse

**File:** `interfaces/api/models/rate_limit_api.py`

```python
from pydantic import BaseModel, Field
from typing import List, Literal
from datetime import datetime

class TimeWindowResponse(BaseModel):
    """Response model for time window."""
    id: int
    from_time: str
    to_time: str
    max_requests: int
    max_tokens: int

class RateLimitResponse(BaseModel):
    """Response model for rate limit configuration."""
    id: int
    scope_type: Literal["global", "model", "group_model"]
    scope_id: Optional[str]
    windows: List[TimeWindowResponse]
    enabled: bool
    created_at: str
    updated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "scope_type": "model",
                "scope_id": "gpt-4",
                "windows": [
                    {
                        "id": 1,
                        "from_time": "00:00:00",
                        "to_time": "23:59:59",
                        "max_requests": 1000,
                        "max_tokens": 500000
                    }
                ],
                "enabled": True,
                "created_at": "2025-12-06T10:30:00Z",
                "updated_at": "2025-12-06T10:30:00Z"
            }
        }
```

---

## Database Schema

### SQL Schema (PostgreSQL)

**File:** `alembic/versions/xxxx_add_rate_limiting.py`

```sql
-- Table: rate_limits
CREATE TYPE scope_type_enum AS ENUM ('global', 'model', 'group_model');

CREATE TABLE rate_limits (
    id SERIAL PRIMARY KEY,
    scope_type scope_type_enum NOT NULL,
    scope_id VARCHAR(255),  -- NULL for global, model name or "group:model" for others
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Unique constraint: one rate limit per scope
    CONSTRAINT uq_rate_limit_scope UNIQUE (scope_type, scope_id)
);

-- Indexes
CREATE INDEX idx_rate_limits_scope_type ON rate_limits(scope_type);
CREATE INDEX idx_rate_limits_enabled ON rate_limits(enabled);
CREATE INDEX idx_rate_limits_scope_id ON rate_limits(scope_id);

-- Table: rate_limit_windows
CREATE TABLE rate_limit_windows (
    id SERIAL PRIMARY KEY,
    rate_limit_id INTEGER NOT NULL REFERENCES rate_limits(id) ON DELETE CASCADE,
    from_time TIME NOT NULL,
    to_time TIME NOT NULL,
    max_requests INTEGER NOT NULL DEFAULT 0,  -- 0 = unlimited
    max_tokens INTEGER NOT NULL DEFAULT 0,    -- 0 = unlimited

    -- Constraints
    CONSTRAINT chk_time_range CHECK (to_time > from_time),
    CONSTRAINT chk_at_least_one_limit CHECK (max_requests > 0 OR max_tokens > 0)
);

-- Indexes
CREATE INDEX idx_rate_limit_windows_rate_limit_id ON rate_limit_windows(rate_limit_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_rate_limit_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_rate_limits_updated_at
    BEFORE UPDATE ON rate_limits
    FOR EACH ROW
    EXECUTE FUNCTION update_rate_limit_updated_at();
```

### Redis Schema (Counter Storage)

Rate limit counters stored in Redis with keys following this pattern:

```
# Key format: ratelimit:{scope_identifier}:{metric}:{window_start_unix}
# Example: ratelimit:model:gpt-4:requests:1701936000

Key: ratelimit:model:gpt-4:requests:1701936000
Type: STRING (integer counter)
Value: 87
TTL: 7200 seconds (2x window duration)

# Commands:
INCR ratelimit:model:gpt-4:requests:1701936000  # Atomic increment
EXPIRE ratelimit:model:gpt-4:requests:1701936000 7200  # Set TTL
GET ratelimit:model:gpt-4:requests:1701936000  # Get current count
```

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                         Rate Limiting System                     │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  RateLimit   │ 1     * │ RateLimitWindow  │         │ RateLimitUsage  │
│──────────────│◄────────│──────────────────│         │─────────────────│
│ id           │         │ id               │         │ scope_identifier│
│ scope_type   │         │ rate_limit_id FK │         │ metric          │
│ scope_id     │         │ from_time        │         │ window_start    │
│ enabled      │         │ to_time          │         │ window_duration │
│ created_at   │         │ max_requests     │         │ current_count   │
│ updated_at   │         │ max_tokens       │         │ limit           │
└──────────────┘         └──────────────────┘         └─────────────────┘
       │                                                       │
       │                                                       │
       └───────────────────────────────────────────────────────┘
                                │
                                │ referenced by (not FK)
                                ▼
                    ┌───────────────────────┐
                    │ RateLimitErrorResponse│
                    │───────────────────────│
                    │ error.message         │
                    │ error.type            │
                    │ error.code            │
                    │ error.details         │
                    └───────────────────────┘

Cardinality:
- 1 RateLimit : N RateLimitWindow (one-to-many, cascade delete)
- RateLimitUsage stored in Redis, not related via FK
- RateLimitErrorResponse constructed dynamically from usage data
```

---

## Validation Rules

### RateLimit Validation

| Rule | Description | Enforcement |
|------|-------------|-------------|
| Scope uniqueness | Only one RateLimit per (scope_type, scope_id) | Database UNIQUE constraint |
| Global scope_id | Global scope must have scope_id=None | Pydantic validator |
| Model/group scope_id | Model/group_model scopes require scope_id | Pydantic validator |
| Group/model format | group_model scope_id must contain ':' separator | Pydantic validator |
| Windows required | At least one window when enabled=True | Pydantic validator |

### RateLimitWindow Validation

| Rule | Description | Enforcement |
|------|-------------|-------------|
| Time ordering | to_time must be after from_time | Pydantic validator + DB CHECK |
| One limit required | At least one of max_requests or max_tokens must be > 0 | Pydantic validator + DB CHECK |
| Non-negative limits | max_requests >= 0, max_tokens >= 0 | Pydantic Field(ge=0) |
| Window overlap | Windows within same RateLimit should not overlap | Application logic warning |

### RateLimitUsage Validation

| Rule | Description | Enforcement |
|------|-------------|-------------|
| Non-negative count | current_count >= 0 | Pydantic Field(ge=0) |
| Positive duration | window_duration > 0 | Pydantic Field(gt=0) |
| Timestamp validity | window_start is valid UNIX timestamp | Application logic |

### API Request Validation

| Rule | Description | Enforcement |
|------|-------------|-------------|
| No global via API | Cannot create/update global limits via API | API endpoint logic |
| Time format | Time strings must be HH:MM:SS | Pydantic validator |
| Non-empty windows | At least one window in request | Pydantic Field(min_length=1) |
| Valid scope type | scope_type in {model, group_model} | Pydantic Literal |

---

## Summary

**Total Entities:** 4 domain models (RateLimit, RateLimitWindow, RateLimitUsage, RateLimitErrorResponse)

**Database Tables:** 2 (rate_limits, rate_limit_windows)

**Redis Keys:** Dynamic per scope/window (e.g., `ratelimit:model:gpt-4:requests:1701936000`)

**API Models:** 6 (CreateRateLimitRequest, UpdateRateLimitRequest, RateLimitResponse, TimeWindowRequest, TimeWindowResponse, RateLimitErrorResponse)

**Mappers:** 2 (RateLimitMapper, RateLimitWindowMapper)

**Repositories:** 1 protocol (IRateLimitRepository), 1 implementation (SQLRateLimitRepository)

---

**Document Status:** ✅ COMPLETE
**Next Phase:** Contracts Generation (OpenAPI specs)
**Dependencies:** None - ready for implementation
