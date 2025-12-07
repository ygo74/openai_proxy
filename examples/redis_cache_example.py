"""Example demonstrating Redis cache configuration and usage.

This script shows how to:
1. Load configuration from config.json
2. Create cache with automatic Redis/in-memory selection
3. Use cache for rate limit configurations
"""
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory import (
    get_rate_limit_cache,
    reset_cache_singleton
)
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from datetime import time as dt_time


def main():
    print("=" * 80)
    print("Redis Cache Configuration Example")
    print("=" * 80)

    # Step 1: Load configuration from config.json
    print("\n1. Loading configuration from config.json...")
    app_config = AppConfig.load_from_json('config.json')

    print(f"   Redis cache enabled: {app_config.redis_cache.enabled}")
    print(f"   Redis host: {app_config.redis_cache.host}")
    print(f"   Redis port: {app_config.redis_cache.port}")
    print(f"   Redis db: {app_config.redis_cache.db}")
    print(f"   Max cache size: {app_config.redis_cache.max_cache_size}")
    print(f"   TTL seconds: {app_config.redis_cache.ttl_seconds}")

    # Step 2: Create cache (with automatic fallback)
    print("\n2. Creating cache instance...")
    cache = get_rate_limit_cache(app_config.redis_cache)
    cache.start_listener()

    # Step 3: Get cache stats
    print("\n3. Cache statistics:")
    stats = cache.get_stats()
    print(f"   Implementation: {stats['implementation']}")
    print(f"   Size: {stats['size']}/{stats['max_size']}")
    print(f"   TTL: {stats['ttl_seconds']}s")

    if stats['implementation'] == 'redis':
        print(f"   Redis connected: {stats['redis_connected']}")
        print(f"   Pub/sub active: {stats['pubsub_active']}")

    # Step 4: Test cache operations
    print("\n4. Testing cache operations...")

    # Create a test rate limit config
    test_config = RateLimit(
        id=1,
        scope_type="model",
        scope_id="test-model",
        enabled=True,
        windows=[
            RateLimitWindow(
                from_time=dt_time(0, 0, 0),
                to_time=dt_time(23, 59, 59),
                max_requests=100,
                max_tokens=10000
            )
        ],
        created_at=None,
        updated_at=None
    )

    # Set in cache
    print("   Setting test config in cache...")
    cache.set("model", "test-model", test_config)

    # Get from cache
    print("   Getting test config from cache...")
    cached_config = cache.get("model", "test-model")

    if cached_config:
        print(f"   ✓ Cache HIT: Found config for model 'test-model'")
        print(f"     Enabled: {cached_config.enabled}")
        print(f"     Windows: {len(cached_config.windows)}")
    else:
        print(f"   ✗ Cache MISS: Config not found")

    # Test cache miss
    print("   Testing cache miss...")
    missing = cache.get("model", "non-existent")
    print(f"   {'✗' if missing is None else '✓'} Cache correctly returns None for missing entry")

    # Step 5: Test publish_change (invalidation)
    print("\n5. Testing cache invalidation...")
    cache.publish_change("update", "model", "test-model")
    print("   Change published")

    # Verify invalidation
    after_invalidation = cache.get("model", "test-model")
    if after_invalidation is None:
        print("   ✓ Cache correctly invalidated entry")
    else:
        print("   ⚠ Entry still in cache (may be due to timing)")

    # Step 6: Final stats
    print("\n6. Final cache statistics:")
    final_stats = cache.get_stats()
    print(f"   Size: {final_stats['size']}/{final_stats['max_size']}")

    # Cleanup
    print("\n7. Cleanup...")
    cache.clear()
    cache.stop_listener()
    reset_cache_singleton()
    print("   ✓ Cache cleared and listener stopped")

    print("\n" + "=" * 80)
    print("Example completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
