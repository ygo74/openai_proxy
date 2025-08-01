"""Tests for ModelService fetch_available_models method."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.ygo74.fastapi_openai_rag.application.services.model_service import ModelService
from src.ygo74.fastapi_openai_rag.domain.models.configuration import ModelConfig
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from src.ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModelStatus
from src.ygo74.fastapi_openai_rag.domain.unit_of_work import UnitOfWork


@pytest.fixture
def mock_uow():
    """Create mock Unit of Work."""
    uow = MagicMock(spec=UnitOfWork)
    uow.__enter__ = MagicMock(return_value=uow)
    uow.__exit__ = MagicMock(return_value=None)
    uow.session = MagicMock()
    return uow


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    repo = MagicMock()
    repo.get_by_technical_name.return_value = None
    repo.add.return_value = MagicMock(id=1)
    return repo


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.list_models.return_value = [
        {"id": "gpt-3.5-turbo", "object": "model", "capabilities": {}},
        {"id": "gpt-4", "object": "model", "capabilities": {}}
    ]
    client.close.return_value = None
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_success(mock_uow, mock_repository, mock_llm_client):
    """Test ModelService fetch_available_models method success."""
    # arrange
    model_configs = [
        ModelConfig(
            provider="openai",
            url="https://api.openai.com/v1",
            api_key="test-key"
        )
    ]

    def mock_client_factory(model, api_key):
        return mock_llm_client

    service = ModelService(
        uow=mock_uow,
        repository_factory=lambda session: mock_repository,
        llm_client_factory=mock_client_factory
    )

    # act
    await service.fetch_available_models(model_configs)

    # assert
    mock_llm_client.list_models.assert_called_once()
    mock_llm_client.__aenter__.assert_called_once()
    mock_llm_client.__aexit__.assert_called_once()
    assert mock_repository.add.call_count == 2  # Two models added


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_unknown_provider(mock_uow, mock_repository):
    """Test ModelService fetch_available_models with unknown provider."""
    # arrange
    model_configs = [
        ModelConfig(
            provider="unknown",
            url="https://api.unknown.com",
            api_key="test-key"
        )
    ]

    service = ModelService(
        uow=mock_uow,
        repository_factory=lambda session: mock_repository
    )

    # act
    await service.fetch_available_models(model_configs)

    # assert
    mock_repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_client_error(mock_uow, mock_repository):
    """Test ModelService fetch_available_models with client error."""
    # arrange
    model_configs = [
        ModelConfig(
            provider="openai",
            url="https://api.openai.com/v1",
            api_key="test-key"
        )
    ]

    mock_error_client = AsyncMock()
    mock_error_client.list_models.side_effect = Exception("API Error")
    mock_error_client.__aenter__ = AsyncMock(return_value=mock_error_client)
    mock_error_client.__aexit__ = AsyncMock(return_value=None)

    def mock_client_factory(model, api_key):
        return mock_error_client

    service = ModelService(
        uow=mock_uow,
        repository_factory=lambda session: mock_repository,
        llm_client_factory=mock_client_factory
    )

    # act (should not raise exception)
    await service.fetch_available_models(model_configs)

    # assert
    mock_repository.add.assert_not_called()
    mock_error_client.__aenter__.assert_called_once()
    mock_error_client.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_model_service_fetch_available_models_azure(mock_uow, mock_repository, mock_llm_client):
    """Test ModelService fetch_available_models with Azure provider."""
    # arrange
    model_configs = [
        ModelConfig(
            provider="azure",
            url="https://test.openai.azure.com",
            api_key="test-key",
            api_version="2024-06-01"
        )
    ]

    def mock_client_factory(model, api_key):
        return mock_llm_client

    service = ModelService(
        uow=mock_uow,
        repository_factory=lambda session: mock_repository,
        llm_client_factory=mock_client_factory
    )

    # act
    await service.fetch_available_models(model_configs)

    # assert
    mock_llm_client.list_models.assert_called_once()
    assert mock_repository.add.call_count == 2  # Two models added
