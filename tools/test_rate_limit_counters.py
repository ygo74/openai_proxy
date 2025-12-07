"""Test script to check rate limit counters."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter import RateLimitCounter
from datetime import datetime

# Create counter instance
counter = RateLimitCounter(host="localhost", port=6379, fail_open=True)

print("=" * 60)
print("Testing In-Memory Rate Limit Counters")
print("=" * 60)

# Show memory counters state
print(f"\n📊 Current in-memory counters:")
print(f"   Total entries: {len(RateLimitCounter._memory_counters)}")

if RateLimitCounter._memory_counters:
    print("\n   Stored counters:")
    for key, (count, expiry) in RateLimitCounter._memory_counters.items():
        expiry_dt = datetime.fromtimestamp(expiry)
        print(f"   - {key}")
        print(f"     Count: {count}")
        print(f"     Expires: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    print("   (empty)")

print("\n" + "=" * 60)
