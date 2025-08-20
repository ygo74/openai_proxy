"""Unit tests for SQLGroupRepository."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import Mock, MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.infrastructure.db.models.group_orm import GroupORM
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.group_repository import SQLGroupRepository
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.group_mapper import GroupMapper
from tests.conftest import MockSession

class TestSQLGroupRepository:
    """Test suite for SQLGroupRepository class."""

    def setup_method(self):
        """Set up test dependencies."""
        self.mock_session = Mock()
        self.repository = SQLGroupRepository(self.mock_session)

    def test_get_by_name_found(self) -> None:
        """Test getting group by name when it exists."""
        # arrange
        name: str = "test_group"
        group_orm = GroupORM(
            id=1,
            name=name,
            description="Test Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = group_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_name(name)

        # assert
        assert result is not None
        assert result.name == name
        self.mock_session.execute.assert_called_once()

    def test_get_by_name_not_found(self) -> None:
        """Test getting group by name when it doesn't exist."""
        # arrange
        name: str = "non_existent"
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_name(name)

        # assert
        assert result is None
        self.mock_session.execute.assert_called_once()

    def test_get_by_model_id_with_groups(self) -> None:
        """Test getting groups by model ID when groups exist."""
        # arrange
        model_id: int = 1
        group_orms = [
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

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = group_orms
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_model_id(model_id)

        # assert
        assert len(result) == 2
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"
        self.mock_session.execute.assert_called_once()

    def test_get_by_model_id_no_groups(self) -> None:
        """Test getting groups by model ID when no groups exist."""
        # arrange
        model_id: int = 999

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_model_id(model_id)

        # assert
        assert len(result) == 0
        assert result == []
        self.mock_session.execute.assert_called_once()

    def test_repository_initialization(self) -> None:
        """Test repository initialization."""
        # act
        repository = SQLGroupRepository(self.mock_session)

        # assert
        assert repository._session == self.mock_session
        assert repository._orm_class == GroupORM
        assert repository._mapper == GroupMapper

    def test_get_by_id_found(self) -> None:
        """Test getting group by ID when it exists."""
        # arrange
        group_id: int = 1
        group_orm = GroupORM(
            id=group_id,
            name="Test Group",
            description="Test Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        # Set up mock for get method
        self.mock_session.get.return_value = group_orm

        # act
        result = self.repository.get_by_id(group_id)

        # assert
        assert result is not None
        assert result.id == group_id
        assert result.name == "Test Group"
        self.mock_session.get.assert_called_once_with(GroupORM, group_id)

    def test_get_by_id_not_found(self) -> None:
        """Test getting group by ID when it doesn't exist."""
        # arrange
        group_id: int = 999
        self.mock_session.get.return_value = None

        # act
        result = self.repository.get_by_id(group_id)

        # assert
        assert result is None
        self.mock_session.get.assert_called_once_with(GroupORM, group_id)

    def test_get_all_groups(self) -> None:
        """Test getting all groups."""
        # arrange
        group_orms = [
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

        # Configure the query mock
        mock_query = Mock()
        mock_query.all.return_value = group_orms
        self.mock_session.query.return_value = mock_query

        # act
        result = self.repository.get_all()

        # assert
        assert len(result) == 2
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"
        self.mock_session.query.assert_called_once_with(GroupORM)

    def test_add_group(self) -> None:
        """Test adding a new group."""
        # arrange
        group = Group(
            name="New Group",
            description="New Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            models=[]
        )

        # Mock expected ORM result after add
        added_orm = GroupORM(
            id=1,
            name="New Group",
            description="New Description",
            created=group.created,
            updated=group.updated
        )

        # Configure mocks
        def mock_add(orm_entity):
            # Set ID on the entity being added
            orm_entity.id = 1

        self.mock_session.add = MagicMock(side_effect=mock_add)

        # act
        result = self.repository.add(group)

        # assert
        assert result.name == group.name
        assert result.id == 1  # ID assigned after add
        self.mock_session.add.assert_called_once()
        self.mock_session.flush.assert_called_once()
        self.mock_session.refresh.assert_called_once()

    def test_update_group_found(self) -> None:
        """Test updating an existing group."""
        # arrange
        group = Group(
            id=1,
            name="Updated Group",
            description="Updated Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            models=[]
        )

        # Setup existing ORM entity
        existing_orm = GroupORM(
            id=1,
            name="Original Group",
            description="Original Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        # Setup updated ORM entity to be returned after update
        updated_orm = GroupORM(
            id=1,
            name="Updated Group",
            description="Updated Description",
            created=group.created,
            updated=group.updated
        )

        # Configure mocks
        self.mock_session.get.side_effect = [existing_orm, updated_orm]

        # act
        result = self.repository.update(group)

        # assert
        assert result.name == "Updated Group"
        assert result.description == "Updated Description"
        self.mock_session.get.assert_any_call(GroupORM, 1)
        self.mock_session.merge.assert_called_once()
        self.mock_session.flush.assert_called_once()

    def test_update_group_not_found(self) -> None:
        """Test updating a non-existent group."""
        # arrange
        group = Group(
            id=999,
            name="Non-existent Group",
            description="Non-existent Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            models=[]
        )

        # Configure mock to return None for get
        self.mock_session.get.return_value = None

        # act & assert
        with pytest.raises(ValueError, match=f"Entity with id 999 not found"):
            self.repository.update(group)

        self.mock_session.get.assert_called_once_with(GroupORM, 999)
        self.mock_session.merge.assert_not_called()
        self.mock_session.flush.assert_not_called()

    def test_delete_group_found(self) -> None:
        """Test removing existing group."""
        # arrange
        group_id: int = 1
        existing_orm = GroupORM(
            id=group_id,
            name="Group to Delete",
            description="Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        # Set up mock for get method
        self.mock_session.get.return_value = existing_orm

        # act
        self.repository.delete(group_id)

        # assert
        self.mock_session.get.assert_called_once_with(GroupORM, group_id)
        self.mock_session.delete.assert_called_once_with(existing_orm)
        self.mock_session.flush.assert_called_once()

    def test_delete_group_not_found(self) -> None:
        """Test removing group that doesn't exist."""
        # arrange
        group_id: int = 999

        # Set up mock for get method to return None
        self.mock_session.get.return_value = None

        # act & assert
        with pytest.raises(ValueError, match=f"Entity with id {group_id} not found"):
            self.repository.delete(group_id)

        self.mock_session.get.assert_called_once_with(GroupORM, group_id)
        self.mock_session.delete.assert_not_called()
        self.mock_session.flush.assert_not_called()