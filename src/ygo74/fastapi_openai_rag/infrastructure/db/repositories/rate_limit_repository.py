"""Rate limit repository for database operations."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....domain.models.rate_limit import RateLimit
from ....domain.repositories.rate_limit_repository import IRateLimitRepository
from ..models.rate_limit_orm import RateLimitORM, RateLimitWindowORM, ScopeTypeEnum
from ..mappers.rate_limit_mapper import RateLimitMapper
from .base_repository import SQLBaseRepository


class SQLRateLimitRepository(SQLBaseRepository[RateLimit, RateLimitORM], IRateLimitRepository):
    """Repository for RateLimit operations.

    Provides database access for rate limit configurations including
    CRUD operations and scope-based queries.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: Database session for transactions
        """
        super().__init__(session, RateLimitORM, RateLimitMapper)

    def get_by_scope(self, scope_type: str, scope_id: Optional[str] = None) -> Optional[RateLimit]:
        """Get rate limit configuration for a specific scope.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope (None for global, model_id for model,
                     'group_id:model_id' for group_model)

        Returns:
            Optional[RateLimit]: The rate limit configuration if found, None otherwise
        """
        # Convert string scope_type to enum
        try:
            scope_enum = ScopeTypeEnum(scope_type)
        except ValueError:
            return None

        # Build query with eager loading of windows
        stmt = (
            select(RateLimitORM)
            .options(selectinload(RateLimitORM.windows))
            .where(RateLimitORM.scope_type == scope_enum)
        )

        # Add scope_id filter based on scope type
        if scope_type == "global":
            stmt = stmt.where(RateLimitORM.scope_id.is_(None))
        else:
            stmt = stmt.where(RateLimitORM.scope_id == scope_id)

        result = self._session.execute(stmt)
        orm_entity = result.scalar_one_or_none()

        if orm_entity:
            return self._mapper.to_domain(orm_entity)
        return None

    def get_all_by_scope_type(self, scope_type: str) -> List[RateLimit]:
        """Get all rate limits for a specific scope type.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')

        Returns:
            List[RateLimit]: List of rate limit configurations for the scope type
        """
        # Convert string scope_type to enum
        try:
            scope_enum = ScopeTypeEnum(scope_type)
        except ValueError:
            return []

        stmt = (
            select(RateLimitORM)
            .options(selectinload(RateLimitORM.windows))
            .where(RateLimitORM.scope_type == scope_enum)
            .order_by(RateLimitORM.id)
        )

        result = self._session.execute(stmt)
        orm_entities = result.scalars().all()

        return [self._mapper.to_domain(orm_entity) for orm_entity in orm_entities]

    def get_enabled_only(self) -> List[RateLimit]:
        """Get all enabled rate limit configurations.

        Returns:
            List[RateLimit]: List of enabled rate limit configurations
        """
        stmt = (
            select(RateLimitORM)
            .options(selectinload(RateLimitORM.windows))
            .where(RateLimitORM.enabled == True)
            .order_by(RateLimitORM.scope_type, RateLimitORM.id)
        )

        result = self._session.execute(stmt)
        orm_entities = result.scalars().all()

        return [self._mapper.to_domain(orm_entity) for orm_entity in orm_entities]

    def upsert(self, rate_limit: RateLimit) -> RateLimit:
        """Create or update a rate limit configuration.

        If a rate limit with the same scope_type and scope_id exists, it will be updated.
        Otherwise, a new rate limit will be created.

        Args:
            rate_limit: The rate limit configuration to create or update

        Returns:
            RateLimit: The created or updated rate limit configuration
        """
        # Check if rate limit already exists by scope
        existing = self.get_by_scope(rate_limit.scope_type, rate_limit.scope_id)

        if existing:
            # Update existing rate limit
            existing_orm = (
                self._session.query(RateLimitORM)
                .options(selectinload(RateLimitORM.windows))
                .filter(RateLimitORM.id == existing.id)
                .one()
            )

            # Use mapper to update ORM entity
            updated_orm = self._mapper.to_orm(rate_limit, existing_orm=existing_orm)
            self._session.flush()
            self._session.refresh(updated_orm)

            return self._mapper.to_domain(updated_orm)
        else:
            # Create new rate limit
            return self.add(rate_limit)

    def delete_by_scope(self, scope_type: str, scope_id: Optional[str] = None) -> bool:
        """Delete a rate limit configuration by scope.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope

        Returns:
            bool: True if deleted, False if not found
        """
        # Find the rate limit by scope
        rate_limit = self.get_by_scope(scope_type, scope_id)

        if rate_limit and rate_limit.id:
            self.delete(rate_limit.id)
            return True

        return False

    def get_all(self) -> List[RateLimit]:
        """Get all rate limit configurations.

        Returns:
            List[RateLimit]: List of all rate limit configurations
        """
        stmt = (
            select(RateLimitORM)
            .options(selectinload(RateLimitORM.windows))
            .order_by(RateLimitORM.scope_type, RateLimitORM.id)
        )

        result = self._session.execute(stmt)
        orm_entities = result.scalars().all()

        return [self._mapper.to_domain(orm_entity) for orm_entity in orm_entities]
