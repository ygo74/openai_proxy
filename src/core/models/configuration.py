from typing import List, Optional
from pydantic import BaseModel

class ModelConfig(BaseModel):
    url: str
    api_key: str
    api_version: Optional[str]
    provider: str
    status: str = "NEW"

class AppConfig(BaseModel):
    model_configs: List[ModelConfig]
    db_type: str
