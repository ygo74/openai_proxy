"""Factory for creating LLM clients."""
from typing import Dict, Optional, Union
from ...domain.models.llm import LLMProvider
from ...domain.models.llm_model import LlmModel, AzureLlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
from .openai_proxy_client import OpenAIProxyClient
from .azure_openai_proxy_client import AzureOpenAIProxyClient
import logging

logger = logging.getLogger(__name__)

class LLMClientFactory:
    """Factory for creating appropriate LLM clients."""

    @staticmethod
    def create_client(model: Union[LlmModel, AzureLlmModel], api_key: str) -> LLMClientProtocol:
        """Create appropriate LLM client based on model configuration.

        Args:
            model (Union[LlmModel, AzureLlmModel]): Model configuration
            api_key (str): API key for authentication

        Returns:
            LLMClientProtocol: Configured client

        Raises:
            ValueError: If provider not supported or missing required configuration
        """
        provider = model.provider

        if provider == LLMProvider.AZURE:
            if not model.is_azure_model() or not model.api_version:
                raise ValueError("Azure provider requires AzureLlmModel with api_version")

            logger.debug(f"Creating Azure OpenAI proxy client for {provider} at {model.url} with API version {model.api_version}")
            return AzureOpenAIProxyClient(
                api_key=api_key,
                base_url=model.url,
                api_version=model.api_version,
                provider=provider
            )
        elif provider == LLMProvider.OPENAI:
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
