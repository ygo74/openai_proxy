"""User repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.user import User
from .base import BaseRepository

class IUserRepository(BaseRepository[User]):
    """Interface for user repository operations."""

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username.

        Args:
            username (str): The username

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email.

        Args:
            email (str): The email address

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        pass

    @abstractmethod
    def find_by_api_key_hash(self, key_hash: str) -> Optional[User]:
        """Find user by API key hash.

        Args:
            key_hash (str): Hashed API key

        Returns:
            Optional[User]: User if found, None otherwise
        """
        pass

    @abstractmethod
    def get_active_users(self) -> List[User]:
        """Get all active users.

        Returns:
            List[User]: List of active users
        """
        pass

    @abstractmethod
    def add_user_to_group(self, user_id: str, group_name: str) -> None:
        """Add a user to a group.

        Args:
            user_id (str): The user ID
            group_name (str): The group name to add
        """
        pass

    @abstractmethod
    def remove_user_from_group(self, user_id: str, group_name: str) -> None:
        """Remove a user from a group.

        Args:
            user_id (str): The user ID
            group_name (str): The group name to remove
        """
        pass
