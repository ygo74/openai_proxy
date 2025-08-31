"""Azure OpenAI proxy client for Azure-specific API calls."""
import httpx
import json
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, AsyncIterator, List
from datetime import datetime, timezone

from ...domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,ChatCompletionStreamChoice,
    ChatCompletionStreamResponse, ChatMessage
)
from ...domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ...domain.models.llm import LLMProvider, TokenUsage
from ...domain.protocols.llm_client import LLMClientProtocol

from .azure_management_client import AzureManagementClient
from .http_client_factory import HttpClientFactory
from .retry_handler import with_enterprise_retry, LLMRetryHandler
from .enterprise_config import EnterpriseConfig
import logging

logger = logging.getLogger(__name__)

class AzureOpenAIProxyClient(LLMClientProtocol):
    """Azure OpenAI proxy client with API versioning support and retry resilience."""

    def __init__(self, api_key: str, base_url: str, api_version: str, provider: LLMProvider = LLMProvider.AZURE,
                 management_client: Optional[AzureManagementClient] = None,
                 enterprise_config: Optional[EnterpriseConfig] = None):
        """Initialize Azure OpenAI proxy client with enterprise configuration.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the Azure OpenAI API
            api_version (str): Azure API version (e.g., "2024-06-01")
            provider (LLMProvider): Provider type (defaults to AZURE)
            management_client (Optional[AzureManagementClient]): Optional management client for deployment listing
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.api_version = api_version
        self.provider = provider
        self.management_client = management_client

        # Use default enterprise config if none provided
        if enterprise_config is None:
            enterprise_config = EnterpriseConfig()

        self.enterprise_config = enterprise_config

        # Create HTTP client using factory with enterprise settings
        self._client = HttpClientFactory.create_async_client(
            target_url=self.base_url,
            timeout=120.0,
            proxy_url=enterprise_config.proxy_url,
            proxy_auth=enterprise_config.proxy_auth,
            verify_ssl=enterprise_config.verify_ssl,
            ca_cert_file=enterprise_config.ca_cert_file,
            client_cert_file=enterprise_config.client_cert_file,
            client_key_file=enterprise_config.client_key_file
        )

        logger.debug(f"AzureOpenAIProxyClient initialized for {provider} at {base_url} with API version {api_version}, retry enabled: {enterprise_config.enable_retry}")

    @with_enterprise_retry
    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create text completion via Azure OpenAI API with smart routing and retry resilience.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        # Check if model supports completions endpoint
        model_name = request.model
        if self._should_use_chat_completions(model_name):
            logger.info(f"Model {model_name} doesn't support completions endpoint, converting to chat completion")
            return await self._completion_via_chat(request)

        # Use standard completions endpoint
        return await self._direct_completion(request)

    async def _direct_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Direct completion via completions endpoint with automatic retry.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response
        """
        start_time = time.time()
        url = self._build_url("completions", request.model)

        headers = self._get_headers()
        payload = self._prepare_completion_payload(request)

        logger.debug(f"Making Azure text completion request to {url}")
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
            error_details = self._parse_azure_error(e)
            logger.error(f"Azure HTTP error in text completion: {error_details}")
            raise httpx.HTTPError(f"Azure OpenAI API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Azure text completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Azure text completion: {str(e)}")
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

    @with_enterprise_retry
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create chat completion via Azure OpenAI API with retry resilience.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response

        Raises:
            httpx.HTTPError: If API request fails after all retries
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

        except httpx.HTTPStatusError as e:
            error_details = self._parse_azure_error(e)
            logger.error(f"Azure HTTP error in chat completion: {error_details}")
            raise httpx.HTTPError(f"Azure OpenAI API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Azure chat completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Azure chat completion: {str(e)}")
            raise

    @with_enterprise_retry
    async def _establish_stream_connection(self, request: ChatCompletionRequest):
        """Establish streaming connection with retry capability.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            httpx.AsyncClient.stream: HTTP streaming response
        """
        url = self._build_url("chat/completions", request.model)
        headers = self._get_headers()

        payload = self._prepare_chat_payload(request)
        payload["stream"] = True

        logger.debug(f"Starting Azure streaming chat completion to {url}")
        logger.debug(f"Stream request payload: {payload}")
        logger.debug(f"Stream request headers: {headers}")

        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=120.0
        )

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Stream chat completion via Azure OpenAI API.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionStreamResponse: Streaming response chunks
        """
        try:
            # Get streaming connection with retry
            stream_ctx = await self._establish_stream_connection(request)

            # Process the stream without retry
            async with stream_ctx as res:
                res.raise_for_status()

                # Les en-têtes sont gérés au niveau de OverrideStreamResponse et pas ici
                # car nous ne retournons pas directement la réponse HTTP, mais des objets ChatCompletionStreamResponse

                async for line in res.aiter_lines():
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # Strip "data: " prefix if present (for SSE format)
                    line = line.strip()
                    if line.startswith('data: '):
                        line = line[6:]  # Remove 'data: ' prefix

                    # Check for the [DONE] message that indicates end of stream
                    if line == '[DONE]':
                        break

                    try:
                        # Parse the JSON data into a dictionary
                        chunk_data = json.loads(line)

                        # Convert to ChatCompletionStreamResponse
                        stream_response = self._parse_stream_chunk(chunk_data)

                        # Yield the parsed response object
                        yield stream_response

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse streaming response chunk: {line}")
                        continue

        except httpx.HTTPStatusError as e:
            error_details = self._parse_azure_error(e)
            logger.error(f"Azure HTTP error in streaming chat completion: {error_details}")
            raise httpx.HTTPError(f"Azure OpenAI API error: {error_details}")

    @with_enterprise_retry
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Azure OpenAI API with retry resilience.

        Returns:
            List[Dict[str, Any]]: List of available models

        Raises:
            httpx.HTTPError: If API request fails after all retries
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

    @with_enterprise_retry
    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployed models from Azure using Management API or fallback to models endpoint with retry.

        Returns:
            List[Dict[str, Any]]: List of deployed models with deployment info

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        # If management client is available, use it for true deployment listing
        if self.management_client:
            try:
                return await self.management_client.list_deployments()
            except Exception as e:
                logger.warning(f"Failed to get deployments from Management API, falling back to models endpoint: {e}")

        # Fallback to the standard models endpoint with retry
        return await self.list_models()

    def _supports_chat_completions(self, model_name: str) -> bool:
        """Check if a model supports chat completions.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports chat completions
        """
        chat_models = ["gpt-4", "gpt-3.5-turbo", "gpt-35-turbo"]
        return any(chat_model in model_name.lower() for chat_model in chat_models)

    def _supports_completions(self, model_name: str) -> bool:
        """Check if a model supports text completions.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports completions
        """
        completion_models = [
            "text-davinci-003", "text-davinci-002", "text-curie-001",
            "text-babbage-001", "text-ada-001", "davinci-002", "babbage-002"
        ]
        return any(comp_model in model_name.lower() for comp_model in completion_models)

    def _supports_embeddings(self, model_name: str) -> bool:
        """Check if a model supports embeddings.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports embeddings
        """
        embedding_models = ["text-embedding", "ada-002"]
        return any(emb_model in model_name.lower() for emb_model in embedding_models)

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

        # Azure-specific adjustments
        # Remove parameters that Azure doesn't support or handle differently
        unsupported_params = ["best_of", "suffix", "echo", "logit_bias"]
        for param in unsupported_params:
            payload.pop(param, None)

        # Ensure prompt is properly formatted
        if "prompt" in payload:
            # Azure expects prompt as string, not array
            if isinstance(payload["prompt"], list):
                # Join multiple prompts with newlines
                payload["prompt"] = "\n".join(str(p) for p in payload["prompt"])

        # Adjust logprobs parameter - Azure may have different limits
        if "logprobs" in payload and payload["logprobs"] is not None:
            # Azure supports logprobs but may have different limits
            payload["logprobs"] = min(payload["logprobs"], 5)

        # Ensure stop sequences are properly formatted
        if "stop" in payload and payload["stop"] is not None:
            if isinstance(payload["stop"], str):
                # Convert single string to array
                payload["stop"] = [payload["stop"]]
            elif isinstance(payload["stop"], list):
                # Limit to maximum 4 stop sequences for Azure
                payload["stop"] = payload["stop"][:4]

        # Set reasonable defaults for Azure - use higher default for max_tokens
        if "max_tokens" not in payload or payload["max_tokens"] is None:
            payload["max_tokens"] = 1000  # Higher default for better responses
            logger.debug("No max_tokens specified, using default: 1000")

        # Ensure temperature is within Azure limits
        if "temperature" in payload and payload["temperature"] is not None:
            payload["temperature"] = max(0.0, min(2.0, payload["temperature"]))

        # Ensure top_p is within limits
        if "top_p" in payload and payload["top_p"] is not None:
            payload["top_p"] = max(0.0, min(1.0, payload["top_p"]))

        # Ensure n is within Azure limits
        if "n" in payload and payload["n"] is not None:
            payload["n"] = max(1, min(128, payload["n"]))

        # Ensure penalties are within limits
        for penalty_field in ["presence_penalty", "frequency_penalty"]:
            if penalty_field in payload and payload[penalty_field] is not None:
                payload[penalty_field] = max(-2.0, min(2.0, payload[penalty_field]))

        logger.debug(f"Prepared Azure completion payload: {payload}")
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
        # Extract choices data from the chunk
        choices: List[ChatCompletionStreamChoice] = []
        for choice_data in chunk_data.get("choices", []):
            # Extract the delta content from the choice
            delta = choice_data.get("delta", {})

            # Log the actual content for debugging
            logger.debug(f"Stream chunk delta content: {delta}")

            # Assigner une valeur par défaut pour le rôle si elle est None
            role = delta.get("role")
            if role is None:
                # Dans les chunks de streaming Azure, le rôle est souvent défini uniquement
                # dans le premier chunk et est généralement "assistant" pour les chunks suivants
                role = "assistant"

            # Create a message object from the delta
            message = ChatMessage(
                role=role,  # Utilisez la valeur par défaut si nécessaire
                content=delta.get("content", ""),  # Ensure content is never None
                function_call=delta.get("function_call"),
                tool_calls=delta.get("tool_calls")
            )

            choice = ChatCompletionStreamChoice(
                index=choice_data.get("index", 0),
                delta=message,
                finish_reason=choice_data.get("finish_reason")
            )
            choices.append(choice)

        # Create the response with all required fields
        return ChatCompletionStreamResponse(
            id=chunk_data.get("id", str(uuid.uuid4())),
            object=chunk_data.get("object", "chat.completion.chunk"),
            created=chunk_data.get("created", int(time.time())),
            model=chunk_data.get("model", "unknown"),
            system_fingerprint=chunk_data.get("system_fingerprint"),
            choices=choices,
            provider=self.provider,
            raw_response=chunk_data,
            latency_ms=None,  # Ces valeurs seront définies plus tard dans le service
            timestamp=datetime.now(timezone.utc)
        )

    def _parse_azure_error(self, error: httpx.HTTPStatusError) -> str:
        """Parse Azure OpenAI error response.

        Args:
            error (httpx.HTTPStatusError): HTTP status error

        Returns:
            str: Formatted error message
        """
        try:
            error_body = error.response.text
            logger.debug(f"Raw Azure error response: {error_body}")

            # Try to parse JSON error response
            if error_body:
                try:
                    error_data = error.response.json()
                    if "error" in error_data:
                        error_info = error_data["error"]
                        code = error_info.get("code", "Unknown")
                        message = error_info.get("message", "No message provided")
                        return f"Code: {code}, Message: {message}"
                except Exception:
                    # Fallback to raw text if JSON parsing fails
                    return f"Status: {error.response.status_code}, Body: {error_body[:500]}"

            return f"HTTP {error.response.status_code}: {error.response.reason_phrase}"

        except Exception as e:
            logger.warning(f"Failed to parse Azure error: {e}")
            return f"HTTP {error.response.status_code}: {str(error)}"

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
