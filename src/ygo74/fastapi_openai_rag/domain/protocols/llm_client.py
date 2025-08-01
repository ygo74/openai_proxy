"""Protocols for LLM client implementations."""
from typing import Protocol, List, Dict, Any
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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.close()
