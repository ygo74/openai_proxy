"""Enterprise configuration for LLM clients."""
import ssl
from typing import Optional, Union
from dataclasses import dataclass, field
import httpx
from .retry_handler import LLMRetryHandler


@dataclass
class EnterpriseConfig:
    """Configuration for enterprise features."""
    enable_retry: bool = True
    retry_handler: Optional[LLMRetryHandler] = None
    # Proxy configuration - None means auto-detect from environment
    proxy_url: Optional[str] = field(default=None)  # None = auto-detect, "" = no proxy
    proxy_auth: Optional[httpx.Auth] = None
    verify_ssl: Union[bool, str, ssl.SSLContext] = True
    ca_cert_file: Optional[str] = None
    client_cert_file: Optional[str] = None
    client_key_file: Optional[str] = None

    def should_auto_detect_proxy(self) -> bool:
        """Check if proxy should be auto-detected from environment variables.

        Returns:
            bool: True if should auto-detect proxy
        """
        # Auto-detect if proxy_url is None (default)
        # Don't auto-detect if proxy_url is explicitly set (even empty string)
        return self.proxy_url is None
