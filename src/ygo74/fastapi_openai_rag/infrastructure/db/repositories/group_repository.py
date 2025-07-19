"""SQLAlchemy repository implementation for Group entity."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.infrastructure.db.models.group_orm import GroupORM
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.group_mapper import GroupMapper
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository

class SQLGroupRepository(SQLBaseRepository[Group, GroupORM]):
    """Repository implementation for Group entity using SQLAlchemy."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, GroupORM, GroupMapper())

    def get_by_name(self, name: str) -> Optional[Group]:
        """Get group by name.

        Args:
            name (str): Group name

        Returns:
            Optional[Group]: Group if found, None otherwise
        """
        orm_model = self._session.query(GroupORM).filter(
            GroupORM.name == name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_by_model_id(self, model_id: int) -> List[Group]:
        """Get all groups associated with a model.

        Args:
            model_id (int): Model ID

        Returns:
            List[Group]: List of groups that have access to the model
        """
        stmt = select(GroupORM).join(GroupORM.models).filter(
            GroupORM.models.any(id=model_id)
        )
        orm_models = self._session.execute(stmt).scalars().all()
        return self._mapper.to_domain_list(orm_models)