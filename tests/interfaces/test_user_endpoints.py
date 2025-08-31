"""Tests for user endpoints."""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from src.ygo74.fastapi_openai_rag.domain.models.user import User, ApiKey
from src.ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from src.ygo74.fastapi_openai_rag.domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from src.ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser
from src.ygo74.fastapi_openai_rag.interfaces.api.endpoints.users import router, get_user_service, require_admin_role

# Mock the dependencies to avoid database calls in tests
@pytest.fixture
def mock_user_service():
    """Mock UserService for testing."""
    return Mock()

@pytest.fixture
def client(mock_user_service):
    """Create test client with mocked dependencies."""
    from src.ygo74.fastapi_openai_rag.main import app
    from src.ygo74.fastapi_openai_rag.interfaces.api.endpoints.users import get_user_service

    # Override the dependency
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    app.dependency_overrides[require_admin_role] = lambda: AuthenticatedUser(id="user1", username="admin", groups=["admin"], type="jwt")  # type: ignore

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()

class TestUserEndpoints:
    """Tests for user endpoints."""

    def test_get_users_success(self, client, mock_user_service):
        """Test successful retrieval of users."""
        # arrange
        users = [
            User(
                id="user-1",
                username="user1",
                email="user1@example.com",
                created_at=datetime.now(timezone.utc),
                groups=["admin"],
                api_keys=[]
            ),
            User(
                id="user-2",
                username="user2",
                email="user2@example.com",
                created_at=datetime.now(timezone.utc),
                groups=["user"],
                api_keys=[]
            )
        ]
        mock_user_service.get_active_users.return_value = users

        # act
        response = client.get("/v1/admin/users/")

        # assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["username"] == "user1"
        assert data[0]["email"] == "user1@example.com"
        assert data[0]["groups"] == ["admin"]

    def test_create_user_success(self, client, mock_user_service):
        """Test successful user creation."""
        # arrange
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "groups": ["user"]
        }
        created_user = User(
            id="user-123",
            username="newuser",
            email="newuser@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            groups=["user"]
        )
        mock_user_service.add_or_update_user.return_value = ("created", created_user)

        # act
        response = client.post("/v1/admin/users/", json=user_data)

        # assert
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["groups"] == ["user"]
        mock_user_service.add_or_update_user.assert_called_once_with(
            username="newuser",
            email="newuser@example.com",
            groups=["user"]
        )

    def test_create_user_duplicate_username(self, client, mock_user_service):
        """Test user creation with duplicate username."""
        # arrange
        user_data = {
            "username": "existing_user"
        }
        mock_user_service.add_or_update_user.side_effect = EntityAlreadyExistsError("User", "username existing_user")

        # act
        response = client.post("/v1/admin/users/", json=user_data)

        # assert
        assert response.status_code == 409

    def test_get_user_by_id_success(self, client, mock_user_service):
        """Test successful user retrieval by ID."""
        # arrange
        user_id = "user-123"
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            groups=["admin"],
            api_keys=[]
        )
        mock_user_service.get_user_by_id.return_value = user

        # act
        response = client.get(f"/v1/admin/users/{user_id}")

        # assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_get_user_by_id_not_found(self, client, mock_user_service):
        """Test user retrieval by ID when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_user_service.get_user_by_id.side_effect = EntityNotFoundError("User", user_id)

        # act
        response = client.get(f"/v1/admin/users/{user_id}")

        # assert
        assert response.status_code == 404

    def test_update_user_success(self, client, mock_user_service):
        """Test successful user update."""
        # arrange
        user_id = "user-123"
        update_data = {
            "email": "updated@example.com",
            "groups": ["admin", "user"]
        }
        updated_user = User(
            id=user_id,
            username="testuser",
            email="updated@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            groups=["admin", "user"]
        )
        mock_user_service.add_or_update_user.return_value = ("updated", updated_user)

        # act
        response = client.put(f"/v1/admin/users/{user_id}", json=update_data)

        # assert
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["groups"] == ["admin", "user"]

    def test_delete_user_success(self, client, mock_user_service):
        """Test successful user deletion."""
        # arrange
        user_id = "user-123"

        # act
        response = client.delete(f"/v1/admin/users/{user_id}")

        # assert
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]
        mock_user_service.delete_user.assert_called_once_with(user_id)

    def test_create_api_key_success(self, client, mock_user_service):
        """Test successful API key creation."""
        # arrange
        user_id = "user-123"
        api_key_data = {
            "name": "Test Key"
        }
        api_key = ApiKey(
            id="key-456",
            key_hash="hash",
            name="Test Key",
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
        plain_key = "sk-test-key-123"
        mock_user_service.create_api_key.return_value = (plain_key, api_key)

        # act
        response = client.post(f"/v1/admin/users/{user_id}/api-keys", json=api_key_data)

        # assert
        assert response.status_code == 201
        data = response.json()
        assert data["api_key"] == plain_key
        assert data["key_info"]["name"] == "Test Key"
        assert data["key_info"]["is_active"] is True

    def test_get_user_statistics_success(self, client, mock_user_service):
        """Test successful user statistics retrieval."""
        # arrange
        all_users = [
            User(id="1", username="user1", is_active=True, created_at=datetime.now(timezone.utc), api_keys=[]),
            User(id="2", username="user2", is_active=False, created_at=datetime.now(timezone.utc), api_keys=[])
        ]
        active_users = [user for user in all_users if user.is_active]

        mock_user_service.get_all_users.return_value = all_users
        mock_user_service.get_active_users.return_value = active_users

        # act
        response = client.get("/v1/admin/users/statistics")

        # assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 2
        assert data["active_users"] == 1
        assert data["inactive_users"] == 1
        assert data["inactive_users"] == 1

    def test_add_user_groups_endpoint_success(self, client, mock_user_service):
        """Add groups to a user returns updated user."""
        user_id = "u-1"
        updated_user = User(
            id=user_id,
            username="john",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True,
            groups=["user", "admin", "editor"]
        )
        mock_user_service.add_user_groups.return_value = updated_user

        resp = client.post(f"/v1/admin/users/{user_id}/groups/add", json={"groups": ["admin", "editor"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user_id
        assert data["groups"] == ["user", "admin", "editor"]
        mock_user_service.add_user_groups.assert_called_once_with(user_id, ["admin", "editor"])

    def test_remove_user_groups_endpoint_success(self, client, mock_user_service):
        """Remove groups from a user returns updated user."""
        user_id = "u-2"
        updated_user = User(
            id=user_id,
            username="jane",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_active=True,
            groups=["user"]
        )
        mock_user_service.remove_user_groups.return_value = updated_user

        resp = client.post(f"/v1/admin/users/{user_id}/groups/remove", json={"groups": ["editor", "viewer"]})

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user_id
        assert data["groups"] == ["user"]
        mock_user_service.remove_user_groups.assert_called_once_with(user_id, ["editor", "viewer"])

    def test_add_user_groups_endpoint_user_not_found(self, client, mock_user_service):
        """Adding groups to a missing user returns 404 via endpoint handler."""
        user_id = "missing"
        mock_user_service.add_user_groups.side_effect = EntityNotFoundError("User", user_id)

        resp = client.post(f"/v1/admin/users/{user_id}/groups/add", json={"groups": ["admin"]})

        assert resp.status_code == 404

    def test_remove_user_groups_endpoint_user_not_found(self, client, mock_user_service):
        """Removing groups for a missing user returns 404 via endpoint handler."""
        user_id = "missing"
        mock_user_service.remove_user_groups.side_effect = EntityNotFoundError("User", user_id)

        resp = client.post(f"/v1/admin/users/{user_id}/groups/remove", json={"groups": ["admin"]})

        assert resp.status_code == 404
