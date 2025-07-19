"""Unit tests for SQLBaseRepository."""
import sys
import os
import pytest
from unittest.mock import Mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository


class MockDomainEntity:
    """Mock domain entity for testing."""
    def __init__(self, id: int = None, name: str = "test"):
        self.id = id
        self.name = name


class MockORMEntity:
    """Mock ORM entity for testing."""
    def __init__(self, id: int = None, name: str = "test"):
        self.id = id
        self.name = name


def test_base_repository_get_by_id_found():
    """Test getting entity by ID when found."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    mock_orm_entity = MockORMEntity(1, "test")
    mock_domain_entity = MockDomainEntity(1, "test")

    mock_session.query.return_value.get.return_value = mock_orm_entity
    mock_mapper.to_domain.return_value = mock_domain_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_by_id(1)

    # assert
    assert result == mock_domain_entity
    mock_session.query.assert_called_once_with(MockORMEntity)
    mock_mapper.to_domain.assert_called_once_with(mock_orm_entity)


def test_base_repository_get_by_id_not_found():
    """Test getting entity by ID when not found."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()

    mock_session.query.return_value.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_by_id(1)

    # assert
    assert result is None
    mock_mapper.to_domain.assert_not_called()


def test_base_repository_get_all():
    """Test getting all entities."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    mock_orm_entities = [MockORMEntity(1, "test1"), MockORMEntity(2, "test2")]
    mock_domain_entities = [MockDomainEntity(1, "test1"), MockDomainEntity(2, "test2")]

    mock_session.query.return_value.all.return_value = mock_orm_entities
    mock_mapper.to_domain_list.return_value = mock_domain_entities

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_all()

    # assert
    assert result == mock_domain_entities
    mock_session.query.assert_called_once_with(MockORMEntity)
    mock_mapper.to_domain_list.assert_called_once_with(mock_orm_entities)


def test_base_repository_add():
    """Test adding new entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    domain_entity = MockDomainEntity(None, "test")
    orm_entity = MockORMEntity(1, "test")
    returned_entity = MockDomainEntity(1, "test")

    mock_mapper.to_orm.return_value = orm_entity
    mock_mapper.to_domain.return_value = returned_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.add(domain_entity)

    # assert
    assert result == returned_entity
    mock_session.add.assert_called_once_with(orm_entity)
    mock_session.flush.assert_called_once()
    mock_mapper.to_orm.assert_called_once_with(domain_entity)
    mock_mapper.to_domain.assert_called_once_with(orm_entity)


def test_base_repository_update_found():
    """Test updating existing entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    domain_entity = MockDomainEntity(1, "updated")
    orm_entity = MockORMEntity(1, "test")
    updated_orm = MockORMEntity(1, "updated")
    returned_entity = MockDomainEntity(1, "updated")

    mock_session.query.return_value.get.return_value = orm_entity
    mock_mapper.to_orm.return_value = updated_orm
    mock_mapper.to_domain.return_value = returned_entity

    # Mock __dict__ to simulate attribute updates
    setattr(updated_orm, '__dict__', {"id": 1, "name": "updated"})

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.update(domain_entity)

    # assert
    assert result == returned_entity
    mock_session.flush.assert_called_once()
    mock_mapper.to_domain.assert_called_once_with(orm_entity)


def test_base_repository_update_not_found():
    """Test updating non-existent entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    domain_entity = MockDomainEntity(1, "updated")

    mock_session.query.return_value.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act & assert
    with pytest.raises(ValueError, match="Entity with id 1 not found"):
        repository.update(domain_entity)


def test_base_repository_remove_found():
    """Test removing existing entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    orm_entity = MockORMEntity(1, "test")

    mock_session.query.return_value.get.return_value = orm_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    repository.remove(1)

    # assert
    mock_session.delete.assert_called_once_with(orm_entity)
    mock_session.flush.assert_called_once()


def test_base_repository_remove_not_found():
    """Test removing non-existent entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()

    mock_session.query.return_value.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act & assert
    with pytest.raises(ValueError, match="Entity with id 1 not found"):
        repository.remove(1)
