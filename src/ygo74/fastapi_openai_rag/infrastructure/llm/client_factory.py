"""Factory for creating LLM clients."""
from typing import Dict, Optional
from ...domain.models.llm import LLMProvider
from ...domain.models.llm_model import LlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
from .openai_proxy_client import OpenAIProxyClient
import logging

logger = logging.getLogger(__name__)

class LLMClientFactory:
    """Factory for creating appropriate LLM clients."""

    @staticmethod
    def create_client(model: LlmModel, api_key: str) -> LLMClientProtocol:
        """Create appropriate LLM client based on model configuration.

        Args:
            model (Model): Model configuration
            api_key (str): API key for authentication

        Returns:
            LLMClientProtocol: Configured client

        Raises:
            ValueError: If provider not supported
        """
        provider = model.provider

        if provider in [LLMProvider.OPENAI, LLMProvider.AZURE]:
            logger.debug(f"Creating OpenAI proxy client for {provider} at {model.url}")
            return OpenAIProxyClient(
                api_key=api_key,
                base_url=model.url,
                provider=provider
            )
        elif provider == LLMProvider.ANTHROPIC:
            # Would implement AnthropicClient here
            raise ValueError(f"Anthropic client not yet implemented")
        elif provider == LLMProvider.MISTRAL:
            # Would implement MistralClient here
            raise ValueError(f"Mistral client not yet implemented")
        else:
            raise ValueError(f"Unsupported provider for client creation: {provider}")
