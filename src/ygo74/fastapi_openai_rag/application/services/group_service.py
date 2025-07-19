"""Group service implementation."""
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.exc import NoResultFound
from ...domain.models.group import Group
from ...domain.repositories.group_repository import IGroupRepository
from ...domain.unit_of_work import UnitOfWork
from ...infrastructure.db.repositories.group_repository import SQLGroupRepository
from ...infrastructure.db.unit_of_work import SQLUnitOfWork
import logging

logger = logging.getLogger(__name__)

class GroupService:
    """Service for managing groups."""

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """Initialize service with Unit of Work and optional repository factory.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: SQLGroupRepository(session))
        logger.debug("GroupService initialized with Unit of Work")

    def add_or_update_group(self, group_id: Optional[int] = None,
                           name: Optional[str] = None,
                           description: Optional[str] = None) -> Tuple[str, Group]:
        """Add a new group or update an existing one.

        Args:
            group_id (Optional[int]): ID of group to update
            name (Optional[str]): Group name
            description (Optional[str]): Group description

        Returns:
            Tuple[str, Group]: Status and group entity

        Raises:
            ValueError: If required fields missing for creation
            NoResultFound: If group not found for update
        """
        with self._uow as uow:
            repository: IGroupRepository = self._repository_factory(uow.session)

            if group_id:
                logger.info(f"Updating group {group_id}")
                existing_group: Optional[Group] = repository.get_by_id(group_id)
                if not existing_group:
                    raise NoResultFound(f"Group with id {group_id} not found")

                updated_group: Group = Group(
                    id=group_id,
                    name=name or existing_group.name,
                    description=description or existing_group.description,
                    created=existing_group.created,
                    updated=datetime.now(timezone.utc)
                )
                result: Group = repository.update(entity=updated_group)
                logger.info(f"Group {group_id} updated successfully")
                return ("updated", result)

            logger.info("Creating new group")
            if not name:
                raise ValueError("Name is required for new groups")

            existing: Optional[Group] = repository.get_by_name(name)
            if existing:
                raise ValueError(f"Group with name {name} already exists")

            new_group: Group = Group(
                name=name,
                description=description,
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            result: Group = repository.add(new_group)
            logger.info(f"Group created successfully with id {result.id}")
            return ("created", result)

    def get_all_groups(self) -> List[Group]:
        """Get all groups.

        Returns:
            List[Group]: List of all group entities
        """
        logger.info("Fetching all groups")
        with self._uow as uow:
            repository: IGroupRepository = self._repository_factory(uow.session)
            groups: List[Group] = repository.get_all()
            logger.debug(f"Found {len(groups)} groups")
            return groups

    def get_group_by_id(self, group_id: int) -> Optional[Group]:
        """Get group by ID.

        Args:
            group_id (int): Group ID

        Returns:
            Optional[Group]: Group entity if found, None otherwise
        """
        logger.info(f"Fetching group {group_id}")
        with self._uow as uow:
            repository: IGroupRepository = self._repository_factory(uow.session)
            group: Optional[Group] = repository.get_by_id(group_id)
            logger.debug(f"Group {group_id} {'found' if group else 'not found'}")
            return group

    def get_group_by_name(self, name: str) -> Optional[Group]:
        """Get group by name.

        Args:
            name (str): Group name

        Returns:
            Optional[Group]: Group entity if found, None otherwise
        """
        logger.info(f"Fetching group by name: {name}")
        with self._uow as uow:
            repository: IGroupRepository = self._repository_factory(uow.session)
            group: Optional[Group] = repository.get_by_name(name)
            logger.debug(f"Group '{name}' {'found' if group else 'not found'}")
            return group

    def delete_group(self, group_id: int) -> None:
        """Delete a group.

        Args:
            group_id (int): ID of group to delete

        Raises:
            NoResultFound: If group not found
        """
        logger.info(f"Deleting group {group_id}")
        with self._uow as uow:
            repository: IGroupRepository = self._repository_factory(uow.session)
            repository.remove(group_id)
            logger.info(f"Group {group_id} deleted successfully")