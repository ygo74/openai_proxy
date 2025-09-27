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

from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent

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
    async def completion(self, request: CompletionRequest) -> CompletionResponse:
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
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in text completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")
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
        messages: List[ChatMessage] = []
        # Prompt normalization
        if isinstance(request.prompt, str):
            content: str = request.prompt
        elif isinstance(request.prompt, list):  # type: ignore[unreachable]
            content = "\n".join(str(p) for p in request.prompt)
        else:
            content = str(request.prompt)
        messages.append(ChatMessage(role="user", content=content))  # type: ignore[arg-type]

        max_tokens: int = request.max_tokens if request.max_tokens is not None else 1000
        if request.max_tokens is None:
            logger.debug("No max_tokens specified, using default: %d", max_tokens)

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
            seed=request.seed,
            top_logprobs=None,  # ensure required param if present in model
        )
        # Make chat completion request
        chat_response = await self.chat_completion(chat_request)

        # Convert chat response back to completion response
        return self._convert_chat_to_completion_response(chat_response)

    def _convert_chat_to_completion_response(self, chat_response: ChatCompletionResponse) -> CompletionResponse:
        """Convert chat completion response to completion response.

        Args:
            chat_response: Chat completion response

        Returns:
            CompletionResponse: Converted completion response
        """
        # Add explicit typing for linter clarity
        choices: List[CompletionChoice] = []
        for chat_choice in chat_response.choices:  # type: ignore[attr-defined]
            choice = CompletionChoice(
                text=getattr(chat_choice.message, 'content', '') or "",
                index=getattr(chat_choice, 'index', 0),
                logprobs=None,
                finish_reason=getattr(chat_choice, 'finish_reason', None)
            )
            choices.append(choice)
        return CompletionResponse(
            id=getattr(chat_response, 'id', str(uuid.uuid4())),
            object="text_completion",
            created=getattr(chat_response, 'created', int(time.time())),
            model=getattr(chat_response, 'model', ''),
            system_fingerprint=getattr(chat_response, 'system_fingerprint', None),
            choices=choices,
            usage=cast(TokenUsage, getattr(chat_response, 'usage', None)) if getattr(chat_response, 'usage', None) else None,  # type: ignore[arg-type]
            latency_ms=cast(float, getattr(chat_response, 'latency_ms', None)) if getattr(chat_response, 'latency_ms', None) else None,  # type: ignore[arg-type]
            timestamp=getattr(chat_response, 'timestamp', datetime.now(timezone.utc)),
            raw_response=getattr(chat_response, 'raw_response', {})
        )

    @with_enterprise_retry
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
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

            return self._parse_chat_response(response_data, latency_ms)

        except httpx.HTTPStatusError as e:
            error_details = self._parse_error(e)
            logger.error(f"HTTP error in chat completion: {error_details}")
            raise httpx.HTTPError(f"API error: {error_details}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in chat completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat completion: {str(e)}")
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

        logger.debug(f"Starting streaming chat completion to {url}")
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
        """Stream chat completion via API.

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

        logger.debug(f"responses() call -> url={url} keys={list(body.keys())}")

        try:
            res = await self._client.post(url=url, headers=headers, json=body, timeout=120.0)
            res.raise_for_status()
            data = res.json()
            try:
                return OpenAIResponse.model_validate(data)  # type: ignore[attr-defined]
            except AttributeError:
                # Fallback if model_validate not available
                return data

        except httpx.HTTPStatusError as e:
            err = self._parse_error(e)
            logger.error(f"HTTP error in responses: {err}")
            raise httpx.HTTPError(f"API error: {err}")
        except Exception as e:
            logger.error(f"Unexpected error in responses API: {e}")
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

        logger.debug(f"responses_stream() opening stream -> url={url}")

        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=body,
            timeout=120.0
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
                        evt_dict = self._prepare_stream_event(evt_raw)
                        # Validate/Coerce once (version-tolerant)
                        try:
                            evt_obj = self._build_stream_event(evt_dict)
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

    def _build_stream_event(self, evt: Dict[str, Any]) -> ResponseStreamEvent:
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

    def _prepare_stream_event(self, evt: Dict[str, Any]) -> Dict[str, Any]:
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

    def _parse_stream_chunk(self, chunk_data: Dict[str, Any]) -> ChatCompletionStreamResponse:
        """Parse streaming response chunk.

        Args:
            chunk_data (Dict[str, Any]): Raw chunk data

        Returns:
            ChatCompletionStreamResponse: Parsed streaming response chunk
        """
        # Extract choices data from the chunk
        choices: List[ChatCompletionStreamChoice] = []
        for choice_data in chunk_data.get("choices", []):
            # Extract the delta content from the choice
            delta = choice_data.get("delta", {})

            # Log the actual content for debugging
            logger.debug(f"Stream chunk delta content: {delta}")

            # Assign a default value for role if None
            role = delta.get("role") or "assistant"
            if isinstance(role, str) and role not in {r.value for r in ChatMessageRole}:  # type: ignore[attr-defined]
                role = ChatMessageRole.ASSISTANT

            # Create a message object from the delta
            message = ChatMessage(
                role=role,  # type: ignore[arg-type]
                content=delta.get("content", ""),
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
            latency_ms=None,  # Will be set later in the service
            timestamp=datetime.now(timezone.utc)
        )

    def _parse_chat_response(self, response_data: Dict[str, Any], latency_ms: float) -> ChatCompletionResponse:
        """Parse chat completion response.

        Args:
            response_data (Dict[str, Any]): Raw API response
            latency_ms (float): Request latency

        Returns:
            ChatCompletionResponse: Domain model response
        """
        # Extract choices
        choices: List[ChatCompletionChoice] = []
        for choice_data in response_data.get("choices", []):
            message_data = choice_data.get("message", {})
            role_raw = message_data.get("role") or "assistant"
            if isinstance(role_raw, str) and role_raw not in {r.value for r in ChatMessageRole}:  # type: ignore[attr-defined]
                role_raw = ChatMessageRole.ASSISTANT

            message = ChatMessage(
                role=role_raw,  # type: ignore[arg-type]
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
            CompletionResponse: Domain model response
        """
        # Extract choices
        choices: List[CompletionChoice] = []
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