"""Rate limit counter storage using Redis atomic operations.

This module implements atomic counter operations for rate limiting using Redis INCR/INCRBY.
It follows the onion architecture pattern with the infrastructure layer implementing
storage concerns while keeping the domain layer pure.

Implementation:
- Redis INCR for atomic request counting
- Redis INCRBY for token consumption tracking
- Automatic TTL management (2x window duration)
- Connection pooling and retry logic
- Fail-open behavior when Redis unavailable

Performance:
- ~0.3-0.5ms for local Redis INCR
- ~1-2ms for networked Redis
- Meets <10ms p99 requirement
"""
import logging
import time
from typing import Optional, Tuple
from redis import Redis, ConnectionPool, RedisError
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)


class RateLimitCounter:
    """Redis-backed atomic counter for rate limit enforcement.

    Provides thread-safe and distributed counter operations using Redis atomic
    commands. Supports horizontal scaling across multiple FastAPI instances.

    Key Format: `rate_limit:{scope_type}:{scope_id}:{metric}:{window_start}`
    Example: `rate_limit:model:gpt-4:requests:1701880800`

    Attributes:
        _redis_pool: Redis connection pool for efficient connection reuse
        _retry_count: Number of retries on connection failures (default: 1)
        _retry_backoff_ms: Backoff delay between retries in milliseconds (default: 100)
        _fail_open: If True, allow requests when Redis unavailable (default: True)
    """

    # Class-level variables for in-memory fallback (shared across all instances)
    import threading
    _memory_counters: dict[str, Tuple[int, float]] = {}  # key -> (count, expiry_time)
    _memory_lock = threading.Lock()

    def __init__(self,
                 host: str = "localhost",
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 connection_timeout: float = 0.5,
                 socket_timeout: float = 0.5,
                 retry_count: int = 1,
                 retry_backoff_ms: int = 100,
                 fail_open: bool = True,
                 max_connections: int = 50):
        """Initialize Redis counter with connection pooling.

        Falls back to in-memory counter if Redis is unavailable.

        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Optional Redis password
            connection_timeout: Connection timeout in seconds
            socket_timeout: Socket operation timeout in seconds
            retry_count: Number of retries on connection failures
            retry_backoff_ms: Backoff delay between retries in milliseconds
            fail_open: If True, allow requests when Redis unavailable
            max_connections: Maximum connections in the pool
        """
        self._retry_count = retry_count
        self._retry_backoff_ms = retry_backoff_ms
        self._fail_open = fail_open
        self._redis_available = False
        self._redis_pool = None

        # Try to connect to Redis
        try:
            self._redis_pool = ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=connection_timeout,
                socket_timeout=socket_timeout,
                max_connections=max_connections
            )
            # Test connection
            test_client = Redis(connection_pool=self._redis_pool)
            test_client.ping()
            self._redis_available = True
            logger.info(f"RateLimitCounter initialized with Redis: host={host}, port={port}, db={db}, fail_open={fail_open}")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory counter: {e}")
            self._redis_pool = None
            self._redis_available = False

    def increment_request_count(self,
                                scope_type: str,
                                scope_id: Optional[str],
                                window_start: int,
                                window_duration: int) -> Optional[int]:
        """Atomically increment request counter for a time window.

        Uses Redis INCR for atomic increment and EXPIRE for automatic cleanup.
        Thread-safe and works across distributed instances.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            window_start: Unix timestamp of window start
            window_duration: Window duration in seconds

        Returns:
            Optional[int]: Current count after increment, None if Redis unavailable and fail_open=True

        Raises:
            RedisError: If Redis operation fails and fail_open=False
        """
        key = self._build_key(scope_type, scope_id, "requests", window_start)
        ttl = window_duration * 2  # Keep for 2x duration for safety

        return self._increment_with_ttl(key, ttl, increment=1)

    def increment_token_count(self,
                             scope_type: str,
                             scope_id: Optional[str],
                             window_start: int,
                             window_duration: int,
                             token_count: int) -> Optional[int]:
        """Atomically increment token counter for a time window.

        Uses Redis INCRBY for atomic increment by specified amount.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            window_start: Unix timestamp of window start
            window_duration: Window duration in seconds
            token_count: Number of tokens to add

        Returns:
            Optional[int]: Current count after increment, None if Redis unavailable and fail_open=True

        Raises:
            RedisError: If Redis operation fails and fail_open=False
        """
        key = self._build_key(scope_type, scope_id, "tokens", window_start)
        ttl = window_duration * 2

        return self._increment_with_ttl(key, ttl, increment=token_count)

    def get_current_count(self,
                         scope_type: str,
                         scope_id: Optional[str],
                         metric: str,
                         window_start: int) -> Optional[int]:
        """Get current counter value without incrementing.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            metric: Counter metric ('requests' or 'tokens')
            window_start: Unix timestamp of window start

        Returns:
            Optional[int]: Current count, 0 if key doesn't exist, None if Redis unavailable
        """
        key = self._build_key(scope_type, scope_id, metric, window_start)

        # Use in-memory counter if Redis unavailable
        if not self._redis_available:
            return self._get_memory(key)

        try:
            redis_client = Redis(connection_pool=self._redis_pool)
            value = redis_client.get(key)
            return int(value) if value is not None else 0

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis connection error getting count for {key}: {e}")
            if self._fail_open:
                return 0  # Return 0 to allow request in fail-open mode
            raise

        except RedisError as e:
            logger.error(f"Redis error getting count for {key}: {e}")
            if self._fail_open:
                return 0
            raise

    def _increment_with_ttl(self, key: str, ttl: int, increment: int = 1) -> Optional[int]:
        """Atomically increment counter and set TTL using pipeline.

        Uses Redis pipeline to ensure INCR and EXPIRE execute atomically.
        Falls back to in-memory counter if Redis unavailable.

        Args:
            key: Redis key
            ttl: TTL in seconds
            increment: Amount to increment by (default: 1)

        Returns:
            Optional[int]: Current count after increment, None if Redis unavailable and fail_open=True

        Raises:
            RedisError: If Redis operation fails and fail_open=False
        """
        # Use in-memory counter if Redis unavailable
        if not self._redis_available:
            return self._increment_memory(key, ttl, increment)

        for attempt in range(self._retry_count + 1):
            try:
                redis_client = Redis(connection_pool=self._redis_pool)

                # Use pipeline for atomic INCR + EXPIRE
                pipe = redis_client.pipeline()
                if increment == 1:
                    pipe.incr(key)
                else:
                    pipe.incrby(key, increment)
                pipe.expire(key, ttl)
                results = pipe.execute()

                current_count = results[0]
                logger.debug(f"Incremented {key} by {increment} -> {current_count} (TTL={ttl}s)")
                return current_count

            except (ConnectionError, TimeoutError) as e:
                if attempt < self._retry_count:
                    # Retry with backoff
                    time.sleep(self._retry_backoff_ms / 1000.0)
                    logger.warning(f"Redis connection error on attempt {attempt + 1}, retrying: {e}")
                    continue
                else:
                    # Final attempt failed
                    logger.error(f"Redis connection failed after {self._retry_count + 1} attempts: {e}")
                    if self._fail_open:
                        logger.warning(f"Fail-open enabled: allowing request despite Redis failure")
                        return None  # Caller should handle None as "allow request"
                    raise

            except RedisError as e:
                logger.error(f"Redis error incrementing {key}: {e}")
                if self._fail_open:
                    return None
                raise

        # Should not reach here, but handle defensively
        if self._fail_open:
            return None
        raise RedisError(f"Failed to increment counter for {key} after all retries")

    def _increment_memory(self, key: str, ttl: int, increment: int = 1) -> int:
        """Increment in-memory counter (fallback when Redis unavailable).

        Args:
            key: Counter key
            ttl: TTL in seconds
            increment: Amount to increment by

        Returns:
            int: Current count after increment
        """
        import time as time_module
        current_time = time_module.time()
        expiry_time = current_time + ttl

        with self._memory_lock:
            # Clean expired entries
            expired_keys = [k for k, (_, exp) in self._memory_counters.items() if exp < current_time]
            for k in expired_keys:
                del self._memory_counters[k]

            # Increment counter
            if key in self._memory_counters:
                count, _ = self._memory_counters[key]
                count += increment
                self._memory_counters[key] = (count, expiry_time)
            else:
                count = increment
                self._memory_counters[key] = (count, expiry_time)

            logger.debug(f"In-memory counter: {key} = {count}")
            return count

    def _get_memory(self, key: str) -> int:
        """Get in-memory counter value (fallback when Redis unavailable).

        Args:
            key: Counter key

        Returns:
            int: Current count, 0 if key doesn't exist or expired
        """
        import time as time_module
        current_time = time_module.time()

        with self._memory_lock:
            if key in self._memory_counters:
                count, expiry = self._memory_counters[key]
                if expiry >= current_time:
                    return count
                # Expired
                del self._memory_counters[key]
            return 0

    def _build_key(self,
                   scope_type: str,
                   scope_id: Optional[str],
                   metric: str,
                   window_start: int) -> str:
        """Build Redis key for counter.

        Key format: rate_limit:{scope_type}:{scope_id}:{metric}:{window_start}

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            metric: Counter metric ('requests' or 'tokens')
            window_start: Unix timestamp of window start

        Returns:
            str: Redis key
        """
        scope_part = f"{scope_type}:{scope_id}" if scope_id else scope_type
        return f"rate_limit:{scope_part}:{metric}:{window_start}"

    def health_check(self) -> Tuple[bool, Optional[str]]:
        """Check Redis connection health.

        Returns:
            Tuple[bool, Optional[str]]: (is_healthy, error_message)
        """
        try:
            redis_client = Redis(connection_pool=self._redis_pool)
            redis_client.ping()
            return True, None
        except Exception as e:
            return False, str(e)

    def close(self) -> None:
        """Close Redis connection pool.

        Should be called on application shutdown.
        """
        try:
            self._redis_pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}")
