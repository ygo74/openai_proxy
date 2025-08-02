"""Tests for Azure OpenAI proxy client."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client import AzureOpenAIProxyClient
from src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory import EnterpriseConfig
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from src.ygo74.fastapi_openai_rag.domain.models.chat_completion import ChatCompletionRequest, ChatMessage
from src.ygo74.fastapi_openai_rag.domain.models.completion import CompletionRequest


class TestAzureOpenAIProxyClient:
    """Test AzureOpenAIProxyClient class."""

    def test_azure_openai_proxy_client_init_default_config(self):
        """Test Azure OpenAI proxy client initialization with default config."""
        # arrange & act
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # assert
        assert client.api_key == "test-key"
        assert client.base_url == "https://test.openai.azure.com"
        assert client.api_version == "2024-06-01"
        assert client.provider == LLMProvider.AZURE
        assert client.enterprise_config is not None
        assert client.enterprise_config.enable_retry is True

    def test_azure_openai_proxy_client_init_custom_config(self):
        """Test Azure OpenAI proxy client initialization with custom config."""
        # arrange
        enterprise_config = EnterpriseConfig(enable_retry=False)

        # act
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com/",  # with trailing slash
                api_version="2024-06-01",
                provider=LLMProvider.AZURE,
                enterprise_config=enterprise_config
            )

        # assert
        assert client.api_key == "test-key"
        assert client.base_url == "https://test.openai.azure.com"  # trailing slash removed
        assert client.api_version == "2024-06-01"
        assert client.provider == LLMProvider.AZURE
        assert client.enterprise_config.enable_retry is False

    def test_azure_openai_proxy_client_build_url(self):
        """Test URL building for Azure OpenAI API."""
        # arrange
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # act
        url = client._build_url("chat/completions", "gpt-4")

        # assert
        expected_url = "https://test.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2024-06-01"
        assert url == expected_url

    def test_azure_openai_proxy_client_get_headers(self):
        """Test headers generation for Azure OpenAI API."""
        # arrange
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # act
        headers = client._get_headers()

        # assert
        assert headers["api-key"] == "test-key"
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers

    def test_azure_openai_proxy_client_should_use_chat_completions(self):
        """Test model endpoint detection."""
        # arrange
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # act & assert
        assert client._should_use_chat_completions("gpt-4") is True
        assert client._should_use_chat_completions("gpt-35-turbo") is True
        assert client._should_use_chat_completions("text-davinci-003") is False

    def test_azure_openai_proxy_client_supports_capabilities(self):
        """Test model capability detection."""
        # arrange
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory'):
            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # act & assert
        assert client._supports_chat_completions("gpt-4") is True
        assert client._supports_completions("text-davinci-003") is True
        assert client._supports_embeddings("text-embedding-ada-002") is True

    @pytest.mark.asyncio
    async def test_azure_openai_proxy_client_close(self):
        """Test client cleanup."""
        # arrange
        mock_http_client = AsyncMock()

        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory') as mock_factory:
            mock_factory.create_async_client.return_value = mock_http_client

            client = AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            )

        # act
        await client.close()

        # assert
        mock_http_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_azure_openai_proxy_client_context_manager(self):
        """Test async context manager."""
        # arrange
        mock_http_client = AsyncMock()

        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client.HttpClientFactory') as mock_factory:
            mock_factory.create_async_client.return_value = mock_http_client

            # act
            async with AzureOpenAIProxyClient(
                api_key="test-key",
                base_url="https://test.openai.azure.com",
                api_version="2024-06-01"
            ) as client:
                assert client is not None

        # assert
        mock_http_client.aclose.assert_called_once()
