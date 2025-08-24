"""Base SQLAlchemy repository implementation."""
from typing import TypeVar, Generic, List, Optional, Type, Any
from sqlalchemy.orm import Session
from ....domain.repositories.base import BaseRepository
import inspect

DomainType = TypeVar('DomainType')
ORMType = TypeVar('ORMType')

class SQLBaseRepository(Generic[DomainType, ORMType], BaseRepository[DomainType]):
    """Base repository implementation using SQLAlchemy.

    Attributes:
        _session (Session): SQLAlchemy session
        _orm_class (Type[ORMType]): ORM model class
        _mapper: Mapper class for domain-ORM conversion
    """

    def __init__(self, session: Session, orm_class: Type[ORMType], mapper: Any):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
            orm_class (Type[ORMType]): ORM model class
            mapper: Mapper class with static methods to_domain and to_orm
        """
        self._session = session
        self._orm_class = orm_class
        self._mapper = mapper

    def get_by_id(self, id: int) -> Optional[DomainType]:
        """Get entity by ID.

        Args:
            id (int): Entity ID

        Returns:
            Optional[DomainType]: Domain model if found, None otherwise
        """
        orm_entity = self._session.get(self._orm_class, id)
        return self._mapper.to_domain(orm_entity) if orm_entity else None

    def get_all(self) -> List[DomainType]:
        """Get all entities.

        Returns:
            List[DomainType]: List of domain models
        """
        orm_entities = self._session.query(self._orm_class).all()
        return [self._mapper.to_domain(orm_entity) for orm_entity in orm_entities]

    def add(self, entity: DomainType) -> DomainType:
        """Add new entity to session without committing.

        Args:
            entity (DomainType): Domain entity to add

        Returns:
            DomainType: Added domain entity
        """
        orm_entity = self._mapper.to_orm(entity)
        self._session.add(orm_entity)
        self._session.flush()  # Get the ID without committing
        self._session.refresh(orm_entity)  # Ensure all fields are populated
        return self._mapper.to_domain(orm_entity)

    def update(self, entity: DomainType) -> DomainType:
        """Update existing entity in session without committing.

        Args:
            entity (DomainType): Domain entity to update

        Returns:
            DomainType: Updated domain entity

        Raises:
            ValueError: If entity not found
        """
        # Get ID from entity - assumes entity has an id attribute
        entity_id = getattr(entity, 'id')
        if entity_id is None:
            raise ValueError("Cannot update entity without an ID")

        orm_entity = self._session.get(self._orm_class, entity_id)
        if not orm_entity:
            raise ValueError(f"Entity with id {entity_id} not found")

        # Update entity by creating a new ORM entity and merging it
        updated_orm = self._mapper.to_orm(entity)

        # Manually handle collections to ensure empty lists are properly synchronized
        self._sync_collections(orm_entity, updated_orm)

        # Now merge the updated ORM entity
        self._session.merge(updated_orm)
        self._session.flush()

        # Refresh to get updated data
        refreshed_orm = self._session.get(self._orm_class, entity_id)
        return self._mapper.to_domain(refreshed_orm)

    def _sync_collections(self, existing_orm: ORMType, updated_orm: ORMType) -> None:
        """Synchronize collections between existing and updated ORM entities.

        This ensures empty collections in the updated entity will clear
        corresponding collections in the database.

        Args:
            existing_orm: Existing ORM entity from database
            updated_orm: Updated ORM entity with new values
        """
        # Get all relationship attributes from the ORM class
        for attr_name, attr_value in inspect.getmembers(self._orm_class):
            # Skip private attributes and non-relationship properties
            if attr_name.startswith('_') or not hasattr(existing_orm, attr_name):
                continue

            # Check if this is a relationship attribute (has a collection)
            existing_value = getattr(existing_orm, attr_name)
            updated_value = getattr(updated_orm, attr_name)

            # If it's a list/collection attribute and the new value is empty
            if isinstance(existing_value, list) and updated_value == []:
                # Clear the existing collection explicitly
                existing_value.clear()

    def delete(self, id: int) -> None:
        """Remove entity from session without committing.

        Args:
            id (int): Entity ID to remove

        Raises:
            ValueError: If entity not found
        """
        orm_entity = self._session.get(self._orm_class, id)
        if not orm_entity:
            raise ValueError(f"Entity with id {id} not found")

        self._session.delete(orm_entity)
        self._session.flush()