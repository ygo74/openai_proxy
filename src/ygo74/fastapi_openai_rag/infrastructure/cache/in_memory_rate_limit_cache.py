"""In-memory implementation of rate limit cache.

This implementation provides a simple in-memory LRU cache with TTL
for single-instance deployments or when Redis is unavailable.
"""
import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InMemoryRateLimitCache:
    """In-memory cache for rate limit configurations.

    Features:
    - LRU cache with configurable size (default 64 entries)
    - TTL-based expiration (default 30 seconds)
    - Thread-safe operations
    - No cross-instance synchronization (single-instance only)

    Attributes:
        _cache: Dictionary mapping cache keys to (value, expiry) tuples
        _cache_lock: Thread lock for cache operations
        _max_cache_size: Maximum LRU cache entries
        _ttl_seconds: Cache entry TTL in seconds
    """

    def __init__(
        self,
        max_cache_size: int = 64,
        ttl_seconds: int = 30
    ):
        """Initialize in-memory cache.

        Args:
            max_cache_size: Maximum number of cache entries (default 64)
            ttl_seconds: Time-to-live for cache entries in seconds (default 30)
        """
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_lock = threading.Lock()
        self._max_cache_size = max_cache_size
        self._ttl_seconds = ttl_seconds
        logger.info(
            f"InMemoryRateLimitCache initialized: "
            f"max_size={max_cache_size}, ttl={ttl_seconds}s"
        )

    def _make_cache_key(self, scope_type: str, scope_id: Optional[str]) -> str:
        """Create cache key from scope identifiers.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)

        Returns:
            Cache key string
        """
        if scope_id is None:
            return f"rate_limit:{scope_type}"
        return f"rate_limit:{scope_type}:{scope_id}"

    def get(self, scope_type: str, scope_id: Optional[str]) -> Optional[Any]:
        """Retrieve rate limit config from cache.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)

        Returns:
            Cached config or None if not found or expired
        """
        cache_key = self._make_cache_key(scope_type, scope_id)

        with self._cache_lock:
            if cache_key in self._cache:
                value, expiry = self._cache[cache_key]

                # Check if expired
                if datetime.utcnow() < expiry:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return value
                else:
                    # Remove expired entry
                    del self._cache[cache_key]
                    logger.debug(f"Cache EXPIRED: {cache_key}")

            logger.debug(f"Cache MISS: {cache_key}")
            return None

    def set(self, scope_type: str, scope_id: Optional[str], value: Any) -> None:
        """Store rate limit config in cache.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
            value: Config value to cache
        """
        cache_key = self._make_cache_key(scope_type, scope_id)
        expiry = datetime.utcnow() + timedelta(seconds=self._ttl_seconds)

        with self._cache_lock:
            # Implement LRU eviction if cache is full
            if len(self._cache) >= self._max_cache_size and cache_key not in self._cache:
                # Remove oldest entry (simple FIFO for now)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache eviction: {oldest_key}")

            self._cache[cache_key] = (value, expiry)
            logger.debug(f"Cache SET: {cache_key}, expires in {self._ttl_seconds}s")

    def _invalidate(self, cache_key: str) -> None:
        """Remove entry from local cache.

        Args:
            cache_key: Cache key to invalidate
        """
        with self._cache_lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.info(f"Cache INVALIDATED: {cache_key}")

    def publish_change(
        self,
        operation: str,
        scope_type: str,
        scope_id: Optional[str]
    ) -> None:
        """Invalidate local cache entry (no cross-instance notification).

        Args:
            operation: Type of operation (create, update, delete)
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
        """
        cache_key = self._make_cache_key(scope_type, scope_id)
        self._invalidate(cache_key)
        logger.debug(
            f"Local cache invalidation: operation={operation}, "
            f"scope={scope_type}:{scope_id}"
        )

    def clear(self) -> None:
        """Clear all cache entries (useful for testing)."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("In-memory cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        with self._cache_lock:
            return {
                'implementation': 'in-memory',
                'size': len(self._cache),
                'max_size': self._max_cache_size,
                'ttl_seconds': self._ttl_seconds,
                'entries': list(self._cache.keys())
            }

    def start_listener(self) -> None:
        """No-op for in-memory cache (no cross-instance synchronization)."""
        logger.debug("In-memory cache: no listener to start")

    def stop_listener(self) -> None:
        """No-op for in-memory cache (no resources to cleanup)."""
        logger.debug("In-memory cache: no listener to stop")
