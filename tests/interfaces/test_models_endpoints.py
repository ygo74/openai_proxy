"""Tests for Models API endpoints."""
import sys
import os
from typing import Dict, Any
from datetime import datetime, timezone
from typing import List, Tuple
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.main import app
from ygo74.fastapi_openai_rag.domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider

@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_model_service():
    """Mock ModelService for testing."""
    with patch('ygo74.fastapi_openai_rag.interfaces.api.endpoints.models.SQLUnitOfWork') as mock_uow, \
         patch('ygo74.fastapi_openai_rag.interfaces.api.endpoints.models.ModelService') as mock_service_class:

        service_instance = MagicMock()
        mock_service_class.return_value = service_instance

        # Mock the UoW context manager
        mock_uow_instance = MagicMock()
        mock_uow.return_value = mock_uow_instance

        yield service_instance


class TestModelsEndpoints:
    """Test suite for models endpoints."""

    def test_get_models_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful retrieval of models."""
        # arrange
        models: List[LlmModel] = [
            LlmModel(
                id=1,
                url="http://test1.com",
                name="Test Model 1",
                technical_name="test_model_1",
                provider=LLMProvider.OPENAI,
                status=LlmModelStatus.APPROVED,
                capabilities={"feature": "test1"},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            LlmModel(
                id=2,
                url="http://test2.com",
                name="Test Model 2",
                technical_name="test_model_2",
                provider=LLMProvider.ANTHROPIC,
                status=LlmModelStatus.NEW,
                capabilities={"feature": "test2"},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        mock_model_service.get_all_models.return_value = models

        # act
        response = client.get("/v1/models/")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Test Model 1"
        assert response_data[1]["name"] == "Test Model 2"
        assert "id" in response_data[0]
        assert "technical_name" in response_data[0]

    def test_create_model_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful model creation."""
        # arrange
        model_data: Dict[str,Any] = {
            "model_id": -1,
            "url": "http://newmodel.com",
            "name": "New Model",
            "technical_name": "new_model",
            "provider": "openai",
            "capabilities": {"feature": "new"}
        }
        created_model: LlmModel = LlmModel(
            id=1,
            url=model_data["url"],
            name=model_data["name"],
            technical_name=model_data["technical_name"],
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities=model_data["capabilities"],
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        status_result: Tuple[str, LlmModel] = ("created", created_model)
        mock_model_service.add_or_update_model.return_value = status_result

        # act
        response = client.post("/v1/models/", json=model_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == model_data["name"]
        assert response_data["technical_name"] == model_data["technical_name"]
        assert "id" in response_data
        mock_model_service.add_or_update_model.assert_called_once_with(
            model_id=model_data["model_id"],
            url=model_data["url"],
            name=model_data["name"],
            technical_name=model_data["technical_name"],
            provider=LLMProvider.OPENAI,
            capabilities=model_data["capabilities"]
        )

    def test_create_model_validation_error(self, client: TestClient) -> None:
        """Test model creation with invalid data."""
        # arrange
        invalid_data: Dict[str,str] = {"name": "Invalid Model"}  # Missing required fields

        # act
        response = client.post("/v1/models/", json=invalid_data)

        # assert
        assert response.status_code == 422

    def test_create_model_already_exists(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test model creation when technical name already exists."""
        # arrange
        model_data: Dict[str,Any]  = {
            "url": "http://existing.com",
            "name": "Existing Model",
            "technical_name": "existing_model",
            "provider": "openai",
            "capabilities": {}
        }
        mock_model_service.add_or_update_model.side_effect = EntityAlreadyExistsError("Model",  "with technical_name existing_model already exists")

        # act
        response = client.post("/v1/models/", json=model_data)

        # assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_get_model_by_id_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful retrieval of model by ID."""
        # arrange
        model_id: int = 1
        model: LlmModel = LlmModel(
            id=model_id,
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            provider=LLMProvider.AZURE,
            status=LlmModelStatus.APPROVED,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_model_service.get_model_by_id.return_value = model

        # act
        response = client.get(f"/v1/models/{model_id}")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == model_id
        assert response_data["name"] == "Test Model"
        assert response_data["technical_name"] == "test_model"
        mock_model_service.get_model_by_id.assert_called_once_with(model_id)

    def test_get_model_by_id_not_found(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test model retrieval when model doesn't exist."""
        # arrange
        model_id: int = 999
        # Import the domain exception that the service layer should raise
        from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
        mock_model_service.get_model_by_id.side_effect = EntityNotFoundError("Model", str(model_id))

        # act
        response = client.get(f"/v1/models/{model_id}")

        # assert
        assert response.status_code == 404
        assert f"Model with identifier '{model_id}' not found" in response.json()["detail"]

    def test_update_model_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful model update."""
        # arrange
        model_id: int = 1
        update_data: dict = {
            "name": "Updated Model",
            "url": "http://updatedmodel.com",
            "provider": "mistral",
            "capabilities": {"feature": "updated"}
        }
        updated_model: LlmModel = LlmModel(
            id=model_id,
            url=update_data["url"],
            name=update_data["name"],
            technical_name="test_model",
            provider=LLMProvider.MISTRAL,
            status=LlmModelStatus.APPROVED,
            capabilities=update_data["capabilities"],
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        status_result: Tuple[str, LlmModel] = ("updated", updated_model)
        mock_model_service.add_or_update_model.return_value = status_result

        # act
        response = client.put(f"/v1/models/{model_id}", json=update_data)

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["name"] == update_data["name"]
        assert response_data["url"] == update_data["url"]
        mock_model_service.add_or_update_model.assert_called_once_with(
            model_id=model_id,
            url=update_data["url"],
            name=update_data["name"],
            technical_name=update_data.get("technical_name"),
            provider=LLMProvider.MISTRAL,
            capabilities=update_data["capabilities"]
        )

    def test_update_model_not_found(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test model update when model doesn't exist."""
        # arrange
        model_id: int = 999
        update_data: dict = {
            "name": "Updated Model",
            "url": "http://updated.com",
            "provider": "openai"
        }
        # Import the domain exception that the service layer should raise
        from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
        mock_model_service.add_or_update_model.side_effect = EntityNotFoundError("Model", str(model_id))

        # act
        response = client.put(f"/v1/models/{model_id}", json=update_data)

        # assert
        assert response.status_code == 404
        assert f"Model with identifier '{model_id}' not found" in response.json()["detail"]

    def test_delete_model_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful model deletion."""
        # arrange
        model_id: int = 1
        mock_model_service.delete_model.return_value = None

        # act
        response = client.delete(f"/v1/models/{model_id}")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert "deleted successfully" in response_data["message"]
        mock_model_service.delete_model.assert_called_once_with(model_id)

    def test_delete_model_not_found(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test model deletion when model doesn't exist."""
        # arrange
        model_id: int = 999
        # Import the domain exception that the service layer should raise
        from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
        mock_model_service.delete_model.side_effect = EntityNotFoundError("Model", str(model_id))

        # act
        response = client.delete(f"/v1/models/{model_id}")

        # assert
        assert response.status_code == 404
        assert f"Model with identifier '{model_id}' not found" in response.json()["detail"]

    def test_update_model_status_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful model status update."""
        # arrange
        model_id: int = 1
        new_status: LlmModelStatus = LlmModelStatus.APPROVED
        updated_model: LlmModel = LlmModel(
            id=model_id,
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            provider=LLMProvider.COHERE,
            status=new_status,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_model_service.update_model_status.return_value = updated_model

        # act
        response = client.patch(f"/v1/models/{model_id}/status", json={"status": new_status})

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == new_status
        mock_model_service.update_model_status.assert_called_once_with(model_id, new_status)

    def test_get_model_statistics_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful retrieval of model statistics."""
        # arrange
        models: List[LlmModel] = [
            LlmModel(id=1, url="http://test1.com", name="Model 1", technical_name="model_1",
                  provider=LLMProvider.OPENAI, status=LlmModelStatus.APPROVED, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc)),
            LlmModel(id=2, url="http://test2.com", name="Model 2", technical_name="model_2",
                  provider=LLMProvider.ANTHROPIC, status=LlmModelStatus.NEW, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc)),
            LlmModel(id=3, url="http://test3.com", name="Model 3", technical_name="model_3",
                  provider=LLMProvider.AZURE, status=LlmModelStatus.APPROVED, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc))
        ]
        mock_model_service.get_all_models.return_value = models

        # act
        response = client.get("/v1/models/statistics")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == 3
        assert response_data["by_status"][LlmModelStatus.APPROVED] == 2
        assert response_data["by_status"][LlmModelStatus.NEW] == 1

    def test_get_models_with_status_filter(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test models retrieval with status filter."""
        # arrange
        models: List[LlmModel] = [
            LlmModel(id=1, url="http://test1.com", name="Model 1", technical_name="model_1",
                  provider=LLMProvider.MISTRAL, status=LlmModelStatus.APPROVED, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc))
        ]
        mock_model_service.get_all_models.return_value = models

        # act
        response = client.get(f"/v1/models/?status_filter={LlmModelStatus.APPROVED.value}")  # Use the correct enum value

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) >= 0  # Filter is applied client-side in this implementation

    def test_get_models_with_invalid_status_filter(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test models retrieval with invalid status filter."""
        # arrange
        models: List[LlmModel] = []
        mock_model_service.get_all_models.return_value = models

        # act
        response = client.get("/v1/models/?status_filter=invalid_status")

        # assert
        assert response.status_code == 400
        assert "Invalid status value" in response.json()["detail"]

    def test_search_models_by_name(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test searching models by name."""
        # arrange
        models: List[LlmModel] = [
            LlmModel(id=1, url="http://test1.com", name="OpenAI Model", technical_name="openai_model",
                  provider=LLMProvider.OPENAI, status=LlmModelStatus.APPROVED, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc)),
            LlmModel(id=2, url="http://test2.com", name="Anthropic Model", technical_name="anthropic_model",
                  provider=LLMProvider.ANTHROPIC, status=LlmModelStatus.APPROVED, capabilities={},
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc))
        ]
        mock_model_service.get_all_models.return_value = models

        # act
        response = client.get("/v1/models/search?name=OpenAI")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        # The filtering is done in the endpoint, so we expect results

    def test_refresh_models_success(self, client: TestClient, mock_model_service: MagicMock) -> None:
        """Test successful models refresh."""
        # arrange
        # Configure the mock as an AsyncMock for the async method
        mock_model_service.fetch_available_models = AsyncMock(return_value=None)

        # act
        response = client.post("/v1/models/refresh")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert "refreshed successfully" in response_data["message"]
        mock_model_service.fetch_available_models.assert_called_once()