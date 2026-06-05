"""Authentication context for API client."""
import os
import json
import time
from typing import Optional, Dict, Any, cast
import logging
import requests
from requests.auth import AuthBase
from pathlib import Path
from datetime import datetime, timedelta
import keyring
import base64
import hashlib
import urllib.parse
from knack.log import get_logger
from .exceptions import AIGatewayClientError

logger = get_logger(__name__)

# # import requests
# # try:
# #     from requests_kerberos import HTTPKerberosAuth, OPTIONAL
# #     HAS_LINUX_KERBEROS = True
# # except ImportError:
# #     HAS_LINUX_KERBEROS = False
# HAS_LINUX_KERBEROS = False

# try:
#     from requests_negotiate_sspi import HttpNegotiateAuth
#     HAS_WINDOWS_KERBEROS = True
# except ImportError:
#     HAS_WINDOWS_KERBEROS = False

# HAS_KERBEROS = HAS_LINUX_KERBEROS or HAS_WINDOWS_KERBEROS

import urllib3


def _create_kerberos_auth() -> AuthBase:
    """Detect and return the appropriate Kerberos auth handler.

    Tries ``requests_negotiate_sspi`` (Windows) first, then
    ``requests_kerberos`` (Linux). Raises if neither is installed.

    Returns:
        A Kerberos auth handler compatible with ``requests.Session``.

    Raises:
        AIToolkitConfigError: If no Kerberos library is available.
    """
    try:
        from requests_negotiate_sspi import HttpNegotiateAuth  # noqa: PLC0415

        logger.debug("Using requests-negotiate-sspi (Windows SSPI)")
        return cast("AuthBase", HttpNegotiateAuth())
    except ImportError:
        pass

    try:
        from requests_kerberos import OPTIONAL, HTTPKerberosAuth  # noqa: PLC0415

        logger.debug("Using requests-kerberos (Linux/MIT Kerberos)")
        return cast("AuthBase", HTTPKerberosAuth(mutual_authentication=OPTIONAL))
    except ImportError:
        pass

    raise AIGatewayClientError(
        "No Kerberos authentication library found. Install one of:\n"
        "  - Linux:   pip install ubp-genai-hub-ai-toolkit[kerberos]\n"
        "  - Windows: pip install ubp-genai-hub-ai-toolkit[kerberos-win]\n"
        "On Linux, also ensure MIT Kerberos is installed and run 'kinit' "
        "to obtain a ticket.\n"
        "On Windows, verify you are logged into your Active Directory domain."
    )



session = requests.Session()
session.verify = True
# if HAS_KERBEROS:
#     if HAS_LINUX_KERBEROS:
#         session.auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)
#     else:
#         session.auth = HttpNegotiateAuth()

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
                "keycloak_url": "http://localhost:8080/realms/fastapi-openai-rag",
                "client_id": "fastapi-app",
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

    @staticmethod
    def _urlsafe_b64encode_no_padding(data: bytes) -> str:
        """Encode bytes to base64 URL-safe format without padding.

        Args:
            data: Bytes to encode

        Returns:
            str: Base64 URL-safe encoded string without padding
        """
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate PKCE code verifier.

        Returns:
            str: Random 32-byte code verifier encoded in base64 URL-safe format
        """
        random_bytes = os.urandom(32)
        return AuthContext._urlsafe_b64encode_no_padding(random_bytes)

    @staticmethod
    def _generate_code_challenge(code_verifier: str) -> str:
        """Generate PKCE code challenge from verifier.

        Args:
            code_verifier: Code verifier string

        Returns:
            str: SHA256 hash of verifier encoded in base64 URL-safe format
        """
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return AuthContext._urlsafe_b64encode_no_padding(digest)

    def _get_auth_code_with_kerberos(self, auth_url: str) -> str:
        """Obtain authorization code using Kerberos/SPNEGO authentication.

        This method performs a Kerberos-authenticated request to the authorization endpoint.
        The server redirects to the redirect_uri with the authorization code.

        Args:
            auth_url: Authorization URL with PKCE parameters

        Returns:
            str: Authorization code

        Raises:
            RuntimeError: If authentication fails or code cannot be extracted
        """
        # Kerberos configuration
        session.auth = _create_kerberos_auth()

        # Perform Kerberos authentication without following redirects
        resp = session.get(auth_url, allow_redirects=False, verify=True)

        # Check for redirect response
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                raise RuntimeError("Redirect response missing Location header")

            # Extract authorization code from redirect URL
            parsed = urllib.parse.urlparse(location)
            qs = urllib.parse.parse_qs(parsed.query)
            code_values = qs.get("code")

            if not code_values:
                raise RuntimeError(f"Authorization code not found in redirect URL: {location}")

            return code_values[0]
        else:
            raise RuntimeError(
                f"Unexpected response status {resp.status_code}. "
                f"Expected redirect with authorization code. Body: {resp.text[:500]}"
            )

    def _exchange_code_for_token(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code obtained from Kerberos flow
            code_verifier: PKCE code verifier

        Returns:
            dict: Token response containing access_token, refresh_token, expires_in

        Raises:
            RuntimeError: If token exchange fails
        """
        keycloak_url = self.config["keycloak_url"]
        token_url = f"{keycloak_url}/protocol/openid-connect/token"
        client_id = self.config["client_id"]
        client_secret = self.config.get("client_secret")

        # Construct redirect URI (should match the one used in auth request)
        redirect_uri = self.config.get("redirect_uri", "urn:ietf:wg:oauth:2.0:oob")

        data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        }

        if client_secret:
            data["client_secret"] = client_secret

        try:
            resp = session.post(token_url, data=data, verify=True)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text}") from e

    def login_with_kerberos(self) -> bool:
        """Authenticate using Kerberos/SPNEGO with PKCE flow.

        This method requires:
        - User to have obtained Kerberos ticket (via kinit)
        - requests-kerberos package installed
        - Keycloak configured for SPNEGO/Kerberos authentication

        Returns:
            bool: True if authentication was successful
        """

        try:
            # 1) Generate PKCE parameters
            code_verifier = self._generate_code_verifier()
            code_challenge = self._generate_code_challenge(code_verifier)

            # 2) Build authorization URL with PKCE
            keycloak_url = self.config["keycloak_url"]
            auth_url = f"{keycloak_url}/protocol/openid-connect/auth"

            redirect_uri = self.config.get("redirect_uri", "urn:ietf:wg:oauth:2.0:oob")

            auth_params = {
                "client_id": self.config["client_id"],
                "response_type": "code",
                "scope": "openid",
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            auth_url = f"{auth_url}?{urllib.parse.urlencode(auth_params)}"

            logger.info("Attempting Kerberos authentication...")
            logger.debug(f"Url: {auth_url}")

            # 3) Obtain authorization code via Kerberos
            code = self._get_auth_code_with_kerberos(auth_url)
            logger.debug(f"Obtained authorization code: {code[:10]}...")

            # 4) Exchange code for tokens
            token_data = self._exchange_code_for_token(code, code_verifier)

            # 5) Add expiry timestamp
            token_data["expires_at"] = time.time() + token_data["expires_in"]

            # 6) Cache the token
            self.token_cache = token_data
            self._save_token_cache()

            logger.info("Successfully authenticated with Kerberos")
            return True

        except Exception as e:
            logger.error(f"Kerberos authentication failed: {e}")
            return False

    def login_interactive(self, username: Optional[str], password: Optional[str]) -> bool:
        """Authenticate with username and password using OAuth2.

        Args:
            username: Keycloak username
            password: Keycloak password

        Returns:
            bool: True if authentication was successful
        """
        # If no credentials provided, try Kerberos/PKCE flow
        if not username and not password:
            return self.login_with_kerberos()

        # Perform OAuth2 password grant flow
        keycloak_url = self.config["keycloak_url"]
        token_url = f"{keycloak_url}/protocol/openid-connect/token"
        auth_url = f"{keycloak_url}/protocol/openid-connect/auth"
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
            response = session.post(token_url, data=data)
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

        keycloak_url = self.config["keycloak_url"]
        token_url = f"{keycloak_url}/protocol/openid-connect/token"
        client_id = self.config["client_id"]
        client_secret = self.config.get("client_secret", None)

        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token
        }

        # Add client secret if configured
        if client_secret:
            data["client_secret"] = client_secret

        try:
            response = session.post(token_url, data=data)
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
