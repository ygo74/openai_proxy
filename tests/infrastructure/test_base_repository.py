"""Unit tests for SQLBaseRepository."""
import sys
import os
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

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

    # Configure mock to use get() instead of query().get()
    mock_session.get.return_value = mock_orm_entity
    mock_mapper.to_domain.return_value = mock_domain_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_by_id(1)

    # assert
    assert result == mock_domain_entity
    mock_session.get.assert_called_once_with(MockORMEntity, 1)
    mock_mapper.to_domain.assert_called_once_with(mock_orm_entity)


def test_base_repository_get_by_id_not_found():
    """Test getting entity by ID when not found."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()

    # Configure mock to use get() instead of query().get()
    mock_session.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_by_id(1)

    # assert
    assert result is None
    mock_session.get.assert_called_once_with(MockORMEntity, 1)
    mock_mapper.to_domain.assert_not_called()


def test_base_repository_get_all():
    """Test getting all entities."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    mock_orm_entities = [MockORMEntity(1, "test1"), MockORMEntity(2, "test2")]
    mock_domain_entities = [MockDomainEntity(1, "test1"), MockDomainEntity(2, "test2")]

    # Setup mock query chain
    mock_query = MagicMock()
    mock_query.all.return_value = mock_orm_entities
    mock_session.query.return_value = mock_query

    # Setup mapper to handle list of entities
    mock_mapper.to_domain.side_effect = lambda x: MockDomainEntity(x.id, x.name)

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.get_all()

    # assert
    assert len(result) == len(mock_domain_entities)
    assert all(r.id == e.id and r.name == e.name for r, e in zip(result, mock_domain_entities))
    mock_session.query.assert_called_once_with(MockORMEntity)
    assert mock_mapper.to_domain.call_count == 2


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
    mock_session.refresh.assert_called_once_with(orm_entity)
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
    refreshed_orm = MockORMEntity(1, "updated_and_refreshed")
    returned_entity = MockDomainEntity(1, "updated_and_refreshed")

    # Configure get() to return for both initial check and refresh
    mock_session.get.side_effect = [orm_entity, refreshed_orm]
    mock_mapper.to_orm.return_value = updated_orm
    mock_mapper.to_domain.return_value = returned_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    result = repository.update(domain_entity)

    # assert
    assert result == returned_entity
    mock_session.get.assert_any_call(MockORMEntity, 1)  # Initial check
    mock_session.merge.assert_called_once_with(updated_orm)
    mock_session.flush.assert_called_once()
    mock_session.get.assert_called_with(MockORMEntity, 1)  # Refresh check
    mock_mapper.to_domain.assert_called_once_with(refreshed_orm)


def test_base_repository_update_not_found():
    """Test updating non-existent entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    domain_entity = MockDomainEntity(1, "updated")

    mock_session.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act & assert
    with pytest.raises(ValueError, match="Entity with id 1 not found"):
        repository.update(domain_entity)


def test_base_repository_delete_found():
    """Test deleting existing entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()
    orm_entity = MockORMEntity(1, "test")

    mock_session.get.return_value = orm_entity

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act
    repository.delete(1)

    # assert
    mock_session.get.assert_called_once_with(MockORMEntity, 1)
    mock_session.delete.assert_called_once_with(orm_entity)
    mock_session.flush.assert_called_once()


def test_base_repository_delete_not_found():
    """Test deleting non-existent entity."""
    # arrange
    mock_session = Mock()
    mock_mapper = Mock()

    mock_session.get.return_value = None

    repository = SQLBaseRepository(mock_session, MockORMEntity, mock_mapper)

    # act & assert
    with pytest.raises(ValueError, match="Entity with id 1 not found"):
        repository.delete(1)
