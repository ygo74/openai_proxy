"""In-memory implementation of rate limit counter."""
import logging
import time
import threading
from typing import Optional, Dict, Tuple
from .base_rate_limit_counter import BaseRateLimitCounter

logger = logging.getLogger(__name__)


class InMemoryRateLimitCounter(BaseRateLimitCounter):
    """In-memory rate limit counter implementation.

    Uses a thread-safe dictionary with expiry timestamps for counting.
    Suitable for single-instance deployments or development environments.

    Key features:
    - Thread-safe operations with locks
    - Automatic expiry cleanup
    - LRU-style eviction when size limit reached
    - No external dependencies

    Limitations:
    - No cross-instance synchronization
    - Lost on application restart
    - Not suitable for horizontal scaling
    """

    def __init__(self, max_size: int = 10000, fail_open: bool = True):
        """Initialize in-memory counter.

        Args:
            max_size: Maximum number of counters to store (default: 10000)
            fail_open: If True, allow requests when operations fail
        """
        super().__init__(fail_open=fail_open)
        self._counters: Dict[str, Tuple[int, float]] = {}  # key -> (count, expiry_time)
        self._lock = threading.Lock()
        self._max_size = max_size
        logger.info(f"InMemoryRateLimitCounter initialized: max_size={max_size}, fail_open={fail_open}")

    def _increment(self, key: str, ttl: int, increment: int = 1) -> Optional[int]:
        """Increment counter in memory.

        Args:
            key: Counter key
            ttl: TTL in seconds
            increment: Amount to increment by

        Returns:
            Optional[int]: Current count after increment
        """
        current_time = time.time()
        expiry_time = current_time + ttl

        with self._lock:
            # Clean expired entries
            self._cleanup_expired(current_time)

            # Check size limit
            if key not in self._counters and len(self._counters) >= self._max_size:
                # Evict oldest (first inserted)
                oldest_key = next(iter(self._counters))
                del self._counters[oldest_key]
                logger.warning(f"Counter size limit reached, evicted: {oldest_key}")

            # Increment counter
            if key in self._counters:
                count, old_expiry = self._counters[key]
                # Check if expired
                if old_expiry < current_time:
                    # Expired, reset counter
                    count = increment
                else:
                    # Not expired, increment
                    count += increment
            else:
                # New counter
                count = increment

            # Store with new expiry
            self._counters[key] = (count, expiry_time)
            logger.debug(f"In-memory counter incremented: {key} = {count} (TTL={ttl}s)")
            return count

    def _get(self, key: str) -> Optional[int]:
        """Get counter value from memory.

        Args:
            key: Counter key

        Returns:
            Optional[int]: Current count, 0 if key doesn't exist or expired
        """
        current_time = time.time()

        with self._lock:
            # Cleanup expired entries first
            self._cleanup_expired(current_time)

            if key in self._counters:
                count, expiry = self._counters[key]
                if expiry >= current_time:
                    return count
                # Should not happen after cleanup, but be defensive
                del self._counters[key]

            return 0

    def _cleanup_expired(self, current_time: float) -> None:
        """Remove expired counters.

        Args:
            current_time: Current timestamp
        """
        expired_keys = [k for k, (_, exp) in self._counters.items() if exp < current_time]
        for k in expired_keys:
            del self._counters[k]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired counters")

    def get_stats(self) -> Dict[str, int]:
        """Get counter statistics.

        Returns:
            Dict with statistics (total_counters, max_size)
        """
        with self._lock:
            return {
                "total_counters": len(self._counters),
                "max_size": self._max_size
            }

    def close(self) -> None:
        """Close and cleanup resources."""
        with self._lock:
            self._counters.clear()
        logger.info("InMemoryRateLimitCounter closed")
