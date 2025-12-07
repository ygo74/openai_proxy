"""Example demonstrating unified Redis configuration for rate limiting.

This example shows how RateLimitCounter and RateLimitCache both use
the same RedisCacheConfig from AppConfig, ensuring consistent Redis
configuration across all rate limiting components.

Usage:
    python examples/unified_redis_config_example.py
"""
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.configuration import RedisCacheConfig, AppConfig
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory import (
    create_rate_limit_counter,
    get_rate_limit_counter
)
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory import (
    create_rate_limit_cache,
    get_rate_limit_cache
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_in_memory_configuration():
    """Example 1: In-memory configuration (Redis disabled)."""
    print("\n" + "="*80)
    print("Example 1: In-Memory Configuration")
    print("="*80)

    # Create configuration with Redis disabled
    redis_config = RedisCacheConfig(enabled=False)

    # Create counter and cache with same config
    counter = create_rate_limit_counter(redis_config)
    cache = create_rate_limit_cache(redis_config)

    print(f"✓ Counter type: {type(counter).__name__}")
    print(f"✓ Cache type: {type(cache).__name__}")

    # Test counter operations
    count = counter.increment_request_count(
        scope_type="global",
        scope_id=None,
        window_start=1701880800,
        window_duration=3600
    )
    print(f"✓ Counter increment successful: count = {count}")

    # Test cache operations
    cache.set("test_key", {"max_requests": 100})
    value = cache.get("test_key")
    print(f"✓ Cache set/get successful: value = {value}")

    print("\nResult: Both counter and cache use in-memory storage ✓")


def example_2_redis_configuration_with_fallback():
    """Example 2: Redis configuration with automatic fallback."""
    print("\n" + "="*80)
    print("Example 2: Redis Configuration with Automatic Fallback")
    print("="*80)

    # Create configuration with Redis enabled (but not available)
    redis_config = RedisCacheConfig(
        enabled=True,
        host="localhost",
        port=6379,
        db=0
    )

    # Create counter and cache with same config
    counter = create_rate_limit_counter(redis_config)
    cache = create_rate_limit_cache(redis_config)

    print(f"✓ Counter type: {type(counter).__name__} (fail_open enabled)")
    print(f"✓ Cache type: {type(cache).__name__}")

    # Both should work with in-memory fallback
    count = counter.increment_request_count(
        scope_type="model",
        scope_id="gpt-4",
        window_start=1701880800,
        window_duration=3600
    )
    print(f"✓ Counter works with fallback: count = {count}")

    cache.set("test_key", {"max_tokens": 10000})
    value = cache.get("test_key")
    print(f"✓ Cache works with fallback: value = {value}")

    print("\nResult: Both components gracefully fell back to in-memory ✓")


def example_3_load_from_config_json():
    """Example 3: Load configuration from config.json."""
    print("\n" + "="*80)
    print("Example 3: Load Configuration from config.json")
    print("="*80)

    # Load AppConfig from config.json
    config_file = os.path.join(os.path.dirname(__file__), '..', 'config.json')

    if not os.path.exists(config_file):
        print(f"⚠ Config file not found: {config_file}")
        print("Skipping this example.")
        return

    app_config = AppConfig.load_from_json(config_file)
    redis_config = app_config.redis_cache

    print(f"✓ Redis configuration loaded from config.json:")
    print(f"  - Enabled: {redis_config.enabled}")
    print(f"  - Host: {redis_config.host}")
    print(f"  - Port: {redis_config.port}")
    print(f"  - DB: {redis_config.db}")
    print(f"  - Max cache size: {redis_config.max_cache_size}")
    print(f"  - TTL: {redis_config.ttl_seconds}s")

    # Create components with loaded config
    counter = get_rate_limit_counter(redis_config)
    cache = get_rate_limit_cache(redis_config)

    print(f"\n✓ Components created from config.json:")
    print(f"  - Counter type: {type(counter).__name__}")
    print(f"  - Cache: {type(cache).__name__}")

    print("\nResult: Configuration successfully loaded from config.json ✓")


def example_4_service_integration():
    """Example 4: How RateLimitService uses unified configuration."""
    print("\n" + "="*80)
    print("Example 4: RateLimitService Integration")
    print("="*80)

    print("""
The RateLimitService now uses unified Redis configuration:

1. ConfigService loads config.json
2. AppConfig contains RedisCacheConfig
3. RateLimitService initializes both counter and cache:

    app_config = self._config_service.get_config()

    # Counter initialization
    self._counter = RateLimitCounter(redis_config=app_config.redis_cache)

    # Cache initialization
    self._cache = get_rate_limit_cache(app_config.redis_cache)

4. Both components share the same configuration source
5. Both have automatic fallback to in-memory if Redis unavailable

Benefits:
✓ Single configuration source (config.json)
✓ Consistent behavior across components
✓ Automatic fallback for resilience
✓ Easy to switch between Redis and in-memory
✓ No environment variables needed
    """)

    print("Result: Unified configuration ensures consistency ✓")


def main():
    """Run all examples."""
    print("\n" + "="*80)
    print("UNIFIED REDIS CONFIGURATION FOR RATE LIMITING")
    print("="*80)
    print("""
This example demonstrates how RateLimitCounter and RateLimitCache
both use RedisCacheConfig from AppConfig, ensuring:
- Consistent Redis configuration
- Automatic fallback to in-memory
- Single source of truth (config.json)
    """)

    try:
        example_1_in_memory_configuration()
        example_2_redis_configuration_with_fallback()
        example_3_load_from_config_json()
        example_4_service_integration()

        print("\n" + "="*80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY ✓")
        print("="*80)
        print("""
To enable Redis in production:
1. Start Redis: docker run -d -p 6379:6379 redis:latest
2. Edit config.json: set "redis_cache.enabled": true
3. Restart the application

Both counter and cache will automatically use Redis!
        """)

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
