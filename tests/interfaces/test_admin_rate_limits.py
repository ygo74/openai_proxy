"""Tests for Admin Rate Limits API endpoints."""
import sys
import os
from datetime import datetime, timezone, time
from typing import List
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ygo74.fastapi_openai_rag.domain.exceptions.validation_error import ValidationError
from ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser
from ygo74.fastapi_openai_rag.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_rate_limit_service():
    """Mock RateLimitService with mocked cache for testing."""
    # Create a mock cache
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # Default: cache miss
    mock_cache.set.return_value = None
    mock_cache.publish_change.return_value = None

    # Create a mock service and inject the mock cache
    with patch('ygo74.fastapi_openai_rag.interfaces.api.admin.rate_limits.SQLUnitOfWork') as mock_uow, \
         patch('ygo74.fastapi_openai_rag.interfaces.api.admin.rate_limits.RateLimitService') as mock_service_class:

        service_instance = MagicMock()
        service_instance._cache = mock_cache  # Inject mock cache
        mock_service_class.return_value = service_instance

        # Mock the UoW context manager
        mock_uow_instance = MagicMock()
        mock_uow.return_value = mock_uow_instance

        yield service_instance


@pytest.fixture
def mock_admin_auth(client, mock_rate_limit_service):
    """Mock admin authentication and rate limit service."""
    from ygo74.fastapi_openai_rag.interfaces.api.security.auth import require_admin_role
    from ygo74.fastapi_openai_rag.interfaces.api.admin.rate_limits import get_rate_limit_service

    def override_require_admin_role():
        return AuthenticatedUser(
            id="admin1",
            username="admin",
            groups=["admin"],
            type="jwt"
        )

    def override_get_rate_limit_service():
        return mock_rate_limit_service

    app.dependency_overrides[require_admin_role] = override_require_admin_role
    app.dependency_overrides[get_rate_limit_service] = override_get_rate_limit_service
    yield
    app.dependency_overrides.clear()


class TestAdminRateLimitsEndpoints:
    """Test suite for admin rate limits endpoints."""

    def test_list_rate_limits_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful retrieval of all rate limits."""
        # arrange
        from datetime import time
        rate_limits: List[RateLimit] = [
            RateLimit(
                id=1,
                scope_type="model",
                scope_id="gpt-4",
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=1,
                        from_time=time(0, 0),
                        to_time=time(1, 0),
                        max_requests=100,
                        max_tokens=50000
                    )
                ]
            ),
            RateLimit(
                id=2,
                scope_type="group_model",
                scope_id="engineering:gpt-4",
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=2,
                        from_time=time(0, 0),
                        to_time=time(1, 0),
                        max_requests=50,
                        max_tokens=25000
                    )
                ]
            )
        ]
        mock_rate_limit_service.get_all_rate_limits.return_value = rate_limits

        # act
        response = client.get("/v1/admin/rate-limits")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == 2
        assert len(response_data["rate_limits"]) == 2
        assert response_data["rate_limits"][0]["scope_type"] == "model"
        assert response_data["rate_limits"][0]["scope_id"] == "gpt-4"
        assert response_data["rate_limits"][1]["scope_type"] == "group_model"

    def test_list_rate_limits_empty(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test retrieval when no rate limits exist."""
        # arrange
        mock_rate_limit_service.get_all_rate_limits.return_value = []

        # act
        response = client.get("/v1/admin/rate-limits")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == 0
        assert response_data["rate_limits"] == []

    def test_create_model_rate_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful creation of model rate limit."""
        # arrange
        from datetime import time
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 100,
                    "max_tokens": 50000
                }
            ]
        }
        created_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = created_rate_limit

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["scope_type"] == "model"
        assert response_data["scope_id"] == "gpt-4"
        assert response_data["enabled"] is True
        assert len(response_data["windows"]) == 1
        assert response_data["windows"][0]["max_requests"] == 100

    def test_create_model_rate_limit_validation_no_windows(
        self,
        client: TestClient,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test validation failure when no windows provided."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": []
        }

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 422  # Validation error

    def test_create_model_rate_limit_validation_no_limits(
        self,
        client: TestClient,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test validation failure when neither max_requests nor max_tokens provided."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": 3600
                }
            ]
        }

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 422  # Validation error

    def test_create_model_rate_limit_validation_invalid_time_range(
        self,
        client: TestClient,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test validation failure when from_time >= to_time."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "01:00",
                    "to_time": 0,
                    "max_requests": 100
                }
            ]
        }

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 422  # Validation error

    def test_create_group_model_rate_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful creation of group+model rate limit."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 50,
                    "max_tokens": 25000
                }
            ]
        }
        created_rate_limit = RateLimit(
            id=1,
            scope_type="group_model",
            scope_id="engineering:gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=50,
                    max_tokens=25000
                )
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = created_rate_limit

        # act
        response = client.post(
            "/v1/admin/rate-limits/groups/engineering/models/gpt-4",
            json=request_data
        )

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["scope_type"] == "group_model"
        assert response_data["scope_id"] == "engineering:gpt-4"
        assert response_data["enabled"] is True

    def test_update_model_rate_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful update of existing model rate limit."""
        # arrange
        request_data = {
            "enabled": False,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 200,
                    "max_tokens": 100000
                }
            ]
        }
        updated_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=False,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=200,
                    max_tokens=100000
                )
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = updated_rate_limit

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["enabled"] is False
        assert response_data["windows"][0]["max_requests"] == 200

    def test_delete_model_rate_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful deletion of model rate limit."""
        # arrange
        mock_rate_limit_service.delete_rate_limit.return_value = True

        # act
        response = client.delete("/v1/admin/rate-limits/model/gpt-4")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["scope_type"] == "model"
        assert response_data["scope_id"] == "gpt-4"
        assert "deleted successfully" in response_data["message"]

    def test_delete_group_model_rate_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test successful deletion of group+model rate limit."""
        # arrange
        mock_rate_limit_service.delete_rate_limit.return_value = True

        # act
        response = client.delete("/v1/admin/rate-limits/group_model/engineering:gpt-4")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["scope_type"] == "group_model"
        assert response_data["scope_id"] == "engineering:gpt-4"

    def test_delete_rate_limit_not_found(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test deletion of non-existent rate limit returns 404."""
        # arrange
        mock_rate_limit_service.delete_rate_limit.return_value = False

        # act
        response = client.delete("/v1/admin/rate-limits/model/nonexistent")

        # assert
        assert response.status_code == 404
        response_data = response.json()
        assert "not found" in response_data["detail"].lower()

    def test_delete_rate_limit_invalid_scope_type(
        self,
        client: TestClient,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test deletion with invalid scope_type returns 400."""
        # act
        response = client.delete("/v1/admin/rate-limits/invalid_scope/some-id")

        # assert
        assert response.status_code == 400
        response_data = response.json()
        assert "Invalid scope_type" in response_data["detail"]

    def test_get_global_rate_limit_not_implemented(
        self,
        client: TestClient,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test global rate limit endpoint returns 501."""
        # act
        response = client.get("/v1/admin/rate-limits/global")

        # assert
        assert response.status_code == 501
        response_data = response.json()
        assert "phase 9" in response_data["detail"].lower() or "not yet implemented" in response_data["detail"].lower()

    def test_create_rate_limit_service_error(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test handling of service layer errors."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 100
                }
            ]
        }
        mock_rate_limit_service.create_or_update_rate_limit.side_effect = Exception("Database error")

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 500
        response_data = response.json()
        assert "error" in response_data["detail"].lower()

    def test_multiple_windows_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test creation with multiple time windows."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 100,
                    "max_tokens": 50000
                },
                {
                    "from_time": "01:00",
                    "to_time": "02:00",
                    "max_requests": 50,
                    "max_tokens": 25000
                }
            ]
        }
        created_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(id=1, from_time=time(0, 0), to_time=time(1, 0), max_requests=100, max_tokens=50000),
                RateLimitWindow(id=2, from_time=time(1, 0), to_time=time(2, 0), max_requests=50, max_tokens=25000)
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = created_rate_limit

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert len(response_data["windows"]) == 2

    def test_token_only_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test creation with token limit only (no request limit)."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_tokens": 100000
                }
            ]
        }
        created_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=None,
                    max_tokens=100000
                )
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = created_rate_limit

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["windows"][0]["max_tokens"] == 100000
        assert response_data["windows"][0]["max_requests"] is None

    def test_request_only_limit_success(
        self,
        client: TestClient,
        mock_rate_limit_service: MagicMock,
        mock_admin_auth: MagicMock
    ) -> None:
        """Test creation with request limit only (no token limit)."""
        # arrange
        request_data = {
            "enabled": True,
            "windows": [
                {
                    "from_time": "00:00",
                    "to_time": "01:00",
                    "max_requests": 100
                }
            ]
        }
        created_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=None
                )
            ]
        )
        mock_rate_limit_service.create_or_update_rate_limit.return_value = created_rate_limit

        # act
        response = client.post("/v1/admin/rate-limits/models/gpt-4", json=request_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["windows"][0]["max_requests"] == 100
        assert response_data["windows"][0]["max_tokens"] is None
