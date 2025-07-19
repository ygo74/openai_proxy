"""LLM service for handling model requests."""
import time
from typing import Dict, Any, Optional, Protocol
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ...domain.models.llm import LLMRequest, LLMResponse, LLMProvider, TokenUsage
from ...domain.models.model import Model, ModelStatus
from ...infrastructure.db.repositories.model_repository import SQLModelRepository
import logging

logger = logging.getLogger(__name__)

class LLMClientProtocol(Protocol):
    """Protocol for LLM client implementations."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from the LLM.

        Args:
            request (LLMRequest): Request parameters

        Returns:
            LLMResponse: Generated response with metadata
        """
        ...

class LLMService:
    """Service for handling LLM interactions."""

    def __init__(self, session: Session, llm_clients: Dict[LLMProvider, LLMClientProtocol]):
        """Initialize service.

        Args:
            session (Session): Database session
            llm_clients (Dict[LLMProvider, LLMClientProtocol]): LLM client implementations
        """
        self._session = session
        self._model_repository = SQLModelRepository(session)
        self._llm_clients = llm_clients
        logger.debug("LLMService initialized with repository and clients")

    async def generate(
        self,
        technical_name: str,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Generate text using specified model.

        Args:
            technical_name (str): Technical name of the model to use
            prompt (str): Input prompt
            max_tokens (Optional[int]): Maximum tokens in response
            temperature (Optional[float]): Sampling temperature
            additional_params (Optional[Dict[str, Any]]): Additional parameters

        Returns:
            LLMResponse: Generated response with metadata

        Raises:
            ValueError: If model not found or not approved
            RuntimeError: If provider client not configured
        """
        logger.info(f"Generating text using model {technical_name}")

        # Get model configuration
        model = self._model_repository.get_by_technical_name(technical_name)
        if not model:
            raise ValueError(f"Model {technical_name} not found")

        if model.status != ModelStatus.APPROVED:
            raise ValueError(f"Model {technical_name} is not approved for use")

        # Determine provider from model configuration
        provider = self._get_provider_from_url(model.url)
        client = self._llm_clients.get(provider)
        if not client:
            raise RuntimeError(f"No client configured for provider {provider}")

        # Prepare request
        request = LLMRequest(
            model=technical_name,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider,
            additional_params=additional_params or {}
        )

        # Measure request time
        start_time = time.time()
        try:
            response = await client.generate(request)
            logger.info(f"Successfully generated text with model {technical_name}")
            return response
        except Exception as e:
            logger.error(f"Error generating text with model {technical_name}: {str(e)}")
            raise
        finally:
            latency = (time.time() - start_time) * 1000
            logger.debug(f"Request completed in {latency:.2f}ms")

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
        else:
            raise ValueError(f"Cannot determine provider from URL: {url}")