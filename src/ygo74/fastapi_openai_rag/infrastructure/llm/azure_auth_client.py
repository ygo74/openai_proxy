"""Azure AD authentication client."""
import httpx
import ssl
import logging
from typing import Optional, Union
from datetime import datetime, timedelta
from .http_client_factory import HttpClientFactory
from .retry_handler import with_enterprise_retry

logger = logging.getLogger(__name__)

class AzureAuthClient:
    """Azure AD authentication client for management API access."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 proxy_url: Optional[str] = None,
                 proxy_auth: Optional[httpx.Auth] = None,
                 verify_ssl: Union[bool, str, ssl.SSLContext] = True,
                 ca_cert_file: Optional[str] = None,
                 client_cert_file: Optional[str] = None,
                 client_key_file: Optional[str] = None):
        """Initialize Azure AD authentication client.

        Args:
            tenant_id (str): Azure AD tenant ID
            client_id (str): Service principal client ID
            client_secret (str): Service principal client secret
            proxy_url (Optional[str]): Corporate proxy URL
            proxy_auth (Optional[httpx.Auth]): Proxy authentication
            verify_ssl (Union[bool, str, ssl.SSLContext]): SSL verification setting
            ca_cert_file (Optional[str]): Path to custom CA certificate file
            client_cert_file (Optional[str]): Path to client certificate file
            client_key_file (Optional[str]): Path to client private key file
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        # Target URL for proxy configuration
        target_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        # Create HTTP client using factory with enterprise settings
        self._client = HttpClientFactory.create_async_client(
            target_url=target_url,
            timeout=30.0,
            proxy_url=proxy_url,
            proxy_auth=proxy_auth,
            verify_ssl=verify_ssl,
            ca_cert_file=ca_cert_file,
            client_cert_file=client_cert_file,
            client_key_file=client_key_file
        )

        logger.debug(f"AzureAuthClient initialized for tenant {tenant_id}")

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
        """Close the HTTP client."""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
