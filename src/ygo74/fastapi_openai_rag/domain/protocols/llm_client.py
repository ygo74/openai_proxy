"""Protocols for LLM client implementations."""
from typing import AsyncGenerator, Protocol, List, Dict, Any, Optional, Type
from types import TracebackType

from ..models.chat_completion import (
    ChatCompletionRequest
)
from ..models.completion import CompletionRequest, CompletionResponse
from ..models.response import ResponsesCreatePayload

# OpenAI SDK response types
from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.chat.chat_completion import ChatCompletion as OpenAIChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion import Completion as OpenAICompletion

class LLMClientProtocol(Protocol):
    """Protocol for LLM client implementations.

    All concrete clients must implement these coroutine methods. The Responses API
    methods operate on the domain's `ResponsesCreatePayload` and return official
    OpenAI SDK typed objects, leaving any provider-specific fallback or
    transformation logic to the client implementation.
    """

    async def chat_completion(self, request: ChatCompletionRequest) -> OpenAIChatCompletion:
        """Generate chat completion from the LLM.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response with metadata
        """
        ...

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Stream chat completion via Azure OpenAI API with retry for connection establishment.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionChunk: Streaming response chunks
        """
        yield  # type: ignore[misc]
        raise StopAsyncIteration  # pragma: no cover

    async def completion(self, request: CompletionRequest) -> OpenAICompletion:
        """Generate text completion from the LLM.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response with metadata
        """
        ...

    async def completion_stream(self, request: CompletionRequest) -> AsyncGenerator[OpenAICompletion, None]:
        """Stream text completion from the LLM.

        Args:
            request (CompletionRequest): Text completion request

        Yields:
            OpenAICompletion: Streaming response chunks
        """
        yield  # type: ignore[misc]
        raise StopAsyncIteration  # pragma: no cover

    # --- Responses API methods ---
    async def responses(self, payload: ResponsesCreatePayload) -> OpenAIResponse:
        """Execute a Responses API request returning an OpenAI SDK Response object.

        Implementations may perform capability detection and internally fall back
        to a chat-based emulation, but MUST return a proper `openai.types.responses.response.Response`.
        """
        ...

    async def responses_stream(self, payload: ResponsesCreatePayload) -> AsyncGenerator[ResponseStreamEvent, None]:
        """Stream Responses API events as OpenAI SDK `ResponseStreamEvent` objects."""
        yield ResponseStreamEvent(type="response.completed")  # type: ignore[arg-type]
        raise StopAsyncIteration  # pragma: no cover

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from the LLM provider.

        Returns:
            List[Dict[str, Any]]: List of available models with their metadata
        """
        ...

    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployed models from the LLM provider.

        For Azure, this returns actual deployments.
        For other providers, this may return the same as list_models.

        Returns:
            List[Dict[str, Any]]: List of deployed models with deployment info
        """
        ...

    async def close(self) -> None:
        """Close the client and cleanup resources.

        Should be called when the client is no longer needed to properly
        cleanup HTTP connections and other resources.
        """
        ...

    async def __aenter__(self) -> "LLMClientProtocol":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        """Async context manager exit with automatic cleanup."""
        await self.close()
        return None
