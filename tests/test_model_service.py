from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from sqlalchemy.exc import NoResultFound
from src.core.models.domain import Model, ModelStatus
from src.core.application.model_service import ModelService
from src.infrastructure.model_crud import ModelRepository
from typing import Dict, Any

@pytest.fixture
def mock_repository() -> MagicMock:
    """Create a mock repository."""
    return MagicMock(spec=ModelRepository)

@pytest.fixture
def model_service(mock_repository: MagicMock) -> ModelService:
    """Create a ModelService instance with a mock repository."""
    mock_session = MagicMock()
    return ModelService(mock_session, repository=mock_repository)

def test_add_model_success(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test the successful addition of a new model."""
    # Arrange
    url = "http://test.com"
    name = "test-model"
    technical_name = "test_model"
    capabilities = {"feature": "test"}
    new_model = Model(
        id=1,
        url=url,
        name=name,
        technical_name=technical_name,
        status=ModelStatus.NEW,
        capabilities=capabilities,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    mock_repository.create.return_value = new_model
    mock_repository.get_by_technical_name.return_value = None

    # Act
    result: Dict[str, Any] = model_service.add_or_update_model(
        url=url, name=name, technical_name=technical_name, capabilities=capabilities
    )

    # Assert
    assert result["status"] == "created"
    assert result["model"] == new_model
    mock_repository.create.assert_called_once_with(
        url=url, name=name, technical_name=technical_name,
        status=ModelStatus.NEW, capabilities=capabilities
    )

def test_add_model_already_exists(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test adding a model that already exists."""
    # Arrange
    technical_name = "test_model"
    existing_model = Model(
        id=1,
        url="http://test.com",
        name="test-model",
        technical_name=technical_name,
        status=ModelStatus.NEW,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    mock_repository.get_by_technical_name.return_value = existing_model

    # Act & Assert
    with pytest.raises(ValueError, match=f"Model with technical_name {technical_name} already exists"):
        model_service.add_or_update_model(
            url="http://test.com",
            name="test-model",
            technical_name=technical_name
        )

def test_add_model_missing_fields(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test adding a model with missing required fields."""
    # Arrange
    mock_repository.get_by_technical_name.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="URL, name, and technical_name are required"):
        model_service.add_or_update_model(
            url="http://test.com",
            name=None,
            technical_name="test_model"
        )

def test_get_all_models(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test retrieving all models."""
    # Arrange
    models = [
        Model(
            id=1,
            url="http://test1.com",
            name="model1",
            technical_name="test_model1",
            status=ModelStatus.NEW,
            capabilities={"feature": "test1"},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        ),
        Model(
            id=2,
            url="http://test2.com",
            name="model2",
            technical_name="test_model2",
            status=ModelStatus.APPROVED,
            capabilities={"feature": "test2"},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
    ]
    mock_repository.get_all.return_value = models

    # Act
    result = model_service.get_all_models()

    # Assert
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2
    assert result[0]["status"] == ModelStatus.NEW
    assert result[1]["status"] == ModelStatus.APPROVED
    mock_repository.get_all.assert_called_once()

def test_update_model_status_success(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test successful model status update."""
    # Arrange
    model_id = 1
    now = datetime.now(timezone.utc)
    existing_model = Model(
        id=model_id,
        url="http://test.com",
        name="test-model",
        technical_name="test_model",
        status=ModelStatus.NEW,
        created=now,
        updated=now
    )
    mock_repository.get_by_id.return_value = existing_model

    updated_model = Model(
        id=model_id,
        url="http://test.com",
        name="test-model",
        technical_name="test_model",
        status=ModelStatus.APPROVED,
        created=now,
        updated=now
    )
    mock_repository.update.return_value = updated_model

    # Act
    result = model_service.update_model_status(model_id, ModelStatus.APPROVED)

    # Assert
    assert result["status"] == "updated"
    assert result["model"].status == ModelStatus.APPROVED
    mock_repository.update.assert_called_once()

def test_update_model_status_not_found(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test updating status of a non-existent model."""
    # Arrange
    model_id = 999
    mock_repository.get_by_id.return_value = None

    # Act & Assert
    with pytest.raises(NoResultFound, match=f"Model with id {model_id} not found"):
        model_service.update_model_status(model_id, ModelStatus.APPROVED)

def test_delete_model_success(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test successful model deletion."""
    # Arrange
    model_id = 1
    mock_repository.delete.return_value = None

    # Act
    result = model_service.delete_model(model_id)

    # Assert
    assert result["status"] == "deleted"
    mock_repository.delete.assert_called_once_with(model_id)

def test_delete_model_not_found(model_service: ModelService, mock_repository: MagicMock) -> None:
    """Test deleting a non-existent model."""
    # Arrange
    model_id = 999
    mock_repository.delete.side_effect = NoResultFound(f"Model with id {model_id} not found")

    # Act & Assert
    with pytest.raises(NoResultFound):
        model_service.delete_model(model_id)