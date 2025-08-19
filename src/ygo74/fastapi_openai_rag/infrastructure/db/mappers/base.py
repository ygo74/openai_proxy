"""Base mapper for domain/ORM conversion."""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List

DomainType = TypeVar('DomainType')
ORMType = TypeVar('ORMType')

class BaseMapper(Generic[DomainType, ORMType], ABC):
    """Base mapper for converting between domain and ORM models."""

    @staticmethod
    @abstractmethod
    def to_domain(orm_entity: ORMType) -> DomainType:
        """Convert ORM entity to domain entity.

        Args:
            orm_entity: ORM entity

        Returns:
            Domain entity
        """
        pass

    @staticmethod
    @abstractmethod
    def to_orm(entity: DomainType) -> ORMType:
        """Convert domain entity to ORM entity.

        Args:
            entity: Domain entity

        Returns:
            ORM entity
        """
        pass

    @classmethod
    def to_domain_list(cls, orm_entities: List[ORMType]) -> List[DomainType]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities: List of ORM entities

        Returns:
            List of domain entities
        """
        return [cls.to_domain(orm_entity) for orm_entity in orm_entities]