"""Protocol for rate limit cache implementations."""
from typing import Protocol, Optional, Any, Dict


class IRateLimitCache(Protocol):
    """Protocol defining the interface for rate limit cache implementations.

    This protocol ensures that both in-memory and Redis cache implementations
    provide the same interface for storing and retrieving rate limit configurations.
    """

    def get(self, scope_type: str, scope_id: Optional[str]) -> Optional[Any]:
        """Retrieve rate limit config from cache.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)

        Returns:
            Cached config or None if not found or expired
        """
        ...

    def set(self, scope_type: str, scope_id: Optional[str], value: Any) -> None:
        """Store rate limit config in cache.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
            value: Config value to cache
        """
        ...

    def publish_change(
        self,
        operation: str,
        scope_type: str,
        scope_id: Optional[str]
    ) -> None:
        """Publish configuration change notification.

        For Redis: Uses pub/sub to notify all instances
        For in-memory: Only invalidates local cache

        Args:
            operation: Type of operation (create, update, delete)
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
        """
        ...

    def clear(self) -> None:
        """Clear all cache entries (useful for testing)."""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics (implementation-specific)
        """
        ...

    def start_listener(self) -> None:
        """Start background listener for cache invalidation events.

        For Redis: Starts pub/sub listener thread
        For in-memory: No-op (no cross-instance synchronization)
        """
        ...

    def stop_listener(self) -> None:
        """Stop background listener and cleanup resources.

        For Redis: Stops pub/sub thread and closes connections
        For in-memory: No-op
        """
        ...
