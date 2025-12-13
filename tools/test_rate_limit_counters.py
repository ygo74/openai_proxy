"""Test script to check rate limit counters."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_counter import InMemoryRateLimitCounter
from src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter import RedisRateLimitCounter
from datetime import datetime

# Create counter instance (try Redis, fallback to in-memory)
try:
    counter = RedisRateLimitCounter(host="localhost", port=6379, fail_open=True)
    counter_type = "Redis (with fail_open)"
except:
    counter = InMemoryRateLimitCounter()
    counter_type = "In-Memory"

print("=" * 60)
print(f"Testing Rate Limit Counters - Using {counter_type}")
print("=" * 60)

# For InMemory counter, show memory state
if isinstance(counter, InMemoryRateLimitCounter):
    print(f"\n📊 Current in-memory counters:")
    stats = counter.get_stats()
    print(f"   Total entries: {stats['total_keys']}")

    if stats['total_keys'] > 0:
        print(f"\n   Counter stats:")
        print(f"   - Active entries: {stats['total_keys']}")
    else:
        print("   (empty)")
else:
    print(f"\n📊 Using {counter_type} counter")
    print(f"   Health check: {'✓ OK' if counter.health_check() else '✗ Failed'}")

print("\n" + "=" * 60)
