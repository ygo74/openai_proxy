"""Unit tests for SQLGroupRepository."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.infrastructure.db.models.group_orm import GroupORM
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.group_repository import SQLGroupRepository
from tests.conftest import MockSession


class TestSQLGroupRepository:
    """Test suite for SQLGroupRepository class."""

    @pytest.fixture
    def repository(self, session: MockSession) -> SQLGroupRepository:
        """Create a GroupRepository instance with mock session."""
        return SQLGroupRepository(session)

    def test_get_by_name_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting group by name when it exists."""
        # arrange
        name: str = "test_group"
        expected_group: GroupORM = GroupORM(
            id=1,
            name=name,
            description="Test Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([expected_group])

        # act
        result: Optional[Group] = repository.get_by_name(name)

        # assert
        assert result is not None
        assert result.name == name

    def test_get_by_name_not_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting group by name when it doesn't exist."""
        # arrange
        name: str = "non_existent"
        session.set_query_result([])

        # act
        result: Optional[Group] = repository.get_by_name(name)

        # assert
        assert result is None

    def test_get_by_model_id_with_groups(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting groups by model ID when groups exist."""
        # arrange
        model_id: int = 1
        groups: List[GroupORM] = [
            GroupORM(
                id=1,
                name="Group 1",
                description="Description 1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            GroupORM(
                id=2,
                name="Group 2",
                description="Description 2",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]

        # Mock the execute result
        mock_result: MagicMock = MagicMock()
        mock_result.scalars.return_value.all.return_value = groups
        session.set_execute_result(mock_result)

        # act
        result: List[Group] = repository.get_by_model_id(model_id)

        # assert
        assert len(result) == 2
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"

    def test_get_by_model_id_no_groups(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting groups by model ID when no groups exist."""
        # arrange
        model_id: int = 999

        # Mock the execute result
        mock_result: MagicMock = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.set_execute_result(mock_result)

        # act
        result: List[Group] = repository.get_by_model_id(model_id)

        # assert
        assert len(result) == 0
        assert result == []

    def test_repository_initialization(self, session: MockSession) -> None:
        """Test repository initialization."""
        # act
        repository: SQLGroupRepository = SQLGroupRepository(session)

        # assert
        assert repository._session == session
        assert repository._orm_class.__name__ == "GroupORM"
        assert repository._mapper is not None

    def test_get_by_id_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting group by ID when it exists."""
        # arrange
        group_id: int = 1
        expected_group: GroupORM = GroupORM(
            id=group_id,
            name="Test Group",
            description="Test Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([expected_group])

        # act
        result: Optional[Group] = repository.get_by_id(group_id)

        # assert
        assert result is not None
        assert result.id == group_id
        assert result.name == "Test Group"

    def test_get_by_id_not_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting group by ID when it doesn't exist."""
        # arrange
        group_id: int = 999
        session.set_query_result([])

        # act
        result: Optional[Group] = repository.get_by_id(group_id)

        # assert
        assert result is None

    def test_get_all_groups(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test getting all groups."""
        # arrange
        groups: List[GroupORM] = [
            GroupORM(
                id=1,
                name="Group 1",
                description="Description 1",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            GroupORM(
                id=2,
                name="Group 2",
                description="Description 2",
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        session.set_query_result(groups)

        # act
        result: List[Group] = repository.get_all()

        # assert
        assert len(result) == 2
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"

    def test_add_group(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test adding new group."""
        # arrange
        name: str = "Test Group"
        description: str = "Test Description"
        group: Group = Group(
            name=name,
            description=description,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        # act
        result: Group = repository.add(group)

        # assert
        assert len(session.added_items) == 1
        assert result.name == name
        assert result.description == description

    def test_update_group_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test updating existing group."""
        # arrange
        group_id: int = 1
        updated_group: Group = Group(
            id=group_id,
            name="Updated Group",
            description="Updated Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        existing_orm: GroupORM = GroupORM(
            id=group_id,
            name="Original Group",
            description="Original Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([existing_orm])

        # act
        result: Group = repository.update(updated_group)

        # assert
        assert result.name == "Updated Group"
        assert result.description == "Updated Description"

    def test_update_group_not_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test updating group that doesn't exist."""
        # arrange
        group_id: int = 999
        updated_group: Group = Group(
            id=group_id,
            name="Updated Group",
            description="Updated Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([])

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.update(updated_group)

    def test_remove_group_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test removing existing group."""
        # arrange
        group_id: int = 1
        existing_orm: GroupORM = GroupORM(
            id=group_id,
            name="Group to Delete",
            description="Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([existing_orm])

        # act
        repository.delete(group_id)

        # assert
        assert session.deleted is True

    def test_remove_group_not_found(self, repository: SQLGroupRepository, session: MockSession) -> None:
        """Test removing group that doesn't exist."""
        # arrange
        group_id: int = 999
        session.set_query_result([])

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.delete(group_id)