"""Factory for creating LLM clients."""
import ssl
from typing import Dict, Optional, Union
from ...domain.models.llm import LLMProvider
from ...domain.models.llm_model import LlmModel
from ...domain.protocols.llm_client import LLMClientProtocol
from .openai.openai_proxy_client import OpenAIClient
from .azure_openai.azure_openai_proxy_client import AzureOpenAIClient
from .unique.unique_proxy_client import UniqueProxyClient
from ...domain.models.configuration import AzureModelConfig, EnterpriseSettings, ModelConfig, UniqueModelConfig
from .azure_openai.azure_auth_client import AzureAuthClient
from .azure_openai.azure_management_client import AzureManagementClient
from .retry_handler import CloudRetryHandler, LLMRetryHandler
import logging

logger = logging.getLogger(__name__)

class LLMClientFactory:
    """Factory for creating appropriate LLM clients with enterprise features."""

    @staticmethod
    def _create_retry_handler(
        enterprise_settings: Optional[EnterpriseSettings],
    ) -> Optional[CloudRetryHandler]:
        """Create a retry handler if enterprise retry is enabled.

        Args:
            enterprise_settings: Enterprise configuration, may be None.

        Returns:
            A LLMRetryHandler instance when retry is enabled, None otherwise.
        """
        if (
            enterprise_settings is not None
            and getattr(enterprise_settings, "enable_retry", False)
        ):
            logger.debug("Enterprise retry enabled — creating LLMRetryHandler")
            retry_kwargs: Dict[str, Union[int, float]] = {}
            if enterprise_settings.retry_max_attempts is not None:
                retry_kwargs["max_attempts"] = enterprise_settings.retry_max_attempts
            if enterprise_settings.retry_base_delay is not None:
                retry_kwargs["base_delay"] = enterprise_settings.retry_base_delay
            if enterprise_settings.retry_max_delay is not None:
                retry_kwargs["max_delay"] = enterprise_settings.retry_max_delay
            return LLMRetryHandler(**retry_kwargs)
        return None

    @staticmethod
    def create_client(
        model: LlmModel,
        model_config: Union[ModelConfig, AzureModelConfig, UniqueModelConfig],
        enterprise_settings: Optional[EnterpriseSettings] = None,
    ) -> LLMClientProtocol:
        """Create appropriate LLM client based on model configuration.

        All clients use the shared httpx.AsyncClient from HttpClientFactory
        (initialized at application startup with enterprise proxy/SSL settings).

        Args:
            model: Model configuration
            model_config: Additional configuration from the config file
            enterprise_settings: Optional enterprise settings for retry/proxy/SSL

        Returns:
            Configured client implementing LLMClientProtocol

        Raises:
            ValueError: If provider not supported or missing required configuration
        """
        provider = model.provider
        retry_handler: Optional[CloudRetryHandler] = LLMClientFactory._create_retry_handler(
            enterprise_settings
        )

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
                        client_secret=model_config.client_secret,
                        retry_handler=retry_handler,
                    )

                    management_client = AzureManagementClient(
                        auth_client=auth_client,
                        subscription_id=model_config.subscription_id,
                        resource_group=model_config.resource_group,
                        account_name=model_config.resource_name,
                        retry_handler=retry_handler,
                    )
                    logger.debug("Azure Management client created for deployment listing")

                except Exception as e:
                    logger.warning(f"Failed to create Azure Management client: {e}")

            logger.debug(f"Creating Azure OpenAI proxy client for {provider} at {model.url} with API version {model_config.api_version}")
            return AzureOpenAIClient(
                api_key=model_config.api_key,
                base_url=model.url,
                api_version=model_config.api_version,
                management_client=management_client,
                retry_handler=retry_handler,
            )

        elif provider == LLMProvider.OPENAI:
            logger.debug(f"Creating OpenAI proxy client for {provider} at {model.url}")
            return OpenAIClient(
                api_key=model_config.api_key,
                base_url=model.url,
                retry_handler=retry_handler,
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
                retry_handler=retry_handler,
            )

        elif provider == LLMProvider.ANTHROPIC:
            raise ValueError(f"Anthropic client not yet implemented")

        elif provider == LLMProvider.MISTRAL:
            raise ValueError(f"Mistral client not yet implemented")

        else:
            raise ValueError(f"Unsupported provider for client creation: {provider}")
