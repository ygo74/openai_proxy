"""Model domain model."""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, field_validator
from .llm import LLMProvider

if TYPE_CHECKING:
    from .group import Group


class LlmModelStatus(str, Enum):
    """Model status enumeration."""
    NEW = "NEW"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISABLED = "DISABLED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class LlmModel(BaseModel):
    """Model domain model.

    Attributes:
        id (Optional[int]): Model ID
        url (str): Model API endpoint URL
        name (str): Model display name
        technical_name (str): Model unique technical identifier
        status (ModelStatus): Current model status
        provider (LLMProvider): LLM provider type
        created (datetime): Creation timestamp
        updated (datetime): Last update timestamp
        capabilities (Dict[str, Any]): Model capabilities configuration
        groups (List[Group]): Groups that have access to this model
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[int] = None
    url: str
    name: str
    technical_name: str
    status: LlmModelStatus = LlmModelStatus.NEW
    provider: LLMProvider
    created: datetime
    updated: datetime
    capabilities: Dict[str, Any] = {}
    groups: List['Group'] = []

    def is_azure_model(self) -> bool:
        """Check if this is an Azure model.

        Returns:
            bool: True if this is an Azure model
        """
        return hasattr(self, 'api_version') and self.provider == LLMProvider.AZURE

    @property
    def model_type(self) -> str:
        """Get the model type identifier.

        Returns:
            str: Model type identifier
        """
        return "azure" if self.is_azure_model() else "standard"


class AzureLlmModel(LlmModel):
    """Azure-specific LLM model with API version support.

    Attributes:
        api_version (str): Azure API version (required for Azure OpenAI)
    """

    api_version: str
    provider: LLMProvider = LLMProvider.AZURE

    def is_azure_model(self) -> bool:
        """Check if this is an Azure model.

        Returns:
            bool: Always True for AzureLlmModel
        """
        return True

    @field_validator('provider')
    @classmethod
    def validate_azure_provider(cls, v: LLMProvider) -> LLMProvider:
        """Validate that provider is Azure.

        Args:
            v (LLMProvider): Provider value

        Returns:
            LLMProvider: Validated provider

        Raises:
            ValueError: If provider is not Azure
        """
        if v != LLMProvider.AZURE:
            raise ValueError("AzureLlmModel must have Azure provider")
        return v

# Resolve forward references after all models are defined
try:
    from .group import Group
    LlmModel.model_rebuild()
    AzureLlmModel.model_rebuild()
except ImportError:
    # Group not yet available, will be resolved later
    pass
