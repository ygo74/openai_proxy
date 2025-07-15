from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from src.infrastructure.group_crud import GroupRepository
from typing import Dict, Any, List, Optional
from src.core.models.domain import Group
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class GroupService:
    """Service class for managing groups."""

    def __init__(self, session: Session, repository: Optional[GroupRepository] = None):
        """Initialize the service with a database session and optional repository.

        Args:
            session (Session): The database session
            repository (Optional[GroupRepository]): Optional repository instance for testing
        """
        self._repository = repository if repository is not None else GroupRepository(session)
        logger.debug("GroupService initialized with session and repository")

    def add_or_update_group(self, group_id: Optional[int] = None, name: Optional[str] = None,
                           description: Optional[str] = None) -> Dict[str, Any]:
        """Add a new group or update an existing one.

        Args:
            group_id (Optional[int]): ID of the group to update
            name (Optional[str]): Name of the group
            description (Optional[str]): Description of the group

        Returns:
            Dict[str, Any]: Operation result with status and group data

        Raises:
            ValueError: If name is missing when creating a new group
            NoResultFound: If group is not found when updating
        """
        if group_id:
            logger.info(f"Attempting to update group with id {group_id}")
            logger.debug(f"Update parameters: name={name}, description={description}")

            existing_group = self._repository.get_by_id(group_id)
            if not existing_group:
                logger.error(f"Group with id {group_id} not found")
                raise NoResultFound(f"Group with id {group_id} not found")

            updated_group = Group(
                id=group_id,
                name=name or existing_group.name,
                description=description if description is not None else existing_group.description,
                created=existing_group.created,
                updated=datetime.now(timezone.utc)
            )
            result = self._repository.update(group_id, updated_group)
            logger.info(f"Successfully updated group {group_id}")
            return {"status": "updated", "group": result}

        # Create new group
        logger.info(f"Attempting to create new group with name: {name}")

        if not name:
            logger.error("Attempted to create group without name")
            raise ValueError("Name is required when creating a new group")

        # Check if group with same name exists
        existing_groups = self._repository.get_all()
        if any(g.name == name for g in existing_groups):
            logger.error(f"Group with name {name} already exists")
            raise ValueError(f"Group with name {name} already exists")

        result = self._repository.create(name, description)
        logger.info(f"Successfully created new group with id {result.id}")
        return {"status": "created", "group": result}

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Get all groups.

        Returns:
            List[Dict[str, Any]]: List of groups with their details
        """
        logger.info("Fetching all groups")
        groups = self._repository.get_all()
        logger.debug(f"Found {len(groups)} groups")
        return [{"id": group.id, "name": group.name, "description": group.description}
                for group in groups]

    def delete_group(self, group_id: int) -> Dict[str, str]:
        """Delete a group.

        Args:
            group_id (int): ID of the group to delete

        Returns:
            Dict[str, str]: Operation result status

        Raises:
            NoResultFound: If group doesn't exist
        """
        logger.info(f"Attempting to delete group {group_id}")
        try:
            self._repository.delete(group_id)
            logger.info(f"Successfully deleted group {group_id}")
            return {"status": "deleted"}
        except NoResultFound as e:
            logger.error(f"Failed to delete group {group_id}: {str(e)}")
            raise