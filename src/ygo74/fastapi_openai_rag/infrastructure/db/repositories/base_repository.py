"""Base SQLAlchemy repository implementation."""
from typing import TypeVar, Generic, List, Optional, Type
from sqlalchemy.orm import Session
from ...db.mappers.base import BaseMapper

DomainType = TypeVar('DomainType')
ORMType = TypeVar('ORMType')

class SQLBaseRepository(Generic[DomainType, ORMType]):
    """Base repository implementation using SQLAlchemy.

    Attributes:
        session (Session): SQLAlchemy session
        orm_class (Type[ORMType]): ORM model class
        mapper (BaseMapper): Mapper for domain-ORM conversion
    """

    def __init__(self, session: Session, orm_class: Type[ORMType], mapper: BaseMapper[DomainType, ORMType]):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
            orm_class (Type[ORMType]): ORM model class
            mapper (BaseMapper): Mapper for domain-ORM conversion
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
        orm_entity = self._session.query(self._orm_class).get(id)
        return self._mapper.to_domain(orm_entity) if orm_entity else None

    def get_all(self) -> List[DomainType]:
        """Get all entities.

        Returns:
            List[DomainType]: List of domain models
        """
        orm_entities = self._session.query(self._orm_class).all()
        return self._mapper.to_domain_list(orm_entities)

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
        orm_entity = self._session.query(self._orm_class).get(entity.id)
        if not orm_entity:
            raise ValueError(f"Entity with id {entity.id} not found")

        for key, value in self._mapper.to_orm(entity).__dict__.items():
            if not key.startswith('_'):
                setattr(orm_entity, key, value)

        self._session.flush()
        return self._mapper.to_domain(orm_entity)

    def remove(self, id: int) -> None:
        """Remove entity from session without committing.

        Args:
            id (int): Entity ID to remove

        Raises:
            ValueError: If entity not found
        """
        orm_entity = self._session.query(self._orm_class).get(id)
        if not orm_entity:
            raise ValueError(f"Entity with id {id} not found")

        self._session.delete(orm_entity)
        self._session.flush()