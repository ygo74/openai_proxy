"""Rate limit repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.rate_limit import RateLimit
from .base import BaseRepository

class IRateLimitRepository(BaseRepository[RateLimit]):
    """Interface for rate limit repository operations.

    Provides CRUD operations for rate limit configurations at different scopes
    (global, model, group/model). Follows the repository pattern defined in
    the project's onion architecture.
    """

    @abstractmethod
    def get_by_scope(self, scope_type: str, scope_id: Optional[str] = None) -> Optional[RateLimit]:
        """Get rate limit configuration for a specific scope.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope (None for global, model_id for model,
                     'group_id:model_id' for group_model)

        Returns:
            Optional[RateLimit]: The rate limit configuration if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all_by_scope_type(self, scope_type: str) -> List[RateLimit]:
        """Get all rate limits for a specific scope type.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')

        Returns:
            List[RateLimit]: List of rate limit configurations for the scope type
        """
        pass

    @abstractmethod
    def get_enabled_only(self) -> List[RateLimit]:
        """Get all enabled rate limit configurations.

        Returns:
            List[RateLimit]: List of enabled rate limit configurations
        """
        pass

    @abstractmethod
    def upsert(self, rate_limit: RateLimit) -> RateLimit:
        """Create or update a rate limit configuration.

        If a rate limit with the same scope_type and scope_id exists, it will be updated.
        Otherwise, a new rate limit will be created.

        Args:
            rate_limit: The rate limit configuration to create or update

        Returns:
            RateLimit: The created or updated rate limit configuration
        """
        pass

    @abstractmethod
    def delete_by_scope(self, scope_type: str, scope_id: Optional[str] = None) -> bool:
        """Delete a rate limit configuration by scope.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope

        Returns:
            bool: True if deleted, False if not found
        """
        pass
