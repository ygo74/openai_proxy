"""Tests for OpenAI proxy client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.ygo74.fastapi_openai_rag.infrastructure.llm.openai_proxy_client import OpenAIProxyClient
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider


@pytest.fixture
def openai_client():
    """Create OpenAI proxy client for testing."""
    return OpenAIProxyClient(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        provider=LLMProvider.OPENAI
    )


@pytest.mark.asyncio
async def test_openai_proxy_client_list_models_success(openai_client):
    """Test OpenAI proxy client list_models method success."""
    # arrange
    mock_response_data = {
        "data": [
            {"id": "gpt-3.5-turbo", "object": "model"},
            {"id": "gpt-4", "object": "model"}
        ]
    }

    with patch.object(openai_client._client, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        # act
        result = await openai_client.list_models()

        # assert
        assert len(result) == 2
        assert result[0]["id"] == "gpt-3.5-turbo"
        assert result[1]["id"] == "gpt-4"
        mock_get.assert_called_once_with(
            url="https://api.openai.com/v1/models",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
                "User-Agent": "fastapi-openai-rag/1.0.0"
            },
            timeout=30.0
        )


@pytest.mark.asyncio
async def test_openai_proxy_client_list_models_http_error(openai_client):
    """Test OpenAI proxy client list_models method with HTTP error."""
    # arrange
    with patch.object(openai_client._client, 'get') as mock_get:
        mock_get.side_effect = httpx.HTTPError("API Error")

        # act & assert
        with pytest.raises(httpx.HTTPError):
            await openai_client.list_models()


@pytest.mark.asyncio
async def test_openai_proxy_client_close():
    """Test OpenAI proxy client close method."""
    # arrange
    client = OpenAIProxyClient("test-key", "https://api.openai.com/v1", LLMProvider.OPENAI)
    client._client = AsyncMock()

    # act
    await client.close()

    # assert
    client._client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_openai_proxy_client_context_manager():
    """Test OpenAI proxy client async context manager."""
    # arrange
    client = OpenAIProxyClient("test-key", "https://api.openai.com/v1", LLMProvider.OPENAI)
    client._client = AsyncMock()

    # act
    async with client as ctx_client:
        assert ctx_client is client

    # assert
    client._client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_openai_proxy_client_close_without_client():
    """Test OpenAI proxy client close method when _client is None."""
    # arrange
    client = OpenAIProxyClient("test-key", "https://api.openai.com/v1", LLMProvider.OPENAI)
    client._client = None

    # act (should not raise exception)
    await client.close()

    # assert - no exception raised
    assert True
