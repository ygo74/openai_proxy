"""Factory for creating LLM clients."""
import ssl
from typing import Dict, Optional, Union
from ...domain.models.llm import LLMProvider
from ...domain.models.llm_model import LlmModel, AzureLlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
from .openai_proxy_client import OpenAIProxyClient
from .azure_openai_proxy_client import AzureOpenAIProxyClient
from ...domain.models.configuration import AzureModelConfig, ModelConfig
from .azure_auth_client import AzureAuthClient
from .azure_management_client import AzureManagementClient
from .retry_handler import LLMRetryHandler
from .enterprise_config import EnterpriseConfig
import httpx
import logging

logger = logging.getLogger(__name__)

class LLMClientFactory:
    """Factory for creating appropriate LLM clients with enterprise features."""

    @staticmethod
    def create_client(
        model: Union[LlmModel, AzureLlmModel],
        api_key: str,
        model_config: Optional[Union[ModelConfig, AzureModelConfig]] = None,
        enterprise_config: Optional[EnterpriseConfig] = None
    ) -> LLMClientProtocol:
        """Create appropriate LLM client based on model configuration with enterprise features.

        Args:
            model (Union[LlmModel, AzureLlmModel]): Model configuration
            api_key (str): API key for authentication
            model_config (Optional[Union[ModelConfig, AzureModelConfig]]): Additional configuration
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration

        Returns:
            LLMClientProtocol: Configured client with enterprise features

        Raises:
            ValueError: If provider not supported or missing required configuration
        """
        # Use default enterprise config if none provided
        if enterprise_config is None:
            enterprise_config = EnterpriseConfig()

        provider = model.provider

        if provider == LLMProvider.AZURE:
            if not model.is_azure_model() or not model.api_version:
                raise ValueError("Azure provider requires AzureLlmModel with api_version")

            management_client = None

            # Create management client if Azure configuration is available
            if isinstance(model_config, AzureModelConfig):
                try:
                    auth_client = AzureAuthClient(
                        tenant_id=model_config.tenant_id,
                        client_id=model_config.client_id,
                        client_secret=model_config.client_secret
                    )

                    management_client = AzureManagementClient(
                        auth_client=auth_client,
                        subscription_id=model_config.subscription_id,
                        resource_group=model_config.resource_group,
                        account_name=model_config.resource_name
                    )
                    logger.debug("Azure Management client created for deployment listing")

                except Exception as e:
                    logger.warning(f"Failed to create Azure Management client: {e}")

            logger.debug(f"Creating Azure OpenAI proxy client for {provider} at {model.url} with API version {model.api_version}")
            return AzureOpenAIProxyClient(
                api_key=api_key,
                base_url=model.url,
                api_version=model.api_version,
                provider=provider,
                management_client=management_client,
                enterprise_config=enterprise_config
            )

        elif provider == LLMProvider.OPENAI:
            logger.debug(f"Creating OpenAI proxy client for {provider} at {model.url}")
            return OpenAIProxyClient(
                api_key=api_key,
                base_url=model.url,
                provider=provider,
                enterprise_config=enterprise_config
            )

        elif provider == LLMProvider.ANTHROPIC:
            # Would implement AnthropicClient here
            raise ValueError(f"Anthropic client not yet implemented")

        elif provider == LLMProvider.MISTRAL:
            # Would implement MistralClient here
            raise ValueError(f"Mistral client not yet implemented")

        else:
            raise ValueError(f"Unsupported provider for client creation: {provider}")

    @staticmethod
    def create_enterprise_client(
        model: Union[LlmModel, AzureLlmModel],
        api_key: str,
        model_config: Optional[Union[ModelConfig, AzureModelConfig]] = None,
        **enterprise_kwargs
    ) -> LLMClientProtocol:
        """Create LLM client with default enterprise settings.

        Args:
            model (Union[LlmModel, AzureLlmModel]): Model configuration
            api_key (str): API key for authentication
            model_config (Optional[Union[ModelConfig, AzureModelConfig]]): Additional configuration
            **enterprise_kwargs: Additional enterprise configuration parameters

        Returns:
            LLMClientProtocol: Configured client with enterprise defaults
        """
        # Create enterprise config with defaults
        enterprise_config = EnterpriseConfig(
            enable_retry=True,
            retry_handler=LLMRetryHandler(),
            verify_ssl=True,
            **enterprise_kwargs
        )

        return LLMClientFactory.create_client(
            model=model,
            api_key=api_key,
            model_config=model_config,
            enterprise_config=enterprise_config
        )
