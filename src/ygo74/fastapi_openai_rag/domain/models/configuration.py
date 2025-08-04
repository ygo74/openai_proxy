"""Domain model for configuration."""
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, model_validator
import json
import os

class ModelConfig(BaseModel):
    """Model configuration settings.

    Attributes:
        name (str): Display name of the models' provider
        technical_name (str): Unique technical identifier
        url (str): API endpoint URL
        provider (str): Provider type (openai, azure, etc.)
        api_key (Optional[str]): API key for authentication
        api_version (Optional[str]): API version for Azure models
        rate_limit (Optional[int]): Rate limit per minute
        capabilities (Dict[str, Any]): Model-specific capabilities
    """
    name: str
    technical_name: str
    url: str
    provider: str
    api_key: Optional[str] = None
    api_version: Optional[str] = None  # For Azure models
    rate_limit: Optional[int] = None
    capabilities: Dict[str, Any] = {}

class AzureModelConfig(ModelConfig):
    """Azure-specific model configuration with management API support."""

    api_version: str
    # Required for Azure Management API deployment listing
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: str
    resource_group: str
    resource_name: str

    @model_validator(mode='before')
    @classmethod
    def validate_azure_provider(cls, values):
        """Ensure provider is set to azure for AzureModelConfig."""
        if isinstance(values, dict):
            values['provider'] = 'azure'
        return values

class AppConfig(BaseModel):
    """AppConfig is a configuration model for the application.

    Attributes:
        model_configs (List[Union[ModelConfig, AzureModelConfig]]): List of model configurations
        db_type (str): The type of database being used
    """
    model_configs: List[Union[ModelConfig, AzureModelConfig]]
    db_type: str

    @classmethod
    def load_from_json(cls, config_path: str = "config.json") -> "AppConfig":
        """Load settings from a JSON file with proper config type discrimination.

        Args:
            config_path (str): Path to JSON configuration file

        Returns:
            AppConfig: Application settings instance
        """
        if not os.path.exists(config_path):
            return cls(model_configs=[], db_type="sqlite")

        with open(config_path, "r") as config_file:
            config_data = json.load(config_file)

            # Process model configs to determine the correct type
            processed_configs = []
            for model_config_data in config_data.get("model_configs", []):
                if model_config_data.get("provider", "").lower() == "azure":
                    # Check if it has Azure-specific fields
                    azure_fields = ["tenant_id", "client_id", "client_secret",
                                   "subscription_id", "resource_group", "resource_name"]

                    if all(field in model_config_data for field in azure_fields):
                        # It's an Azure config with management fields
                        processed_configs.append(AzureModelConfig(**model_config_data))
                    else:
                        # It's a basic Azure config without management fields
                        processed_configs.append(ModelConfig(**model_config_data))
                else:
                    # It's a regular model config
                    processed_configs.append(ModelConfig(**model_config_data))

            return cls(
                model_configs=processed_configs,
                db_type=config_data.get("db_type", "sqlite")
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Configuration as dictionary
        """
        return {
            "model_configs": [
                config.model_dump() for config in self.model_configs
            ],
            "db_type": self.db_type
        }

    def save_to_json(self, config_path: str = "config.json") -> None:
        """Save configuration to JSON file.

        Args:
            config_path (str): Path to save JSON configuration file
        """
        with open(config_path, "w") as config_file:
            json.dump(self.to_dict(), config_file, indent=2, default=str)