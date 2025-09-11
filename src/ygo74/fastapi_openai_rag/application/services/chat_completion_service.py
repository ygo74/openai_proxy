"""Chat completion service for handling OpenAI-compatible requests."""
import time
import uuid
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime, timezone

from ...domain.models.autenticated_user import AuthenticatedUser
from ...domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatMessage, ChatMessageRole
)
from ...domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ...domain.models.llm import LLMProvider, TokenUsage
from ...domain.models.llm_model import LlmModel, LlmModelStatus
from ...domain.unit_of_work import UnitOfWork
from ...domain.repositories.model_repository import IModelRepository
from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.validation_error import ValidationError
from ...domain.protocols.llm_client import LLMClientProtocol
from ...infrastructure.db.repositories.model_repository import SQLModelRepository
from ...infrastructure.db.repositories.group_repository import SQLGroupRepository
from ...infrastructure.llm.client_factory import LLMClientFactory
from .config_service import config_service
import logging

logger = logging.getLogger(__name__)

class ChatCompletionService:
    """Service for handling OpenAI-compatible chat and text completions."""

    def __init__(self, uow: UnitOfWork):
        """Initialize service.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
        """
        self._uow = uow
        self._client_cache: Dict[str, LLMClientProtocol] = {}
        logger.debug("ChatCompletionService initialized")

    async def create_chat_completion(self, request: ChatCompletionRequest, user: AuthenticatedUser) -> ChatCompletionResponse:
        """Create a chat completion.

        Args:
            request (ChatCompletionRequest): Chat completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            ChatCompletionResponse: Generated chat completion

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating chat completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_chat_request(request, model)

        # Measure request time and execute
        start_time = time.time()
        try:
            response = await client.chat_completion(request_with_provider)
            latency_ms = (time.time() - start_time) * 1000

            # Update response with timing info
            response.latency_ms = latency_ms
            response.timestamp = datetime.now(timezone.utc)

            logger.info(f"Chat completion successful in {latency_ms:.2f}ms")
            return response

        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise

    async def create_completion(self, request: CompletionRequest, user: AuthenticatedUser) -> CompletionResponse:
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

        model = await self._get_and_validate_model(request.model, user)
        client = self._get_or_create_client(model)
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
        try:
            if supports_completions or not supports_chat:
                # Direct call (or no chat fallback available)
                response = await client.completion(request_with_provider)
            else:
                logger.info("Model lacks 'completions' capability; falling back to chat completion conversion")
                response = await self._completion_via_chat_fallback(request_with_provider, client, model)

            latency_ms = (time.time() - start_time) * 1000
            response.latency_ms = latency_ms
            response.timestamp = datetime.now(timezone.utc)
            logger.info(f"Text completion successful in {latency_ms:.2f}ms (fallback={not supports_completions and supports_chat})")
            return response
        except Exception as e:
            logger.error(f"Error in text completion: {str(e)}")
            raise

    async def create_chat_completion_stream(self, request: ChatCompletionRequest, user: AuthenticatedUser) -> AsyncGenerator[ChatCompletionResponse, None]:
        """Create a streaming chat completion.

        Args:
            request (ChatCompletionRequest): Chat completion request
            user (AuthenticatedUser): Authenticated user with group memberships

        Yields:
            ChatCompletionResponse: Streaming chunks of the response

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            PermissionError: If user is not authorized to access the model
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating streaming chat completion with model {request.model}")

        # Validate and get model, checking authorization
        model = await self._get_and_validate_model(request.model, user)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_chat_request(request, model)

        # Ensure we're requesting a stream
        request_with_provider.stream = True

        # Start timing
        start_time = time.time()

        try:
            # Ne pas utiliser await ici car chat_completion_stream retourne déjà un générateur asynchrone
            # et non une coroutine à attendre
            async for chunk in client.chat_completion_stream(request_with_provider):
                # Add timing information
                chunk.latency_ms = (time.time() - start_time) * 1000
                chunk.timestamp = datetime.now(timezone.utc)

                yield chunk

            logger.info(f"Streaming chat completion finished in {(time.time() - start_time) * 1000:.2f}ms")

        except Exception as e:
            logger.error(f"Error in streaming chat completion: {str(e)}")
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
        request_dict['model'] = model.name  # Use technical name for API calls
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
        request_dict['model'] = model.name  # Use technical name for API calls
        return CompletionRequest(**request_dict)

    async def _completion_via_chat_fallback(self, request: CompletionRequest, client: LLMClientProtocol, model: LlmModel) -> CompletionResponse:
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
        elif isinstance(request.prompt, list):
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
            seed=request.seed
        )

        chat_response = await client.chat_completion(chat_request)
        return self._convert_chat_to_completion_response(chat_response, model)

    def _convert_chat_to_completion_response(self, chat_response: ChatCompletionResponse, model: LlmModel) -> CompletionResponse:
        """Convert a ChatCompletionResponse to a CompletionResponse for fallback cases."""
        choices: List[CompletionChoice] = []
        for chat_choice in chat_response.choices:
            choices.append(CompletionChoice(
                text=chat_choice.message.content or "",
                index=chat_choice.index,
                logprobs=None,
                finish_reason=chat_choice.finish_reason
            ))

        return CompletionResponse(
            id=chat_response.id,
            object="text_completion",
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

    def get_models_for_user(self, user: AuthenticatedUser) -> List[LlmModel]:
        """Get models accessible to user based on group membership.

        Args:
            user (AuthenticatedUser): Authenticated user with group memberships

        Returns:
            List of LLM models the user has access to
        """
        logger.debug(f"Getting models for user : {user.username}")
        return user.models
