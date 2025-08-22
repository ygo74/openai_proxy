"""Authentication context for API client."""
import os
import json
import time
from typing import Optional, Dict, Any
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
import keyring

logger = logging.getLogger(__name__)

# Constants for token cache and config
CONFIG_DIR = Path.home() / ".rag-client"
TOKEN_CACHE_FILE = CONFIG_DIR / "token_cache.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

class AuthContext:
    """Authentication context for API client.

    Handles authentication with both API keys and OAuth2/Keycloak.
    Caches tokens and handles token refresh.
    """

    def __init__(self, cli_ctx=None):
        """Initialize authentication context.

        Args:
            cli_ctx: CLI context from knack
        """
        self.cli_ctx = cli_ctx
        self._ensure_config_dir()
        self.config = self._load_config()
        self.token_cache = self._load_token_cache()
        self._api_key = None

    def _ensure_config_dir(self):
        """Ensure the config directory exists."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            # Create default config
            default_config = {
                "api_url": "http://localhost:8000",
                "keycloak_url": "http://localhost:8080/realms/rag-proxy/protocol/openid-connect/token",
                "client_id": "fastapi-client",
                "client_secret": ""
            }

            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=2)

            return default_config

        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)

    def _load_token_cache(self) -> Dict[str, Any]:
        """Load token cache from file."""
        if not TOKEN_CACHE_FILE.exists():
            return {}

        try:
            with open(TOKEN_CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_token_cache(self):
        """Save token cache to file."""
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(self.token_cache, f)

    def set_api_key(self, api_key: str):
        """Set API key for authentication."""
        self._api_key = api_key
        # Store in keyring for added security
        keyring.set_password("rag-client", "api-key", api_key)

    def get_api_key(self) -> Optional[str]:
        """Get API key from memory or keyring."""
        if self._api_key:
            return self._api_key

        try:
            return keyring.get_password("rag-client", "api-key")
        except Exception:
            return None

    def login_interactive(self, username: str, password: str) -> bool:
        """Authenticate with username and password using OAuth2.

        Args:
            username: Keycloak username
            password: Keycloak password

        Returns:
            bool: True if authentication was successful
        """
        # Perform OAuth2 password grant flow
        token_url = self.config["keycloak_url"]
        client_id = self.config["client_id"]
        client_secret = self.config["client_secret"]

        data = {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password
        }

        # Add client secret if configured
        if client_secret:
            data["client_secret"] = client_secret

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            # Add expiry timestamp
            token_data["expires_at"] = time.time() + token_data["expires_in"]

            # Cache the token
            self.token_cache = token_data
            self._save_token_cache()

            logger.info(f"Successfully authenticated as {username}")
            return True

        except requests.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """Get valid access token, refreshing if necessary.

        Returns:
            str: Valid access token or None if no token available
        """
        # Check if we have a cached token
        if not self.token_cache:
            return None

        # Check if token is expired or about to expire (within 30 seconds)
        if time.time() > (self.token_cache.get("expires_at", 0) - 30):
            # Try to refresh the token
            if not self._refresh_token():
                return None

        return self.token_cache.get("access_token")

    def _refresh_token(self) -> bool:
        """Refresh access token using refresh token.

        Returns:
            bool: True if token was successfully refreshed
        """
        refresh_token = self.token_cache.get("refresh_token")
        if not refresh_token:
            logger.warning("No refresh token available")
            return False

        token_url = self.config["keycloak_url"]
        client_id = self.config["client_id"]
        client_secret = self.config["client_secret"]

        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token
        }

        # Add client secret if configured
        if client_secret:
            data["client_secret"] = client_secret

        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            # Add expiry timestamp
            token_data["expires_at"] = time.time() + token_data["expires_in"]

            # Update token cache
            self.token_cache = token_data
            self._save_token_cache()

            logger.info("Successfully refreshed access token")
            return True

        except requests.RequestException as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    def logout(self):
        """Clear authentication data."""
        self.token_cache = {}
        self._api_key = None
        self._save_token_cache()

        try:
            keyring.delete_password("rag-client", "api-key")
        except Exception:
            pass

        logger.info("Successfully logged out")

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests.

        Prioritizes API key over OAuth token.

        Returns:
            dict: Authorization headers
        """
        api_key = self.get_api_key()
        if api_key:
            if api_key.startswith("sk-"):
                return {"Authorization": api_key}
            else:
                return {"Authorization": f"Bearer {api_key}"}

        token = self.get_token()
        if token:
            return {"Authorization": f"Bearer {token}"}

        return {}

    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return bool(self.get_api_key() or self.get_token())

    def get_api_url(self) -> str:
        """Get base API URL."""
        return self.config["api_url"].rstrip("/")
