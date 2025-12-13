"""Base class for rate limit counter implementations."""
import logging
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseRateLimitCounter(ABC):
    """Abstract base class for rate limit counter implementations.

    Provides common functionality and defines the interface that all
    counter implementations must follow.
    """

    def __init__(self, fail_open: bool = True):
        """Initialize base counter.

        Args:
            fail_open: If True, allow requests when counter operations fail
        """
        self._fail_open = fail_open

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
            Optional[int]: Current count after increment, float('inf') if fail_open and operation fails
        """
        key = self._build_key(scope_type, scope_id, "requests", window_start)
        ttl = window_duration * 2  # Keep for 2x duration for safety
        result = self._increment(key, ttl, increment=1)
        # Convert None to inf when fail_open allows requests despite failure
        return float('inf') if result is None and self._fail_open else result

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
            Optional[int]: Current count after increment, float('inf') if fail_open and operation fails
        """
        key = self._build_key(scope_type, scope_id, "tokens", window_start)
        ttl = window_duration * 2
        result = self._increment(key, ttl, increment=token_count)
        # Convert None to inf when fail_open allows requests despite failure
        return float('inf') if result is None and self._fail_open else result

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
        key = self._build_key(scope_type, scope_id, metric, window_start)
        return self._get(key)

    def _build_key(
        self,
        scope_type: str,
        scope_id: Optional[str],
        metric: str,
        window_start: int
    ) -> str:
        """Build counter key.

        Key format: rate_limit:{scope_type}:{scope_id}:{metric}:{window_start}

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            metric: Counter metric ('requests' or 'tokens')
            window_start: Unix timestamp of window start

        Returns:
            str: Counter key
        """
        scope_part = f"{scope_type}:{scope_id}" if scope_id else scope_type
        return f"rate_limit:{scope_part}:{metric}:{window_start}"

    @abstractmethod
    def _increment(self, key: str, ttl: int, increment: int = 1) -> Optional[int]:
        """Increment counter (implementation-specific).

        Args:
            key: Counter key
            ttl: TTL in seconds
            increment: Amount to increment by

        Returns:
            Optional[int]: Current count after increment, None if operation fails and fail_open=True
        """
        ...

    @abstractmethod
    def _get(self, key: str) -> Optional[int]:
        """Get counter value (implementation-specific).

        Args:
            key: Counter key

        Returns:
            Optional[int]: Current count, 0 if key doesn't exist
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Close connections and cleanup resources."""
        ...
