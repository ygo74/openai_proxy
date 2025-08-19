"""Mapper for Group domain and ORM models."""
from typing import List
from datetime import datetime
from ....domain.models.group import Group
from ..models.group_orm import GroupORM
from .base import BaseMapper

class GroupMapper(BaseMapper[Group, GroupORM]):
    """Mapper for converting between Group domain and ORM models."""

    @staticmethod
    def to_orm(entity: Group) -> GroupORM:
        """Convert Group domain entity to ORM entity.

        Args:
            entity (Group): Domain entity instance

        Returns:
            GroupORM: ORM entity instance
        """
        now = datetime.utcnow()
        return GroupORM(
            id=entity.id if hasattr(entity, 'id') and entity.id else None,
            name=entity.name,
            description=entity.description,
            created=entity.created if hasattr(entity, 'created') and entity.created else now,
            updated=entity.updated if hasattr(entity, 'updated') and entity.updated else now
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
            updated=orm_entity.updated
        )

    @staticmethod
    def to_domain_list(orm_entities: List[GroupORM]) -> List[Group]:
        """Convert list of ORM entities to list of domain entities.

        Args:
            orm_entities (List[GroupORM]): List of ORM entities

        Returns:
            List[Group]: List of domain entities
        """
        return [GroupMapper.to_domain(orm_entity) for orm_entity in orm_entities]
