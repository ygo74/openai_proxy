"""Chat completion service for handling OpenAI-compatible requests."""
import time
import uuid
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone
from ...domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice,
    ChatMessage, ChatMessageRole
)
from ...domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ...domain.models.llm import LLMProvider, TokenUsage
from ...domain.models.llm_model import LlmModel, LlmModelStatus, AzureLlmModel
from ...domain.unit_of_work import UnitOfWork
from ...domain.repositories.model_repository import IModelRepository
from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.validation_error import ValidationError
from ...domain.protocols.llm_client import LLMClientProtocol
from ...infrastructure.db.repositories.model_repository import SQLModelRepository
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

    async def create_chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create a chat completion.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated chat completion

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating chat completion with model {request.model}")

        # Validate and get model
        model = await self._get_and_validate_model(request.model)

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

    async def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create a text completion.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated text completion

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved or validation fails
            RuntimeError: If provider client not configured
        """
        logger.info(f"Creating text completion with model {request.model}")

        # Validate and get model
        model = await self._get_and_validate_model(request.model)

        # Get or create client for this model
        client = self._get_or_create_client(model)

        # Update request with provider info
        request_with_provider = self._prepare_completion_request(request, model)

        # Measure request time and execute
        start_time = time.time()
        try:
            response = await client.completion(request_with_provider)
            latency_ms = (time.time() - start_time) * 1000

            # Update response with timing info
            response.latency_ms = latency_ms
            response.timestamp = datetime.now(timezone.utc)

            logger.info(f"Text completion successful in {latency_ms:.2f}ms")
            return response

        except Exception as e:
            logger.error(f"Error in text completion: {str(e)}")
            raise

    async def _get_and_validate_model(self, model_name: str) -> Union[LlmModel, AzureLlmModel]:
        """Get and validate model from database.

        Args:
            model_name (str): Model name or technical name

        Returns:
            Union[LlmModel, AzureLlmModel]: Validated model entity

        Raises:
            EntityNotFoundError: If model not found
            ValidationError: If model not approved
        """
        with self._uow as uow:
            repository: IModelRepository = SQLModelRepository(uow.session)

            # Try to get by technical name first, then by name
            model = repository.get_by_technical_name(model_name)
            if not model:
                # Try to find by name if technical name fails
                models = repository.get_all()
                model = next((m for m in models if m.name == model_name), None)

            if not model:
                raise EntityNotFoundError("Model", model_name)

            if model.status != LlmModelStatus.APPROVED:
                raise ValidationError(f"Model {model_name} is not approved for use")

            # The repository will return the appropriate type based on the stored data
            # If it's an Azure model, it will be an AzureLlmModel instance
            return model

    def _get_or_create_client(self, model: Union[LlmModel, AzureLlmModel]) -> LLMClientProtocol:
        """Get or create LLM client for the model.

        Args:
            model (Union[LlmModel, AzureLlmModel]): Model entity

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
        api_key = config_service.get_api_key(model.provider)

        if not api_key:
            raise RuntimeError(f"No API key configured for provider {model.provider}")

        # Create client using factory
        try:
            client = LLMClientFactory.create_client(model, api_key)
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
        request_dict['model'] = model.technical_name  # Use technical name for API calls
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
        request_dict['model'] = model.technical_name  # Use technical name for API calls
        return CompletionRequest(**request_dict)

    def _get_provider_from_url(self, url: str) -> LLMProvider:
        """Determine provider from model URL.

        Args:
            url (str): Model API URL

        Returns:
            LLMProvider: Determined provider

        Raises:
            ValueError: If provider cannot be determined
        """
        url = url.lower()
        if "openai.azure.com" in url:
            return LLMProvider.AZURE
        elif "api.openai.com" in url:
            return LLMProvider.OPENAI
        elif "anthropic.com" in url:
            return LLMProvider.ANTHROPIC
        elif "mistral" in url:
            return LLMProvider.MISTRAL
        elif "cohere" in url:
            return LLMProvider.COHERE
        else:
            raise ValueError(f"Cannot determine provider from URL: {url}")
