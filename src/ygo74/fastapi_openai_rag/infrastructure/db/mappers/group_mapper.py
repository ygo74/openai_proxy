"""Mapper for Group domain and ORM models."""
from typing import Optional
from .base import BaseMapper
from ....domain.models.group import Group
from ..models.group_orm import GroupORM

class GroupMapper(BaseMapper[Group, GroupORM]):
    """Mapper for converting between Group domain and ORM models."""

    def to_orm(self, entity: Group) -> GroupORM:
        """Convert Group domain entity to ORM entity.

        Args:
            entity (Group): Domain entity instance

        Returns:
            GroupORM: ORM entity instance
        """
        return GroupORM(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            created=entity.created,
            updated=entity.updated
        )

    def to_domain(self, orm_entity: GroupORM) -> Group:
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
            updated=orm_entity.updated
        )
