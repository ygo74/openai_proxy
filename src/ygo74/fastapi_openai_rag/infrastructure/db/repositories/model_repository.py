"""SQLAlchemy repository implementation for Model entity."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel
from ygo74.fastapi_openai_rag.infrastructure.db.models.model_orm import ModelORM
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.model_mapper import ModelMapper
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository

class SQLModelRepository(SQLBaseRepository[LlmModel, ModelORM]):
    """Repository implementation for Model entity using SQLAlchemy."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, ModelORM, ModelMapper())

    def get_by_name(self, name: str) -> Optional[LlmModel]:
        """Get model by name.

        Args:
            name (str): Model name

        Returns:
            Optional[Model]: Model if found, None otherwise
        """
        orm_model = self._session.query(ModelORM).filter(
            ModelORM.name == name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None


    def get_by_technical_name(self, technical_name: str) -> Optional[LlmModel]:
        """Get model by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            Optional[Model]: Model if found, None otherwise
        """
        orm_model = self._session.query(ModelORM).filter(
            ModelORM.technical_name == technical_name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_by_group_id(self, group_id: int) -> List[LlmModel]:
        """Get all models associated with a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[Model]: List of models in the group
        """
        stmt = select(ModelORM).join(ModelORM.groups).filter(
            ModelORM.groups.any(id=group_id)
        )
        orm_models = self._session.execute(stmt).scalars().all()
        return self._mapper.to_domain_list(orm_models)