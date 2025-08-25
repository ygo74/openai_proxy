"""Domain models for LLM interactions."""
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from pydantic import BaseModel, Field

class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    MISTRAL = "mistral"
    COHERE = "cohere"

class TokenUsage(BaseModel):
    """Token usage information for an LLM request.

    Attributes:
        prompt_tokens (int): Number of tokens in the prompt
        completion_tokens (int): Number of tokens in the completion
        total_tokens (int): Total tokens used
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int = Field(..., description="Total tokens used in the request")
