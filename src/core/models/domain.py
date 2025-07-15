from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ModelStatus(str, Enum):
    NEW = "NEW"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"

class Model(BaseModel):
    id: Optional[int] = None
    url: str
    name: str
    technical_name: str
    status: ModelStatus = ModelStatus.NEW
    created: datetime
    updated: datetime
    capabilities: Dict[str, Any] = {}
    groups: List["Group"] = []

class Group(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    created: datetime
    updated: datetime
    models: List[Model] = []

# Éviter les références circulaires
Model.model_rebuild()
Group.model_rebuild()