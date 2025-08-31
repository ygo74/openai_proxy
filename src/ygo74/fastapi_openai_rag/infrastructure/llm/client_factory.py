"""Factory for creating LLM clients."""
import ssl
from typing import Dict, Optional, Union
from ...domain.models.llm import LLMProvider
from ...domain.models.llm_model import LlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
from .openai_proxy_client import OpenAIProxyClient
from .azure_openai_proxy_client import AzureOpenAIProxyClient
from .unique_proxy_client import UniqueProxyClient
from ...domain.models.configuration import AzureModelConfig, ModelConfig, UniqueModelConfig
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
        model: LlmModel,
        model_config: Union[ModelConfig, AzureModelConfig, UniqueModelConfig],
        enterprise_config: Optional[EnterpriseConfig] = None
    ) -> LLMClientProtocol:
        """Create appropriate LLM client based on model configuration with enterprise features.

        Args:
            model (LlmModel): Model configuration
            model_config (Union[ModelConfig, AzureModelConfig, UniqueModelConfig]): Additional configuration from the config file
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
            if not model.is_azure_model() or not model_config.api_version or model_config.api_version.strip() == "":
                raise ValueError("Azure provider requires api_version")

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

            logger.debug(f"Creating Azure OpenAI proxy client for {provider} at {model.url} with API version {model_config.api_version}")
            return AzureOpenAIProxyClient(
                api_key=model_config.api_key,
                base_url=model.url,
                api_version=model_config.api_version,
                provider=provider,
                management_client=management_client,
                enterprise_config=enterprise_config
            )

        elif provider == LLMProvider.OPENAI:
            logger.debug(f"Creating OpenAI proxy client for {provider} at {model.url}")
            return OpenAIProxyClient(
                api_key=model_config.api_key,
                base_url=model.url,
                provider=provider,
                enterprise_config=enterprise_config
            )

        elif provider == LLMProvider.UNIQUE:
            # Validate that we have a UniqueModelConfig
            if not isinstance(model_config, UniqueModelConfig):
                raise ValueError("Unique provider requires UniqueModelConfig")

            if not model_config.company_id:
                raise ValueError("Unique provider requires company_id")

            logger.debug(f"Creating Unique proxy client for {provider} at {model.url}")
            return UniqueProxyClient(
                api_key=model_config.api_key,
                app_id=model_config.app_id,
                company_id=model_config.company_id,
                user_id=model_config.user_id,
                base_url=model.url or model_config.base_url,
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
