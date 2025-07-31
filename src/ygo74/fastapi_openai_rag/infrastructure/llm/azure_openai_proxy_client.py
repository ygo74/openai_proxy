"""Azure OpenAI proxy client for Azure-specific API calls."""
import asyncio
import httpx
import json
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime, timezone

from ...domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatCompletionStreamResponse, ChatMessage
)
from ...domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ...domain.models.llm import LLMProvider, TokenUsage
from ...domain.models.llm_model import LlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
import logging

logger = logging.getLogger(__name__)

class AzureOpenAIProxyClient:
    """Azure OpenAI proxy client with API versioning support."""

    def __init__(self, api_key: str, base_url: str, api_version: str, provider: LLMProvider = LLMProvider.AZURE):
        """Initialize Azure OpenAI proxy client.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the Azure OpenAI API
            api_version (str): Azure API version (e.g., "2024-06-01")
            provider (LLMProvider): Provider type (defaults to AZURE)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.api_version = api_version
        self.provider = provider
        self._client = httpx.AsyncClient(timeout=120.0)
        logger.debug(f"AzureOpenAIProxyClient initialized for {provider} at {base_url} with API version {api_version}")

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create chat completion via Azure OpenAI API.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails
        """
        start_time = time.time()
        url = self._build_url("chat/completions", request.model)

        headers = self._get_headers()
        payload = self._prepare_chat_payload(request)

        logger.debug(f"Making Azure chat completion request to {url}")

        try:
            response = await self._client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()

            response_data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            return self._parse_chat_response(response_data, latency_ms)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Azure chat completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Azure chat completion: {str(e)}")
            raise

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create text completion via Azure OpenAI API.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails
        """
        start_time = time.time()
        url = self._build_url("completions", request.model)

        headers = self._get_headers()
        payload = self._prepare_completion_payload(request)

        logger.debug(f"Making Azure text completion request to {url}")

        try:
            response = await self._client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()

            response_data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            return self._parse_completion_response(response_data, latency_ms)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Azure text completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Azure text completion: {str(e)}")
            raise

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Stream chat completion via Azure OpenAI API.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionStreamResponse: Streaming response chunks
        """
        url = self._build_url("chat/completions", request.model)
        headers = self._get_headers()

        payload = self._prepare_chat_payload(request)
        payload["stream"] = True

        logger.debug(f"Starting Azure streaming chat completion to {url}")

        async with self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=120.0
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]

                    if data.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data)
                        yield self._parse_stream_chunk(chunk_data)
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Azure OpenAI API.

        Returns:
            List[Dict[str, Any]]: List of available models

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.base_url}/openai/models?api-version={self.api_version}"
        headers = self._get_headers()

        logger.debug(f"Fetching available Azure models from {url}")

        try:
            response = await self._client.get(
                url=url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()

            response_data = response.json()
            models = response_data.get("data", [])

            logger.debug(f"Found {len(models)} available Azure models")
            return models

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Azure models: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching Azure models: {str(e)}")
            raise

    def _build_url(self, endpoint: str, deployment_name: str) -> str:
        """Build Azure OpenAI API URL with deployment and API version.

        Args:
            endpoint (str): API endpoint (e.g., "chat/completions")
            deployment_name (str): Azure deployment name

        Returns:
            str: Complete API URL
        """
        return f"{self.base_url}/openai/deployments/{deployment_name}/{endpoint}?api-version={self.api_version}"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Azure OpenAI API requests.

        Returns:
            Dict[str, str]: Request headers
        """
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "fastapi-openai-rag/1.0.0"
        }

    def _prepare_chat_payload(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Prepare chat completion payload for Azure API.

        Args:
            request (ChatCompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        payload = request.model_dump(exclude_none=True)

        # Remove model from payload as it's in the URL for Azure
        payload.pop("model", None)

        if "messages" in payload:
            payload["messages"] = [
                msg.model_dump(exclude_none=True) for msg in request.messages
            ]

        return payload

    def _prepare_completion_payload(self, request: CompletionRequest) -> Dict[str, Any]:
        """Prepare text completion payload for Azure API.

        Args:
            request (CompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        payload = request.model_dump(exclude_none=True)
        # Remove model from payload as it's in the URL for Azure
        payload.pop("model", None)
        return payload

    def _parse_chat_response(self, response_data: Dict[str, Any], latency_ms: float) -> ChatCompletionResponse:
        """Parse Azure chat completion response.

        Args:
            response_data (Dict[str, Any]): Raw API response
            latency_ms (float): Request latency

        Returns:
            ChatCompletionResponse: Domain response
        """
        choices = []
        for choice_data in response_data.get("choices", []):
            message_data = choice_data.get("message", {})
            message = ChatMessage(
                role=message_data.get("role"),
                content=message_data.get("content"),
                function_call=message_data.get("function_call"),
                tool_calls=message_data.get("tool_calls")
            )

            choice = ChatCompletionChoice(
                index=choice_data.get("index", 0),
                message=message,
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)

        usage_data = response_data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )

        return ChatCompletionResponse(
            id=response_data.get("id", str(uuid.uuid4())),
            object=response_data.get("object", "chat.completion"),
            created=response_data.get("created", int(time.time())),
            model=response_data.get("model", ""),
            system_fingerprint=response_data.get("system_fingerprint"),
            choices=choices,
            usage=usage,
            provider=self.provider,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc),
            raw_response=response_data
        )

    def _parse_completion_response(self, response_data: Dict[str, Any], latency_ms: float) -> CompletionResponse:
        """Parse Azure text completion response.

        Args:
            response_data (Dict[str, Any]): Raw API response
            latency_ms (float): Request latency

        Returns:
            CompletionResponse: Domain response
        """
        choices = []
        for choice_data in response_data.get("choices", []):
            choice = CompletionChoice(
                text=choice_data.get("text", ""),
                index=choice_data.get("index", 0),
                logprobs=choice_data.get("logprobs"),
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)

        usage_data = response_data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )

        return CompletionResponse(
            id=response_data.get("id", str(uuid.uuid4())),
            object=response_data.get("object", "text_completion"),
            created=response_data.get("created", int(time.time())),
            model=response_data.get("model", ""),
            system_fingerprint=response_data.get("system_fingerprint"),
            choices=choices,
            usage=usage,
            provider=self.provider,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc),
            raw_response=response_data
        )

    def _parse_stream_chunk(self, chunk_data: Dict[str, Any]) -> ChatCompletionStreamResponse:
        """Parse Azure streaming response chunk.

        Args:
            chunk_data (Dict[str, Any]): Raw chunk data

        Returns:
            ChatCompletionStreamResponse: Streaming response
        """
        return ChatCompletionStreamResponse(
            id=chunk_data.get("id", ""),
            object=chunk_data.get("object", "chat.completion.chunk"),
            created=chunk_data.get("created", int(time.time())),
            model=chunk_data.get("model", ""),
            choices=[]
        )

    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()
            logger.debug(f"Azure OpenAI proxy client closed for {self.provider} with API version {self.api_version}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.close()
