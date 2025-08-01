"""OpenAI proxy client for transparent API calls."""
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

class OpenAIProxyClient:
    """Transparent OpenAI proxy client for compatible providers."""

    def __init__(self, api_key: str, base_url: str, provider: LLMProvider):
        """Initialize OpenAI proxy client.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the OpenAI-compatible API
            provider (LLMProvider): Provider type (OPENAI, AZURE, etc.)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.provider = provider
        self._client = httpx.AsyncClient(timeout=120.0)
        logger.debug(f"OpenAIProxyClient initialized for {provider} at {base_url}")


    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create chat completion via transparent proxy.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails
        """
        start_time = time.time()
        url = f"{self.base_url}/chat/completions"

        headers = self._get_headers()

        # Convert domain model to OpenAI API format
        payload = self._prepare_chat_payload(request)

        logger.debug(f"Making chat completion request to {url}")

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

            # Convert response to domain model
            return self._parse_chat_response(response_data, latency_ms)

        except httpx.HTTPStatusError as e:
            error_details = self._parse_openai_error(e)
            logger.error(f"OpenAI HTTP error in text completion: {error_details}")
            raise httpx.HTTPError(f"OpenAI API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in text completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in text completion: {str(e)}")
            raise

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create text completion via transparent proxy with smart routing.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Check if model supports completions endpoint
        model_name = request.model
        if self._should_use_chat_completions(model_name):
            logger.info(f"Model {model_name} doesn't support completions endpoint, converting to chat completion")
            return await self._completion_via_chat(request)

        # Use standard completions endpoint
        return await self._direct_completion(request)

    async def _direct_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Direct completion via completions endpoint.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response
        """
        start_time = time.time()
        url = f"{self.base_url}/completions"

        headers = self._get_headers()
        payload = self._prepare_completion_payload(request)

        logger.debug(f"Making text completion request to {url}")
        logger.debug(f"Request payload: {payload}")

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

        except httpx.HTTPStatusError as e:
            error_details = self._parse_openai_error(e)
            logger.error(f"OpenAI HTTP error in text completion: {error_details}")
            raise httpx.HTTPError(f"OpenAI API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in text completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in text completion: {str(e)}")
            raise

    async def _completion_via_chat(self, request: CompletionRequest) -> CompletionResponse:
        """Convert completion request to chat completion for models that don't support completions.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response converted from chat completion
        """
        from ...domain.models.chat_completion import ChatCompletionRequest, ChatMessage

        # Convert completion request to chat completion request
        messages = []

        # Handle prompt conversion
        if isinstance(request.prompt, str):
            content = request.prompt
        elif isinstance(request.prompt, list):
            content = "\n".join(str(p) for p in request.prompt)
        else:
            content = str(request.prompt)

        messages.append(ChatMessage(role="user", content=content))

        # Ensure max_tokens is properly set - use higher default if not specified
        max_tokens = request.max_tokens
        if max_tokens is None:
            max_tokens = 1000  # Higher default for better responses
            logger.debug(f"No max_tokens specified, using default: {max_tokens}")

        logger.debug(f"Converting completion to chat completion with max_tokens: {max_tokens}")

        # Create chat completion request
        chat_request = ChatCompletionRequest(
            model=request.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            n=request.n,
            stream=request.stream,
            stop=request.stop,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
            user=request.user,
            seed=request.seed
        )

        # Make chat completion request
        chat_response = await self.chat_completion(chat_request)

        # Convert chat response back to completion response
        return self._convert_chat_to_completion_response(chat_response)

    def _convert_chat_to_completion_response(self, chat_response) -> CompletionResponse:
        """Convert chat completion response to completion response.

        Args:
            chat_response: Chat completion response

        Returns:
            CompletionResponse: Converted completion response
        """
        choices = []
        for chat_choice in chat_response.choices:
            choice = CompletionChoice(
                text=chat_choice.message.content or "",
                index=chat_choice.index,
                logprobs=None,  # Chat completions don't provide logprobs in the same format
                finish_reason=chat_choice.finish_reason
            )
            choices.append(choice)

        return CompletionResponse(
            id=chat_response.id,
            object="text_completion",  # Keep original object type
            created=chat_response.created,
            model=chat_response.model,
            system_fingerprint=chat_response.system_fingerprint,
            choices=choices,
            usage=chat_response.usage,
            provider=chat_response.provider,
            latency_ms=chat_response.latency_ms,
            timestamp=chat_response.timestamp,
            raw_response=chat_response.raw_response
        )

    def _should_use_chat_completions(self, model_name: str) -> bool:
        """Determine if model should use chat completions endpoint.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if should use chat completions
        """
        # List of models that support completions endpoint
        completion_models = [
            "text-davinci-003",
            "text-davinci-002",
            "text-curie-001",
            "text-babbage-001",
            "text-ada-001",
            "davinci-002",
            "babbage-002"
        ]

        model_name_lower = model_name.lower()
        supports_completions = any(comp_model in model_name_lower for comp_model in completion_models)

        # If it doesn't support completions, use chat completions
        return not supports_completions

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Stream chat completion via transparent proxy.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionStreamResponse: Streaming response chunks
        """
        url = f"{self.base_url}/chat/completions"
        headers = self._get_headers()

        # Enable streaming
        payload = self._prepare_chat_payload(request)
        payload["stream"] = True

        logger.debug(f"Starting streaming chat completion to {url}")

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
                    data = line[6:]  # Remove "data: " prefix

                    if data.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data)
                        yield self._parse_stream_chunk(chunk_data)
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from OpenAI-compatible API.

        Returns:
            List[Dict[str, Any]]: List of available models

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.base_url}/models"
        headers = self._get_headers()

        logger.debug(f"Fetching available models from {url}")

        try:
            response = await self._client.get(
                url=url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()

            response_data = response.json()
            models = response_data.get("data", [])

            logger.debug(f"Found {len(models)} available models")
            return models

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching models: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {str(e)}")
            raise

    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployed models from OpenAI-compatible API.

        For non-Azure providers, this returns the same as list_models
        since there's no separate deployment concept.

        Returns:
            List[Dict[str, Any]]: List of available models
        """
        # For non-Azure providers, deployments are the same as models
        models = await self.list_models()

        # Transform to match deployment format for consistency
        deployments = []
        for model in models:
            deployment = model.copy()
            deployment["deployment_id"] = model.get("id", "")
            deployment["deployment_status"] = "succeeded"  # Assume available
            deployments.append(deployment)

        return deployments

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dict[str, str]: Request headers
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "fastapi-openai-rag/1.0.0"
        }

        # Add provider-specific headers
        if self.provider == LLMProvider.AZURE:
            headers["api-key"] = self.api_key

        return headers

    def _prepare_chat_payload(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Prepare chat completion payload.

        Args:
            request (ChatCompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        # Convert to dict and filter None values
        payload = request.model_dump(exclude_none=True)

        # Convert messages to API format
        if "messages" in payload:
            payload["messages"] = [
                msg.model_dump(exclude_none=True) for msg in request.messages
            ]

        return payload

    def _prepare_completion_payload(self, request: CompletionRequest) -> Dict[str, Any]:
        """Prepare text completion payload.

        Args:
            request (CompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        return request.model_dump(exclude_none=True)

    def _parse_chat_response(self, response_data: Dict[str, Any], latency_ms: float) -> ChatCompletionResponse:
        """Parse chat completion response.

        Args:
            response_data (Dict[str, Any]): Raw API response
            latency_ms (float): Request latency

        Returns:
            ChatCompletionResponse: Domain response
        """
        # Extract choices
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

        # Extract usage
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
        """Parse text completion response.

        Args:
            response_data (Dict[str, Any]): Raw API response
            latency_ms (float): Request latency

        Returns:
            CompletionResponse: Domain response
        """
        # Extract choices
        choices = []
        for choice_data in response_data.get("choices", []):
            choice = CompletionChoice(
                text=choice_data.get("text", ""),
                index=choice_data.get("index", 0),
                logprobs=choice_data.get("logprobs"),
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)

        # Extract usage
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
        """Parse streaming response chunk.

        Args:
            chunk_data (Dict[str, Any]): Raw chunk data

        Returns:
            ChatCompletionStreamResponse: Streaming response
        """
        # This is a simplified implementation
        # You would need to implement proper streaming response parsing
        return ChatCompletionStreamResponse(
            id=chunk_data.get("id", ""),
            object=chunk_data.get("object", "chat.completion.chunk"),
            created=chunk_data.get("created", int(time.time())),
            model=chunk_data.get("model", ""),
            choices=[]  # Would need proper parsing
        )

    def _parse_openai_error(self, error: httpx.HTTPStatusError) -> str:
        """Parse OpenAI error response.

        Args:
            error (httpx.HTTPStatusError): HTTP status error

        Returns:
            str: Formatted error message
        """
        try:
            error_body = error.response.text
            logger.debug(f"Raw OpenAI error response: {error_body}")

            # Try to parse JSON error response
            if error_body:
                try:
                    error_data = error.response.json()
                    if "error" in error_data:
                        error_info = error_data["error"]
                        code = error_info.get("code", "Unknown")
                        message = error_info.get("message", "No message provided")
                        error_type = error_info.get("type", "Unknown")
                        return f"Type: {error_type}, Code: {code}, Message: {message}"
                except Exception:
                    # Fallback to raw text if JSON parsing fails
                    return f"Status: {error.response.status_code}, Body: {error_body[:500]}"

            return f"HTTP {error.response.status_code}: {error.response.reason_phrase}"

        except Exception as e:
            logger.warning(f"Failed to parse OpenAI error: {e}")
            return f"HTTP {error.response.status_code}: {str(error)}"

    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()
            logger.debug(f"OpenAI proxy client closed for {self.provider}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with automatic cleanup."""
        await self.close()
