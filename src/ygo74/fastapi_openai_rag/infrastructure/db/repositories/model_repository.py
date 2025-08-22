"""SQLAlchemy repository implementation for Model entity."""
from typing import Optional, List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from ....domain.models.llm_model import LlmModel, LlmModelStatus
from ....domain.repositories.model_repository import IModelRepository
from ..models.model_orm import ModelORM
from ..mappers.model_mapper import ModelMapper
from .base_repository import SQLBaseRepository

class SQLModelRepository(SQLBaseRepository[LlmModel, ModelORM], IModelRepository):
    """Repository implementation for Model entity using SQLAlchemy."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, ModelORM, ModelMapper)

    def get_by_id(self, id: int) -> Optional[LlmModel]:
        """Get model by ID.

        This method overrides the base implementation to ensure groups are loaded.

        Args:
            id (int): Model ID

        Returns:
            Optional[LlmModel]: Model if found, None otherwise
        """
        stmt = select(ModelORM).options(selectinload(ModelORM.groups)).where(ModelORM.id == id)
        result = self._session.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_all(self) -> List[LlmModel]:
        """Get all models.

        This method overrides the base implementation to ensure groups are loaded.

        Returns:
            List[LlmModel]: All models
        """
        stmt = select(ModelORM).options(selectinload(ModelORM.groups))
        result = self._session.execute(stmt)
        orm_models = result.scalars().all()
        return [self._mapper.to_domain(orm_model) for orm_model in orm_models]

    def get_by_name(self, name: str) -> List[LlmModel]:
        """Get models by name.

        Args:
            name (str): Model name

        Returns:
            List[LlmModel]: List of models with the given name
        """
        # Use SQLAlchemy 2.0 style query instead of 1.x style
        stmt = select(ModelORM).options(selectinload(ModelORM.groups)).where(ModelORM.name == name)
        result = self._session.execute(stmt)
        orm_models = result.scalars().all()
        return [self._mapper.to_domain(orm_model) for orm_model in orm_models]

    def get_by_technical_name(self, technical_name: str) -> List[LlmModel]:
        """Get models by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            List[LlmModel]: List of models with the given technical name
        """
        stmt = select(ModelORM).options(selectinload(ModelORM.groups)).where(ModelORM.technical_name == technical_name)
        result = self._session.execute(stmt)
        orm_models = result.scalars().all()

        return [self._mapper.to_domain(orm_model) for orm_model in orm_models]

    def get_by_model_provider(self, name: str, technical_name: str) -> Optional[LlmModel]:
        """Get a model by its name and provider's technical name.

        Args:
            name (str): The name of the model
            technical_name (str): The technical name of the model's provider

        Returns:
            Optional[LlmModel]: The model if found, None otherwise
        """
        stmt = select(ModelORM).options(selectinload(ModelORM.groups)).where(
            ModelORM.name == name,
            ModelORM.technical_name == technical_name
        )
        result = self._session.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_by_group_id(self, group_id: int) -> List[LlmModel]:
        """Get all models associated with a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[LlmModel]: List of distinct models in the group
        """
        stmt = (
            select(ModelORM)
            .options(selectinload(ModelORM.groups))
            .join(ModelORM.groups)
            .where(ModelORM.groups.any(id=group_id))
            .distinct()  # Add distinct to avoid duplicate models
        )
        result = self._session.execute(stmt)
        model_orms = result.scalars().all()
        return [self._mapper.to_domain(model_orm) for model_orm in model_orms]

    def get_approved_by_name(self, name: str) -> List[LlmModel]:
        """Get all approved models by their name.

        Args:
            name (str): Model name

        Returns:
            List[LlmModel]: List of approved models with the given name
        """
        stmt = select(ModelORM).options(selectinload(ModelORM.groups)).where(
            ModelORM.name == name,
            ModelORM.status == LlmModelStatus.APPROVED
        )
        result = self._session.execute(stmt)
        orm_models = result.scalars().all()
        return [self._mapper.to_domain(orm_model) for orm_model in orm_models]