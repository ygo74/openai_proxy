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

class LLMRequestType(str, Enum):
    """Types of LLM requests."""
    COMPLETION = "completion"
    CHAT_COMPLETION = "chat_completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"

class BaseLLMRequest(BaseModel):
    """Base class for all LLM requests.

    Attributes:
        request_id (Optional[str]): Unique request identifier
        request_type (LLMRequestType): Type of LLM request
        user_id (Optional[str]): User making the request
        metadata (Dict[str, Any]): Additional request metadata
    """
    request_id: Optional[str] = None
    request_type: LLMRequestType
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

class LLMRequest(BaseLLMRequest):
    """Base LLM request model.

    Attributes:
        model (str): The model identifier to use
        prompt (str): The prompt text
        max_tokens (Optional[int]): Maximum tokens in response
        temperature (Optional[float]): Sampling temperature
        provider (LLMProvider): The LLM provider to use
        additional_params (Dict[str, Any]): Provider-specific parameters
    """
    model: str
    prompt: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    provider: LLMProvider
    additional_params: Dict[str, Any] = {}
    request_type: LLMRequestType = LLMRequestType.COMPLETION

class LLMResponse(BaseModel):
    """Base LLM response model.

    Attributes:
        text (str): Generated text
        model (str): Model that generated the response
        provider (LLMProvider): Provider that generated the response
        usage (TokenUsage): Token usage information
        latency_ms (float): Request latency in milliseconds
        timestamp (datetime): Response timestamp
        raw_response (Dict[str, Any]): Original provider response
    """
    text: str
    model: str
    provider: LLMProvider
    usage: TokenUsage
    latency_ms: float
    timestamp: datetime
    raw_response: Dict[str, Any]