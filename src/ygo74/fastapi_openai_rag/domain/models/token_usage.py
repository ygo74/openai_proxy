"""Domain model for token usage tracking."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class TokenUsage(BaseModel):
    """Represents token usage for a specific user and model.

    Attributes:
        id (Optional[int]): Database ID
        user_id (str): User identifier
        model (str): Model name
        prompt_tokens (int): Number of tokens in the prompt
        completion_tokens (int): Number of tokens in the completion
        total_tokens (int): Total tokens used
        timestamp (datetime): When the usage occurred
        request_id (Optional[str]): Associated request ID
        endpoint (str): API endpoint used
    """
    id: Optional[int] = None
    user_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int = Field(default=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None
    endpoint: str
