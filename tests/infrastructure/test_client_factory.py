"""Tests for LLM client factory."""
import pytest
from unittest.mock import patch

from src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory import LLMClientFactory
from src.ygo74.fastapi_openai_rag.infrastructure.llm.openai_proxy_client import OpenAIProxyClient
from src.ygo74.fastapi_openai_rag.infrastructure.llm.azure_openai_proxy_client import AzureOpenAIProxyClient
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from src.ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, AzureLlmModel, LlmModelStatus
from datetime import datetime, timezone


def test_client_factory_create_openai_client():
    """Test client factory creates OpenAI client correctly."""
    # arrange
    model = LlmModel(
        url="https://api.openai.com/v1",
        name="GPT-4",
        technical_name="openai_gpt-4",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.APPROVED,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    api_key = "test-api-key"

    # act
    client = LLMClientFactory.create_client(model, api_key)

    # assert
    assert isinstance(client, OpenAIProxyClient)
    assert client.api_key == api_key
    assert client.base_url == "https://api.openai.com/v1"
    assert client.provider == LLMProvider.OPENAI


def test_client_factory_create_azure_client():
    """Test client factory creates Azure OpenAI client correctly."""
    # arrange
    model = AzureLlmModel(
        url="https://test.openai.azure.com",
        name="GPT-4",
        technical_name="azure_gpt-4",
        provider=LLMProvider.AZURE,
        api_version="2024-06-01",
        status=LlmModelStatus.APPROVED,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    api_key = "test-api-key"

    # act
    client = LLMClientFactory.create_client(model, api_key)

    # assert
    assert isinstance(client, AzureOpenAIProxyClient)
    assert client.api_key == api_key
    assert client.base_url == "https://test.openai.azure.com"
    assert client.provider == LLMProvider.AZURE
    assert client.api_version == "2024-06-01"


def test_client_factory_azure_without_azure_model():
    """Test client factory raises error for Azure provider without AzureLlmModel."""
    # arrange
    model = LlmModel(
        url="https://test.openai.azure.com",
        name="GPT-4",
        technical_name="azure_gpt-4",
        provider=LLMProvider.AZURE,
        status=LlmModelStatus.APPROVED,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    api_key = "test-api-key"

    # act & assert
    with pytest.raises(ValueError, match="Azure provider requires AzureLlmModel with api_version"):
        LLMClientFactory.create_client(model, api_key)


def test_client_factory_unsupported_provider():
    """Test client factory raises error for unsupported provider."""
    # arrange
    model = LlmModel(
        url="https://api.anthropic.com",
        name="Claude",
        technical_name="anthropic_claude",
        provider=LLMProvider.ANTHROPIC,
        status=LlmModelStatus.APPROVED,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    api_key = "test-api-key"

    # act & assert
    with pytest.raises(ValueError, match="Anthropic client not yet implemented"):
        LLMClientFactory.create_client(model, api_key)
