"""Tests for ModelService class."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from unittest.mock import MagicMock, Mock
import pytest
from sqlalchemy.exc import NoResultFound

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from ygo74.fastapi_openai_rag.application.services.model_service import ModelService
from ygo74.fastapi_openai_rag.domain.repositories.model_repository import IModelRepository
from ygo74.fastapi_openai_rag.domain.unit_of_work import UnitOfWork
from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ygo74.fastapi_openai_rag.domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ygo74.fastapi_openai_rag.domain.exceptions.validation_error import ValidationError


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self) -> None:
        self.session: Mock = Mock()
        self.committed: bool = False
        self.rolled_back: bool = False

    def __enter__(self) -> 'MockUnitOfWork':
        return self

    def __exit__(self, exc_type: any, exc_val: any, exc_tb: any) -> None:
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestModelService:
    """Test suite for ModelService."""

    @pytest.fixture
    def mock_uow(self) -> MockUnitOfWork:
        """Create a mock Unit of Work."""
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository with all necessary methods."""
        repository = Mock()
        # Explicitly add the methods that will be called
        repository.get_by_technical_name = Mock()
        repository.get_by_id = Mock()
        repository.get_all = Mock()
        repository.add = Mock()
        repository.update = Mock()
        repository.delete = Mock()
        repository.get_by_group_id = Mock()
        return repository

    @pytest.fixture
    def mock_repository_factory(self, mock_repository: Mock) -> Mock:
        """Create a mock repository factory."""
        factory: Mock = Mock()
        factory.return_value = mock_repository
        return factory

    @pytest.fixture
    def service(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> ModelService:
        """Create a ModelService instance with mocks."""
        return ModelService(mock_uow, mock_repository_factory)

    def test_add_model_success(self, service: ModelService, mock_repository: Mock) -> None:
        """Test successful model creation."""
        # arrange
        url: str = "http://test.com"
        name: str = "test-model"
        technical_name: str = "test_model"
        provider: LLMProvider = LLMProvider.OPENAI
        capabilities: dict = {"feature": "test"}
        new_model: LlmModel = LlmModel(
            id=1,
            url=url,
            name=name,
            technical_name=technical_name,
            provider=provider,
            status=LlmModelStatus.NEW,
            capabilities=capabilities,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_technical_name.return_value = None
        mock_repository.add.return_value = new_model

        # act
        status, result_model = service.add_or_update_model(
            model_id=0,  # Pour création
            url=url,
            name=name,
            technical_name=technical_name,
            provider=provider,
            capabilities=capabilities
        )

        # assert
        assert status == "created"
        assert result_model == new_model
        mock_repository.add.assert_called_once()
        mock_repository.get_by_technical_name.assert_called_once_with(technical_name)

    def test_add_model_already_exists(self, service: ModelService, mock_repository: Mock) -> None:
        """Test model creation with existing technical name."""
        # arrange
        technical_name: str = "test_model"
        existing_model: LlmModel = LlmModel(
            id=1,
            url="http://existing.com",
            name="existing-model",
            technical_name=technical_name,
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_technical_name.return_value = existing_model

        # act & assert
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            service.add_or_update_model(
                model_id=0,
                url="http://test.com",
                name="test-model",
                technical_name=technical_name,
                provider=LLMProvider.OPENAI,
                capabilities={}
            )

        assert f"technical_name {technical_name}" in str(exc_info.value)

    def test_add_model_missing_fields(self, service: ModelService, mock_repository: Mock) -> None:
        """Test model creation without required fields."""
        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            service.add_or_update_model(
                model_id=0,
                name="test-model",
                provider=LLMProvider.OPENAI
            )

        assert "URL, name, technical_name, and provider are required for new models" in str(exc_info.value)

    def test_update_model_success(self, service: ModelService, mock_repository: Mock) -> None:
        """Test successful model update."""
        # arrange
        model_id: int = 1
        updated_url: str = "http://updated.com"
        updated_name: str = "updated-model"
        existing_model: LlmModel = LlmModel(
            id=model_id,
            url="http://original.com",
            name="original-model",
            technical_name="original_model",
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        updated_model: LlmModel = LlmModel(
            id=model_id,
            url=updated_url,
            name=updated_name,
            technical_name="original_model",
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=existing_model.created,
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = existing_model
        mock_repository.update.return_value = updated_model

        # act
        status, result_model = service.add_or_update_model(
            model_id=model_id,
            url=updated_url,
            name=updated_name,
            technical_name="original_model",
            provider=LLMProvider.OPENAI
        )

        # assert
        assert status == "updated"
        assert result_model.url == updated_url
        assert result_model.name == updated_name
        mock_repository.get_by_id.assert_called_once_with(model_id)
        mock_repository.update.assert_called_once()

    def test_update_model_not_found(self, service: ModelService, mock_repository: Mock) -> None:
        """Test updating a non-existent model raises EntityNotFoundError."""
        # arrange
        model_id: int = 999
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            service.add_or_update_model(
                model_id=model_id,
                url="http://example.com/new",
                name="Updated Model",
                technical_name="updated_model",
                provider=LLMProvider.OPENAI
            )

        assert "Model with identifier '999' not found" in str(exc_info.value)

    def test_update_model_status_success(self, service: ModelService, mock_repository: Mock) -> None:
        """Test successful model status update."""
        # arrange
        model_id: int = 1
        new_status: LlmModelStatus = LlmModelStatus.APPROVED
        existing_model: LlmModel = LlmModel(
            id=model_id,
            url="http://test.com",
            name="test-model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        updated_model: LlmModel = LlmModel(
            id=model_id,
            url="http://test.com",
            name="test-model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            status=new_status,
            capabilities={},
            created=existing_model.created,
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = existing_model
        mock_repository.update.return_value = updated_model

        # act
        result: LlmModel = service.update_model_status(model_id, new_status)

        # assert
        assert result.status == new_status
        mock_repository.get_by_id.assert_called_once_with(model_id)
        mock_repository.update.assert_called_once()

    def test_update_model_status_not_found(self, service: ModelService, mock_repository: Mock) -> None:
        """Test updating status of non-existent model raises EntityNotFoundError."""
        # arrange
        model_id: int = 999
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            service.update_model_status(model_id, LlmModelStatus.APPROVED)

        assert "Model with identifier '999' not found" in str(exc_info.value)

    def test_get_all_models(self, service: ModelService, mock_repository: Mock) -> None:
        """Test getting all models."""
        # arrange
        models: List[LlmModel] = [
            LlmModel(
                id=1,
                url="http://test1.com",
                name="model1",
                technical_name="test_model1",
                provider=LLMProvider.OPENAI,
                status=LlmModelStatus.NEW,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            LlmModel(
                id=2,
                url="http://test2.com",
                name="model2",
                technical_name="test_model2",
                provider=LLMProvider.ANTHROPIC,
                status=LlmModelStatus.APPROVED,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        mock_repository.get_all.return_value = models

        # act
        result: List[LlmModel] = service.get_all_models()

        # assert
        assert len(result) == 2
        assert result[0].name == "model1"
        assert result[1].name == "model2"
        assert isinstance(result[0], LlmModel)
        assert isinstance(result[1], LlmModel)
        mock_repository.get_all.assert_called_once()

    def test_get_all_models_empty(self, service: ModelService, mock_repository: Mock) -> None:
        """Test getting all models when none exist."""
        # arrange
        mock_repository.get_all.return_value = []

        # act
        result: List[LlmModel] = service.get_all_models()

        # assert
        assert len(result) == 0
        assert result == []

    def test_delete_model_success(self, service: ModelService, mock_repository: Mock) -> None:
        """Test successful model deletion."""
        # arrange
        model_id: int = 1

        # act
        service.delete_model(model_id)

        # assert
        mock_repository.delete.assert_called_once_with(model_id)

    def test_get_model_by_id(self, service: ModelService, mock_repository: Mock) -> None:
        """Test getting model by ID."""
        # arrange
        model_id: int = 1
        expected_model: LlmModel = LlmModel(
            id=model_id,
            url="http://test.com",
            name="test-model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = expected_model

        # act
        result: Optional[LlmModel] = service.get_model_by_id(model_id)

        # assert
        assert result == expected_model
        mock_repository.get_by_id.assert_called_once_with(model_id)

    def test_get_model_by_technical_name(self, service: ModelService, mock_repository: Mock) -> None:
        """Test getting model by technical name."""
        # arrange
        technical_name: str = "test_model"
        expected_model: LlmModel = LlmModel(
            id=1,
            url="http://test.com",
            name="test-model",
            technical_name=technical_name,
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_technical_name.return_value = [expected_model]

        # act
        result: Optional[LlmModel] = service.get_model_by_technical_name(technical_name)

        # assert
        assert result == expected_model
        mock_repository.get_by_technical_name.assert_called_once_with(technical_name)

    def test_unit_of_work_commit_on_success(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> None:
        """Test that Unit of Work commits on successful operation."""
        # arrange
        service: ModelService = ModelService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.return_value = []

        # act
        service.get_all_models()

        # assert
        assert mock_uow.committed is True
        assert mock_uow.rolled_back is False

    def test_unit_of_work_rollback_on_exception(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> None:
        """Test that Unit of Work rolls back on exception."""
        # arrange
        service: ModelService = ModelService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.side_effect = Exception("Database error")

        # act & assert
        with pytest.raises(Exception, match="Database error"):
            service.get_all_models()

        assert mock_uow.rolled_back is True
        assert mock_uow.committed is False