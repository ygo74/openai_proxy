"""Standard OpenAI client implementation."""
from typing import Dict, Any, Optional

from ....domain.models.llm import LLMProvider
from .base_openai_client import BaseOpenAIClient
import logging
from ..retry_handler import CloudRetryHandler

logger = logging.getLogger(__name__)

class OpenAIClient(BaseOpenAIClient):
    """Standard OpenAI client for the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        retry_handler: Optional[CloudRetryHandler] = None,
    ) -> None:
        """Initialize OpenAI client with standard configuration.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the OpenAI API (default: https://api.openai.com/v1)
            retry_handler (Optional[CloudRetryHandler]): Retry handler for handling retries
        """
        # Provide default base URL if not specified
        if not base_url or base_url.strip() == "":
            base_url = "https://api.openai.com/v1"

        # Call parent constructor with standard OpenAI provider
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            provider=LLMProvider.OPENAI
        )

        self.retry_handler: Optional[CloudRetryHandler] = retry_handler

        logger.debug(f"OpenAIClient initialized at {base_url}")

    # Standard OpenAI doesn't require any overrides of BaseOpenAIClient methods
    # as the base implementations are already targeted for standard OpenAI API