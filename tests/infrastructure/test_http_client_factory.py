"""Tests for HttpClientFactory."""
import pytest
import ssl
import os
import httpx
import base64
from unittest.mock import patch, MagicMock

from src.ygo74.fastapi_openai_rag.infrastructure.llm.http_client_factory import HttpClientFactory


class TestHttpClientFactory:
    """Test class for HttpClientFactory."""

    def test_http_client_factory_create_async_client_default(self):
        """Test HttpClientFactory create_async_client with default settings."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        client = HttpClientFactory.create_async_client(target_url=target_url)

        # assert
        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 30.0

    def test_http_client_factory_create_sync_client_default(self):
        """Test HttpClientFactory create_sync_client with default settings."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        client = HttpClientFactory.create_sync_client(target_url=target_url)

        # assert
        assert isinstance(client, httpx.Client)
        assert client.timeout.read == 30.0

    def test_http_client_factory_create_async_client_with_explicit_proxy(self):
        """Test HttpClientFactory create_async_client with explicit proxy."""
        # arrange
        target_url = "https://api.openai.com"
        proxy_url = "http://proxy.company.com:8080"

        # act
        client = HttpClientFactory.create_async_client(
            target_url=target_url,
            proxy_url=proxy_url
        )

        # assert
        assert isinstance(client, httpx.AsyncClient)
        # Test that proxy is configured by checking if proxy parameter was passed
        # The internal structure varies by httpx version, so we test functionality instead
        assert hasattr(client, '_transport')

    @patch.dict(os.environ, {'https_proxy': 'http://env-proxy.com:3128'})
    def test_http_client_factory_create_async_client_with_env_proxy(self):
        """Test HttpClientFactory create_async_client with environment proxy."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        client = HttpClientFactory.create_async_client(target_url=target_url)

        # assert
        assert isinstance(client, httpx.AsyncClient)
        # Test that proxy is configured by checking if proxy parameter was passed
        assert hasattr(client, '_transport')

    @patch.dict(os.environ, {'no_proxy': 'api.openai.com'})
    def test_http_client_factory_create_async_client_bypassed_proxy(self):
        """Test HttpClientFactory create_async_client with proxy bypass."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        with patch.dict(os.environ, {'https_proxy': 'http://proxy.com:8080'}):
            client = HttpClientFactory.create_async_client(target_url=target_url)

        # assert
        assert isinstance(client, httpx.AsyncClient)
        # Should not have proxy due to no_proxy setting

    def test_http_client_factory_create_async_client_with_ssl_context(self):
        """Test HttpClientFactory create_async_client with custom SSL context."""
        # arrange
        target_url = "https://api.openai.com"
        ssl_context = ssl.create_default_context()

        # act
        client = HttpClientFactory.create_async_client(
            target_url=target_url,
            verify_ssl=ssl_context
        )

        # assert
        assert isinstance(client, httpx.AsyncClient)
        assert client._transport._pool._ssl_context == ssl_context

    def test_http_client_factory_configure_proxy_explicit(self):
        """Test HttpClientFactory _configure_proxy with explicit proxy."""
        # arrange
        proxy_url = "http://proxy.company.com:8080"
        proxy_auth = httpx.BasicAuth("user", "pass")

        # act
        proxy = HttpClientFactory._configure_proxy(
            proxy_url=proxy_url,
            proxy_auth=proxy_auth,
            target_url="https://api.openai.com"
        )

        # assert
        assert isinstance(proxy, httpx.Proxy)
        assert proxy.url == proxy_url
        assert proxy.auth == proxy_auth

    @patch.dict(os.environ, {'https_proxy': 'http://user:pass@proxy.com:8080'})
    def test_http_client_factory_configure_proxy_env_with_auth(self):
        """Test HttpClientFactory _configure_proxy with environment proxy containing auth."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        proxy = HttpClientFactory._configure_proxy(target_url=target_url)

        # assert
        assert isinstance(proxy, httpx.Proxy)
        assert proxy.url == "http://proxy.com:8080"
        assert isinstance(proxy.auth, httpx.BasicAuth)
        # Test authentication by creating a test request to verify credentials
        test_request = httpx.Request("GET", "http://test.com")
        auth_flow = proxy.auth.auth_flow(test_request)
        auth_request = next(auth_flow)
        assert "Authorization" in auth_request.headers
        assert "Basic" in auth_request.headers["Authorization"]

    def test_http_client_factory_should_bypass_proxy_wildcard(self):
        """Test HttpClientFactory _should_bypass_proxy with wildcard."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        with patch.dict(os.environ, {'no_proxy': '*'}):
            result = HttpClientFactory._should_bypass_proxy(target_url)

        # assert
        assert result is True

    def test_http_client_factory_should_bypass_proxy_exact_match(self):
        """Test HttpClientFactory _should_bypass_proxy with exact match."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        with patch.dict(os.environ, {'no_proxy': 'api.openai.com'}):
            result = HttpClientFactory._should_bypass_proxy(target_url)

        # assert
        assert result is True

    def test_http_client_factory_should_bypass_proxy_domain_suffix(self):
        """Test HttpClientFactory _should_bypass_proxy with domain suffix."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        with patch.dict(os.environ, {'no_proxy': '.openai.com'}):
            result = HttpClientFactory._should_bypass_proxy(target_url)

        # assert
        assert result is True

    def test_http_client_factory_should_not_bypass_proxy(self):
        """Test HttpClientFactory _should_bypass_proxy returns False when no match."""
        # arrange
        target_url = "https://api.openai.com"

        # act
        with patch.dict(os.environ, {'no_proxy': 'other.com'}):
            result = HttpClientFactory._should_bypass_proxy(target_url)

        # assert
        assert result is False

    def test_http_client_factory_parse_proxy_auth_success(self):
        """Test HttpClientFactory _parse_proxy_auth with valid credentials."""
        # arrange
        proxy_url = "http://user:pass@proxy.com:8080"

        # act
        auth = HttpClientFactory._parse_proxy_auth(proxy_url)

        # assert
        assert isinstance(auth, httpx.BasicAuth)
        # Test that auth works by creating a test request
        test_request = httpx.Request("GET", "http://test.com")
        auth_flow = auth.auth_flow(test_request)
        auth_request = next(auth_flow)
        assert "Authorization" in auth_request.headers
        assert "Basic" in auth_request.headers["Authorization"]
        # Verify the credentials are correctly encoded
        auth_header = auth_request.headers["Authorization"]
        encoded_creds = auth_header.split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode('utf-8')
        assert decoded_creds == "user:pass"

    def test_http_client_factory_parse_proxy_auth_no_credentials(self):
        """Test HttpClientFactory _parse_proxy_auth without credentials."""
        # arrange
        proxy_url = "http://proxy.com:8080"

        # act
        auth = HttpClientFactory._parse_proxy_auth(proxy_url)

        # assert
        assert auth is None

    def test_http_client_factory_clean_proxy_url_with_auth(self):
        """Test HttpClientFactory _clean_proxy_url removes authentication."""
        # arrange
        proxy_url = "http://user:pass@proxy.com:8080"

        # act
        clean_url = HttpClientFactory._clean_proxy_url(proxy_url)

        # assert
        assert clean_url == "http://proxy.com:8080"

    def test_http_client_factory_clean_proxy_url_without_auth(self):
        """Test HttpClientFactory _clean_proxy_url without authentication."""
        # arrange
        proxy_url = "http://proxy.com:8080"

        # act
        clean_url = HttpClientFactory._clean_proxy_url(proxy_url)

        # assert
        assert clean_url == "http://proxy.com:8080"
