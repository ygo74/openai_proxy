"""Group repository for database operations."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ....domain.models.group import Group
from ....domain.repositories.group_repository import IGroupRepository
from ..models.group_orm import GroupORM
from ..mappers.group_mapper import GroupMapper
from .base_repository import SQLBaseRepository

class SQLGroupRepository(SQLBaseRepository[Group, GroupORM], IGroupRepository):
    """Repository for Group operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session (Session): Database session
        """
        super().__init__(session, GroupORM, GroupMapper)

    def get_by_name(self, name: str) -> Optional[Group]:
        """
        Get group by name.

        Args:
            name: Group name

        Returns:
            Group domain model if found, None otherwise
        """
        stmt = select(GroupORM).where(GroupORM.name == name)
        result = self._session.execute(stmt)
        group_orm = result.scalar_one_or_none()

        if group_orm:
            return self._mapper.to_domain(group_orm)
        return None

    def get_by_model_id(self, model_id: int) -> List[Group]:
        """
        Get all groups associated with a model.

        Args:
            model_id: Model ID

        Returns:
            List of groups that have access to the model
        """
        stmt = (
            select(GroupORM)
            .options(selectinload(GroupORM.models))
            .join(GroupORM.models)
            .where(GroupORM.models.any(id=model_id))
        )
        result = self._session.execute(stmt)
        group_orms = result.scalars().all()
        return [self._mapper.to_domain(group_orm) for group_orm in group_orms]
