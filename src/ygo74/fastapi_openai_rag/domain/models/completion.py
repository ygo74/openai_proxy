"""Domain models for OpenAI Completion API."""
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, model_validator
from .llm import TokenUsage, LLMProvider

from openai.types.chat.chat_completion_stream_options_param import ChatCompletionStreamOptionsParam

class CompletionRequest(BaseModel):
    """Text completion request model.

    Attributes:
        model (str): ID of the model to use
        prompt (Union[str, List[str]]): The prompt(s) to generate completions for
        suffix (Optional[str]): The suffix that comes after a completion of inserted text
        max_tokens (Optional[int]): Maximum tokens in response
        temperature (Optional[float]): Sampling temperature (0-2)
        top_p (Optional[float]): Nucleus sampling parameter
        n (Optional[int]): Number of completions to generate
        stream (Optional[bool]): Whether to stream results
        logprobs (Optional[int]): Include log probabilities on most likely tokens
        echo (Optional[bool]): Echo back the prompt in addition to completion
        stop (Optional[Union[str, List[str]]]): Stop sequences
        presence_penalty (Optional[float]): Presence penalty (-2.0 to 2.0)
        frequency_penalty (Optional[float]): Frequency penalty (-2.0 to 2.0)
        best_of (Optional[int]): Number of completions to generate server-side
        logit_bias (Optional[Dict[str, float]]): Logit bias modifications
        user (Optional[str]): User identifier for abuse monitoring
        seed (Optional[int]): Random seed for deterministic outputs
    """
    model: str
    prompt: Union[str, List[str]] = ""
    best_of: Optional[int] = Field(None, ge=1, le=20)
    echo: Optional[bool] = False
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    logprobs: Optional[int] = Field(None, ge=0, le=5)
    max_tokens: Optional[int] = Field(1000, ge=1)
    n: Optional[int] = Field(1, ge=1, le=128)
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    stream: Optional[bool] = False
    stream_options: Optional[ChatCompletionStreamOptionsParam] = None
    suffix: Optional[str] = None
    temperature: Optional[float] = Field(1.0, ge=0, le=2)
    top_p: Optional[float] = Field(1.0, ge=0, le=1)
    user: Optional[str] = None

    @model_validator(mode="before")
    def _validate_stream_options(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Always request usage information to monitor the number of tokens.

        Args:
            values (dict): Raw input data.

        Returns:
            dict: Modified input data with stream_options set.
        """
        values["stream_options"] = ChatCompletionStreamOptionsParam(include_usage=True)
        return values


class CompletionChoice(BaseModel):
    """A single completion choice.

    Attributes:
        text (str): The generated text
        index (int): Choice index
        logprobs (Optional[Dict[str, Any]]): Log probability information
        finish_reason (Optional[str]): Reason for stopping generation
    """
    text: str
    index: int
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None

class CompletionResponse(BaseModel):
    """Text completion response model.

    Attributes:
        id (str): Unique identifier for the completion
        object (str): Object type (always "text_completion")
        created (int): Unix timestamp of creation
        model (str): Model used for completion
        system_fingerprint (Optional[str]): System fingerprint
        choices (List[CompletionChoice]): List of completion choices
        usage (TokenUsage): Token usage information
        provider (LLMProvider): Provider that generated the response
        latency_ms (float): Request latency in milliseconds
        timestamp (datetime): Response timestamp
        raw_response (Dict[str, Any]): Original provider response
    """
    id: str
    object: str = "text_completion"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[CompletionChoice]
    usage: TokenUsage
    provider: LLMProvider
    latency_ms: float
    timestamp: datetime
    raw_response: Dict[str, Any]

class CompletionStreamChoice(BaseModel):
    """A single streaming completion choice.

    Attributes:
        text (str): The delta text content
        index (int): Choice index
        logprobs (Optional[Dict[str, Any]]): Log probability information
        finish_reason (Optional[str]): Reason for stopping generation
    """
    text: str
    index: int
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None

class CompletionStreamResponse(BaseModel):
    """Streaming text completion response model.

    Attributes:
        id (str): Unique identifier for the completion
        object (str): Object type (always "text_completion")
        created (int): Unix timestamp of creation
        model (str): Model used for completion
        system_fingerprint (Optional[str]): System fingerprint
        choices (List[CompletionStreamChoice]): List of streaming choices
    """
    id: str
    object: str = "text_completion"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[CompletionStreamChoice]
