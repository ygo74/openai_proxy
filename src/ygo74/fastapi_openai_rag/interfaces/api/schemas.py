"""API schemas using Pydantic models."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModelStatus

class ModelBase(BaseModel):
    """Base model schema."""
    name: str = Field(..., description="Model name")
    provider: str = Field(..., description="Model provider (e.g., OpenAI, Anthropic)")
    max_tokens: int = Field(..., description="Maximum tokens allowed per request")
    rate_limit: int = Field(..., description="Rate limit for requests per minute")
    url: str = Field(..., description="Model API endpoint URL")
    technical_name: str = Field(..., description="Unique technical identifier")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Model capabilities")

class ModelCreate(ModelBase):
    """Schema for creating a new model."""
    pass

class ModelUpdate(ModelBase):
    """Schema for updating an existing model."""
    name: Optional[str] = None
    provider: Optional[str] = None
    max_tokens: Optional[int] = None
    rate_limit: Optional[int] = None
    status: Optional[LlmModelStatus] = None

class ModelResponse(ModelBase):
    """Schema for model response."""
    id: int = Field(..., description="Model ID")
    status: LlmModelStatus = Field(..., description="Model status")
    groups: List['GroupResponse'] = Field(default_factory=list, description="Groups this model belongs to")

    class Config:
        """Pydantic config."""
        from_attributes = True

class GroupBase(BaseModel):
    """Base group schema."""
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")

class GroupCreate(GroupBase):
    """Schema for creating a new group."""
    pass

class GroupUpdate(GroupBase):
    """Schema for updating an existing group."""
    name: Optional[str] = None
    description: Optional[str] = None

class GroupResponse(GroupBase):
    """Schema for group response."""
    id: int = Field(..., description="Group ID")
    models: List[ModelResponse] = Field(default_factory=list, description="Models in this group")

    class Config:
        """Pydantic config."""
        from_attributes = True

class MessageResponse(BaseModel):
    """Schema for message responses."""
    status: str = Field(..., description="Status of the operation")
    message: str = Field(..., description="Message describing the result")

# Update forward references
ModelResponse.model_rebuild()
GroupResponse.model_rebuild()