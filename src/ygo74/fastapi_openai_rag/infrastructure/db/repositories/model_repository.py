"""SQLAlchemy repository implementation for Model entity."""
from typing import Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import select
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, AzureLlmModel
from ygo74.fastapi_openai_rag.infrastructure.db.models.model_orm import ModelORM, AzureModelORM
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.model_mapper import ModelMapper
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository

class SQLModelRepository(SQLBaseRepository[Union[LlmModel, AzureLlmModel], Union[ModelORM, AzureModelORM]]):
    """Repository implementation for Model entity using SQLAlchemy with polymorphic support."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, ModelORM, ModelMapper())

    def get_by_name(self, name: str) -> Optional[Union[LlmModel, AzureLlmModel]]:
        """Get model by name.

        Args:
            name (str): Model name

        Returns:
            Optional[Union[LlmModel, AzureLlmModel]]: Model if found, None otherwise
        """
        # SQLAlchemy will automatically return the correct polymorphic type
        orm_model = self._session.query(ModelORM).filter(
            ModelORM.name == name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_by_technical_name(self, technical_name: str) -> Optional[Union[LlmModel, AzureLlmModel]]:
        """Get model by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            Optional[Union[LlmModel, AzureLlmModel]]: Model if found, None otherwise
        """
        # SQLAlchemy will automatically return the correct polymorphic type
        orm_model = self._session.query(ModelORM).filter(
            ModelORM.technical_name == technical_name
        ).first()
        return self._mapper.to_domain(orm_model) if orm_model else None

    def get_by_group_id(self, group_id: int) -> List[Union[LlmModel, AzureLlmModel]]:
        """Get all models associated with a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[Union[LlmModel, AzureLlmModel]]: List of models in the group
        """
        stmt = select(ModelORM).join(ModelORM.groups).filter(
            ModelORM.groups.any(id=group_id)
        )
        orm_models = self._session.execute(stmt).scalars().all()
        return self._mapper.to_domain_list(orm_models)

    def get_all(self) -> List[Union[LlmModel, AzureLlmModel]]:
        """Get all models.

        Returns:
            List[Union[LlmModel, AzureLlmModel]]: List of all models
        """
        # Override to ensure polymorphic queries work correctly
        orm_models = self._session.query(ModelORM).all()
        return self._mapper.to_domain_list(orm_models)

    def add(self, entity: Union[LlmModel, AzureLlmModel]) -> Union[LlmModel, AzureLlmModel]:
        """Add a new model entity.

        Args:
            entity (Union[LlmModel, AzureLlmModel]): Model to add

        Returns:
            Union[LlmModel, AzureLlmModel]: Added model with ID
        """
        orm_entity = self._mapper.to_orm(entity)
        self._session.add(orm_entity)
        self._session.flush()  # To get the ID
        return self._mapper.to_domain(orm_entity)

    def update(self, entity: Union[LlmModel, AzureLlmModel]) -> Union[LlmModel, AzureLlmModel]:
        """Update an existing model entity.

        Args:
            entity (Union[LlmModel, AzureLlmModel]): Model to update

        Returns:
            Union[LlmModel, AzureLlmModel]: Updated model
        """
        orm_entity = self._mapper.to_orm(entity)
        merged_orm = self._session.merge(orm_entity)
        return self._mapper.to_domain(merged_orm)