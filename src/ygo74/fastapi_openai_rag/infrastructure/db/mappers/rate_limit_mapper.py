"""Mapper for RateLimit and RateLimitWindow domain and ORM models.

This mapper belongs to the infrastructure layer and handles conversions between:
- Domain entities (domain layer)
- SQLAlchemy ORM models (infrastructure layer)

It does NOT handle API/Pydantic conversions - those are in interfaces/api/mappers/.
"""
from typing import List, Optional
from datetime import datetime, timezone

from ....domain.models.rate_limit import RateLimit, RateLimitWindow
from ..models.rate_limit_orm import RateLimitORM, RateLimitWindowORM, ScopeTypeEnum
from .base import BaseMapper


class RateLimitWindowMapper:
    """Mapper for converting between RateLimitWindow domain and ORM models."""

    @staticmethod
    def to_orm(
        domain: RateLimitWindow,
        rate_limit_id: Optional[int] = None,
        existing_orm: Optional[RateLimitWindowORM] = None
    ) -> RateLimitWindowORM:
        """Convert RateLimitWindow domain entity to ORM entity.

        Args:
            domain: Domain entity instance
            rate_limit_id: Foreign key to parent rate limit (required for new entities)
            existing_orm: Existing ORM entity to update (optional)

        Returns:
            RateLimitWindowORM: ORM entity instance
        """
        if existing_orm:
            # Update existing entity
            existing_orm.from_time = domain.from_time
            existing_orm.to_time = domain.to_time
            existing_orm.max_requests = domain.max_requests if domain.max_requests is not None else 0
            existing_orm.max_tokens = domain.max_tokens if domain.max_tokens is not None else 0
            return existing_orm
        else:
            # Create new entity
            return RateLimitWindowORM(
                id=domain.id,
                rate_limit_id=rate_limit_id,
                from_time=domain.from_time,
                to_time=domain.to_time,
                max_requests=domain.max_requests if domain.max_requests is not None else 0,
                max_tokens=domain.max_tokens if domain.max_tokens is not None else 0
            )

    @staticmethod
    def to_domain(orm_entity: RateLimitWindowORM) -> RateLimitWindow:
        """Convert ORM entity to RateLimitWindow domain entity.

        Args:
            orm_entity: ORM entity instance

        Returns:
            RateLimitWindow: Domain entity instance
        """
        return RateLimitWindow(
            id=orm_entity.id,
            from_time=orm_entity.from_time,
            to_time=orm_entity.to_time,
            max_requests=orm_entity.max_requests if orm_entity.max_requests != 0 else None,
            max_tokens=orm_entity.max_tokens if orm_entity.max_tokens != 0 else None
        )

    @classmethod
    def to_domain_list(cls, orm_entities: List[RateLimitWindowORM]) -> List[RateLimitWindow]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities: List of ORM entities

        Returns:
            List[RateLimitWindow]: List of domain entities
        """
        return [cls.to_domain(orm_entity) for orm_entity in orm_entities]


class RateLimitMapper(BaseMapper[RateLimit, RateLimitORM]):
    """Mapper for converting between RateLimit domain and ORM models."""

    @staticmethod
    def to_orm(
        domain: RateLimit,
        existing_orm: Optional[RateLimitORM] = None
    ) -> RateLimitORM:
        """Convert RateLimit domain entity to ORM entity.

        Args:
            domain: Domain entity instance
            existing_orm: Existing ORM entity to update (optional)

        Returns:
            RateLimitORM: ORM entity instance with nested windows
        """
        now = datetime.now(timezone.utc)

        if existing_orm:
            # Update existing entity
            existing_orm.scope_type = ScopeTypeEnum(domain.scope_type)
            existing_orm.scope_id = domain.scope_id
            existing_orm.enabled = domain.enabled
            existing_orm.updated_at = now

            # Update windows (replace strategy)
            # Remove existing windows not in domain
            existing_window_ids = {w.id for w in domain.windows if w.id is not None}
            existing_orm.windows = [
                w for w in existing_orm.windows if w.id in existing_window_ids
            ]

            # Update or add windows
            for domain_window in domain.windows:
                if domain_window.id:
                    # Update existing window
                    existing_window = next(
                        (w for w in existing_orm.windows if w.id == domain_window.id),
                        None
                    )
                    if existing_window:
                        RateLimitWindowMapper.to_orm(
                            domain_window,
                            rate_limit_id=existing_orm.id,
                            existing_orm=existing_window
                        )
                else:
                    # Add new window
                    new_window = RateLimitWindowMapper.to_orm(
                        domain_window,
                        rate_limit_id=existing_orm.id
                    )
                    existing_orm.windows.append(new_window)

            return existing_orm
        else:
            # Create new entity
            orm_entity = RateLimitORM(
                id=domain.id if domain.id else None,
                scope_type=ScopeTypeEnum(domain.scope_type),
                scope_id=domain.scope_id,
                enabled=domain.enabled,
                created_at=domain.created_at if domain.created_at else now,
                updated_at=domain.updated_at if domain.updated_at else now,
                windows=[]
            )

            # Add windows (will be persisted with cascade)
            for domain_window in domain.windows:
                window_orm = RateLimitWindowMapper.to_orm(
                    domain_window,
                    rate_limit_id=None  # Will be set by SQLAlchemy relationship
                )
                orm_entity.windows.append(window_orm)

            return orm_entity

    @staticmethod
    def to_domain(orm_entity: RateLimitORM) -> RateLimit:
        """Convert ORM entity to RateLimit domain entity.

        Args:
            orm_entity: ORM entity instance

        Returns:
            RateLimit: Domain entity instance with nested windows
        """
        # Convert windows
        windows = RateLimitWindowMapper.to_domain_list(orm_entity.windows)

        return RateLimit(
            id=orm_entity.id,
            scope_type=orm_entity.scope_type.value,
            scope_id=orm_entity.scope_id,
            windows=windows,
            enabled=orm_entity.enabled,
            created_at=orm_entity.created_at.isoformat() if orm_entity.created_at else None,
            updated_at=orm_entity.updated_at.isoformat() if orm_entity.updated_at else None
        )

    @classmethod
    def to_domain_list(cls, orm_entities: List[RateLimitORM]) -> List[RateLimit]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities: List of ORM entities

        Returns:
            List[RateLimit]: List of domain entities
        """
        return [cls.to_domain(orm_entity) for orm_entity in orm_entities]
