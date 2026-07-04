"""Azure AD authentication client."""
import httpx
import ssl
import logging
from typing import Optional, Union
from datetime import datetime, timedelta
from ..http_client_factory import HttpClientFactory
from ..retry_handler import CloudRetryHandler, with_enterprise_retry

logger = logging.getLogger(__name__)

class AzureAuthClient:
    """Azure AD authentication client for management API access."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        retry_handler: Optional[CloudRetryHandler] = None,
    ):
        """Initialize Azure AD authentication client using the shared HTTP client.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Service principal client ID
            client_secret: Service principal client secret
            retry_handler: Optional retry handler for resilient HTTP calls
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.retry_handler: Optional[CloudRetryHandler] = retry_handler
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        # Use the singleton shared HTTP client
        self._client = HttpClientFactory.get_client()

        logger.debug(f"AzureAuthClient initialized for tenant {tenant_id} (using shared HTTP client)")

    @with_enterprise_retry
    async def get_access_token(self) -> str:
        """Get valid access token for Azure Management API.

        Returns:
            str: Valid access token

        Raises:
            httpx.HTTPError: If authentication fails
        """
        # Check if current token is still valid
        if self._access_token and self._token_expiry:
            if datetime.utcnow() < self._token_expiry - timedelta(minutes=5):
                return self._access_token

        # Request new token
        await self._refresh_token()
        return self._access_token

    @with_enterprise_retry
    async def _refresh_token(self) -> None:
        """Refresh the access token from Azure AD.

        Raises:
            httpx.HTTPError: If token refresh fails
        """
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://management.azure.com/.default"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        logger.debug(f"Requesting Azure AD token from {url}")

        try:
            response = await self._client.post(url, data=payload, headers=headers)
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]

            # Calculate expiry time (subtract 5 minutes for safety)
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.debug("Azure AD token refreshed successfully")

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Azure AD token: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting Azure AD token: {str(e)}")
            raise

    async def close(self) -> None:
        """No-op: the shared HTTP client lifecycle is managed by HttpClientFactory."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit — no-op for shared client."""
        pass
