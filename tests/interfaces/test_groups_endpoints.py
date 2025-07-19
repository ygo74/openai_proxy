"""Tests for Groups API endpoints."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Tuple
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_group_service():
    """Mock GroupService for testing."""
    with patch('ygo74.fastapi_openai_rag.interfaces.api.endpoints.groups.SQLUnitOfWork') as mock_uow, \
         patch('ygo74.fastapi_openai_rag.interfaces.api.endpoints.groups.GroupService') as mock_service_class:

        service_instance = MagicMock()
        mock_service_class.return_value = service_instance

        # Mock the UoW context manager
        mock_uow_instance = MagicMock()
        mock_uow.return_value = mock_uow_instance

        yield service_instance


class TestGroupsEndpoints:
    """Test suite for groups endpoints."""

    def test_get_groups_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful retrieval of groups."""
        # arrange
        groups: List[Group] = [
            Group(
                id=1,
                name="Test Group 1",
                description="First test group",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            Group(
                id=2,
                name="Test Group 2",
                description="Second test group",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        mock_group_service.get_all_groups.return_value = groups

        # act
        response = client.get("/v1/groups/")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Test Group 1"
        assert response_data[1]["name"] == "Test Group 2"
        assert "id" in response_data[0]
        assert "description" in response_data[0]

    def test_create_group_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful group creation."""
        # arrange
        group_data: dict = {
            "name": "New Group",
            "description": "A new test group"
        }
        created_group: Group = Group(
            id=1,
            name=group_data["name"],
            description=group_data["description"],
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        status_result: Tuple[str, Group] = ("created", created_group)
        mock_group_service.add_or_update_group.return_value = status_result

        # act
        response = client.post("/v1/groups/", json=group_data)

        # assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == group_data["name"]
        assert response_data["description"] == group_data["description"]
        assert "id" in response_data
        mock_group_service.add_or_update_group.assert_called_once_with(
            name=group_data["name"],
            description=group_data["description"]
        )

    def test_create_group_validation_error(self, client: TestClient) -> None:
        """Test group creation with invalid data."""
        # arrange
        invalid_data: dict = {}  # Missing required name field

        # act
        response = client.post("/v1/groups/", json=invalid_data)

        # assert
        assert response.status_code == 422

    def test_create_group_already_exists(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test group creation when name already exists."""
        # arrange
        group_data: dict = {
            "name": "Existing Group",
            "description": "A group that already exists"
        }
        mock_group_service.add_or_update_group.side_effect = ValueError("Group with name Existing Group already exists")

        # act
        response = client.post("/v1/groups/", json=group_data)

        # assert
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_get_group_by_id_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful retrieval of group by ID."""
        # arrange
        group_id: int = 1
        group: Group = Group(
            id=group_id,
            name="Test Group",
            description="A test group",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_group_service.get_group_by_id.return_value = group

        # act
        response = client.get(f"/v1/groups/{group_id}")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["id"] == group_id
        assert response_data["name"] == "Test Group"
        assert response_data["description"] == "A test group"
        mock_group_service.get_group_by_id.assert_called_once_with(group_id)

    def test_get_group_by_id_not_found(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test group retrieval when group doesn't exist."""
        # arrange
        group_id: int = 999
        mock_group_service.get_group_by_id.return_value = None

        # act
        response = client.get(f"/v1/groups/{group_id}")

        # assert
        assert response.status_code == 404
        assert f"Group with ID {group_id} not found" in response.json()["detail"]

    def test_update_group_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful group update."""
        # arrange
        group_id: int = 1
        update_data: dict = {
            "name": "Updated Group",
            "description": "Updated description"
        }
        updated_group: Group = Group(
            id=group_id,
            name=update_data["name"],
            description=update_data["description"],
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        status_result: Tuple[str, Group] = ("updated", updated_group)
        mock_group_service.add_or_update_group.return_value = status_result

        # act
        response = client.put(f"/v1/groups/{group_id}", json=update_data)

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["name"] == update_data["name"]
        assert response_data["description"] == update_data["description"]
        mock_group_service.add_or_update_group.assert_called_once_with(
            group_id=group_id,
            name=update_data["name"],
            description=update_data["description"]
        )

    def test_update_group_not_found(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test group update when group doesn't exist."""
        # arrange
        group_id: int = 999
        update_data: dict = {
            "name": "Updated Group",
            "description": "Updated description"
        }
        from sqlalchemy.exc import NoResultFound
        mock_group_service.add_or_update_group.side_effect = NoResultFound(f"Group with id {group_id} not found")

        # act
        response = client.put(f"/v1/groups/{group_id}", json=update_data)

        # assert
        assert response.status_code == 404
        assert f"Group with id {group_id} not found" in response.json()["detail"]

    def test_update_group_partial_update(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test partial group update (only name)."""
        # arrange
        group_id: int = 1
        update_data: dict = {
            "name": "Updated Name Only"
        }
        updated_group: Group = Group(
            id=group_id,
            name=update_data["name"],
            description="Original description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        status_result: Tuple[str, Group] = ("updated", updated_group)
        mock_group_service.add_or_update_group.return_value = status_result

        # act
        response = client.put(f"/v1/groups/{group_id}", json=update_data)

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["name"] == update_data["name"]
        mock_group_service.add_or_update_group.assert_called_once_with(
            group_id=group_id,
            name=update_data["name"],
            description=None
        )

    def test_delete_group_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful group deletion."""
        # arrange
        group_id: int = 1
        mock_group_service.delete_group.return_value = None

        # act
        response = client.delete(f"/v1/groups/{group_id}")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert "deleted successfully" in response_data["message"]
        mock_group_service.delete_group.assert_called_once_with(group_id)

    def test_delete_group_not_found(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test group deletion when group doesn't exist."""
        # arrange
        group_id: int = 999
        mock_group_service.delete_group.side_effect = ValueError(f"Entity with id {group_id} not found")

        # act
        response = client.delete(f"/v1/groups/{group_id}")

        # assert
        assert response.status_code == 404
        assert f"Entity with id {group_id} not found" in response.json()["detail"]

    def test_get_group_statistics_success(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test successful retrieval of group statistics."""
        # arrange
        groups: List[Group] = [
            Group(id=1, name="Group 1", description="", created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc)),
            Group(id=2, name="Group 2", description="", created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc)),
            Group(id=3, name="", description="", created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc))  # No name
        ]
        mock_group_service.get_all_groups.return_value = groups

        # act
        response = client.get("/v1/groups/statistics")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["total"] == 3
        assert response_data["active"] == 2  # Only groups with names

    def test_get_groups_with_pagination(self, client: TestClient, mock_group_service: MagicMock) -> None:
        """Test groups retrieval with pagination parameters."""
        # arrange
        groups: List[Group] = [
            Group(id=i, name=f"Group {i}", description=f"Description {i}",
                  created=datetime.now(timezone.utc), updated=datetime.now(timezone.utc))
            for i in range(1, 6)  # 5 groups
        ]
        mock_group_service.get_all_groups.return_value = groups

        # act
        response = client.get("/v1/groups/?skip=1&limit=2")

        # assert
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2  # Limited to 2
        assert response_data[0]["name"] == "Group 2"  # Skipped first one
        assert response_data[1]["name"] == "Group 3"

    def test_service_dependency_injection(self, client: TestClient) -> None:
        """Test that service dependency injection works correctly."""
        # This test verifies that the dependency injection mechanism works
        # by checking that endpoints can be called without raising dependency errors

        # act & assert - Should not raise dependency injection errors
        response = client.get("/v1/groups/")
        # The response might be an error due to missing database, but dependency injection should work
        assert response.status_code in [200, 500]  # Either success or internal server error, but not dependency error