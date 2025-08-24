"""Domain models for OpenAI Chat Completion API."""
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field
from .llm import TokenUsage, LLMProvider

class ChatMessageRole(str, Enum):
    """Role of the message author."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"

class ChatMessage(BaseModel):
    """A single chat message.

    Attributes:
        role (ChatMessageRole): The role of the message author
        content (Optional[str]): The content of the message
        name (Optional[str]): Name of the author (for function/tool messages)
        function_call (Optional[Dict[str, Any]]): Function call information
        tool_calls (Optional[List[Dict[str, Any]]]): Tool call information
        tool_call_id (Optional[str]): ID of the tool call being responded to
    """
    role: ChatMessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatCompletionFunction(BaseModel):
    """Function definition for chat completion.

    Attributes:
        name (str): Function name
        description (Optional[str]): Function description
        parameters (Dict[str, Any]): JSON schema for function parameters
    """
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]

class ChatCompletionTool(BaseModel):
    """Tool definition for chat completion.

    Attributes:
        type (Literal["function"]): Tool type
        function (ChatCompletionFunction): Function definition
    """
    type: Literal["function"] = "function"
    function: ChatCompletionFunction

class ChatCompletionRequest(BaseModel):
    """Chat completion request model.

    Attributes:
        model (str): ID of the model to use
        messages (List[ChatMessage]): List of messages in the conversation
        max_tokens (Optional[int]): Maximum tokens in response
        temperature (Optional[float]): Sampling temperature (0-2)
        top_p (Optional[float]): Nucleus sampling parameter
        n (Optional[int]): Number of completions to generate
        stream (Optional[bool]): Whether to stream results
        stop (Optional[Union[str, List[str]]]): Stop sequences
        presence_penalty (Optional[float]): Presence penalty (-2.0 to 2.0)
        frequency_penalty (Optional[float]): Frequency penalty (-2.0 to 2.0)
        logit_bias (Optional[Dict[str, float]]): Logit bias modifications
        user (Optional[str]): User identifier for abuse monitoring
        functions (Optional[List[ChatCompletionFunction]]): Available functions
        function_call (Optional[Union[str, Dict[str, str]]]): Function call control
        tools (Optional[List[ChatCompletionTool]]): Available tools
        tool_choice (Optional[Union[str, Dict[str, Any]]]): Tool choice control
        response_format (Optional[Dict[str, str]]): Response format specification
        seed (Optional[int]): Random seed for deterministic outputs
        logprobs (Optional[bool]): Whether to return log probabilities
        top_logprobs (Optional[int]): Number of top log probabilities to return
    """
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = Field(None, ge=1)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    top_p: Optional[float] = Field(None, ge=0, le=1)
    n: Optional[int] = Field(1, ge=1, le=128)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    functions: Optional[List[ChatCompletionFunction]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    tools: Optional[List[ChatCompletionTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, str]] = None
    seed: Optional[int] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = Field(None, ge=0, le=5)

class ChatCompletionChoice(BaseModel):
    """A single chat completion choice.

    Attributes:
        index (int): Choice index
        message (ChatMessage): The generated message
        logprobs (Optional[Dict[str, Any]]): Log probability information
        finish_reason (Optional[str]): Reason for stopping generation
    """
    index: int
    message: ChatMessage
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None

class ChatCompletionResponse(BaseModel):
    """Chat completion response model.

    Attributes:
        id (str): Unique identifier for the completion
        object (str): Object type (always "chat.completion")
        created (int): Unix timestamp of creation
        model (str): Model used for completion
        system_fingerprint (Optional[str]): System fingerprint
        choices (List[ChatCompletionChoice]): List of completion choices
        usage (TokenUsage): Token usage information
        provider (LLMProvider): Provider that generated the response
        latency_ms (float): Request latency in milliseconds
        timestamp (datetime): Response timestamp
        raw_response (Dict[str, Any]): Original provider response
    """
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[ChatCompletionChoice]
    usage: TokenUsage
    provider: LLMProvider
    latency_ms: float
    timestamp: datetime
    raw_response: Dict[str, Any]

class ChatCompletionStreamChoice(BaseModel):
    """A single streaming chat completion choice.

    Attributes:
        index (int): Choice index
        delta (ChatMessage): The delta message content
        logprobs (Optional[Dict[str, Any]]): Log probability information
        finish_reason (Optional[str]): Reason for stopping generation
    """
    index: int
    delta: ChatMessage
    logprobs: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None

class ChatCompletionStreamResponse(BaseModel):
    """OpenAI-compatible streaming chat completion response.

    Attributes:
        id (str): Unique identifier for the completion
        object (str): Object type (always "chat.completion.chunk")
        created (int): Unix timestamp of creation
        model (str): Model used for completion
        system_fingerprint (Optional[str]): System fingerprint
        choices (List[ChatCompletionChoice]): List of completion choices
        provider (Optional[LLMProvider]): Provider that generated the response
        raw_response (Optional[Dict[str, Any]]): Original provider response
        latency_ms (Optional[float]): Request latency in milliseconds
        timestamp (Optional[datetime]): Response timestamp
    """
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    system_fingerprint: Optional[str] = None
    choices: List[ChatCompletionStreamChoice] = []
    provider: Optional[LLMProvider] = None
    raw_response: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None
    timestamp: Optional[datetime] = None
