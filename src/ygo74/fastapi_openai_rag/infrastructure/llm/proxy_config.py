"""Shared proxy and SSL configuration utilities for HTTP clients."""
import ssl
import os
import urllib.parse
import httpx
import logging
from typing import Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ProxySSLConfigBuilder:
    """Builder class for proxy and SSL configuration for enterprise environments."""

    @staticmethod
    def configure_proxy(proxy_url: Optional[str] = None,
                       proxy_auth: Optional[httpx.Auth] = None,
                       target_url: str = "") -> Optional[httpx.Proxy]:
        """Configure proxy settings from parameters or environment variables.

        Args:
            proxy_url (Optional[str]): Explicit proxy URL
            proxy_auth (Optional[httpx.Auth]): Explicit proxy authentication
            target_url (str): Target URL to check against no_proxy patterns

        Returns:
            Optional[httpx.Proxy]: Configured proxy or None
        """
        # If proxy URL is explicitly provided, use it
        if proxy_url:
            logger.debug(f"Using explicit proxy configuration: {proxy_url}")
            return httpx.Proxy(url=proxy_url, auth=proxy_auth)

        # Check environment variables for proxy configuration
        env_proxy = ProxySSLConfigBuilder._get_proxy_from_env(target_url)
        if env_proxy:
            return env_proxy

        return None

    @staticmethod
    def configure_ssl_context(verify_ssl: Union[bool, str, ssl.SSLContext] = True,
                             ca_cert_file: Optional[str] = None,
                             client_cert_file: Optional[str] = None,
                             client_key_file: Optional[str] = None) -> Optional[ssl.SSLContext]:
        """Configure SSL context for enterprise environments with custom certificates.

        Args:
            verify_ssl (Union[bool, str, ssl.SSLContext]): SSL verification setting
            ca_cert_file (Optional[str]): Path to CA certificate file
            client_cert_file (Optional[str]): Path to client certificate file
            client_key_file (Optional[str]): Path to client key file

        Returns:
            Optional[ssl.SSLContext]: Configured SSL context or None
        """
        # If SSL context is already provided, use it
        if isinstance(verify_ssl, ssl.SSLContext):
            return verify_ssl

        # If SSL verification is disabled, return None
        if verify_ssl is False:
            logger.warning("SSL verification is disabled - not recommended for production")
            return None

        # Create SSL context for enterprise environments
        if ca_cert_file or client_cert_file:
            try:
                # Create SSL context with secure defaults
                context = ssl.create_default_context()

                # Load custom CA certificates (common in enterprise environments with SSL interception)
                if ca_cert_file and Path(ca_cert_file).exists():
                    context.load_verify_locations(cafile=ca_cert_file)
                    logger.debug(f"Loaded custom CA certificates from: {ca_cert_file}")
                elif ca_cert_file:
                    logger.warning(f"CA certificate file not found: {ca_cert_file}")

                # Load client certificate for mutual TLS authentication
                if client_cert_file and client_key_file:
                    if Path(client_cert_file).exists() and Path(client_key_file).exists():
                        context.load_cert_chain(client_cert_file, client_key_file)
                        logger.debug(f"Loaded client certificate: {client_cert_file}")
                    else:
                        logger.warning(f"Client certificate or key file not found: {client_cert_file}, {client_key_file}")

                return context

            except Exception as e:
                logger.error(f"Failed to configure SSL context: {e}")
                # Fall back to default SSL verification
                return None

        return None

    @staticmethod
    def _get_proxy_from_env(target_url: str) -> Optional[httpx.Proxy]:
        """Get proxy configuration from environment variables.

        Args:
            target_url (str): Target URL to check against no_proxy patterns

        Returns:
            Optional[httpx.Proxy]: Configured proxy or None
        """
        # Check if target URL should bypass proxy
        if ProxySSLConfigBuilder._should_bypass_proxy(target_url):
            logger.debug("Target URL matches no_proxy pattern, bypassing proxy")
            return None

        # Determine which proxy to use based on target URL scheme
        target_scheme = urllib.parse.urlparse(target_url).scheme.lower()

        # Check for scheme-specific proxy first
        proxy_env_vars = []
        if target_scheme == 'https':
            proxy_env_vars = ['https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY']
        else:
            proxy_env_vars = ['http_proxy', 'HTTP_PROXY']

        for env_var in proxy_env_vars:
            proxy_url = os.environ.get(env_var)
            if proxy_url:
                logger.debug(f"Found proxy configuration in environment variable {env_var}: {proxy_url}")

                # Parse proxy URL and extract authentication if present
                proxy_auth = ProxySSLConfigBuilder._parse_proxy_auth(proxy_url)

                # Remove auth from URL if present (httpx handles it separately)
                clean_proxy_url = ProxySSLConfigBuilder._clean_proxy_url(proxy_url)

                return httpx.Proxy(url=clean_proxy_url, auth=proxy_auth)

        return None

    @staticmethod
    def _should_bypass_proxy(target_url: str) -> bool:
        """Check if target URL should bypass proxy based on no_proxy environment variable.

        Args:
            target_url (str): Target URL to check

        Returns:
            bool: True if proxy should be bypassed
        """
        no_proxy = os.environ.get('no_proxy') or os.environ.get('NO_PROXY')
        if not no_proxy:
            return False

        # Parse target hostname
        target_parsed = urllib.parse.urlparse(target_url)
        target_host = target_parsed.hostname
        if not target_host:
            return False

        # Check each no_proxy entry
        for no_proxy_entry in no_proxy.split(','):
            no_proxy_entry = no_proxy_entry.strip()
            if not no_proxy_entry:
                continue

            # Handle different no_proxy patterns
            if no_proxy_entry == '*':
                return True
            elif no_proxy_entry.startswith('.'):
                # Domain suffix match (e.g., .company.com)
                if target_host.endswith(no_proxy_entry[1:]):
                    return True
            elif no_proxy_entry == target_host:
                # Exact hostname match
                return True
            elif '/' in no_proxy_entry:
                # CIDR notation - simplified check for exact match
                if target_host == no_proxy_entry.split('/')[0]:
                    return True

        return False

    @staticmethod
    def _parse_proxy_auth(proxy_url: str) -> Optional[httpx.Auth]:
        """Parse authentication from proxy URL.

        Args:
            proxy_url (str): Proxy URL potentially containing authentication

        Returns:
            Optional[httpx.Auth]: Authentication object or None
        """
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            if parsed.username and parsed.password:
                logger.debug("Found proxy authentication in URL")
                return httpx.BasicAuth(username=parsed.username, password=parsed.password)
        except Exception as e:
            logger.warning(f"Failed to parse proxy authentication: {e}")

        return None

    @staticmethod
    def _clean_proxy_url(proxy_url: str) -> str:
        """Remove authentication from proxy URL.

        Args:
            proxy_url (str): Proxy URL potentially containing authentication

        Returns:
            str: Clean proxy URL without authentication
        """
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            if parsed.username or parsed.password:
                # Reconstruct URL without authentication
                clean_netloc = parsed.hostname
                if parsed.port:
                    clean_netloc = f"{clean_netloc}:{parsed.port}"

                clean_url = urllib.parse.urlunparse((
                    parsed.scheme,
                    clean_netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
                return clean_url
        except Exception as e:
            logger.warning(f"Failed to clean proxy URL: {e}")

        return proxy_url
