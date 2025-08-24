"""Mapper for Group domain and ORM models."""
from typing import List
from datetime import datetime, timezone
from ....domain.models.group import Group
from ..models.group_orm import GroupORM
from .base import BaseMapper

class GroupMapper(BaseMapper[Group, GroupORM]):
    """Mapper for converting between Group domain and ORM models."""

    @staticmethod
    def to_orm(domain: Group) -> GroupORM:
        """Convert Group domain entity to ORM entity.

        Args:
            domain (Group): Domain entity instance

        Returns:
            GroupORM: ORM entity instance
        """
        now = datetime.now(timezone.utc)
        return GroupORM(
            id=domain.id if hasattr(domain, 'id') and domain.id else None,
            name=domain.name,
            description=domain.description,
            created=domain.created if hasattr(domain, 'created') and domain.created else now,
            updated=domain.updated if hasattr(domain, 'updated') and domain.updated else now
        )

    @staticmethod
    def to_domain(orm_entity: GroupORM) -> Group:
        """Convert ORM entity to Group domain entity.

        Args:
            orm_entity (GroupORM): ORM entity instance

        Returns:
            Group: Domain entity instance
        """
        return Group(
            id=orm_entity.id,
            name=orm_entity.name,
            description=orm_entity.description,
            created=orm_entity.created,
            updated=orm_entity.updated,
            models=[]  # Models will be loaded by repository as needed
        )

    @classmethod
    def to_domain_list(cls, orm_entities: List[GroupORM]) -> List[Group]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities (List[GroupORM]): List of ORM entities

        Returns:
            List[Group]: List of domain entities
        """
        return [cls.to_domain(orm_entity) for orm_entity in orm_entities]
