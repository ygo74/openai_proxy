from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import NoResultFound
from src.main import app
from src.core.models.domain import ModelStatus, Model
from datetime import datetime, timezone
import pytest

client = TestClient(app)

def test_refresh_models_success():
    """Test successful model refresh endpoint."""
    response = client.post("/v1/admin/refreshmodels")
    assert response.status_code == 200
    assert response.json() == {"message": "Models refreshed successfully"}

@patch('src.api.endpoints.admin.ModelService')
def test_update_model_status_success(mock_model_service):
    """Test successful model status update."""
    # Arrange
    model_id = 1
    model = Model(
        id=model_id,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        status=ModelStatus.APPROVED,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        capabilities={"feature": "test"}
    )
    
    mock_service_instance = MagicMock()
    mock_service_instance.update_model_status.return_value = {
        "status": "updated",
        "model": model
    }
    mock_model_service.return_value = mock_service_instance

    # Act
    response = client.patch(
        f"/v1/admin/models/{model_id}/status",
        json={"status": "APPROVED"}
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == model_id
    assert response_data["status"] == ModelStatus.APPROVED
    assert response_data["technical_name"] == "test_model"
    mock_service_instance.update_model_status.assert_called_once_with(
        model_id, ModelStatus.APPROVED
    )

@patch('src.api.endpoints.admin.ModelService')
def test_update_model_status_not_found(mock_model_service):
    """Test model status update with non-existent model."""
    # Arrange
    model_id = 999
    mock_service_instance = MagicMock()
    mock_service_instance.update_model_status.side_effect = NoResultFound(
        f"Model with id {model_id} not found"
    )
    mock_model_service.return_value = mock_service_instance

    # Act
    response = client.patch(
        f"/v1/admin/models/{model_id}/status",
        json={"status": "APPROVED"}
    )

    # Assert
    assert response.status_code == 404
    assert f"Model with id {model_id} not found" in response.json()["detail"]

@patch('src.api.endpoints.admin.ModelService')
def test_update_model_status_invalid_status(mock_model_service):
    """Test model status update with invalid status value."""
    # Arrange
    model_id = 1

    # Act
    response = client.patch(
        f"/v1/admin/models/{model_id}/status",
        json={"status": "INVALID_STATUS"}
    )

    # Assert
    assert response.status_code == 422  # FastAPI validation error
    mock_model_service.assert_not_called()

@patch('src.api.endpoints.admin.ModelService')
def test_update_model_status_server_error(mock_model_service):
    """Test model status update with unexpected server error."""
    # Arrange
    model_id = 1
    mock_service_instance = MagicMock()
    mock_service_instance.update_model_status.side_effect = Exception("Unexpected error")
    mock_model_service.return_value = mock_service_instance

    # Act
    response = client.patch(
        f"/v1/admin/models/{model_id}/status",
        json={"status": "APPROVED"}
    )

    # Assert
    assert response.status_code == 500
    assert "Failed to update model status" in response.json()["detail"]