from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import NoResultFound
from src.infrastructure.group_crud import GroupRepository
from src.core.models.domain import Group
from src.infrastructure.db.models.group_orm import GroupORM

class TestGroupRepository:
    """Test suite for GroupRepository class"""

    @pytest.fixture
    def repository(self, session):
        """Create a GroupRepository instance with mock session"""
        return GroupRepository(session)

    def test_create_group_success(self, repository, session):
        """Test successful group creation"""
        # Arrange
        name = "Test Group"
        description = "Test Description"

        # Act
        group = repository.create(name, description)

        # Assert
        assert session.committed
        assert len(session.added_items) == 1
        assert isinstance(session.added_items[0], GroupORM)
        assert group.name == name
        assert group.description == description
        assert isinstance(group.created, datetime)
        assert isinstance(group.updated, datetime)

    def test_get_group_by_id_exists(self, repository, session):
        """Test retrieving an existing group by ID"""
        # Arrange
        group_orm = GroupORM(
            id=1,
            name="Test Group",
            description="Test Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([group_orm])

        # Act
        result = repository.get_by_id(1)

        # Assert
        assert result is not None
        assert result.name == group_orm.name
        assert result.description == group_orm.description

    def test_get_group_by_id_not_exists(self, repository, session):
        """Test retrieving a non-existing group by ID"""
        # Arrange
        session.set_query_result([])

        # Act
        result = repository.get_by_id(999)

        # Assert
        assert result is None

    def test_get_all_groups(self, repository, session):
        """Test retrieving all groups"""
        # Arrange
        groups = [
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

        # Act
        result = repository.get_all()

        # Assert
        assert len(result) == 2
        assert all(isinstance(g, Group) for g in result)
        assert result[0].name == "Group 1"
        assert result[1].name == "Group 2"

    def test_update_group_success(self, repository, session):
        """Test successful group update"""
        # Arrange
        original_group = GroupORM(
            id=1,
            name="Original Name",
            description="Original Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([original_group])

        updated_group = Group(
            name="Updated Name",
            description="Updated Description",
            created=original_group.created,
            updated=datetime.now(timezone.utc)
        )

        # Act
        result = repository.update(1, updated_group)

        # Assert
        assert session.committed
        assert result.name == "Updated Name"
        assert result.description == "Updated Description"

    def test_update_group_not_found(self, repository, session):
        """Test updating a non-existing group"""
        # Arrange
        session.set_query_result([])
        updated_group = Group(
            name="Updated Name",
            description="Updated Description",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

        # Act & Assert
        with pytest.raises(NoResultFound):
            repository.update(999, updated_group)

    def test_delete_group_success(self, repository, session):
        """Test successful group deletion"""
        # Arrange
        session.set_deleted(True)

        # Act
        repository.delete(1)

        # Assert
        assert session.committed

    def test_delete_group_not_found(self, repository, session):
        """Test deleting a non-existing group"""
        # Arrange
        session.set_deleted(False)

        # Act & Assert
        with pytest.raises(NoResultFound):
            repository.delete(999)