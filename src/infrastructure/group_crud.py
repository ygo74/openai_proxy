from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from src.infrastructure.db.models.group_orm import GroupORM
from src.infrastructure.db.mappers.mappers import to_domain_group, to_orm_group
from src.core.models.domain import Group
from typing import List, Optional
from datetime import datetime, timezone

class GroupRepository:
    """Repository for managing groups in the database."""

    def __init__(self, session: Session):
        """Initialize the repository with a database session.

        Args:
            session (Session): SQLAlchemy database session
        """
        self._session = session

    def create(self, name: str, description: str | None = None) -> Group:
        """Create a new group in the database.

        Args:
            name (str): Name of the group
            description (str | None, optional): Description of the group. Defaults to None.

        Returns:
            Group: The created group domain model

        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            new_group = Group(
                name=name,
                description=description,
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            orm_group = to_orm_group(new_group)
            self._session.add(orm_group)
            self._session.commit()
            self._session.refresh(orm_group)
            return to_domain_group(orm_group)
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def get_by_id(self, group_id: int) -> Optional[Group]:
        """Get a group by its ID.

        Args:
            group_id (int): The ID of the group to retrieve

        Returns:
            Optional[Group]: The group if found, None otherwise
        """
        group = self._session.query(GroupORM).filter(GroupORM.id == group_id).first()
        return to_domain_group(group) if group else None

    def get_all(self) -> List[Group]:
        """Get all groups.

        Returns:
            List[Group]: List of all groups
        """
        return [to_domain_group(group) for group in self._session.query(GroupORM).all()]

    def update(self, group_id: int, updated_group: Group) -> Group:
        """Update a group in the database.

        Args:
            group_id (int): ID of the group to update
            updated_group (Group): New group data

        Returns:
            Group: The updated group

        Raises:
            NoResultFound: If group doesn't exist
            SQLAlchemyError: If database operation fails
        """
        try:
            now = datetime.now(timezone.utc)
            result = self._session.query(GroupORM).filter(GroupORM.id == group_id).update({
                GroupORM.name: updated_group.name,
                GroupORM.description: updated_group.description,
                GroupORM.updated: now
            })

            if result == 0:
                raise NoResultFound(f"Group with id {group_id} not found")

            self._session.commit()
            updated = self._session.query(GroupORM).filter(GroupORM.id == group_id).one()
            return to_domain_group(updated)
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def delete(self, group_id: int) -> None:
        """Delete a group from the database.

        Args:
            group_id (int): ID of the group to delete

        Raises:
            NoResultFound: If group doesn't exist
            SQLAlchemyError: If database operation fails
        """
        try:
            result = self._session.query(GroupORM).filter(GroupORM.id == group_id).delete()
            if result == 0:
                raise NoResultFound(f"Group with id {group_id} not found")

            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise