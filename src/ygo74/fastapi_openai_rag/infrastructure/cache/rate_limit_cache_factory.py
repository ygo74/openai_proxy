"""Factory for creating rate limit cache instances based on configuration.

This module provides a factory function that creates the appropriate cache
implementation (Redis or in-memory) based on configuration settings, with
automatic fallback to in-memory if Redis is unavailable.
"""
import logging
from typing import Optional, TYPE_CHECKING

from .in_memory_rate_limit_cache import InMemoryRateLimitCache
from .redis_rate_limit_cache import RedisRateLimitCache

if TYPE_CHECKING:
    from ...domain.models.configuration import RedisCacheConfig

logger = logging.getLogger(__name__)


def create_rate_limit_cache(redis_config: Optional["RedisCacheConfig"] = None):
    """Create rate limit cache instance based on configuration.

    Decision logic:
    1. If redis_config is None or enabled=False → InMemoryRateLimitCache
    2. If redis_config.enabled=True → Try RedisRateLimitCache
    3. If Redis connection fails → Fallback to InMemoryRateLimitCache

    Args:
        redis_config: Optional RedisCacheConfig from domain.models.configuration.
                     If None, uses in-memory cache.

    Returns:
        Cache instance implementing IRateLimitCache protocol
    """
    # No Redis config or explicitly disabled → in-memory
    if redis_config is None or not redis_config.enabled:
        logger.info("Redis cache disabled, using in-memory cache")
        return InMemoryRateLimitCache(
            max_cache_size=64,
            ttl_seconds=30
        )

    # Try to create Redis cache
    logger.info(
        f"Attempting to connect to Redis: "
        f"host={redis_config.host}, port={redis_config.port}, db={redis_config.db}"
    )

    try:
        redis_cache = RedisRateLimitCache(
            redis_host=redis_config.host,
            redis_port=redis_config.port,
            redis_db=redis_config.db,
            redis_password=redis_config.password,
            max_cache_size=redis_config.max_cache_size,
            ttl_seconds=redis_config.ttl_seconds
        )
        logger.info("✓ Redis cache created successfully")
        return redis_cache

    except Exception as e:
        logger.warning(
            f"✗ Failed to connect to Redis (host={redis_config.host}, "
            f"port={redis_config.port}): {e}"
        )
        logger.info("Falling back to in-memory cache")
        return InMemoryRateLimitCache(
            max_cache_size=redis_config.max_cache_size,
            ttl_seconds=redis_config.ttl_seconds
        )


# Global singleton instance
_cache_instance = None


def get_rate_limit_cache(redis_config: Optional["RedisCacheConfig"] = None):
    """Get singleton rate limit cache instance.

    Args:
        redis_config: Optional RedisCacheConfig from domain.models.configuration
                     (only used on first call)

    Returns:
        Cache instance implementing IRateLimitCache protocol
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = create_rate_limit_cache(redis_config)
        _cache_instance.start_listener()

    return _cache_instance


def reset_cache_singleton():
    """Reset the cache singleton (useful for testing).

    Stops any active listeners and clears the singleton instance.
    """
    global _cache_instance

    if _cache_instance is not None:
        _cache_instance.stop_listener()
        _cache_instance = None
        logger.info("Cache singleton reset")
