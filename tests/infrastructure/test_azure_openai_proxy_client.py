"""Tests for Azure OpenAI proxy client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client import AzureOpenAIProxyClient
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider


@pytest.fixture
def azure_client():
    """Create Azure OpenAI proxy client for testing."""
    return AzureOpenAIProxyClient(
        api_key="test-key",
        base_url="https://test.openai.azure.com",
        api_version="2024-06-01",
        provider=LLMProvider.AZURE
    )


@pytest.mark.asyncio
async def test_azure_openai_proxy_client_list_models_success(azure_client):
    """Test Azure OpenAI proxy client list_models method success."""
    # arrange
    mock_response_data = {
        "data": [
            {"id": "gpt-35-turbo", "object": "model"},
            {"id": "gpt-4", "object": "model"}
        ]
    }

    with patch.object(azure_client._client, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        # act
        result = await azure_client.list_models()

        # assert
        assert len(result) == 2
        assert result[0]["id"] == "gpt-35-turbo"
        assert result[1]["id"] == "gpt-4"
        mock_get.assert_called_once_with(
            url="https://test.openai.azure.com/openai/models?api-version=2024-06-01",
            headers={
                "api-key": "test-key",
                "Content-Type": "application/json",
                "User-Agent": "fastapi-openai-rag/1.0.0"
            },
            timeout=30.0
        )


@pytest.mark.asyncio
async def test_azure_openai_proxy_client_list_models_http_error(azure_client):
    """Test Azure OpenAI proxy client list_models method with HTTP error."""
    # arrange
    with patch.object(azure_client._client, 'get') as mock_get:
        mock_get.side_effect = httpx.HTTPError("API Error")

        # act & assert
        with pytest.raises(httpx.HTTPError):
            await azure_client.list_models()


@pytest.mark.asyncio
async def test_azure_openai_proxy_client_close():
    """Test Azure OpenAI proxy client close method."""
    # arrange
    client = AzureOpenAIProxyClient("test-key", "https://test.openai.azure.com", "2024-06-01", LLMProvider.AZURE)
    client._client = AsyncMock()

    # act
    await client.close()

    # assert
    client._client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_azure_openai_proxy_client_context_manager():
    """Test Azure OpenAI proxy client async context manager."""
    # arrange
    client = AzureOpenAIProxyClient("test-key", "https://test.openai.azure.com", "2024-06-01", LLMProvider.AZURE)
    client._client = AsyncMock()

    # act
    async with client as ctx_client:
        assert ctx_client is client

    # assert
    client._client.aclose.assert_called_once()
