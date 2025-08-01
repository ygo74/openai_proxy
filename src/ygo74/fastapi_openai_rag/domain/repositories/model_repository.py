"""Model repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.llm_model import LlmModel
from .base import BaseRepository

class IModelRepository(BaseRepository[LlmModel]):
    """Interface for model repository operations."""

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[LlmModel]:
        """Get a model by its technical name.

        Args:
            technical_name (str): The technical name of the model

        Returns:
            Optional[Model]: The model if found, None otherwise
        """
        pass


    @abstractmethod
    def get_by_technical_name(self, technical_name: str) -> Optional[LlmModel]:
        """Get a model by its technical name.

        Args:
            technical_name (str): The technical name of the model

        Returns:
            Optional[Model]: The model if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_group_id(self, group_id: int) -> List[LlmModel]:
        """Get all models accessible by a group.

        Args:
            group_id (int): Group ID

        Returns:
            List[Model]: List of models accessible by the group
        """
        pass