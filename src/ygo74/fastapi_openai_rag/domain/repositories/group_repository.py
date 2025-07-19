"""Group repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.group import Group
from .base import BaseRepository

class IGroupRepository(BaseRepository[Group]):
    """Interface for group repository operations."""

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Group]:
        """Get a group by its name.

        Args:
            name (str): The name of the group

        Returns:
            Optional[Group]: The group if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_model_id(self, model_id: int) -> List[Group]:
        """Get all groups associated with a model.

        Args:
            model_id (int): Model ID

        Returns:
            List[Group]: List of groups that have access to the model
        """
        pass