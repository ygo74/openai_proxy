"""Protocols for LLM client implementations."""
from typing import Protocol
from ..models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from ..models.completion import CompletionRequest, CompletionResponse

class LLMClientProtocol(Protocol):
    """Protocol for LLM client implementations."""

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Generate chat completion from the LLM.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response with metadata
        """
        ...

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """Generate text completion from the LLM.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response with metadata
        """
        ...
