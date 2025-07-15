from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.core.models.domain import Group
from src.core.application.group_service import GroupService
from src.infrastructure.group_crud import GroupRepository
from sqlalchemy.exc import NoResultFound
import pytest
from typing import Dict, Any, List

@pytest.fixture
def mock_repository() -> MagicMock:
    """Create a mock repository."""
    return MagicMock(spec=GroupRepository)

@pytest.fixture
def group_service(mock_repository: MagicMock) -> GroupService:
    """Create a GroupService instance with a mock repository."""
    mock_session = MagicMock()
    return GroupService(mock_session, repository=mock_repository)

def test_add_group_success(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test the successful addition of a new group."""
    # Arrange
    name = "test-group"
    description = "Test group"
    new_group = Group(
        id=1,
        name=name,
        description=description,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    mock_repository.create.return_value = new_group
    mock_repository.get_all.return_value = []

    # Act
    result: Dict[str, Any] = group_service.add_or_update_group(name=name, description=description)

    # Assert
    assert result["status"] == "created"
    assert result["group"] == new_group
    mock_repository.create.assert_called_once_with(name, description)

def test_add_group_already_exists(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test adding a group that already exists."""
    # Arrange
    name = "test-group"
    description = "Test group"
    existing_group = Group(
        id=1,
        name=name,
        description=description,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc)
    )
    mock_repository.get_all.return_value = [existing_group]

    # Act & Assert
    with pytest.raises(ValueError, match=f"Group with name {name} already exists"):
        group_service.add_or_update_group(name=name, description=description)

def test_get_all_groups(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test retrieving all groups."""
    # Arrange
    groups = [
        Group(
            id=1,
            name="group1",
            description="Group 1",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        ),
        Group(
            id=2,
            name="group2",
            description="Group 2",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
    ]
    mock_repository.get_all.return_value = groups

    # Act
    result: List[Dict[str, Any]] = group_service.get_all_groups()

    # Assert
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2
    mock_repository.get_all.assert_called_once()

def test_delete_group_success(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test successful group deletion."""
    # Arrange
    group_id = 1
    mock_repository.delete.return_value = None

    # Act
    result: Dict[str, str] = group_service.delete_group(group_id)

    # Assert
    assert result["status"] == "deleted"
    mock_repository.delete.assert_called_once_with(group_id)

def test_delete_group_not_found(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test deleting a non-existent group."""
    # Arrange
    group_id = 999
    mock_repository.delete.side_effect = NoResultFound(f"Group with id {group_id} not found")

    # Act & Assert
    with pytest.raises(NoResultFound):
        group_service.delete_group(group_id)

def test_update_group_success(group_service: GroupService, mock_repository: MagicMock) -> None:
    """Test successful group update."""
    # Arrange
    group_id = 1
    name = "updated-group"
    description = "Updated description"
    now = datetime.now(timezone.utc)

    existing_group = Group(
        id=group_id,
        name="old-name",
        description="Old description",
        created=now,
        updated=now
    )

    updated_group = Group(
        id=group_id,
        name=name,
        description=description,
        created=now,
        updated=now
    )

    mock_repository.get_by_id.return_value = existing_group
    mock_repository.update.return_value = updated_group

    # Act
    result: Dict[str, Any] = group_service.add_or_update_group(group_id=group_id, name=name, description=description)

    # Assert
    assert result["status"] == "updated"
    assert result["group"] == updated_group
    mock_repository.get_by_id.assert_called_once_with(group_id)
    mock_repository.update.assert_called_once()