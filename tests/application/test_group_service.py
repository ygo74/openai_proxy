"""Tests for GroupService class."""
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock, Mock
import pytest
from sqlalchemy.exc import NoResultFound

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.application.services.group_service import GroupService
from ygo74.fastapi_openai_rag.domain.repositories.group_repository import IGroupRepository
from ygo74.fastapi_openai_rag.domain.unit_of_work import UnitOfWork


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self) -> None:
        self.session: Mock = Mock()
        self.committed: bool = False
        self.rolled_back: bool = False

    def __enter__(self) -> 'MockUnitOfWork':
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestGroupService:
    """Test suite for GroupService."""

    @pytest.fixture
    def mock_uow(self) -> MockUnitOfWork:
        """Create a mock Unit of Work."""
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository with all necessary methods."""
        repository = Mock()
        # Explicitly add the methods that will be called
        repository.get_by_name = Mock()
        repository.get_by_id = Mock()
        repository.get_all = Mock()
        repository.add = Mock()
        repository.update = Mock()
        repository.remove = Mock()
        repository.get_by_model_id = Mock()
        return repository

    @pytest.fixture
    def mock_repository_factory(self, mock_repository: Mock) -> Mock:
        """Create a mock repository factory."""
        factory: Mock = Mock()
        factory.return_value = mock_repository
        return factory

    @pytest.fixture
    def service(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> GroupService:
        """Create a GroupService instance with mocks."""
        return GroupService(mock_uow, mock_repository_factory)

    def test_add_group_success(self, service: GroupService, mock_repository: Mock) -> None:
        """Test successful group creation."""
        # arrange
        name: str = "test-group"
        description: str = "Test description"
        new_group: Group = Group(
            id=1,
            name=name,
            description=description,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_name.return_value = None
        mock_repository.add.return_value = new_group

        # act
        status, result_group = service.add_or_update_group(
            name=name,
            description=description
        )

        # assert
        assert status == "created"
        assert result_group == new_group
        mock_repository.add.assert_called_once()
        mock_repository.get_by_name.assert_called_once_with(name)

    def test_add_group_already_exists(self, service: GroupService, mock_repository: Mock) -> None:
        """Test group creation with existing name."""
        # arrange
        name: str = "existing-group"
        existing_group: Group = Group(
            id=1,
            name=name,
            description="Existing description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_name.return_value = existing_group

        # act & assert
        with pytest.raises(ValueError, match=f"Group with name {name} already exists"):
            service.add_or_update_group(name=name, description="New description")

    def test_add_group_missing_name(self, service: GroupService, mock_repository: Mock) -> None:
        """Test group creation without name."""
        # act & assert
        with pytest.raises(ValueError, match="Name is required for new groups"):
            service.add_or_update_group(description="Test description")

    def test_update_group_success(self, service: GroupService, mock_repository: Mock) -> None:
        """Test successful group update."""
        # arrange
        group_id: int = 1
        updated_name: str = "updated-group"
        updated_description: str = "Updated description"
        existing_group: Group = Group(
            id=group_id,
            name="original-group",
            description="Original description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        updated_group: Group = Group(
            id=group_id,
            name=updated_name,
            description=updated_description,
            created=existing_group.created,
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = existing_group
        mock_repository.update.return_value = updated_group

        # act
        status, result_group = service.add_or_update_group(
            group_id=group_id,
            name=updated_name,
            description=updated_description
        )

        # assert
        assert status == "updated"
        assert result_group.name == updated_name
        assert result_group.description == updated_description
        mock_repository.get_by_id.assert_called_once_with(group_id)
        mock_repository.update.assert_called_once()

    def test_update_group_not_found(self, service: GroupService, mock_repository: Mock) -> None:
        """Test group update with non-existent group."""
        # arrange
        group_id: int = 999
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(NoResultFound, match=f"Group with id {group_id} not found"):
            service.add_or_update_group(
                group_id=group_id,
                name="test-group",
                description="Test description"
            )

    def test_update_group_partial_update(self, service: GroupService, mock_repository: Mock) -> None:
        """Test partial group update (only name or description)."""
        # arrange
        group_id: int = 1
        new_name: str = "updated-name"
        existing_group: Group = Group(
            id=group_id,
            name="original-name",
            description="original-description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        updated_group: Group = Group(
            id=group_id,
            name=new_name,
            description="original-description",  # Should keep original
            created=existing_group.created,
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = existing_group
        mock_repository.update.return_value = updated_group

        # act
        status, result_group = service.add_or_update_group(
            group_id=group_id,
            name=new_name
            # description not provided - should keep original
        )

        # assert
        assert status == "updated"
        assert result_group.name == new_name
        assert result_group.description == "original-description"

    def test_get_all_groups(self, service: GroupService, mock_repository: Mock) -> None:
        """Test getting all groups."""
        # arrange
        groups: List[Group] = [
            Group(
                id=1,
                name="group1",
                description="Description 1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            Group(
                id=2,
                name="group2",
                description="Description 2",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        mock_repository.get_all.return_value = groups

        # act
        result: List[Group] = service.get_all_groups()

        # assert
        assert len(result) == 2
        assert result[0].name == "group1"
        assert result[1].name == "group2"
        assert isinstance(result[0], Group)
        assert isinstance(result[1], Group)
        mock_repository.get_all.assert_called_once()

    def test_get_all_groups_empty(self, service: GroupService, mock_repository: Mock) -> None:
        """Test getting all groups when none exist."""
        # arrange
        mock_repository.get_all.return_value = []

        # act
        result: List[Group] = service.get_all_groups()

        # assert
        assert len(result) == 0
        assert result == []

    def test_delete_group_success(self, service: GroupService, mock_repository: Mock) -> None:
        """Test successful group deletion."""
        # arrange
        group_id: int = 1

        # act
        service.delete_group(group_id)

        # assert
        mock_repository.remove.assert_called_once_with(group_id)

    def test_unit_of_work_commit_on_success(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> None:
        """Test that Unit of Work commits on successful operation."""
        # arrange
        service: GroupService = GroupService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.return_value = []

        # act
        service.get_all_groups()

        # assert
        assert mock_uow.committed is True
        assert mock_uow.rolled_back is False

    def test_unit_of_work_rollback_on_exception(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> None:
        """Test that Unit of Work rolls back on exception."""
        # arrange
        service: GroupService = GroupService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.side_effect = Exception("Database error")

        # act & assert
        with pytest.raises(Exception, match="Database error"):
            service.get_all_groups()

        assert mock_uow.rolled_back is True
        assert mock_uow.committed is False

    def test_get_group_by_id(self, service: GroupService, mock_repository: Mock) -> None:
        """Test getting group by ID."""
        # arrange
        group_id: int = 1
        expected_group: Group = Group(
            id=group_id,
            name="test-group",
            description="Test description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_id.return_value = expected_group

        # act
        result: Optional[Group] = service.get_group_by_id(group_id)

        # assert
        assert result == expected_group
        mock_repository.get_by_id.assert_called_once_with(group_id)

    def test_get_group_by_name(self, service: GroupService, mock_repository: Mock) -> None:
        """Test getting group by name."""
        # arrange
        name: str = "test-group"
        expected_group: Group = Group(
            id=1,
            name=name,
            description="Test description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        mock_repository.get_by_name.return_value = expected_group

        # act
        result: Optional[Group] = service.get_group_by_name(name)

        # assert
        assert result == expected_group
        mock_repository.get_by_name.assert_called_once_with(name)