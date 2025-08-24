"""Tests for model-group association management in ModelService."""
import sys
import os
from datetime import datetime, timezone
from typing import List
from unittest.mock import Mock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from ygo74.fastapi_openai_rag.application.services.model_service import ModelService
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.group_repository import SQLGroupRepository
from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError

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


@pytest.fixture
def mock_uow() -> MockUnitOfWork:
    """Create a mock Unit of Work."""
    return MockUnitOfWork()


@pytest.fixture
def mock_model_repository() -> Mock:
    """Create a mock model repository."""
    repository = Mock()
    repository.get_by_id = Mock()
    repository.update = Mock()
    return repository


@pytest.fixture
def mock_group_repository() -> Mock:
    """Create a mock group repository."""
    repository = Mock()
    repository.get_by_id = Mock()
    return repository


@pytest.fixture
def mock_repository_factory(mock_model_repository: Mock) -> Mock:
    """Create a mock repository factory."""
    factory = Mock()
    factory.return_value = mock_model_repository
    return factory


@pytest.fixture
def service(mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> ModelService:
    """Create a ModelService instance with mocks."""
    return ModelService(mock_uow, mock_repository_factory)


def test_add_model_to_group_success(
    monkeypatch,
    service: ModelService,
    mock_model_repository: Mock,
    mock_group_repository: Mock
) -> None:
    """Test adding a model to a group successfully."""
    # arrange
    model_id = 1
    group_id = 2

    # Mock objects
    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[]
    )

    group = Group(
        id=group_id,
        name="Test Group",
        description="Test Description",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )

    updated_model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=model.created,
        updated=datetime.now(timezone.utc),
        groups=[group]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model
    mock_group_repository.get_by_id.return_value = group
    mock_model_repository.update.return_value = updated_model

    # Patch the SQLGroupRepository constructor to return our mock
    def mock_group_repo_init(session):
        return mock_group_repository

    monkeypatch.setattr(SQLGroupRepository, "__init__", lambda self, session: None)
    monkeypatch.setattr(SQLGroupRepository, "__new__", lambda cls, session: mock_group_repository)

    # act
    result = service.add_model_to_group(model_id, group_id)

    # assert
    assert result.id == model_id
    assert len(result.groups) == 1
    assert result.groups[0].id == group_id
    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_group_repository.get_by_id.assert_called_once_with(group_id)
    mock_model_repository.update.assert_called_once()


def test_add_model_to_group_model_not_found(
    monkeypatch,
    service: ModelService,
    mock_model_repository: Mock,
    mock_group_repository: Mock
) -> None:
    """Test adding a model to a group when model not found."""
    # arrange
    model_id = 1
    group_id = 2

    # Configure mocks
    mock_model_repository.get_by_id.return_value = None

    # Patch the SQLGroupRepository constructor to return our mock
    monkeypatch.setattr(SQLGroupRepository, "__init__", lambda self, session: None)
    monkeypatch.setattr(SQLGroupRepository, "__new__", lambda cls, session: mock_group_repository)

    # act & assert
    with pytest.raises(EntityNotFoundError, match=f"Model with identifier '{model_id}' not found"):
        service.add_model_to_group(model_id, group_id)

    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_group_repository.get_by_id.assert_not_called()
    mock_model_repository.update.assert_not_called()


def test_add_model_to_group_group_not_found(
    monkeypatch,
    service: ModelService,
    mock_model_repository: Mock,
    mock_group_repository: Mock
) -> None:
    """Test adding a model to a group when group not found."""
    # arrange
    model_id = 1
    group_id = 2

    # Mock objects
    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model
    mock_group_repository.get_by_id.return_value = None

    # Patch the SQLGroupRepository constructor to return our mock
    monkeypatch.setattr(SQLGroupRepository, "__init__", lambda self, session: None)
    monkeypatch.setattr(SQLGroupRepository, "__new__", lambda cls, session: mock_group_repository)

    # act & assert
    with pytest.raises(EntityNotFoundError, match=f"Group with identifier '{group_id}' not found"):
        service.add_model_to_group(model_id, group_id)

    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_group_repository.get_by_id.assert_called_once_with(group_id)
    mock_model_repository.update.assert_not_called()


def test_add_model_to_group_already_associated(
    monkeypatch,
    service: ModelService,
    mock_model_repository: Mock,
    mock_group_repository: Mock
) -> None:
    """Test adding a model to a group when they are already associated."""
    # arrange
    model_id = 1
    group_id = 2

    # Mock objects
    group = Group(
        id=group_id,
        name="Test Group",
        description="Test Description",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )

    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[group]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model
    mock_group_repository.get_by_id.return_value = group

    # Patch the SQLGroupRepository constructor to return our mock
    monkeypatch.setattr(SQLGroupRepository, "__init__", lambda self, session: None)
    monkeypatch.setattr(SQLGroupRepository, "__new__", lambda cls, session: mock_group_repository)

    # act
    result = service.add_model_to_group(model_id, group_id)

    # assert
    assert result == model
    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_group_repository.get_by_id.assert_called_once_with(group_id)
    mock_model_repository.update.assert_not_called()


def test_remove_model_from_group_success(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test removing a model from a group successfully."""
    # arrange
    model_id = 1
    group_id = 2

    # Mock objects
    group = Group(
        id=group_id,
        name="Test Group",
        description="Test Description",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )

    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[group]
    )

    updated_model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=model.created,
        updated=datetime.now(timezone.utc),
        groups=[]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model
    mock_model_repository.update.return_value = updated_model

    # act
    result = service.remove_model_from_group(model_id, group_id)

    # assert
    assert result.id == model_id
    assert len(result.groups) == 0
    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_model_repository.update.assert_called_once()


def test_remove_model_from_group_model_not_found(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test removing a model from a group when model not found."""
    # arrange
    model_id = 1
    group_id = 2

    # Configure mocks
    mock_model_repository.get_by_id.return_value = None

    # act & assert
    with pytest.raises(EntityNotFoundError, match=f"Model with identifier '{model_id}' not found"):
        service.remove_model_from_group(model_id, group_id)

    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_model_repository.update.assert_not_called()


def test_remove_model_from_group_not_associated(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test removing a model from a group when they are not associated."""
    # arrange
    model_id = 1
    group_id = 2

    # Mock objects
    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model

    # act & assert
    with pytest.raises(EntityNotFoundError, match=f"Group with identifier '{group_id} not associated with model {model_id}' not found"):
        service.remove_model_from_group(model_id, group_id)

    mock_model_repository.get_by_id.assert_called_once_with(model_id)
    mock_model_repository.update.assert_not_called()


def test_get_groups_for_model_success(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test getting groups for model successfully."""
    # arrange
    model_id = 1

    # Mock objects
    group1 = Group(
        id=1,
        name="Group 1",
        description="Description 1",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )

    group2 = Group(
        id=2,
        name="Group 2",
        description="Description 2",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )

    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[group1, group2]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model

    # act
    result = service.get_groups_for_model(model_id)

    # assert
    assert len(result) == 2
    assert result[0].id == 1
    assert result[1].id == 2
    mock_model_repository.get_by_id.assert_called_once_with(model_id)


def test_get_groups_for_model_not_found(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test getting groups for model when model not found."""
    # arrange
    model_id = 1

    # Configure mocks
    mock_model_repository.get_by_id.return_value = None

    # act & assert
    with pytest.raises(EntityNotFoundError, match=f"Model with identifier '{model_id}' not found"):
        service.get_groups_for_model(model_id)

    mock_model_repository.get_by_id.assert_called_once_with(model_id)


def test_get_groups_for_model_no_groups(
    service: ModelService,
    mock_model_repository: Mock
) -> None:
    """Test getting groups for model when model has no groups."""
    # arrange
    model_id = 1

    # Mock objects
    model = LlmModel(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[]
    )

    # Configure mocks
    mock_model_repository.get_by_id.return_value = model

    # act
    result = service.get_groups_for_model(model_id)

    # assert
    assert len(result) == 0
    mock_model_repository.get_by_id.assert_called_once_with(model_id)
