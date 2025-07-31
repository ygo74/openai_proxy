"""Domain model for configuration."""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json
import os

class ModelConfig(BaseModel):
    """Model configuration settings.

    Attributes:
        name (str): Display name of the model
        technical_name (str): Unique technical identifier
        url (str): API endpoint URL
        api_key (Optional[str]): API key for authentication
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

class AppConfig(BaseModel):
    """
    AppConfig is a configuration model for the application.

    Attributes:
        model_configs (List[ModelConfig]): A list of model configurations.
        db_type (str): The type of database being used.
    """
    model_configs: List[ModelConfig]
    db_type: str

    @classmethod
    def load_from_json(cls, config_path: str = "config.json") -> "AppConfig":
        """Load settings from a JSON file.

        Args:
            config_path (str): Path to JSON configuration file

        Returns:
            Settings: Application settings instance
        """
        if not os.path.exists(config_path):
            return cls(model_configs=[], db_type="sqlite")

        with open(config_path, "r") as config_file:
            config_data = json.load(config_file)
            return AppConfig(**config_data)