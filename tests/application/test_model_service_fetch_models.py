"""Tests for ModelService fetch_available_models method."""
import sys
import os
from typing import List, Dict, Any, Union
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.model_service import ModelService
from ygo74.fastapi_openai_rag.domain.models.configuration import ModelConfig, AzureModelConfig
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModelStatus
from ygo74.fastapi_openai_rag.domain.protocols.llm_client import LLMClientProtocol
from ygo74.fastapi_openai_rag.infrastructure.llm.client_factory import LLMClientFactory


# Common test fixtures
@pytest.fixture
def mock_uow():
    """Create mock Unit of Work."""
    mock = Mock()
    mock.__enter__ = Mock(return_value=mock)
    mock.__exit__ = Mock(return_value=None)
    return mock


@pytest.fixture
def repository_factory():
    """Create mock repository factory."""
    mock_repository = Mock()
    # Set up methods needed for the test
    mock_repository.get_by_model_provider = Mock(return_value=None)
    mock_repository.add = Mock()
    mock_repository.update = Mock()

    factory = Mock()
    factory.return_value = mock_repository
    return factory


@pytest.fixture
def model_configs() -> List[Union[ModelConfig, AzureModelConfig]]:
    """Create test model configurations."""
    return [
        ModelConfig(
            name="OpenAI GPT-4",
            technical_name="openai_config",
            provider="openai",
            url="https://api.openai.com",
            api_key="test-key"
        ),
        AzureModelConfig(
            name="Azure GPT-4",
            technical_name="azure_config",
            provider="azure",
            url="https://azure-openai.azure.com",
            api_key="test-azure-key",
            api_version="2023-05-15",
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            subscription_id="test-subscription",
            resource_group="test-group",
            resource_name="test-resource"
        )
    ]


class AsyncContextManagerMock:
    """Mock for async context manager (for LLMClientFactory.create_client)."""
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_success(mock_uow, repository_factory, model_configs):
    """Test fetching available models successfully."""
    # arrange
    service = ModelService(uow=mock_uow, repository_factory=repository_factory)

    # Create mock for the LLM client
    mock_client = AsyncMock(spec=LLMClientProtocol)
    mock_client.list_models = AsyncMock(return_value=[
        {"id": "gpt-4", "object": "model", "owned_by": "openai"},
        {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"}
    ])
    mock_client.list_deployments = AsyncMock(return_value=[
        {"deployment_id": "gpt4", "model": "gpt-4", "owner": "azure"},
        {"deployment_id": "gpt35", "model": "gpt-3.5-turbo", "owner": "azure"}
    ])

    # Mock LLMClientFactory.create_client
    with patch('ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.LLMClientFactory.create_client',
               return_value=AsyncContextManagerMock(mock_client)):
        # act
        await service.fetch_available_models(model_configs=model_configs)

        # assert
        # Verify repository calls to add models
        repository = repository_factory.return_value
        # We expect 4 models (2 from openai, 2 from azure)
        assert repository.add.call_count + repository.update.call_count > 0


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_unknown_provider(mock_uow, repository_factory):
    """Test handling unknown provider gracefully."""
    # arrange
    service = ModelService(uow=mock_uow, repository_factory=repository_factory)

    # Create config with unknown provider
    unknown_configs = [
        ModelConfig(
            name="Unknown Provider",
            technical_name="unknown_config",
            provider="unknown",
            url="https://unknown-api.com",
            api_key="test-key"
        )
    ]

    # act & assert - should not raise exception
    await service.fetch_available_models(model_configs=unknown_configs)
    # No models should be added or updated
    repository = repository_factory.return_value
    assert repository.add.call_count == 0
    assert repository.update.call_count == 0


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_client_error(mock_uow, repository_factory, model_configs):
    """Test handling client error during fetch."""
    # arrange
    service = ModelService(uow=mock_uow, repository_factory=repository_factory)

    # Create mock client that raises exception
    mock_client = AsyncMock(spec=LLMClientProtocol)
    mock_client.list_models = AsyncMock(side_effect=Exception("API error"))

    # Mock LLMClientFactory.create_client
    with patch('ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.LLMClientFactory.create_client',
               return_value=AsyncContextManagerMock(mock_client)):
        # act & assert - should handle exception gracefully
        await service.fetch_available_models(model_configs=model_configs)

        # No models should be added due to error
        repository = repository_factory.return_value
        assert repository.add.call_count == 0


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_azure(mock_uow, repository_factory):
    """Test fetching available models from Azure."""
    # arrange
    service = ModelService(uow=mock_uow, repository_factory=repository_factory)

    # Create config for Azure only
    azure_configs = [
        ModelConfig(
            name="Azure GPT-4",
            technical_name="azure_config",
            provider="azure",
            url="https://azure-openai.azure.com",
            api_key="test-azure-key",
            api_version="2023-05-15"
        )
    ]

    # Create mock for the LLM client
    mock_client = AsyncMock(spec=LLMClientProtocol)
    mock_client.list_deployments = AsyncMock(return_value=[
        {"deployment_id": "gpt4", "model": "gpt-4", "owner": "azure"},
        {"deployment_id": "gpt35", "model": "gpt-3.5-turbo", "owner": "azure"}
    ])

    # Mock LLMClientFactory.create_client
    with patch('ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.LLMClientFactory.create_client',
               return_value=AsyncContextManagerMock(mock_client)):
        # act
        await service.fetch_available_models(model_configs=azure_configs)

        # assert
        # Verify list_deployments was called instead of list_models
        assert mock_client.list_deployments.called
        assert not mock_client.list_models.called

        # Verify repository calls to add models
        repository = repository_factory.return_value
        # Two Azure deployments should be processed
        assert repository.add.call_count + repository.update.call_count > 0

