"""Azure OpenAI proxy client for Azure-specific API calls."""
import httpx
import json
import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator, AsyncIterator, List, cast, get_args, get_origin  # noqa: F401
from datetime import datetime, timezone
from pydantic import BaseModel

from ...domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,ChatCompletionStreamChoice,
    ChatCompletionStreamResponse, ChatMessage
)
from ...domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ...domain.models.llm import LLMProvider, TokenUsage
from ...domain.protocols.llm_client import LLMClientProtocol
from ...domain.models.response import ResponsesCreatePayload
from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent

from .azure_management_client import AzureManagementClient
from .http_client_factory import HttpClientFactory
from .retry_handler import with_enterprise_retry, LLMRetryHandler
from .enterprise_config import EnterpriseConfig
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

    @with_enterprise_retry
    async def responses(self, payload: ResponsesCreatePayload) -> OpenAIResponse:
        """Execute Azure Responses API call and return OpenAI SDK Response.

        Args:
            payload (ResponsesCreatePayload): Validated request payload

        Returns:
            OpenAIResponse: Parsed OpenAI Response object
        """
        deployment: str = payload.model
        if not deployment:
            raise ValueError("ResponsesCreatePayload.model must be set for Azure responses API")
        url = f"{self.base_url}/openai/v1/responses"
        headers = self._get_headers()
        body = payload.to_openai_kwargs()
        # Azure endpoint may not require removing model; keep for compatibility
        # Ensure stream disabled for non streaming route
        body["stream"] = False
        logger.debug(f"Azure responses() call -> url={url} keys={list(body.keys())}")
        try:
            res = await self._client.post(url=url, headers=headers, json=body, timeout=120.0)
            res.raise_for_status()
            data = res.json()
            return OpenAIResponse.model_validate(data)  # type: ignore[attr-defined]

        except httpx.HTTPStatusError as e:
            err = self._parse_azure_error(e)
            logger.error(f"Azure HTTP error in responses: {err}")
            raise httpx.HTTPError(f"Azure OpenAI API error: {err}")
        except Exception:
            raise

    @with_enterprise_retry
    async def _establish_responses_stream_connection(self, payload: ResponsesCreatePayload):  # type: ignore[override]
        """Establish streaming connection (typed payload variant)."""
        deployment: str = payload.model
        if not deployment:
            raise ValueError("ResponsesCreatePayload.model must be set for Azure responses streaming")
        url = f"{self.base_url}/openai/v1/responses"
        headers = self._get_headers()
        body = payload.to_openai_kwargs()
        body["stream"] = True
        logger.debug(f"Azure responses_stream() opening stream -> url={url}")
        return self._client.stream(
            "POST",
            url=url,
            headers=headers,
            json=body,
            timeout=120.0
        )

    async def responses_stream(self, payload: ResponsesCreatePayload) -> AsyncGenerator[ResponseStreamEvent, None]:  # type: ignore[override]
        """Stream Azure Responses API events with minimal normalization and diagnostic logging.

        Enhancements:
        - Handle SSE style separate 'event:' header lines (store then apply to next data JSON)
        - Only parse JSON on 'data:' lines (reduces noise)
        - Attach missing 'type' from preceding event header if absent in JSON
        - Normalize created_at -> created (within nested response)
        - Log at DEBUG only first few validation errors with full Pydantic details
        - Suppress repetitive non-JSON skip logs
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
            err = self._parse_azure_error(e)
            logger.error(f"Azure HTTP error in responses stream: {err}")
            raise httpx.HTTPError(f"Azure OpenAI API error: {err}")
        except Exception:
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

    def _build_stream_event(self, evt: Dict[str, Any]) -> ResponseStreamEvent:  # type: ignore[override]
        """Instantiate proper ResponseStreamEvent variant based on 'type' field.

        Adjusted: proactively inject empty logprobs list for text delta/done events when Azure omits it
        instead of relying on exception handling.
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
            if isinstance(payload["prompt"], list):
                payload["prompt"] = "\n".join(str(p) for p in payload["prompt"])  # type: ignore[list-item]

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
        """Parse Azure chat completion response."""
        choices: List[ChatCompletionChoice] = []
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
        """Parse Azure text completion response."""
        choices: List[CompletionChoice] = []
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
        """Parse Azure streaming response chunk."""
        choices: List[ChatCompletionStreamChoice] = []  # fixed generic syntax
        for choice_data in chunk_data.get("choices", []):
            # Extract the delta content from the choice
            delta: Dict[str, Any] = choice_data.get("delta", {})

            # Log the actual content for debugging
            logger.debug(f"Stream chunk delta content: {delta}")

            # Assigner une valeur par défaut pour le rôle si elle est None
            role = delta.get("role")
            if role is None:
                # Dans les chunks de streaming Azure, le rôle est souvent défini uniquement
                # dans le premier chunk et est généralement "assistant" pour les chunks suivants
                role = "assistant"

            # Create a message object from the delta
            message = ChatMessage(  # type: ignore[arg-type]
                role=role_str,  # type: ignore[arg-type]  # casting role string to ChatMessageRole
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

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]):
        """Async context manager exit with automatic cleanup."""
        await self.close()

    def _prepare_stream_event(self, evt: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and enrich raw Azure event dict prior to model parsing."""
        # Removed unnecessary isinstance guard (parameter already typed Dict[str, Any])
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
