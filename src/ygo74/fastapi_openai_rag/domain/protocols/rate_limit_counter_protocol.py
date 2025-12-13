"""Protocol for rate limit counter implementations."""
from typing import Protocol, Optional


class IRateLimitCounter(Protocol):
    """Protocol defining the interface for rate limit counter implementations.

    This protocol ensures that both in-memory and Redis counter implementations
    provide the same interface for atomic counting operations.
    """

    def increment_request_count(
        self,
        scope_type: str,
        scope_id: Optional[str],
        window_start: int,
        window_duration: int
    ) -> Optional[int]:
        """Atomically increment request counter for a time window.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            window_start: Unix timestamp of window start
            window_duration: Window duration in seconds

        Returns:
            Optional[int]: Current count after increment, None if operation fails and fail_open=True
        """
        ...

    def increment_token_count(
        self,
        scope_type: str,
        scope_id: Optional[str],
        window_start: int,
        window_duration: int,
        token_count: int
    ) -> Optional[int]:
        """Atomically increment token counter for a time window.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            window_start: Unix timestamp of window start
            window_duration: Window duration in seconds
            token_count: Number of tokens to add

        Returns:
            Optional[int]: Current count after increment, None if operation fails and fail_open=True
        """
        ...

    def get_current_count(
        self,
        scope_type: str,
        scope_id: Optional[str],
        metric: str,
        window_start: int
    ) -> Optional[int]:
        """Get current counter value without incrementing.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            metric: Counter metric ('requests' or 'tokens')
            window_start: Unix timestamp of window start

        Returns:
            Optional[int]: Current count, 0 if key doesn't exist
        """
        ...

    def close(self) -> None:
        """Close connections and cleanup resources.

        Should be called on application shutdown.
        """
        ...
