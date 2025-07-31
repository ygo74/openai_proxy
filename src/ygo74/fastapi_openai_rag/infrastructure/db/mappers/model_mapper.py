"""Mapper for Model domain and ORM entities."""
from typing import List, Union
from ....domain.models.llm_model import LlmModel, AzureLlmModel, LlmModelStatus  # Ensure correct import path
from ....domain.models.llm import LLMProvider
from ..models.model_orm import ModelORM, AzureModelORM
from .group_mapper import GroupMapper
from datetime import datetime, timezone

class ModelMapper:
    """Mapper between Model domain and ORM entities."""

    @staticmethod
    def to_domain(orm_model: Union[ModelORM, AzureModelORM]) -> Union[LlmModel, AzureLlmModel]:
        """Convert ORM entity to domain model.

        Args:
            orm_model (Union[ModelORM, AzureModelORM]): ORM entity

        Returns:
            Union[LlmModel, AzureLlmModel]: Domain model

        Raises:
            ValueError: If provider is None or invalid
        """
        if not orm_model:
            raise ValueError("ORM model cannot be None")

        if not orm_model.provider:
            raise ValueError("Provider cannot be None")

        # Ensure we have all required fields
        if not hasattr(orm_model, 'model_type') or orm_model.model_type is None:
            orm_model.model_type = "standard"  # Default fallback

        # Normalize provider value to match enum values (lowercase)
        provider_value = orm_model.provider.lower() if orm_model.provider else ""

        # Map common variations to correct enum values
        provider_mapping = {
            "openai": LLMProvider.OPENAI,
            "azure": LLMProvider.AZURE,
            "anthropic": LLMProvider.ANTHROPIC,
            "mistral": LLMProvider.MISTRAL,
            "cohere": LLMProvider.COHERE
        }

        provider = provider_mapping.get(provider_value)
        if not provider:
            raise ValueError(f"Invalid provider: {orm_model.provider}")

        base_data = {
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

        if isinstance(orm_model, AzureModelORM) or orm_model.model_type == "azure":
            base_data["api_version"] = orm_model.api_version
            return AzureLlmModel(**base_data)
        else:
            return LlmModel(**base_data)

    @staticmethod
    def to_orm(domain_model: Union[LlmModel, AzureLlmModel]) -> Union[ModelORM, AzureModelORM]:
        """Convert domain model to ORM entity.

        Args:
            domain_model (Union[LlmModel, AzureLlmModel]): Domain model

        Returns:
            Union[ModelORM, AzureModelORM]: ORM entity
        """
        base_data = {
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

        if domain_model.is_azure_model():
            base_data["api_version"] = domain_model.api_version
            base_data["model_type"] = "azure"
            return AzureModelORM(**base_data)
        else:
            base_data["model_type"] = "standard"
            return ModelORM(**base_data)

    @staticmethod
    def to_domain_list(orm_models: List[Union[ModelORM, AzureModelORM]]) -> List[Union[LlmModel, AzureLlmModel]]:
        """Convert list of ORM entities to domain models.

        Args:
            orm_models (List[Union[ModelORM, AzureModelORM]]): List of ORM entities

        Returns:
            List[Union[LlmModel, AzureLlmModel]]: List of domain models
        """
        return [ModelMapper.to_domain(orm_model) for orm_model in orm_models]