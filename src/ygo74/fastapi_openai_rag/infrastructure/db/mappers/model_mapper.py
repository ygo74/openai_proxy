"""Mapper for Model domain and ORM entities."""
from typing import List, Dict, Any
from ....domain.models.llm_model import LlmModel, LlmModelStatus
from ....domain.models.llm import LLMProvider
from ..models.model_orm import ModelORM
from .group_mapper import GroupMapper
from datetime import datetime, timezone

class ModelMapper:
    """Mapper between Model domain and ORM entities."""

    @staticmethod
    def to_domain(orm_model: ModelORM) -> LlmModel:
        """Convert ORM entity to domain model.

        Args:
            orm_model (ModelORM): ORM entity

        Returns:
            LlmModel: Domain model

        Raises:
            ValueError: If provider is None or invalid
        """
        if not orm_model:
            raise ValueError("ORM model cannot be None")

        if not orm_model.provider:
            raise ValueError("Provider cannot be None")

        # Normalize provider value to match enum values (lowercase)
        provider_value = orm_model.provider.lower() if orm_model.provider else ""

        # Map common variations to correct enum values
        provider_mapping = {
            "openai": LLMProvider.OPENAI,
            "azure": LLMProvider.AZURE,
            "anthropic": LLMProvider.ANTHROPIC,
            "mistral": LLMProvider.MISTRAL,
            "cohere": LLMProvider.COHERE,
            "unique": LLMProvider.UNIQUE  # Add Unique provider mapping
        }

        provider = provider_mapping.get(provider_value)
        if not provider:
            raise ValueError(f"Invalid provider: {orm_model.provider}")

        base_data: Dict[str, Any] = {
            "id": orm_model.id,
            "url": orm_model.url or "",
            "name": orm_model.name or "",
            "technical_name": orm_model.technical_name or "",
            "status": orm_model.status or LlmModelStatus.NEW,
            "provider": provider,
            "created": orm_model.created or datetime.now(timezone.utc),
            "updated": orm_model.updated or datetime.now(timezone.utc),
            "capabilities": orm_model.capabilities or {},
            "groups": [GroupMapper.to_domain(group) for group in orm_model.groups] if orm_model.groups else []
        }

        return LlmModel(**base_data)

    @staticmethod
    def to_orm(domain_model: LlmModel) -> ModelORM:
        """Convert domain model to ORM entity.

        Args:
            domain_model (LlmModel): Domain model

        Returns:
            ModelORM: ORM entity
        """
        from .group_mapper import GroupMapper

        base_data: Dict[str, Any] = {
            "id": domain_model.id,
            "url": domain_model.url,
            "name": domain_model.name,
            "technical_name": domain_model.technical_name,
            "status": domain_model.status,
            "provider": domain_model.provider.value,
            "created": domain_model.created,
            "updated": domain_model.updated,
            "capabilities": domain_model.capabilities
        }

        orm_model = ModelORM(**base_data)

        # Map related groups if they exist
        if domain_model.groups:
            # We need to use existing group ORM objects or create new ones
            # This will likely require fetching existing groups by ID
            # For now, we just map them directly
            orm_model.groups = [GroupMapper.to_orm(group) for group in domain_model.groups]

        return orm_model

    @staticmethod
    def to_domain_list(orm_models: List[ModelORM]) -> List[LlmModel]:
        """Convert list of ORM entities to domain models.

        Args:
            orm_models (List[ModelORM]): List of ORM entities

        Returns:
            List[LlmModel]: List of domain models
        """
        return [ModelMapper.to_domain(orm_model) for orm_model in orm_models]