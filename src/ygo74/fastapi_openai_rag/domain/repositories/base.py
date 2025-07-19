"""Base repository interface."""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """Base repository interface for CRUD operations."""

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """Get an entity by its ID.

        Args:
            id (int): The ID of the entity to retrieve

        Returns:
            Optional[T]: The entity if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """Get all entities.

        Returns:
            List[T]: List of all entities
        """
        pass

    @abstractmethod
    def add(self, entity: T) -> T:
        """Create a new entity.

        Args:
            entity (T): The entity to create

        Returns:
            T: The created entity with its new ID
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Update an existing entity.

        Args:
            id (int): ID of the entity to update
            entity (T): New entity data

        Returns:
            T: The updated entity
        """
        pass

    @abstractmethod
    def delete(self, id: int) -> None:
        """Delete an entity.

        Args:
            id (int): ID of the entity to delete
        """
        pass