"""Mapper for Model domain and ORM models."""
from typing import Optional
from .base import BaseMapper
from ....domain.models.llm_model import LlmModel, LlmModelStatus
from ..models.model_orm import ModelORM
from ....domain.models.llm import LLMProvider

class ModelMapper(BaseMapper[LlmModel, ModelORM]):
    """Mapper for converting between Model domain and ORM models."""

    def to_orm(self, entity: LlmModel) -> ModelORM:
        """Convert Model domain entity to ORM entity.

        Args:
            entity (Model): Domain entity instance

        Returns:
            ModelORM: ORM entity instance
        """
        return ModelORM(
            id=entity.id,
            url=entity.url,
            name=entity.name,
            technical_name=entity.technical_name,
            provider=entity.provider.value,
            status=entity.status,
            capabilities=entity.capabilities,
            created=entity.created,
            updated=entity.updated
        )

    def to_domain(self, orm_entity: ModelORM) -> LlmModel:
        """Convert ORM entity to domain model.

        Args:
            orm_entity (ModelORM): ORM entity

        Returns:
            LlmModel: Domain model
        """
        # Handle provider conversion with fallback
        provider = LLMProvider.OPENAI  # Default provider
        if orm_entity.provider:
            try:
                provider = LLMProvider(orm_entity.provider)
            except ValueError:
                logger.warning(f"Unknown provider '{orm_entity.provider}', using default OPENAI")

        return LlmModel(
            id=orm_entity.id,
            url=orm_entity.url,
            name=orm_entity.name,
            technical_name=orm_entity.technical_name,
            provider=provider,
            status=LlmModelStatus(orm_entity.status),
            capabilities=orm_entity.capabilities or {},
            created=orm_entity.created,
            updated=orm_entity.updated,
            groups=[]
        )