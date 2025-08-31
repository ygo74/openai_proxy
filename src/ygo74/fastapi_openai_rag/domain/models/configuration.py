"""Domain model for configuration."""
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, model_validator
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

class UniqueModelConfig(ModelConfig):
    """Configuration for Unique models.

    Attributes:
        api_key: API key for Unique
        base_url: Base URL for Unique API (optional)
        company_id: Company ID for Unique API calls
        user_id: Default user ID for Unique API calls (optional)
    """
    app_id: str
    company_id: str
    user_id: Optional[str] = None

class ForwarderConfig(BaseModel):
    """Base configuration for audit log forwarders."""
    enabled: bool = False

class PrintForwarderConfig(ForwarderConfig):
    """Configuration for console print forwarder."""
    level: str = "DEBUG"

class HttpForwarderConfig(ForwarderConfig):
    """Configuration for HTTP forwarder."""
    url: str
    headers: Dict[str, str] = {}
    retry_count: int = 3
    timeout_seconds: int = 5

class AuditConfig(BaseModel):
    """Configuration for audit functionality."""
    db_enabled: bool = True
    log_level: str = "INFO"
    exclude_paths: List[str] = ["/health", "/metrics"]
    sensitive_headers: List[str] = ["Authorization", "API-Key"]

class ForwardersConfig(BaseModel):
    """Configuration for all forwarders."""
    print: PrintForwarderConfig = PrintForwarderConfig()
    http: List[HttpForwarderConfig] = []

class AppConfig(BaseModel):
    """AppConfig is a configuration model for the application.

    Attributes:
        model_configs (List[Union[ModelConfig, AzureModelConfig, UniqueModelConfig]]): List of model configurations
        db_type (str): The type of database being used
        forwarders (ForwardersConfig): Configuration for audit forwarders
        audit (AuditConfig): Configuration for audit functionality
    """
    model_configs: List[Union[ModelConfig, AzureModelConfig, UniqueModelConfig]]
    db_type: str
    db_url: str
    forwarders: ForwardersConfig = ForwardersConfig()
    audit: AuditConfig = AuditConfig()

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
                    # It's an Azure config with management fields
                    processed_configs.append(AzureModelConfig(**model_config_data))
                elif model_config_data.get("provider", "").lower() == "unique":
                    # It's a Unique config
                    processed_configs.append(UniqueModelConfig(**model_config_data))
                else:
                    # It's a regular model config
                    processed_configs.append(ModelConfig(**model_config_data))

            # Process forwarders configuration
            forwarders_config = ForwardersConfig()
            if "forwarders" in config_data:
                forwarders_data = config_data["forwarders"]

                # Print forwarder config
                if "print" in forwarders_data:
                    forwarders_config.print = PrintForwarderConfig(**forwarders_data["print"])

                # HTTP forwarders config
                if "http" in forwarders_data and isinstance(forwarders_data["http"], list):
                    forwarders_config.http = [
                        HttpForwarderConfig(**http_config)
                        for http_config in forwarders_data["http"]
                    ]

            # Process audit configuration
            audit_config = AuditConfig()
            if "audit" in config_data:
                audit_config = AuditConfig(**config_data["audit"])

            return cls(
                model_configs=processed_configs,
                db_type=config_data.get("db_type", "sqlite"),
                db_url=config_data.get("db_url"),
                forwarders=forwarders_config,
                audit=audit_config
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
            "db_type": self.db_type,
            "forwarders": {
                "print": self.forwarders.print.model_dump(),
                "http": [http_config.model_dump() for http_config in self.forwarders.http]
            },
            "audit": self.audit.model_dump()
        }

    def save_to_json(self, config_path: str = "config.json") -> None:
        """Save configuration to JSON file.

        Args:
            config_path (str): Path to save JSON configuration file
        """
        with open(config_path, "w") as config_file:
            json.dump(self.to_dict(), config_file, indent=2, default=str)
