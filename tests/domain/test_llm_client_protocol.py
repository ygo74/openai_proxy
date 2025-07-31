"""Tests for LLM client protocol."""
import pytest
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from src.ygo74.fastapi_openai_rag.domain.protocols.llm_client import LLMClientProtocol
from src.ygo74.fastapi_openai_rag.domain.models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from src.ygo74.fastapi_openai_rag.domain.models.completion import CompletionRequest, CompletionResponse


class MockLLMClient:
    """Mock implementation of LLMClientProtocol for testing."""

    def __init__(self):
        self.closed = False
        self.chat_completion = AsyncMock(return_value=MagicMock(spec=ChatCompletionResponse))
        self.completion = AsyncMock(return_value=MagicMock(spec=CompletionResponse))
        self.list_models = AsyncMock(return_value=[{"id": "test-model", "object": "model"}])
        self.close = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


@pytest.mark.asyncio
async def test_llm_client_protocol_chat_completion():
    """Test LLM client protocol chat completion method."""
    # arrange
    client = MockLLMClient()
    request = MagicMock(spec=ChatCompletionRequest)

    # act
    result = await client.chat_completion(request)

    # assert
    assert result is not None
    client.chat_completion.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_llm_client_protocol_completion():
    """Test LLM client protocol completion method."""
    # arrange
    client = MockLLMClient()
    request = MagicMock(spec=CompletionRequest)

    # act
    result = await client.completion(request)

    # assert
    assert result is not None
    client.completion.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_llm_client_protocol_list_models():
    """Test LLM client protocol list_models method."""
    # arrange
    client = MockLLMClient()
    expected_models = [{"id": "test-model", "object": "model"}]

    # act
    result = await client.list_models()

    # assert
    assert result == expected_models
    client.list_models.assert_called_once()


@pytest.mark.asyncio
async def test_llm_client_protocol_close():
    """Test LLM client protocol close method."""
    # arrange
    client = MockLLMClient()

    # act
    await client.close()

    # assert
    client.close.assert_called_once()


@pytest.mark.asyncio
async def test_llm_client_protocol_context_manager():
    """Test LLM client protocol async context manager."""
    # arrange
    client = MockLLMClient()

    # act
    async with client as ctx_client:
        assert ctx_client is client

    # assert
    client.close.assert_called_once()
