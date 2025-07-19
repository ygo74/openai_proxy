"""Model repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.model import Model
from .base import BaseRepository

class IModelRepository(BaseRepository[Model]):
    """Interface for model repository operations."""

    @abstractmethod
    def get_by_technical_name(self, technical_name: str) -> Optional[Model]:
        """Get a model by its technical name.

        Args:
            technical_name (str): The technical name of the model

        Returns:
            Optional[Model]: The model if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_group_id(self, group_id: int) -> List[Model]:
        """Get all models accessible by a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[Model]: List of models accessible by the group
        """
        pass