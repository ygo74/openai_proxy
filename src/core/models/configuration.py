from typing import List, Optional
from pydantic import BaseModel

class ModelConfig(BaseModel):
    """
    ModelConfig is a Pydantic model that represents the configuration for a model provider.

    Attributes:
        url (str): The URL endpoint for the model provider.
        api_key (str): The API key used for authentication with the model provider.
        api_version (Optional[str]): The version of the API to use, if applicable.
        provider (str): The name of the model provider.
        status (str): The current status of the configuration. Defaults to "NEW".
    """
    url: str
    api_key: str
    api_version: Optional[str]
    provider: str
    status: str = "NEW"

class AppConfig(BaseModel):
    """
    AppConfig is a configuration model for the application.

    Attributes:
        model_configs (List[ModelConfig]): A list of model configurations.
        db_type (str): The type of database being used.
    """
    model_configs: List[ModelConfig]
    db_type: str
