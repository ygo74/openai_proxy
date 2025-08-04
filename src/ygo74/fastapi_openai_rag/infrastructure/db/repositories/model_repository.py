"""SQLAlchemy repository implementation for Model entity."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.domain.repositories.model_repository import IModelRepository
from ygo74.fastapi_openai_rag.infrastructure.db.models.model_orm import ModelORM
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.model_mapper import ModelMapper
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository

class SQLModelRepository(SQLBaseRepository[LlmModel, ModelORM], IModelRepository):
    """Repository implementation for Model entity using SQLAlchemy."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, ModelORM, ModelMapper())

    def get_by_name(self, name: str) -> List[LlmModel]:
        """Get models by name.

        Args:
            name (str): Model name

        Returns:
            List[LlmModel]: List of models with the given name
        """
        # SQLAlchemy will automatically return the correct polymorphic type
        orm_models = self._session.query(ModelORM).filter(
            ModelORM.name == name
        ).all()
        return self._mapper.to_domain_list(orm_models)

    def get_by_technical_name(self, technical_name: str) -> List[LlmModel]:
        """Get models by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            List[LlmModel]: List of models with the given technical name
        """
        # SQLAlchemy will automatically return the correct polymorphic type
        orm_models = self._session.query(ModelORM).filter(
            ModelORM.technical_name == technical_name
        ).all()
        return self._mapper.to_domain_list(orm_models)

    def get_by_model_provider(self, name: str, technical_name: str) -> Optional[LlmModel]:
        """Get a model by its name and provider's technical name.

        Args:
            name (str): The name of the model
            technical_name (str): The technical name of the model's provider

        Returns:
            Optional[LlmModel]: The model if found, None otherwise
        """
        orm_model = self._session.query(ModelORM).filter(
            ModelORM.name == name,
            ModelORM.technical_name == technical_name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None


    def get_by_group_id(self, group_id: int) -> List[LlmModel]:
        """Get all models associated with a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[LlmModel]: List of models in the group
        """
        stmt = select(ModelORM).join(ModelORM.groups).filter(
            ModelORM.groups.any(id=group_id)
        )
        orm_models = self._session.execute(stmt).scalars().all()
        return self._mapper.to_domain_list(orm_models)

    def get_all(self) -> List[LlmModel]:
        """Get all models.

        Returns:
            List[LlmModel]: List of all models
        """
        orm_models = self._session.query(ModelORM).all()
        return self._mapper.to_domain_list(orm_models)

    def add(self, entity: LlmModel) -> LlmModel:
        """Add a new model entity.

        Args:
            entity (LlmModel): Model to add

        Returns:
            LlmModel: Added model with ID
        """
        orm_entity = self._mapper.to_orm(entity)
        self._session.add(orm_entity)
        self._session.flush()  # To get the ID
        return self._mapper.to_domain(orm_entity)

    def update(self, entity: LlmModel) -> LlmModel:
        """Update an existing model entity.

        Args:
            entity (LlmModel): Model to update

        Returns:
            LlmModel: Updated model
        """
        orm_entity = self._mapper.to_orm(entity)
        merged_orm = self._session.merge(orm_entity)
        return self._mapper.to_domain(merged_orm)

    def get_approved_by_name(self, name: str) -> List[LlmModel]:
        """Get all approved models by their name.

        Args:
            name (str): Model name

        Returns:
            List[LlmModel]: List of approved models with the given name
        """
        orm_models = self._session.query(ModelORM).filter(
            ModelORM.name == name,
            ModelORM.status == LlmModelStatus.APPROVED
        ).all()
        return self._mapper.to_domain_list(orm_models)