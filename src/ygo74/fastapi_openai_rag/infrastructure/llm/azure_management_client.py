"""Azure Management API client for deployment management."""
import httpx
import ssl
import logging
from typing import Dict, Any, List, Optional, Union
from .azure_auth_client import AzureAuthClient
from .http_client_factory import HttpClientFactory

logger = logging.getLogger(__name__)

class AzureManagementClient:
    """Client for Azure Management API to manage Cognitive Services deployments."""

    def __init__(self, auth_client: AzureAuthClient, subscription_id: str, resource_group: str, account_name: str,
                 proxy_url: Optional[str] = None,
                 proxy_auth: Optional[httpx.Auth] = None,
                 verify_ssl: Union[bool, str, ssl.SSLContext] = True,
                 ca_cert_file: Optional[str] = None,
                 client_cert_file: Optional[str] = None,
                 client_key_file: Optional[str] = None):
        """Initialize Azure Management client.

        Args:
            auth_client (AzureAuthClient): Authentication client
            subscription_id (str): Azure subscription ID
            resource_group (str): Resource group name
            account_name (str): Cognitive Services account name
            proxy_url (Optional[str]): Corporate proxy URL
            proxy_auth (Optional[httpx.Auth]): Proxy authentication
            verify_ssl (Union[bool, str, ssl.SSLContext]): SSL verification setting
            ca_cert_file (Optional[str]): Path to custom CA certificate file
            client_cert_file (Optional[str]): Path to client certificate file
            client_key_file (Optional[str]): Path to client private key file
        """
        self.auth_client = auth_client
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.account_name = account_name

        # Create HTTP client using factory with enterprise settings
        self._client = HttpClientFactory.create_async_client(
            target_url="https://management.azure.com",
            timeout=60.0,
            proxy_url=proxy_url,
            proxy_auth=proxy_auth,
            verify_ssl=verify_ssl,
            ca_cert_file=ca_cert_file,
            client_cert_file=client_cert_file,
            client_key_file=client_key_file
        )

        logger.debug(f"AzureManagementClient initialized for subscription {subscription_id}")

    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployments using Azure Management API.

        Returns:
            List[Dict[str, Any]]: List of deployments with deployment info

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Get access token
        access_token = await self.auth_client.get_access_token()

        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{self.account_name}"
            f"/deployments?api-version=2024-10-01"
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        logger.debug(f"Fetching Azure deployments from Management API: {url}")

        try:
            response = await self._client.get(url=url, headers=headers, timeout=30.0)
            response.raise_for_status()

            response_data = response.json()
            deployments = response_data.get("value", [])

            # Transform deployment data to match our expected format
            deployment_models = []
            for deployment in deployments:
                properties = deployment.get("properties", {})
                model_info = properties.get("model", {})

                deployment_name = deployment.get("name", "")
                model_name = model_info.get("name", "")

                deployment_model = {
                    "id": deployment_name,  # Use deployment name as ID (this is what you use in API calls)
                    "object": "model",
                    "model": model_name,  # Underlying model name
                    "deployment_id": deployment_name,
                    "deployment_status": properties.get("provisioningState", "Unknown"),
                    "model_version": model_info.get("version", ""),
                    "model_format": model_info.get("format", ""),
                    "sku": deployment.get("sku", {}),
                    "scale_settings": properties.get("scaleSettings", {}),
                    "created": deployment.get("systemData", {}).get("createdAt", ""),
                    "owned_by": "azure-openai",
                    "capabilities": {
                        "chat_completions": self._supports_chat_completions(model_name),
                        "completions": self._supports_completions(model_name),
                        "embeddings": self._supports_embeddings(model_name)
                    }
                }
                deployment_models.append(deployment_model)

            logger.debug(f"Found {len(deployment_models)} Azure deployments")
            return deployment_models

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Azure deployments: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Azure deployments: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching Azure deployments: {str(e)}")
            raise

    def _supports_chat_completions(self, model_name: str) -> bool:
        """Check if a model supports chat completions.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports chat completions
        """
        chat_models = ["gpt-4", "gpt-3.5-turbo", "gpt-35-turbo"]
        return any(chat_model in model_name.lower() for chat_model in chat_models)

    def _supports_completions(self, model_name: str) -> bool:
        """Check if a model supports text completions.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports completions
        """
        completion_models = [
            "text-davinci-003", "text-davinci-002", "text-curie-001",
            "text-babbage-001", "text-ada-001", "davinci-002", "babbage-002"
        ]
        return any(comp_model in model_name.lower() for comp_model in completion_models)

    def _supports_embeddings(self, model_name: str) -> bool:
        """Check if a model supports embeddings.

        Args:
            model_name (str): Model name

        Returns:
            bool: True if model supports embeddings
        """
        embedding_models = ["text-embedding", "ada-002"]
        return any(emb_model in model_name.lower() for emb_model in embedding_models)

    async def close(self) -> None:
        """Close the HTTP client."""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
