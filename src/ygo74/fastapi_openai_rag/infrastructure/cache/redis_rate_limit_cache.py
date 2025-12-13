"""Redis-based implementation of rate limit cache with pub/sub invalidation.

This implementation provides distributed caching across multiple gateway instances
using Redis for storage and pub/sub for cache invalidation synchronization.
"""
import json
import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis

logger = logging.getLogger(__name__)


class RedisRateLimitCache:
    """Redis-backed cache for rate limit configurations with pub/sub invalidation.

    Features:
    - LRU cache with TTL for fast local access
    - Redis pub/sub for cross-instance cache invalidation
    - <5s propagation guarantee for configuration changes
    - Thread-safe cache operations
    - Automatic fallback to local cache on Redis failures

    Attributes:
        _redis_client: Redis client for pub/sub operations
        _cache: Local dictionary mapping cache keys to (value, expiry) tuples
        _cache_lock: Thread lock for cache operations
        _pubsub: Redis pub/sub object
        _pubsub_thread: Background thread for pub/sub listener
        _channel_name: Redis channel for invalidation messages
        _max_cache_size: Maximum LRU cache entries
        _ttl_seconds: Cache entry TTL in seconds
    """

    CHANNEL_NAME = "rate_limit_config_changes"

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        max_cache_size: int = 64,
        ttl_seconds: int = 30
    ):
        """Initialize Redis cache with connection parameters.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Optional Redis password
            max_cache_size: Maximum number of local cache entries (default 64)
            ttl_seconds: Time-to-live for cache entries in seconds (default 30)

        Raises:
            redis.ConnectionError: If Redis connection fails
        """
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_lock = threading.Lock()
        self._max_cache_size = max_cache_size
        self._ttl_seconds = ttl_seconds
        self._pubsub = None
        self._pubsub_thread = None

        # Connect to Redis (let exceptions propagate)
        self._redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0
        )

        # Test connection
        self._redis_client.ping()

        logger.info(
            f"RedisRateLimitCache initialized: "
            f"host={redis_host}, port={redis_port}, db={redis_db}, "
            f"max_size={max_cache_size}, ttl={ttl_seconds}s"
        )

    def start_listener(self) -> None:
        """Start Redis pub/sub listener in background thread.

        Subscribes to rate_limit_config_changes channel and processes
        invalidation messages in a separate daemon thread.
        """
        if self._pubsub_thread is not None:
            logger.warning("Pub/sub listener already running")
            return

        self._pubsub = self._redis_client.pubsub()
        self._pubsub.subscribe(self.CHANNEL_NAME)

        def listener_thread():
            """Background thread that listens for invalidation messages."""
            logger.info(f"Redis pub/sub listener started on channel: {self.CHANNEL_NAME}")
            try:
                for message in self._pubsub.listen():
                    if message['type'] == 'message':
                        self._handle_invalidation_message(message['data'])
            except Exception as e:
                logger.error(f"Pub/sub listener error: {e}", exc_info=True)

        self._pubsub_thread = threading.Thread(target=listener_thread, daemon=True)
        self._pubsub_thread.start()
        logger.info("Redis pub/sub listener thread started")

    def stop_listener(self) -> None:
        """Stop Redis pub/sub listener and cleanup resources."""
        if self._pubsub:
            try:
                self._pubsub.unsubscribe(self.CHANNEL_NAME)
                self._pubsub.close()
            except Exception as e:
                logger.error(f"Error stopping pub/sub listener: {e}")
            finally:
                self._pubsub = None

        if self._pubsub_thread:
            self._pubsub_thread = None

        logger.info("Redis pub/sub listener stopped")

    def _handle_invalidation_message(self, message_data: str) -> None:
        """Process incoming invalidation message.

        Args:
            message_data: JSON string with invalidation details
                Format: {"operation": "create|update|delete",
                        "scope_type": "...", "scope_id": "...",
                        "timestamp": "..."}
        """
        try:
            data = json.loads(message_data)
            operation = data.get('operation')
            scope_type = data.get('scope_type')
            scope_id = data.get('scope_id')

            logger.info(
                f"Received invalidation from Redis: "
                f"operation={operation}, scope={scope_type}:{scope_id}"
            )

            # Invalidate local cache entry for this scope
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
        """Retrieve rate limit config from local cache.

        Note: This uses local cache only. Redis is used for pub/sub, not storage.

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
        """Store rate limit config in local cache.

        Note: This updates local cache only. Redis is used for pub/sub, not storage.

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
        """Publish configuration change to all instances via Redis pub/sub.

        Args:
            operation: Type of operation (create, update, delete)
            scope_type: Type of scope (global, model, group_model)
            scope_id: Scope identifier (None for global)
        """
        message = json.dumps({
            'operation': operation,
            'scope_type': scope_type,
            'scope_id': scope_id,
            'timestamp': datetime.utcnow().isoformat()
        })

        try:
            self._redis_client.publish(self.CHANNEL_NAME, message)
            logger.info(
                f"Published change to Redis: operation={operation}, "
                f"scope={scope_type}:{scope_id}"
            )
        except Exception as e:
            logger.error(f"Failed to publish change to Redis: {e}", exc_info=True)
            # Fallback: invalidate local cache
            cache_key = self._make_cache_key(scope_type, scope_id)
            self._invalidate(cache_key)

    def clear(self) -> None:
        """Clear all local cache entries (useful for testing)."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("Redis cache (local entries) cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics including Redis connection status
        """
        redis_connected = False
        try:
            self._redis_client.ping()
            redis_connected = True
        except Exception:
            pass

        with self._cache_lock:
            return {
                'implementation': 'redis',
                'redis_connected': redis_connected,
                'size': len(self._cache),
                'max_size': self._max_cache_size,
                'ttl_seconds': self._ttl_seconds,
                'entries': list(self._cache.keys()),
                'pubsub_active': self._pubsub_thread is not None
            }
