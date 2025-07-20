"""Group domain model."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from .llm_model import LlmModel

class Group(BaseModel):
    """Group domain model.

    Attributes:
        id (Optional[int]): Group ID
        name (str): Group name
        description (Optional[str]): Group description
        created (datetime): Creation timestamp
        updated (datetime): Last update timestamp
        models (List[Model]): List of models in the group
    """
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    created: datetime
    updated: datetime
    models: List['LlmModel'] = []

LlmModel.model_rebuild()  # Ensure forward reference resolution
Group.model_rebuild()  # Ensure forward reference resolution
