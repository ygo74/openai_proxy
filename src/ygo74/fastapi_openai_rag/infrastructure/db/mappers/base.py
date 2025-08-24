"""Base mapper class for domain/ORM conversion."""
from typing import TypeVar, Generic, List

DomainT = TypeVar('DomainT')
ORMT = TypeVar('ORMT')

class BaseMapper(Generic[DomainT, ORMT]):
    """Base mapper class for domain/ORM conversion."""

    @classmethod
    def to_domain(cls, orm_entity: ORMT) -> DomainT:
        """Convert ORM entity to domain entity.

        Args:
            orm_entity: ORM entity

        Returns:
            Domain entity
        """
        raise NotImplementedError("Subclasses must implement to_domain")

    @classmethod
    def to_orm(cls, domain_entity: DomainT) -> ORMT:
        """Convert domain entity to ORM entity.

        Args:
            domain_entity: Domain entity

        Returns:
            ORM entity
        """
        raise NotImplementedError("Subclasses must implement to_orm")

    @classmethod
    def to_domain_list(cls, orm_entities: List[ORMT]) -> List[DomainT]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities: List of ORM entities

        Returns:
            List of domain entities
        """
        return [cls.to_domain(orm_entity) for orm_entity in orm_entities]