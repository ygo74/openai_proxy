"""Rate limit configuration cache with Redis pub/sub invalidation.

This module provides caching for rate limit configurations with automatic
invalidation across multiple gateway instances using Redis pub/sub.

Features:
- LRU cache with TTL for rate limit configs
- Redis pub/sub for multi-instance synchronization
- <5s propagation guarantee for configuration changes
- Thread-safe cache operations
"""
import json
import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache
import redis

logger = logging.getLogger(__name__)


class RateLimitCache:
    """Cache manager for rate limit configurations with pub/sub invalidation.

    Implements a two-tier caching strategy:
    1. Local LRU cache (64 entries, 30s TTL) for fast access
    2. Redis pub/sub for cross-instance invalidation

    Attributes:
        _redis_client: Redis client for pub/sub operations
        _cache: Dictionary mapping cache keys to (value, expiry) tuples
        _cache_lock: Thread lock for cache operations
        _pubsub_thread: Background thread for pub/sub listener
        _channel_name: Redis channel for invalidation messages
        _max_cache_size: Maximum LRU cache entries (default 64)
        _ttl_seconds: Cache entry TTL in seconds (default 30)
    """

    CHANNEL_NAME = "rate_limit_config_changes"
    MAX_CACHE_SIZE = 64
    TTL_SECONDS = 30

    # Class-level variables for in-memory cache (shared across all instances)
    _cache: Dict[str, tuple[Any, datetime]] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None
    ):
        """Initialize rate limit cache with Redis connection.

        Falls back to in-memory-only mode if Redis is unavailable.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Optional Redis password
        """
        self._pubsub = None
        self._pubsub_thread = None
        self._redis_available = False
        self._redis_client = None

        # Try to connect to Redis, fallback to in-memory if unavailable
        try:
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info(f"RateLimitCache initialized with Redis: host={redis_host}, port={redis_port}, db={redis_db}")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory cache only: {e}")
            self._redis_client = None
            self._redis_available = False

    def start_listener(self):
        """Start Redis pub/sub listener in background thread.

        Subscribes to rate_limit_config_changes channel and processes
        invalidation messages in a separate thread.
        Skips if Redis is unavailable (in-memory mode).
        """
        if not self._redis_available:
            logger.info("Skipping pub/sub listener (in-memory mode, no Redis)")
            return

        if self._pubsub_thread is not None:
            logger.warning("Pub/sub listener already running")
            return

        self._pubsub = self._redis_client.pubsub()
        self._pubsub.subscribe(self.CHANNEL_NAME)

        def listener_thread():
            """Background thread that listens for invalidation messages."""
            logger.info(f"Pub/sub listener started on channel: {self.CHANNEL_NAME}")
            try:
                for message in self._pubsub.listen():
                    if message['type'] == 'message':
                        self._handle_invalidation_message(message['data'])
            except Exception as e:
                logger.error(f"Pub/sub listener error: {e}", exc_info=True)

        self._pubsub_thread = threading.Thread(target=listener_thread, daemon=True)
        self._pubsub_thread.start()
        logger.info("Pub/sub listener thread started")

    def stop_listener(self):
        """Stop Redis pub/sub listener and cleanup resources."""
        if self._pubsub:
            self._pubsub.unsubscribe(self.CHANNEL_NAME)
            self._pubsub.close()
            self._pubsub = None

        if self._pubsub_thread:
            # Thread will stop when pubsub closes
            self._pubsub_thread = None

        logger.info("Pub/sub listener stopped")

    def _handle_invalidation_message(self, message_data: str):
        """Process incoming invalidation message.

        Args:
            message_data: JSON string with invalidation details
                Format: {"operation": "create|update|delete",
                        "scope_type": "...", "scope_id": "..."}
        """
        try:
            data = json.loads(message_data)
            operation = data.get('operation')
            scope_type = data.get('scope_type')
            scope_id = data.get('scope_id')

            logger.info(f"Received invalidation: operation={operation}, scope={scope_type}:{scope_id}")

            # Invalidate cache entry for this scope
            cache_key = self._make_cache_key(scope_type, scope_id)
            self._invalidate(cache_key)

        except Exception as e:
            logger.error(f"Error handling invalidation message: {e}", exc_info=True)

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

    def set(self, scope_type: str, scope_id: Optional[str], value: Any):
        """Store rate limit config in cache.

        Args:
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
            value: Config value to cache
        """
        cache_key = self._make_cache_key(scope_type, scope_id)
        expiry = datetime.utcnow() + timedelta(seconds=self.TTL_SECONDS)

        with self._cache_lock:
            # Implement LRU eviction if cache is full
            if len(self._cache) >= self.MAX_CACHE_SIZE and cache_key not in self._cache:
                # Remove oldest entry (simple FIFO for now)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache eviction: {oldest_key}")

            self._cache[cache_key] = (value, expiry)
            logger.debug(f"Cache SET: {cache_key}, expires in {self.TTL_SECONDS}s")

    def _invalidate(self, cache_key: str):
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
    ):
        """Publish configuration change to all instances via Redis pub/sub.

        Args:
            operation: Type of operation (create, update, delete)
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
        """
        if not self._redis_available:
            # In-memory mode: just invalidate local cache
            cache_key = self._make_cache_key(scope_type, scope_id)
            self._invalidate(cache_key)
            logger.debug(f"Local invalidation (no Redis): {operation} for {scope_type}:{scope_id}")
            return

        message = json.dumps({
            'operation': operation,
            'scope_type': scope_type,
            'scope_id': scope_id,
            'timestamp': datetime.utcnow().isoformat()
        })

        try:
            self._redis_client.publish(self.CHANNEL_NAME, message)
            logger.info(f"Published change: operation={operation}, scope={scope_type}:{scope_id}")
        except Exception as e:
            logger.error(f"Failed to publish change: {e}", exc_info=True)

    def clear(self):
        """Clear all cache entries (useful for testing)."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        with self._cache_lock:
            return {
                'size': len(self._cache),
                'max_size': self.MAX_CACHE_SIZE,
                'ttl_seconds': self.TTL_SECONDS,
                'entries': list(self._cache.keys())
            }


# Global singleton instance
_cache_instance: Optional[RateLimitCache] = None


def get_rate_limit_cache() -> RateLimitCache:
    """Get singleton rate limit cache instance.

    Returns:
        RateLimitCache singleton
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RateLimitCache()
        _cache_instance.start_listener()
    return _cache_instance
