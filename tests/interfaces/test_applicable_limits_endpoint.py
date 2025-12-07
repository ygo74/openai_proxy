"""Tests for GET /admin/rate-limits/applicable endpoint.

Tests the hierarchical limit query endpoint that shows which limits
would be applied for a given group/model combination.
"""
import sys
import os
from datetime import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.main import app
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_rate_limit_service():
    """Mock RateLimitService for testing."""
    return MagicMock()


@pytest.fixture
def mock_admin_auth(client, mock_rate_limit_service):
    """Mock admin authentication and rate limit service using dependency_overrides."""
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


def test_get_applicable_limits_returns_all_hierarchy_levels(client, mock_admin_auth, mock_rate_limit_service):
    """Test that endpoint returns all three hierarchy levels when all exist.

    Verifies that the API correctly queries and returns group+model, model,
    and global limits, and correctly identifies the effective limit.
    """
    # Arrange
    group_model_limit = RateLimit(
        id=1,
        scope_type="group_model",
        scope_id="team-a:gpt-4",
        enabled=True,
        windows=[RateLimitWindow(
            id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=50000
        )]
    )

    model_limit = RateLimit(
        id=2,
        scope_type="model",
        scope_id="gpt-4",
        enabled=True,
        windows=[RateLimitWindow(
            id=2,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=250000
        )]
    )

    global_limit = RateLimit(
        id=3,
        scope_type="global",
        scope_id=None,
        enabled=True,
        windows=[RateLimitWindow(
            id=3,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )]
    )

    # Mock service.get_applicable_limits() to return all levels
    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': group_model_limit,
        'model': model_limit,
        'global': global_limit
    }

    # Act
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"group_id": "team-a", "model_id": "gpt-4"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    # Verify request context
    assert data['group_id'] == "team-a"
    assert data['model_id'] == "gpt-4"

    # Verify all three levels returned
    assert data['group_model_limit'] is not None
    assert data['group_model_limit']['scope_type'] == "group_model"
    assert data['group_model_limit']['windows'][0]['max_requests'] == 100

    assert data['model_limit'] is not None
    assert data['model_limit']['scope_type'] == "model"
    assert data['model_limit']['windows'][0]['max_requests'] == 500

    assert data['global_limit'] is not None
    assert data['global_limit']['scope_type'] == "global"
    assert data['global_limit']['windows'][0]['max_requests'] == 1000

    # Verify effective limit is the most specific (group+model)
    assert data['effective_limit'] is not None
    assert data['effective_limit']['scope_type'] == "group_model"
    assert data['effective_limit']['windows'][0]['max_requests'] == 100


def test_get_applicable_limits_with_missing_group_model(client, mock_admin_auth, mock_rate_limit_service):
    """Test endpoint when group+model limit doesn't exist.

    Verifies that effective_limit correctly falls back to model limit
    when no group+model limit is configured.
    """
    # Arrange
    model_limit = RateLimit(
        id=2,
        scope_type="model",
        scope_id="gpt-4",
        enabled=True,
        windows=[RateLimitWindow(
            id=2,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=250000
        )]
    )

    global_limit = RateLimit(
        id=3,
        scope_type="global",
        scope_id=None,
        enabled=True,
        windows=[RateLimitWindow(
            id=3,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )]
    )

    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': None,  # Missing
        'model': model_limit,
        'global': global_limit
    }

    # Act
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"group_id": "team-a", "model_id": "gpt-4"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data['group_model_limit'] is None  # Missing
    assert data['model_limit'] is not None
    assert data['global_limit'] is not None

    # Effective limit should be model (fallback from missing group+model)
    assert data['effective_limit'] is not None
    assert data['effective_limit']['scope_type'] == "model"
    assert data['effective_limit']['windows'][0]['max_requests'] == 500


def test_get_applicable_limits_with_only_global(client, mock_admin_auth, mock_rate_limit_service):
    """Test endpoint when only global limit exists.

    Verifies fallback to global limit when no specific limits configured.
    """
    # Arrange
    global_limit = RateLimit(
        id=3,
        scope_type="global",
        scope_id=None,
        enabled=True,
        windows=[RateLimitWindow(
            id=3,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )]
    )

    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': None,
        'model': None,
        'global': global_limit
    }

    # Act
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"group_id": "team-a", "model_id": "gpt-4"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data['group_model_limit'] is None
    assert data['model_limit'] is None
    assert data['global_limit'] is not None

    # Effective limit should be global (last fallback)
    assert data['effective_limit'] is not None
    assert data['effective_limit']['scope_type'] == "global"


def test_get_applicable_limits_without_group_id(client, mock_admin_auth, mock_rate_limit_service):
    """Test endpoint with only model_id (no group_id).

    Verifies that group+model limit is skipped when group_id not provided.
    """
    # Arrange
    model_limit = RateLimit(
        id=2,
        scope_type="model",
        scope_id="gpt-4",
        enabled=True,
        windows=[RateLimitWindow(
            id=2,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=250000
        )]
    )

    global_limit = RateLimit(
        id=3,
        scope_type="global",
        scope_id=None,
        enabled=True,
        windows=[RateLimitWindow(
            id=3,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )]
    )

    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': None,  # Skipped because no group_id
        'model': model_limit,
        'global': global_limit
    }

    # Act - no group_id parameter
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"model_id": "gpt-4"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data['group_id'] is None  # Not provided
    assert data['model_id'] == "gpt-4"

    assert data['group_model_limit'] is None  # Skipped
    assert data['model_limit'] is not None
    assert data['global_limit'] is not None

    # Effective is model (group+model skipped)
    assert data['effective_limit']['scope_type'] == "model"


def test_get_applicable_limits_with_no_parameters(client, mock_admin_auth, mock_rate_limit_service):
    """Test endpoint with no parameters (only global queried).

    Verifies that only global limit is returned when no identifiers provided.
    """
    # Arrange
    global_limit = RateLimit(
        id=3,
        scope_type="global",
        scope_id=None,
        enabled=True,
        windows=[RateLimitWindow(
            id=3,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )]
    )

    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': None,
        'model': None,
        'global': global_limit
    }

    # Act - no parameters
    response = client.get("/v1/admin/rate-limits/applicable")

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data['group_id'] is None
    assert data['model_id'] is None

    assert data['group_model_limit'] is None
    assert data['model_limit'] is None
    assert data['global_limit'] is not None

    # Only global available
    assert data['effective_limit']['scope_type'] == "global"


def test_get_applicable_limits_with_no_limits_configured(client, mock_admin_auth, mock_rate_limit_service):
    """Test endpoint when no limits are configured at all.

    Verifies correct response when all hierarchy levels return None.
    """
    # Arrange
    mock_rate_limit_service.get_applicable_limits.return_value = {
        'group_model': None,
        'model': None,
        'global': None
    }

    # Act
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"group_id": "team-a", "model_id": "gpt-4"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert data['group_model_limit'] is None
    assert data['model_limit'] is None
    assert data['global_limit'] is None
    assert data['effective_limit'] is None  # No limits configured


def test_get_applicable_limits_requires_admin_role(client):
    """Test that endpoint requires admin authentication.

    Verifies HTTP 401/403 when not authenticated as admin.
    """
    # Act - no auth mock, should fail
    response = client.get(
        "/v1/admin/rate-limits/applicable",
        params={"model_id": "gpt-4"}
    )

    # Assert - should require authentication
    # Note: Actual status code depends on auth middleware config (401 or 403)
    assert response.status_code in [401, 403]
