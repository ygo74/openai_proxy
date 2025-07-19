"""Model domain model."""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .group import Group


class ModelStatus(str, Enum):
    """Model status enumeration."""
    NEW = "NEW"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISABLED = "DISABLED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class Model(BaseModel):
    """Model domain model.

    Attributes:
        id (Optional[int]): Model ID
        url (str): Model API endpoint URL
        name (str): Model display name
        technical_name (str): Model unique technical identifier
        status (ModelStatus): Current model status
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
    status: ModelStatus = ModelStatus.NEW
    created: datetime
    updated: datetime
    capabilities: Dict[str, Any] = {}
    groups: List['Group'] = []
