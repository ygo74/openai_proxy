"""Model repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.llm_model import LlmModel
from .base import BaseRepository

class IModelRepository(BaseRepository[LlmModel]):
    """Interface for model repository operations."""

    @abstractmethod
    def get_by_name(self, name: str) -> List[LlmModel]:
        """Get models by their name.

        Args:
            name (str): The name of the model

        Returns:
            List[LlmModel]: List of models with the given name
        """
        pass


    @abstractmethod
    def get_by_technical_name(self, technical_name: str) -> List[LlmModel]:
        """Get models by their technical name.

        Args:
            technical_name (str): The technical name of the model

        Returns:
            List[LlmModel]: List of models with the given technical name
        """
        pass

    @abstractmethod
    def get_by_model_provider(self, name: str, technical_name: str) -> Optional[LlmModel]:
        """Get a model by its technical name.

        Args:
            name (str): The name of the model
            technical_name (str): The technical name of the model's provider

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

    @abstractmethod
    def get_approved_by_name(self, name: str) -> List[LlmModel]:
        """Get all approved models by their name.

        Args:
            name (str): The name of the model

        Returns:
            List[LlmModel]: List of approved models with the given name
        """
        pass

    @abstractmethod
    def get_approved_by_group_names(self, group_names: List[str]) -> List[LlmModel]:
        """Get all approved models accessible by any of the specified groups.

        Optimized method that fetches all models in a single query instead of N+1 queries.
        Returns distinct models (no duplicates) that are approved and linked to at least
        one of the specified groups.

        Args:
            group_names (List[str]): List of group names

        Returns:
            List[LlmModel]: List of distinct approved models accessible by the groups
        """
        pass