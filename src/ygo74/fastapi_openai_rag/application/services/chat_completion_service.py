"""Chat completion service for handling OpenAI-compatible requests."""
import time
from typing import Dict, Any, List, AsyncGenerator

from ...domain.models.autenticated_user import AuthenticatedUser
from ...domain.models.chat_completion import (
    ChatCompletionRequest,
    ChatMessage, ChatMessageRole
)
from ...domain.models.completion import (
    CompletionRequest
)
from ...domain.models.llm_model import LlmModel
from ...domain.unit_of_work import UnitOfWork
from ...domain.repositories.model_repository import IModelRepository
from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.validation_error import ValidationError
from ...domain.protocols.llm_client import LLMClientProtocol
from ...infrastructure.db.repositories.model_repository import SQLModelRepository
from ...infrastructure.llm.client_factory import LLMClientFactory
from .config_service import config_service
from ...domain.models.response import ResponsesCreatePayload
from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.chat.chat_completion import (
    ChatCompletion as OpenAIChatCompletion
)
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion import Completion as OpenAICompletion
from openai.types.completion_choice import CompletionChoice as OpenAICompletionChoice
from ...domain.models.embedding import EmbeddingCreatePayload, CreateEmbeddingResponse
# from openai.types.create_embedding_response import CreateEmbeddingResponse
import logging

from ..services.model_service import ModelService
from ..services.token_tracking_service import TokenTrackingService
from ..services.rate_limit_service import TokenRateLimitService

logger = logging.getLogger(__name__)

class ChatCompletionService:
    """Service for handling OpenAI-compatible chat and text completions."""

    def __init__(self, uow: UnitOfWork):
        """Initialize service.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
        """
        self._uow = uow
        self._model_service = ModelService(uow)
        self._token_tracking = TokenTrackingService(uow)
        self._token_rate_limit = TokenRateLimitService(uow)
        self._client_cache: Dict[str, LLMClientProtocol] = {}
        logger.debug("ChatCompletionService initialized")

    async def create_completion(self, request: CompletionRequest, user: AuthenticatedUser) -> OpenAICompletion:
        """Create a text completion.

        Args:
            request (CompletionRequest): Text completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            CompletionResponse: Generated text completion

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        """Create a text completion.

        Implements capability-based fallback: if the model does not support the
        'completions' endpoint but supports chat, it will internally perform a
        chat completion and convert the result to a CompletionResponse.
        """
        logger.info(f"Creating text completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_completion_request(request, model)

        # Capability introspection
        capabilities = model.capabilities or {}
        def _as_bool(val: Any) -> bool:
            return val is True or (isinstance(val, str) and val.lower() == "true")
        supports_completions = any(_as_bool(capabilities.get(k)) for k in [
            "completions", "completion", "text_completion"
        ])
        supports_chat = any(_as_bool(capabilities.get(k)) for k in [
            "chat_completions", "chatCompletion", "chat", "chat_completion"
        ])

        start_time = time.time()
        endpoint = "/v1/completions"

        try:

            if supports_completions or not supports_chat:
                with self._token_tracking.track_request_in_progress(request.model):
                    response = await client.completion(request_with_provider)
            else:
                logger.info("Model lacks 'completions' capability; falling back to chat completion conversion")
                response = await self._completion_via_chat_fallback(request_with_provider, client, model)

            self._token_tracking.track_completion(
                response=response,
                user=user,
                model=model,
                endpoint=endpoint,
                start_time=start_time
            )
            latency_ms = (time.time() - start_time) * 1000

            logger.info(f"Text completion successful in {latency_ms:.2f}ms (fallback={not supports_completions and supports_chat})")
            return response

        except Exception as e:
            logger.error(f"Error in text completion: {str(e)}")
            raise

    async def create_completion_stream(self, request: CompletionRequest, user: AuthenticatedUser) -> AsyncGenerator[OpenAICompletion, None]:
        """Create a streaming text completion.

        Args:
            request (CompletionRequest): Text completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Yields:
            OpenAICompletionChoice: Streaming chunks of the response

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating streaming text completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_completion_request(request, model)

        # Ensure we're requesting a stream
        request_with_provider.stream = True

        # Capability introspection
        capabilities = model.capabilities or {}
        def _as_bool(val: Any) -> bool:
            return val is True or (isinstance(val, str) and val.lower() == "true")
        supports_completions = any(_as_bool(capabilities.get(k)) for k in [
            "completions", "completion", "text_completion"
        ])
        supports_chat = any(_as_bool(capabilities.get(k)) for k in [
            "chat_completions", "chatCompletion", "chat", "chat_completion"
        ])

        start_time = time.time()
        endpoint = "/v1/completions"
        try:
            with self._token_tracking.track_request_in_progress(request.model):
                if supports_completions or not supports_chat:
                    async for event in client.completion_stream(request_with_provider):
                        self._token_tracking.track_completion(
                            response=event,
                            user=user,
                            endpoint=endpoint,
                            model=model,
                            start_time=start_time
                        )
                        yield event
                else:
                    logger.info("Model lacks 'completions' streaming capability; falling back to chat completion stream conversion")
                    async for chat_event in self._completion_stream_via_chat_fallback(request_with_provider, client, model):
                        self._token_tracking.track_completion(
                            response=chat_event,
                            user=user,
                            endpoint=endpoint,
                            model=model,
                            start_time=start_time
                        )
                        yield chat_event
            logger.info(f"Streaming text completion finished in {(time.time() - start_time) * 1000:.2f}ms")

        except Exception as e:
            logger.error(f"Error in streaming text completion: {str(e)}")
            raise

    async def create_chat_completion(self, request: ChatCompletionRequest, user: AuthenticatedUser) -> OpenAIChatCompletion:
        """Create a chat completion.

        Args:
            request (ChatCompletionRequest): Chat completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            OpenAIChatCompletion: Generated chat completion

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating chat completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_chat_request(request, model)

        # Measure request time and execute
        start_time = time.time()
        endpoint = "/v1/chat/completions"
        try:
            with self._token_tracking.track_request_in_progress(model.name):
                response = await client.chat_completion(request_with_provider)

                self._token_tracking.track_completion(
                    response=response,
                    user=user,
                    endpoint=endpoint,
                    model=model,
                    start_time=start_time
                )

                return response

        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise

    async def create_chat_completion_stream(self, request: ChatCompletionRequest, user: AuthenticatedUser) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Create a streaming chat completion.

        Args:
            request (ChatCompletionRequest): Chat completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Yields:
            ChatCompletionChunk: Streaming chunks of the response

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating streaming chat completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_chat_request(request, model)

        # Ensure we're requesting a stream
        request_with_provider.stream = True

        # Start timing
        start_time = time.time()
        endpoint = "/v1/chat/completions"
        try:
            with self._token_tracking.track_request_in_progress(request.model):
                async for chunk in client.chat_completion_stream(request_with_provider):
                    self._token_tracking.track_chat_completion_chunk(
                        chunk=chunk,
                        user=user,
                        endpoint=endpoint,
                        model=model,
                        start_time=start_time
                    )
                    yield chunk

            logger.info(f"Streaming chat completion finished in {(time.time() - start_time) * 1000:.2f}ms")

        except Exception as e:
            logger.error(f"Error in streaming chat completion: {str(e)}")
            raise

    async def create_response(self, payload: ResponsesCreatePayload, user: AuthenticatedUser) -> OpenAIResponse:
        """Execute a Responses API request and return the OpenAI SDK Response object.

        Args:
            payload (ResponsesCreatePayload): Validated request payload
            user (AuthenticatedUser): Authenticated user

        Returns:
            OpenAIResponse: OpenAI SDK typed response object
        """
        model_name = payload.model
        if not model_name:
            raise ValidationError("model is required in responses payload")
        model = await self._get_and_validate_model(model_name, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        client = self._get_or_create_client(model)

        start_time = time.time()
        endpoint = "/v1/responses"
        try:

            with self._token_tracking.track_request_in_progress(model_name):
                response = await client.responses(payload)
                self._token_tracking.track_completion(
                    response=response,
                    user=user,
                    endpoint=endpoint,
                    model=model,
                    start_time=start_time
                )

                return response

        except Exception as e:
            logger.error(f"Error in responses API: {str(e)}", exc_info=True)
            raise

    async def create_response_stream(self, payload: ResponsesCreatePayload, user: AuthenticatedUser) -> AsyncGenerator[ResponseStreamEvent, None]:
        """Stream Responses API events (OpenAI SDK ResponseStreamEvent objects).

        Args:
            payload (ResponsesCreatePayload): Validated request payload with stream True
            user (AuthenticatedUser): Authenticated user

        Yields:
            ResponseStreamEvent: OpenAI SDK streaming event objects
        """
        model_name = payload.model
        if not model_name:
            raise ValidationError("model is required in responses payload")
        model = await self._get_and_validate_model(model_name, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        client = self._get_or_create_client(model)

        start_time = time.time()
        endpoint = "/v1/responses"
        payload.stream = True
        try:

            with self._token_tracking.track_request_in_progress(model_name):
                async for event in client.responses_stream(payload):
                    self._token_tracking.track_stream_completion(
                        event=event,
                        user=user,
                        endpoint=endpoint,
                        model=model,
                        start_time=start_time
                    )
                    yield event
        except Exception as e:
            logger.error(f"Error in responses stream: {str(e)}", exc_info=True)
            raise

    async def create_embedding(self, payload: EmbeddingCreatePayload, user: AuthenticatedUser) -> CreateEmbeddingResponse:
        """Create embeddings for the given input.

        Args:
            payload (EmbeddingCreatePayload): Embedding creation request
            user (AuthenticatedUser): Authenticated user

        Returns:
            CreateEmbeddingResponse: OpenAI SDK typed response object

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating embeddings with model {payload.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(payload.model, user)
        self._token_rate_limit.check_rate_limit(user=user, model=model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Measure request time and execute
        start_time = time.time()
        endpoint = "/v1/embeddings"
        try:
            with self._token_tracking.track_request_in_progress(model.name):
                response = await client.embedding(payload)
                self._token_tracking.track_completion(
                    response=response,
                    user=user,
                    endpoint=endpoint,
                    model=model,
                    start_time=start_time
                )

                return response

        except Exception as e:
            logger.error(f"Error in embedding creation: {str(e)}", exc_info=True)
            raise

    async def _get_and_validate_model(self, model_name: str, user: AuthenticatedUser) -> LlmModel:
        """Get and validate model from database, checking user authorization.

        Args:
            model_name (str): Model name or technical name
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            LlmModel: Validated model entity

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved
            PermissionError: If user is not authorized to access the model
        """
        with self._uow as uow:
            repository: IModelRepository = SQLModelRepository(uow.session)

            # Try to find by name if technical name fails
            models = repository.get_approved_by_name(model_name)

            if not models:
                raise EntityNotFoundError("Model", model_name)

            # Take the first model found
            model = models[0]

            # If user is admin, allow access
            if "admin" in user.groups:
                return model

            # For regular users, check if they have access to this model
            # Get all models the user has access to
            accessible_models = user.models

            # Check if requested model is in user's accessible models
            if not any(m.id == model.id for m in accessible_models):
                logger.warning(f"User with groups {user} attempted unauthorized access to model {model_name}")
                raise PermissionError(f"Not authorized to access model {model_name}")

            return model

    def _get_or_create_client(self, model: LlmModel) -> LLMClientProtocol:
        """Get or create LLM client for the model.

        Args:
            model (LlmModel): Model entity

        Returns:
            LLMClientProtocol: Provider client

        Raises:
            RuntimeError: If client cannot be created
        """
        # Use model URL as cache key
        cache_key = f"{model.url}_{model.technical_name}"

        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        # Get API key for the model's provider from config
        model_config = config_service.get_model_config(model.technical_name)

        if not model_config:
            raise RuntimeError(f"No model configuration found for model's provider {model.technical_name}")

        # Create client using factory
        try:
            client = LLMClientFactory.create_client(model=model, model_config=model_config)
            self._client_cache[cache_key] = client
            logger.debug(f"Created and cached client for {model.provider} model {model.technical_name}")
            return client
        except Exception as e:
            logger.error(f"Failed to create client for model {model.technical_name}: {str(e)}")
            raise RuntimeError(f"Failed to create client for model {model.technical_name}: {str(e)}")

    def _prepare_chat_request(self, request: ChatCompletionRequest, model: LlmModel) -> ChatCompletionRequest:
        """Prepare chat completion request with model info.

        Args:
            request (ChatCompletionRequest): Original request
            model (Model): Model entity

        Returns:
            ChatCompletionRequest: Updated request
        """
        # Create a copy with updated model information
        request_dict = request.model_dump()
        request_dict['model'] = model.name
        return ChatCompletionRequest(**request_dict)

    def _prepare_completion_request(self, request: CompletionRequest, model: LlmModel) -> CompletionRequest:
        """Prepare text completion request with model info.

        Args:
            request (CompletionRequest): Original request
            model (Model): Model entity

        Returns:
            CompletionRequest: Updated request
        """
        # Create a copy with updated model information
        request_dict = request.model_dump()
        request_dict['model'] = model.name
        return CompletionRequest(**request_dict)

    async def _completion_via_chat_fallback(self, request: CompletionRequest, client: LLMClientProtocol, model: LlmModel) -> OpenAICompletion:
        """Execute a completion request via chat fallback based on model capabilities.

        Args:
            request (CompletionRequest): Original completion request (with provider model name applied)
            client (LLMClientProtocol): LLM client
            model (LlmModel): Model entity (for metadata)

        Returns:
            CompletionResponse: Converted response from chat completion
        """
        # Build chat messages from prompt
        if isinstance(request.prompt, str):
            content = request.prompt
        elif isinstance(request.prompt, list): # type: ignore
            content = "\n".join(str(p) for p in request.prompt)
        else:
            content = str(request.prompt)

        chat_messages = [ChatMessage(role=ChatMessageRole.USER, content=content)]

        # Choose max_tokens fallback
        max_tokens = request.max_tokens if request.max_tokens is not None else 1000

        chat_request = ChatCompletionRequest(
            model=request.model,  # already replaced by provider name
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            n=request.n,
            stream=False,  # fallback only for non-stream in this method
            stop=request.stop,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
            user=request.user,
            seed=request.seed,
            logit_bias=request.logit_bias,
            top_logprobs=request.logprobs if request.logprobs and request.logprobs > 0 else None
        )

        chat_response = await client.chat_completion(chat_request)
        return self._convert_chat_to_completion_response(chat_response, model)

    def _convert_chat_to_completion_response(self, chat_response: OpenAIChatCompletion, model: LlmModel) -> OpenAICompletion:
        """Convert a ChatCompletionResponse to a CompletionResponse for fallback cases.
        Args:
            chat_response (OpenAIChatCompletion): Chat completion response
            model (LlmModel): Model entity (for metadata)

        Returns:
            OpenAICompletion: Converted completion response

        """

        # Convert ChatCompletionResponse to CompletionResponse
        choices: List[OpenAICompletionChoice] = []
        for chat_choice in chat_response.choices:
            content = chat_choice.message.content
            content_text = content or ""

            finish_reason:str = chat_choice.finish_reason or "stop"
            # Only allow valid finish_reason values
            if finish_reason not in ["stop", "length", "content_filter"]:
                finish_reason = "stop"

            choices.append(OpenAICompletionChoice(
                text=content_text,
                index=chat_choice.index,
                logprobs=None,
                finish_reason=finish_reason
            ))

        return OpenAICompletion(
            id=chat_response.id,
            object="text_completion",
            created=chat_response.created,
            model=chat_response.model,
            system_fingerprint=chat_response.system_fingerprint,
            choices=choices,
            usage=chat_response.usage
        )

    def get_models_for_user(self, user: AuthenticatedUser) -> List[LlmModel]:
        """Get models accessible to user based on group membership.

        Args:
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            List of LLM models the user has access to
        """
        logger.debug(f"Getting models for user : {user.username}")
        return user.models

    async def _completion_stream_via_chat_fallback(self, request: CompletionRequest, client: LLMClientProtocol, model: LlmModel) -> AsyncGenerator[OpenAICompletion, None]:
        """Execute a streaming completion request via chat fallback based on model capabilities.

        Args:
            request (CompletionRequest): Original completion request (with provider model name applied)
            client (LLMClientProtocol): LLM client
            model (LlmModel): Model entity (for metadata)

        Yields:
            OpenAICompletion: Converted completion events from chat completion stream
        """
        # Build chat messages from request prompt
        if isinstance(request.prompt, str):
            content = request.prompt
        elif isinstance(request.prompt, list):  # type: ignore
            content = "\n".join(str(p) for p in request.prompt)
        else:
            content = str(request.prompt)

        chat_messages = [ChatMessage(role=ChatMessageRole.USER, content=content)]

        # Choose max_tokens fallback
        max_tokens = request.max_tokens if request.max_tokens is not None else 1000

        chat_request = ChatCompletionRequest(
            model=request.model,  # already replaced by provider name
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            n=request.n,
            stream=True,  # ensure streaming is enabled
            stop=request.stop,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
            user=request.user,
            seed=request.seed,
            logit_bias=request.logit_bias,
            top_logprobs=request.logprobs if request.logprobs and request.logprobs > 0 else None
        )

        # Generate a unique ID for this completion
        completion_id = f"cmpl-fallback-{int(time.time())}"
        created_timestamp = int(time.time())
        n_choices: int = request.n if request.n is not None else 1
        cumulative_text: List[str] = [""] * n_choices

        # Process chat completion stream and convert each chunk to completion format
        async for chat_chunk in client.chat_completion_stream(chat_request):

            completion_chunk = self._convert_chat_chunk_to_completion_chunk(
                chat_chunk,
                completion_id,
                created_timestamp,
                model.name,
                cumulative_text
            )
            yield completion_chunk

    def _convert_chat_chunk_to_completion_chunk(self,
                                               chat_chunk: ChatCompletionChunk,
                                               completion_id: str,
                                               created_timestamp: int,
                                               model_name: str,
                                               cumulative_text: List[str]) -> OpenAICompletion:
        """Convert a ChatCompletionChunk to a CompletionResponse for stream fallback.

        Args:
            chat_chunk (ChatCompletionChunk): Chat completion chunk
            completion_id (str): Consistent ID for the completion
            created_timestamp (int): Consistent creation timestamp
            model_name (str): Model name for the response
            cumulative_text (List[str]): List to track cumulative text for each choice

        Returns:
            OpenAICompletion: Converted completion chunk
        """
        choices: List[OpenAICompletionChoice] = []

        # Process each choice in the chat chunk
        for choice in chat_chunk.choices:
            index = choice.index
            delta_content = choice.delta.content or ""

            # Update cumulative text for this choice
            if index < len(cumulative_text):
                cumulative_text[index] += delta_content

            # Create completion choice
            finish_reason = choice.finish_reason
            if not finish_reason:
                finish_reason = "content_filter"
            elif finish_reason and finish_reason not in ["stop", "length", "content_filter"]:
                finish_reason = "stop"

            choices.append(OpenAICompletionChoice(
                text=delta_content,  # For streaming, we only send the delta text
                index=index,
                logprobs=None,
                finish_reason=finish_reason
            ))

        # track usage
        usage = chat_chunk.usage

        # Create completion response
        return OpenAICompletion(
            id=completion_id,
            object="text_completion",
            created=created_timestamp,
            model=model_name,
            choices=choices,
            usage=usage
        )
