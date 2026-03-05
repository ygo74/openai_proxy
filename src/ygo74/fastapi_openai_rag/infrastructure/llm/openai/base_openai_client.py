"""Base OpenAI client with shared functionality for standard and Azure implementations."""
import httpx
import json
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, List, Type, Union, cast, get_args, get_origin
from datetime import datetime, timezone
from types import TracebackType
from pydantic import BaseModel

from ....domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatCompletionStreamChoice,
    ChatCompletionStreamResponse, ChatMessage, ChatMessageRole
)
from ....domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ....domain.models.llm import LLMProvider, TokenUsage
from ....domain.protocols.llm_client import LLMClientProtocol
from ....domain.models.response import ResponsesCreatePayload
from ....domain.models.embedding import EmbeddingCreatePayload, CreateEmbeddingResponse

from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.chat.chat_completion import ChatCompletion as OpenAIChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion import Completion as OpenAICompletion
# from openai.types.create_embedding_response import CreateEmbeddingResponse


from ..http_client_factory import HttpClientFactory
from ..retry_handler import with_enterprise_retry, LLMRetryHandler
from ..enterprise_config import EnterpriseConfig
import logging

logger = logging.getLogger(__name__)

class _ResponseStreamEventFallback(BaseModel):
    """Fallback minimal representation of a Responses stream event.

    Used when the OpenAI SDK ResponseStreamEvent class lacks model_validate()
    or instantiation fails. Provides a compatible interface (model_dump()).
    """
    type: str
    sequence_number: Optional[int] = None
    response: Optional[Dict[str, Any]] = None
    output_index: Optional[int] = None
    item: Optional[Dict[str, Any]] = None
    item_id: Optional[str] = None
    content_index: Optional[int] = None
    delta: Optional[str] = None
    obfuscation: Optional[str] = None

class BaseOpenAIClient(LLMClientProtocol):
    """Base OpenAI client with shared functionality for all OpenAI-compatible providers."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        provider: LLMProvider,
        enterprise_config: Optional[EnterpriseConfig] = None
    ):
        """Initialize base OpenAI client with enterprise configuration.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the API
            provider (LLMProvider): Provider type
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.provider = provider

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

        logger.debug(f"BaseOpenAIClient initialized for {provider} at {base_url}")

        self._stream_validation_error_count: int = 0  # limit noisy logs
        self._has_model_validate: bool = callable(getattr(ResponseStreamEvent, 'model_validate', None))
        self._stream_fallback_count: int = 0  # count fallback usages
        self._event_variant_map: Dict[str, Any] = self._build_event_variant_map()
        logger.debug("Stream event variant map size=%d", len(self._event_variant_map))

    @with_enterprise_retry
    async def completion(self, request: CompletionRequest) -> OpenAICompletion:
        """Direct completion via completions endpoint with automatic retry.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            OpenAICompletion: Generated response
        """
        start_time = time.time()
        url = self._build_url("completions", request.model)

        headers = self._get_headers()
        payload = self._prepare_completion_payload(request)

        request_timeout = int(request.timeout) if request.timeout else None
        logger.debug(f"Making text completion request to {url} with timeout={request_timeout}s")

        try:
            start_time = time.perf_counter()
            response = await self._client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=request_timeout
            )
            response.raise_for_status()
            data = response.json()

            duration = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds
            logger.info(f"Text completion request completed in {duration:.2f} ms")

            try:
                return OpenAICompletion.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # Fallback if model_validate not available
                return data


        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in text completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error in text completion: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}, "
                f"request={getattr(e, 'request', None)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in text completion: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}"
            )
            raise


    @with_enterprise_retry
    async def _establish_completion_stream_connection(self, request: CompletionRequest):
        """Establish streaming connection for completions endpoint with retry.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            httpx.AsyncClient.stream: HTTP streaming response
        """
        url = self._build_url("completions", request.model)
        headers = self._get_headers()

        payload = self._prepare_completion_payload(request)
        payload["stream"] = True

        request_timeout = int(request.timeout) if request.timeout else None
        logger.debug(f"Starting streaming text completion to {url} with timeout={request_timeout}s")

        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=request_timeout
        )

    async def completion_stream(self, request: CompletionRequest) -> AsyncGenerator[OpenAICompletion, None]:
        """Stream text completion via completions endpoint.

        Args:
            request (CompletionRequest): Text completion request

        Yields:
            OpenAICompletion: Streaming response chunks
        """
        try:
            # Get streaming connection with retry
            stream_ctx = await self._establish_completion_stream_connection(request)

            # Process the stream without retry
            async with stream_ctx as res:
                res.raise_for_status()
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

                        yield OpenAICompletion.model_validate(chunk_data)  # type: ignore[attr-defined]

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse response chunk: {line}")
                        continue


        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in streaming completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")

    @with_enterprise_retry
    async def chat_completion(self, request: ChatCompletionRequest) -> OpenAIChatCompletion:
        """Create chat completion via API with retry resilience.

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

        request_timeout = int(request.timeout) if request.timeout else None
        logger.debug(f"Making chat completion request to {url} with timeout={request_timeout}s")

        try:
            start_time = time.perf_counter()
            response = await self._client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=request_timeout
            )
            response.raise_for_status()
            data = response.json()
            duration = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds
            logger.info(f"Chat completion request completed in {duration:.2f} ms")

            try:
                return OpenAIChatCompletion.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # Fallback if model_validate not available
                return data


        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in chat completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error in chat completion: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}, "
                f"request={getattr(e, 'request', None)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in chat completion: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}"
            )
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

        request_timeout = int(request.timeout) if request.timeout else None
        logger.debug(f"Starting streaming chat completion to {url} with timeout={request_timeout}s")

        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=payload,
            timeout=request_timeout
        )

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Stream chat completion via API.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionChunk: Streaming response chunks
        """
        try:
            # Get streaming connection with retry
            stream_ctx = await self._establish_stream_connection(request)

            # Process the stream without retry
            async with stream_ctx as res:
                res.raise_for_status()

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
                        if chunk_data["object"] != "chat.completion.chunk":
                            chunk_data["object"] = "chat.completion.chunk"

                        # Convert to ChatCompletionChunk
                        stream_response = ChatCompletionChunk.model_validate(chunk_data)

                        # Yield the parsed response object
                        yield stream_response

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse streaming response chunk: {line}")
                        continue

        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in streaming chat completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")

    @with_enterprise_retry
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from API with retry resilience.

        Returns:
            List[Dict[str, Any]]: List of available models

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        url = self._build_models_url()
        headers = self._get_headers()

        logger.debug(f"Fetching available models from {url}")

        try:
            response = await self._client.get(
                url=url,
                headers=headers,
                timeout=30.0  # Shorter timeout for fast metadata endpoint
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
        """List deployed models (equivalent to list_models for standard OpenAI).

        Returns:
            List[Dict[str, Any]]: List of deployed models

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Default implementation - override in Azure client
        try:
            models = await self.list_models()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching models for deployments: {str(e)}")
            raise

        # Transform to match deployment format for consistency
        deployments = []
        for model in models:
            deployment = model.copy()
            deployment["deployment_id"] = model.get("id", "")
            deployment["deployment_status"] = "succeeded"  # Assume available
            deployments.append(deployment)

        return deployments

    @with_enterprise_retry
    async def responses(self, payload: ResponsesCreatePayload) -> OpenAIResponse:
        """Execute Responses API call.

        Args:
            payload (ResponsesCreatePayload): API request payload

        Returns:
            Dict[str, Any]: Raw API response
        """
        url = self._build_responses_url()
        headers = self._get_headers()
        # Ensure stream disabled for non streaming route
        body = payload.to_openai_kwargs()
        body["stream"] = False

        request_timeout = int(payload.timeout) if payload.timeout else None
        logger.debug(f"Starting response call to {url} with timeout={request_timeout}s")

        try:
            start_time = time.perf_counter()
            res = await self._client.post(
                url=url,
                headers=headers,
                json=body,
                timeout=request_timeout
            )
            res.raise_for_status()
            data = res.json()
            duration = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds
            logger.info(f"responses() completed in {duration:.2f}")
            try:
                return OpenAIResponse.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # Fallback if model_validate not available
                return data

        except httpx.HTTPStatusError as e:
            err = self._parse_error(e)
            logger.error(f"HTTP error in responses: {err}")
            raise httpx.HTTPError(f"API error: {err}")
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error in responses API: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}, "
                f"request={getattr(e, 'request', None)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in responses API: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}"
            )
            raise

    @with_enterprise_retry
    async def _establish_responses_stream_connection(self, payload: ResponsesCreatePayload):
        """Establish streaming connection for responses API with retry capability.

        Args:
            payload (ResponsesCreatePayload): Request payload

        Returns:
            httpx.AsyncClient.stream: HTTP streaming connection
        """
        url = self._build_responses_url()
        headers = self._get_headers()

        # Ensure stream is enabled
        body = payload.to_openai_kwargs()
        body["stream"] = True

        request_timeout = int(payload.timeout) if payload.timeout else None
        logger.debug(f"Starting streaming response call to {url} with timeout={request_timeout}s")

        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=body,
            timeout=request_timeout
        )

    async def responses_stream(self, payload: Dict[str, Any]) -> AsyncGenerator[ResponseStreamEvent, None]:
        """Stream responses API events with normalization and diagnostic logging.

        Args:
            payload (Dict[str, Any]): Request payload with model and inputs

        Yields:
            ResponseStreamEvent: Normalized streaming response events
        """
        try:
            stream_ctx = await self._establish_responses_stream_connection(payload)
            async with stream_ctx as res:
                res.raise_for_status()
                pending_event_type: Optional[str] = None
                non_json_skipped: int = 0
                async for raw_line in res.aiter_lines():
                    if raw_line is None:
                        continue
                    logger.debug("responses_stream raw line: %s", raw_line[:500])
                    line = raw_line.strip()
                    if not line:
                        continue
                    # SSE header line e.g. 'event: response.created'
                    if line.startswith('event:'):
                        pending_event_type = line[6:].strip()
                        continue
                    # Only process JSON on data: lines
                    if line.startswith('data:'):
                        json_part = line[5:].strip()
                        if json_part == '' or json_part == '[DONE]':
                            if json_part == '[DONE]':
                                break
                            continue
                        try:
                            evt_raw = json.loads(json_part)
                        except json.JSONDecodeError:
                            if non_json_skipped < 3:
                                logger.debug(f"Failed to parse data JSON (first occurrences): {json_part[:120]}")
                            non_json_skipped += 1
                            continue
                        # Apply pending event type if JSON lacks type
                        if pending_event_type and isinstance(evt_raw, dict) and 'type' not in evt_raw:
                            evt_raw['type'] = pending_event_type
                        pending_event_type = None
                        # Normalize
                        evt_dict = self._prepare_response_stream_event(evt_raw)
                        # Validate/Coerce once (version-tolerant)
                        try:
                            evt_obj = self._build_response_stream_event(evt_dict)
                            yield evt_obj
                        except Exception as e:  # noqa: BLE001
                            from pydantic import ValidationError
                            self._stream_validation_error_count += 1
                            if self._stream_validation_error_count <= 8:
                                if isinstance(e, ValidationError):
                                    try:
                                        details = e.errors()  # type: ignore[attr-defined]
                                    except Exception:
                                        details = str(e)
                                    logger.debug(
                                        "Responses stream validation error #%d type=%s keys=%s details=%s",
                                        self._stream_validation_error_count,
                                        evt_dict.get('type'),
                                        list(evt_dict.keys())[:10],
                                        details,
                                    )
                                else:
                                    logger.debug(
                                        "Responses stream coercion error #%d: %s | type=%s keys=%s",
                                        self._stream_validation_error_count,
                                        repr(e),
                                        evt_dict.get('type'),
                                        list(evt_dict.keys())[:10],
                                    )
                            continue
                    else:
                        # Non data / non event lines ignored silently (avoid spam)
                        continue
        except httpx.HTTPStatusError as e:
            err = self._parse_error(e)
            logger.error(f"HTTP error in responses stream: {err}")
            raise httpx.HTTPError(f"API error: {err}")
        except Exception as e:
            logger.error(f"Unexpected error in responses stream: {e}")
            raise

    @with_enterprise_retry
    async def embedding(self, request: EmbeddingCreatePayload) -> CreateEmbeddingResponse:
        """Create embeddings using OpenAI-compatible API with automatic retry.

        Args:
            request (EmbeddingCreatePayload): Embedding request

        Returns:
            CreateEmbeddingResponse: Embedding response from OpenAI SDK

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        url = self._build_embeddings_url()
        headers = self._get_headers()

        # Convert to OpenAI SDK parameters
        payload = request.to_openai_kwargs()

        logger.debug(f"Making embedding request to {url}")
        logger.debug(f"Embedding request payload: {payload}")

        try:
            response = await self._client.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Embedding request successful: {len(data.get('data', []))} embeddings created")

            try:
                return CreateEmbeddingResponse.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # Fallback if model_validate not available
                return data

        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in embedding creation: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error in embedding creation: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}, "
                f"request={getattr(e, 'request', None)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in embedding creation: type={type(e).__name__}, "
                f"message={str(e)!r}, repr={repr(e)}"
            )
            raise

    def _build_embeddings_url(self) -> str:
        """Build URL for embeddings endpoint.

        Returns:
            str: Embeddings API URL
        """
        # Default implementation for standard OpenAI
        return f"{self.base_url}/embeddings"

    def _build_event_variant_map(self) -> Dict[str, Any]:
        """Build mapping from event type literal to concrete variant model.

        Enhanced logic:
        - Handle Annotated[Union[...], ...] wrapper used by the OpenAI SDK.
        - Extract event type via the Literal annotation of the 'type' field (since default is often PydanticUndefined).
        - Support both Pydantic v1 (__fields__) and v2 (model_fields) metadata; fall back to __annotations__ / type hints.
        - Reflection fallback kept if union introspection fails.
        """
        from typing import get_type_hints, Literal, Annotated  # local import to avoid unused at module level

        def peel_annotated(tp: Any) -> Any:
            if get_origin(tp) is Annotated:
                args = get_args(tp)
                if args:
                    return args[0]
            return tp

        def extract_literal_from_field(variant_cls: Any) -> Optional[str]:
            # Pydantic v2 path
            model_fields = getattr(variant_cls, 'model_fields', None)
            if model_fields and 'type' in model_fields:
                fld = model_fields['type']
                ann = getattr(fld, 'annotation', None)
                lit = _literal_from_annotation(ann)
                if lit:
                    return lit
            # Pydantic v1 path
            fields_v1 = getattr(variant_cls, '__fields__', None)
            if fields_v1 and 'type' in fields_v1:
                ann = getattr(fields_v1['type'], 'annotation', None)
                lit = _literal_from_annotation(ann)
                if lit:
                    return lit
            # Raw annotations
            try:
                anns = getattr(variant_cls, '__annotations__', {})
                ann = anns.get('type')
                lit = _literal_from_annotation(ann)
                if lit:
                    return lit
                # get_type_hints for forward refs
                th = get_type_hints(variant_cls, include_extras=True)  # type: ignore[call-arg]
                ann = th.get('type')
                lit = _literal_from_annotation(ann)
                if lit:
                    return lit
            except Exception:  # noqa: BLE001
                pass
            return None

        def _literal_from_annotation(ann: Any) -> Optional[str]:
            if ann is None:
                return None
            ann = peel_annotated(ann)
            if get_origin(ann) is Literal:
                lit_args = get_args(ann)
                for arg in lit_args:
                    if isinstance(arg, str):
                        return arg
            return None

        mapping: Dict[str, Any] = {}
        try:
            root = peel_annotated(ResponseStreamEvent)
            root_origin = get_origin(root)
            if root_origin is not None and root_origin.__name__ == 'Union':  # Union of variants
                for variant in get_args(root):  # type: ignore[arg-type]
                    v = peel_annotated(variant)
                    if get_origin(v) is not None:
                        continue
                    if not hasattr(v, '__name__'):
                        continue
                    lit = extract_literal_from_field(v)
                    if lit:
                        mapping[lit] = v
                if mapping:
                    logger.debug("_build_event_variant_map: collected %d variants via Annotated/Union inspection", len(mapping))
        except Exception as e:  # noqa: BLE001
            logger.debug("_build_event_variant_map: union/annotated introspection failed: %s", e)

        if not mapping:
            # Reflection fallback
            try:
                import inspect
                import openai.types.responses.response_stream_event as rse_mod  # type: ignore
                for name, obj in inspect.getmembers(rse_mod, inspect.isclass):
                    if not name.endswith('Event') or name == 'ResponseStreamEvent':
                        continue
                    lit = extract_literal_from_field(obj)
                    if lit:
                        mapping[lit] = obj
                if mapping:
                    logger.debug("_build_event_variant_map: reflection fallback collected %d variants", len(mapping))
            except Exception as e:  # noqa: BLE001
                logger.debug("_build_event_variant_map: reflection fallback failed: %s", e)

        if not mapping:
            logger.debug("_build_event_variant_map: no variants discovered; using fallback model only")
        return mapping

    def _build_response_stream_event(self, evt: Dict[str, Any]) -> ResponseStreamEvent:
        """Instantiate proper ResponseStreamEvent variant based on 'type' field.

        Args:
            evt: Raw event dictionary

        Returns:
            ResponseStreamEvent: Instantiated event object
        """
        if isinstance(evt.get('response'), dict):
            r = evt['response']
            if 'created_at' in r and 'created' not in r:
                r2 = dict(r)
                r2['created'] = r2['created_at']
                evt = {**evt, 'response': r2}

        evt_type = evt.get('type') if isinstance(evt.get('type'), str) else None
        variant = self._event_variant_map.get(evt_type) if evt_type else None
        if variant:
            v_name = getattr(variant, '__name__', '')
            needs_logprobs_default = v_name in ('ResponseTextDeltaEvent', 'ResponseTextDoneEvent') and 'logprobs' not in evt
            evt_for_variant = {**evt, 'logprobs': []} if needs_logprobs_default else evt
            try:
                if hasattr(variant, 'model_validate'):
                    return variant.model_validate(evt_for_variant)  # type: ignore[attr-defined]
                return variant(**evt_for_variant)  # type: ignore[arg-type]
            except Exception as e:  # noqa: BLE001
                if self._stream_fallback_count < 5:
                    logger.debug(
                        "Stream event variant instantiation failed type=%s variant=%s err=%s has_logprobs=%s", \
                        evt_type, v_name, repr(e), 'logprobs' in evt_for_variant
                    )
        self._stream_fallback_count += 1
        if self._stream_fallback_count <= 5:
            logger.debug("Using fallback stream event model type=%s keys=%s", evt_type, list(evt.keys())[:8])
        allowed = getattr(_ResponseStreamEventFallback, 'model_fields', {}).keys()
        filtered = {k: v for k, v in evt.items() if k in allowed}
        if 'type' not in filtered:
            filtered['type'] = evt_type or 'unknown'
        return _ResponseStreamEventFallback(**filtered)  # type: ignore[return-value]

    def _prepare_response_stream_event(self, evt: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and enrich raw event dict prior to model parsing.

        Args:
            evt: Raw event dictionary

        Returns:
            Dict[str, Any]: Normalized event dictionary
        """
        evt_type: str = str(evt.get('type', ''))
        resp_obj = evt.get('response')
        if isinstance(resp_obj, dict) and 'created_at' in resp_obj and 'created' not in resp_obj:
            new_resp_dict = cast(Dict[str, Any], resp_obj)
            # Preserve original map and just add created
            if 'created' not in new_resp_dict:
                new_resp_dict['created'] = new_resp_dict['created_at']
            evt = {**evt, 'response': new_resp_dict}
        if evt_type == 'response.output_text.delta' and 'delta' not in evt:
            evt = {**evt, 'delta': ''}
        return evt

    def _parse_error(self, error: httpx.HTTPStatusError) -> str:
        """Parse API error response.

        Args:
            error (httpx.HTTPStatusError): HTTP status error

        Returns:
            str: Formatted error message
        """
        try:
            error_body = error.response.text
            logger.debug(f"Raw API error response: {error_body}")

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
            logger.warning(f"Failed to parse API error: {e}")
            return f"HTTP {error.response.status_code}: {str(error)}"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dict[str, str]: Request headers
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "fastapi-openai-rag/1.0.0"
        }

    def _build_url(self, endpoint: str, model: str) -> str:
        """Build API URL for endpoints.

        Args:
            endpoint (str): API endpoint (e.g., "chat/completions")
            model (str): Model name/ID

        Returns:
            str: Complete API URL
        """
        # Default implementation for standard OpenAI
        return f"{self.base_url}/{endpoint}"

    def _build_models_url(self) -> str:
        """Build URL for models endpoint.

        Returns:
            str: Models API URL
        """
        # Default implementation for standard OpenAI
        return f"{self.base_url}/models"

    def _build_responses_url(self) -> str:
        """Build URL for responses endpoint.

        Returns:
            str: Responses API URL
        """
        # Default implementation for standard OpenAI
        return f"{self.base_url}/responses"

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

    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()
            logger.debug(f"Client closed for {self.provider}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        """Async context manager exit."""
        await self.close()
        return None