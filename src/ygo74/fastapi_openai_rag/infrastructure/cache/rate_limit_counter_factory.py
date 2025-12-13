"""Factory for creating rate limit counter instances."""
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.models.configuration import RedisCacheConfig
    from ...domain.protocols.rate_limit_counter_protocol import IRateLimitCounter

logger = logging.getLogger(__name__)

# Singleton instance
_counter_instance: Optional["IRateLimitCounter"] = None


def create_rate_limit_counter(
    redis_config: Optional["RedisCacheConfig"] = None
) -> "IRateLimitCounter":
    """Create rate limit counter instance based on configuration.

    Decision logic:
    1. If redis_config is None or enabled=False → InMemoryRateLimitCounter
    2. If redis_config.enabled=True → Try RedisRateLimitCounter
    3. If Redis connection fails → Fallback to InMemoryRateLimitCounter

    Args:
        redis_config: Optional Redis configuration from AppConfig

    Returns:
        IRateLimitCounter: Counter instance (Redis or InMemory)
    """
    from .in_memory_rate_limit_counter import InMemoryRateLimitCounter
    from .redis_rate_limit_counter import RedisRateLimitCounter

    # If no config or disabled, use in-memory
    if redis_config is None or not redis_config.enabled:
        logger.info("Redis counter disabled, using InMemoryRateLimitCounter")
        return InMemoryRateLimitCounter()

    # Try to create Redis counter
    try:
        logger.info(
            f"Creating RedisRateLimitCounter: "
            f"host={redis_config.host}, port={redis_config.port}, db={redis_config.db}"
        )
        counter = RedisRateLimitCounter(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.password,
            fail_open=True
        )
        logger.info("RedisRateLimitCounter created successfully")
        return counter

    except Exception as e:
        logger.warning(
            f"Failed to create RedisRateLimitCounter: {e}. "
            f"Falling back to InMemoryRateLimitCounter"
        )
        return InMemoryRateLimitCounter()


def get_rate_limit_counter(
    redis_config: Optional["RedisCacheConfig"] = None
) -> "IRateLimitCounter":
    """Get or create singleton rate limit counter instance.

    Args:
        redis_config: Optional Redis configuration from AppConfig

    Returns:
        IRateLimitCounter: Singleton counter instance
    """
    global _counter_instance

    if _counter_instance is None:
        _counter_instance = create_rate_limit_counter(redis_config)

    return _counter_instance


def reset_counter_singleton() -> None:
    """Reset singleton counter instance.

    Useful for testing to ensure clean state between tests.
    """
    global _counter_instance

    if _counter_instance is not None:
        try:
            _counter_instance.close()
        except Exception as e:
            logger.warning(f"Error closing counter during reset: {e}")
        _counter_instance = None
        logger.debug("Counter singleton reset")
