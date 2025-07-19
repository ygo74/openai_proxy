"""Base mapper interface for domain-ORM conversion."""
from typing import TypeVar, Generic, List

DomainType = TypeVar('DomainType')
ORMType = TypeVar('ORMType')

class BaseMapper(Generic[DomainType, ORMType]):
    """Base mapper interface for converting between domain and ORM models."""

    def to_orm(self, entity: DomainType) -> ORMType:
        """Convert domain entity to ORM entity.

        Args:
            entity (DomainType): Domain entity instance

        Returns:
            ORMType: ORM entity instance
        """
        raise NotImplementedError

    def to_domain(self, orm_entity: ORMType) -> DomainType:
        """Convert ORM entity to domain entity.

        Args:
            orm_entity (ORMType): ORM entity instance

        Returns:
            DomainType: Domain entity instance
        """
        raise NotImplementedError

    def to_orm_list(self, entities: List[DomainType]) -> List[ORMType]:
        """Convert list of domain entities to ORM entities.

        Args:
            entities (List[DomainType]): List of domain entity instances

        Returns:
            List[ORMType]: List of ORM entity instances
        """
        return [self.to_orm(entity) for entity in entities]

    def to_domain_list(self, orm_entities: List[ORMType]) -> List[DomainType]:
        """Convert list of ORM entities to domain entities.

        Args:
            orm_entities (List[ORMType]): List of ORM entity instances

        Returns:
            List[DomainType]: List of domain entity instances
        """
        return [self.to_domain(orm_entity) for orm_entity in orm_entities]