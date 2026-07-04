"""Azure Management API client for deployment management."""
import httpx
import ssl
import logging
from typing import Dict, Any, List, Optional, Union, Type, cast
from types import TracebackType
from .azure_auth_client import AzureAuthClient
from ..http_client_factory import HttpClientFactory
from ..retry_handler import CloudRetryHandler, with_enterprise_retry

logger = logging.getLogger(__name__)

class AzureManagementClient:
    """Client for Azure Management API to manage Cognitive Services deployments."""

    def __init__(
        self,
        auth_client: "AzureAuthClient",
        subscription_id: str,
        resource_group: str,
        account_name: str,
        retry_handler: Optional[CloudRetryHandler] = None,
    ):
        """Initialize Azure Management client.

        Args:
            auth_client: Azure AD authentication client
            subscription_id: Azure subscription ID
            resource_group: Azure resource group name
            account_name: Azure OpenAI account name
            retry_handler: Optional retry handler for resilient HTTP calls
        """
        self.auth_client = auth_client
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.account_name = account_name
        self.retry_handler: Optional[CloudRetryHandler] = retry_handler

        # Use the singleton shared HTTP client
        self._client = HttpClientFactory.get_client()

        logger.debug(f"AzureManagementClient initialized for subscription {subscription_id} (using shared HTTP client)")

    @with_enterprise_retry
    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployments using Azure Management API.

        Returns:
            List[Dict[str, Any]]: List of deployments with deployment info

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Get access token (cast to str for typing clarity)
        access_token: str = cast(str, await self.auth_client.get_access_token())

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
            deployment_models: List[Dict[str, Any]] = []
            for deployment in deployments:
                properties: Dict[str, Any] = deployment.get("properties", {}) or {}
                model_info: Dict[str, Any] = properties.get("model", {}) or {}

                deployment_name: str = deployment.get("name", "")
                model_name: str = model_info.get("name", "")

                # Use Azure-provided capabilities directly instead of manual heuristic
                raw_capabilities: Dict[str, Any] = properties.get("capabilities", {}) or {}

                # Normalize capabilities if provided, else fallback to heuristic booleans
                if raw_capabilities:
                    def _as_bool(v: object) -> bool:
                        return v if isinstance(v, bool) else str(v).lower() == "true"

                    normalized: Dict[str, Any] = {}
                    for k, v in raw_capabilities.items():
                        # Numeric detection
                        if isinstance(v, str) and v.isdigit():
                            try:
                                normalized[k] = int(v)
                                continue
                            except ValueError:
                                pass
                        # Boolean-like
                        if isinstance(v, (str, bool)):
                            normalized[k] = _as_bool(v)
                        else:
                            normalized[k] = v
                    azure_capabilities: Dict[str, Any] = normalized

                deployment_model: Dict[str, Any] = {
                    "id": deployment_name,
                    "object": "model",
                    "model": model_name,
                    "deployment_id": deployment_name,
                    "deployment_status": properties.get("provisioningState", "Unknown"),
                    "model_version": model_info.get("version", ""),
                    "model_format": model_info.get("format", ""),
                    "sku": deployment.get("sku", {}),
                    "scale_settings": properties.get("scaleSettings", {}),
                    "created": deployment.get("systemData", {}).get("createdAt", ""),
                    "owned_by": "azure-openai",
                    "capabilities": azure_capabilities,
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

    async def close(self) -> None:
        """No-op: the shared HTTP client lifecycle is managed by HttpClientFactory."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> None:
        """Async context manager exit — no-op for shared client."""
        pass
