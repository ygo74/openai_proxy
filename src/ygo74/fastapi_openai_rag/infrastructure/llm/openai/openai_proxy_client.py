"""Standard OpenAI client implementation."""
from typing import Dict, Any, Optional

from ....domain.models.llm import LLMProvider
from .base_openai_client import BaseOpenAIClient
from ..enterprise_config import EnterpriseConfig
import logging

logger = logging.getLogger(__name__)

class OpenAIClient(BaseOpenAIClient):
    """Standard OpenAI client for the OpenAI API."""

    def __init__(self, api_key: str, base_url: str,
                 enterprise_config: Optional[EnterpriseConfig] = None):
        """Initialize OpenAI client with standard configuration.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the OpenAI API (default: https://api.openai.com/v1)
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration
        """
        # Provide default base URL if not specified
        if not base_url or base_url.strip() == "":
            base_url = "https://api.openai.com/v1"

        # Call parent constructor with standard OpenAI provider
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            provider=LLMProvider.OPENAI,
            enterprise_config=enterprise_config
        )

        logger.debug(f"OpenAIClient initialized at {base_url}")

    # Standard OpenAI doesn't require any overrides of BaseOpenAIClient methods
    # as the base implementations are already targeted for standard OpenAI API