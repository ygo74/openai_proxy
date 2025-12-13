"""Tests for RateLimitCache with Redis pub/sub."""
import sys
import os
import json
import time as time_module
from datetime import time, datetime
from unittest.mock import MagicMock, patch, call
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache import RateLimitCache


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock_client = MagicMock()
    mock_pubsub = MagicMock()
    mock_client.pubsub.return_value = mock_pubsub
    return mock_client, mock_pubsub


@pytest.fixture
def rate_limit_cache(mock_redis_client):
    """Create RateLimitCache with mocked Redis."""
    mock_client, mock_pubsub = mock_redis_client

    with patch('redis.Redis', return_value=mock_client):
        cache = RateLimitCache(
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
            redis_password=None
        )
        yield cache


class TestRateLimitCache:
    """Test suite for RateLimitCache."""

    def test_init_creates_redis_connection(self):
        """Test cache initialization creates Redis connection."""
        # arrange & act
        with patch('redis.Redis') as mock_redis:
            cache = RateLimitCache(
                redis_host="test-host",
                redis_port=1234,
                redis_db=5,
                redis_password="secret"
            )

            # assert
            mock_redis.assert_called_once_with(
                host="test-host",
                port=1234,
                db=5,
                password="secret",
                decode_responses=True
            )

    def test_get_cache_miss_returns_none(self, rate_limit_cache):
        """Test get() returns None on cache miss."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"

        # act
        result = rate_limit_cache.get(scope_type, scope_id)

        # assert
        assert result is None

    def test_get_cache_hit_returns_value(self, rate_limit_cache):
        """Test get() returns cached value on cache hit."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"
        rate_limit = RateLimit(
            id=1,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        # act
        rate_limit_cache.set(scope_type, scope_id, rate_limit)
        result = rate_limit_cache.get(scope_type, scope_id)

        # assert
        assert result == rate_limit

    def test_get_expired_entry_returns_none(self, rate_limit_cache):
        """Test get() returns None for expired cache entries."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"
        rate_limit = RateLimit(
            id=1,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        # Set entry with past expiry
        key = rate_limit_cache._make_cache_key(scope_type, scope_id)
        past_expiry = datetime.now().replace(year=2020)
        rate_limit_cache._cache[key] = (rate_limit, past_expiry)

        # act
        result = rate_limit_cache.get(scope_type, scope_id)

        # assert
        assert result is None
        # Entry should be removed
        assert key not in rate_limit_cache._cache

    def test_set_stores_value_with_ttl(self, rate_limit_cache):
        """Test set() stores value with correct TTL."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"
        rate_limit = RateLimit(
            id=1,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        # act
        before = datetime.utcnow()
        rate_limit_cache.set(scope_type, scope_id, rate_limit)
        after = datetime.utcnow()

        # assert
        key = rate_limit_cache._make_cache_key(scope_type, scope_id)
        assert key in rate_limit_cache._cache

        stored_value, expiry = rate_limit_cache._cache[key]
        assert stored_value == rate_limit
        # Expiry should be approximately 30 seconds from now
        assert before < expiry
        delta = (expiry - before).total_seconds()
        assert 29 <= delta <= 31  # Allow 1 second tolerance for execution time

    def test_set_lru_eviction_when_full(self, rate_limit_cache):
        """Test set() evicts oldest entry when MAX_CACHE_SIZE reached."""
        # arrange
        # Fill cache to MAX_CACHE_SIZE (64)
        for i in range(64):
            rate_limit = RateLimit(
                id=i,
                scope_type="model",
                scope_id=f"model-{i}",
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=i,
                        from_time=time(0, 0),
                        to_time=time(1, 0),
                        max_requests=100,
                        max_tokens=50000
                    )
                ]
            )
            rate_limit_cache.set("model", f"model-{i}", rate_limit)

        assert len(rate_limit_cache._cache) == 64

        # act - add one more entry to trigger eviction
        new_rate_limit = RateLimit(
            id=999,
            scope_type="model",
            scope_id="new-model",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=999,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )
        rate_limit_cache.set("model", "new-model", new_rate_limit)

        # assert
        # Cache size should remain at MAX_CACHE_SIZE
        assert len(rate_limit_cache._cache) == 64

        # First entry should be evicted (FIFO)
        first_key = rate_limit_cache._make_cache_key("model", "model-0")
        assert first_key not in rate_limit_cache._cache

        # New entry should exist
        new_key = rate_limit_cache._make_cache_key("model", "new-model")
        assert new_key in rate_limit_cache._cache

    def test_publish_change_sends_redis_message(self, rate_limit_cache, mock_redis_client):
        """Test publish_change() sends message to Redis channel."""
        # arrange
        mock_client, _ = mock_redis_client
        scope_type = "model"
        scope_id = "gpt-4"

        # act
        rate_limit_cache.publish_change("update", scope_type, scope_id)

        # assert - just verify publish was called with correct channel and a valid JSON message
        call_args = mock_client.publish.call_args
        assert call_args is not None
        channel, message_str = call_args[0]

        assert channel == "rate_limit_config_changes"
        message = json.loads(message_str)
        assert message["operation"] == "update"
        assert message["scope_type"] == scope_type
        assert message["scope_id"] == scope_id
        assert "timestamp" in message

    def test_handle_invalidation_message_removes_cache_entry(self, rate_limit_cache):
        """Test _handle_invalidation_message() removes correct cache entry."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"
        rate_limit = RateLimit(
            id=1,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        rate_limit_cache.set(scope_type, scope_id, rate_limit)
        assert rate_limit_cache.get(scope_type, scope_id) is not None

        # act
        message_data = json.dumps({
            "operation": "update",
            "scope_type": scope_type,
            "scope_id": scope_id,
            "timestamp": datetime.now().isoformat()
        })

        rate_limit_cache._handle_invalidation_message(message_data)

        # assert
        assert rate_limit_cache.get(scope_type, scope_id) is None

    def test_handle_invalidation_message_ignores_invalid_json(self, rate_limit_cache):
        """Test _handle_invalidation_message() handles invalid JSON gracefully."""
        # arrange
        scope_type = "model"
        scope_id = "gpt-4"
        rate_limit = RateLimit(
            id=1,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=time(0, 0),
                    to_time=time(1, 0),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        rate_limit_cache.set(scope_type, scope_id, rate_limit)

        # act - send invalid JSON
        rate_limit_cache._handle_invalidation_message("invalid json {{{")

        # assert - cache entry should still exist
        assert rate_limit_cache.get(scope_type, scope_id) is not None

    def test_clear_removes_all_entries(self, rate_limit_cache):
        """Test clear() removes all cache entries."""
        # arrange
        for i in range(10):
            rate_limit = RateLimit(
                id=i,
                scope_type="model",
                scope_id=f"model-{i}",
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=i,
                        from_time=time(0, 0),
                        to_time=time(1, 0),
                        max_requests=100,
                        max_tokens=50000
                    )
                ]
            )
            rate_limit_cache.set("model", f"model-{i}", rate_limit)

        assert len(rate_limit_cache._cache) == 10

        # act
        rate_limit_cache.clear()

        # assert
        assert len(rate_limit_cache._cache) == 0

    def test_get_stats_returns_metrics(self, rate_limit_cache):
        """Test get_stats() returns cache metrics."""
        # arrange
        for i in range(5):
            rate_limit = RateLimit(
                id=i,
                scope_type="model",
                scope_id=f"model-{i}",
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=i,
                        from_time=time(0, 0),
                        to_time=time(1, 0),
                        max_requests=100,
                        max_tokens=50000
                    )
                ]
            )
            rate_limit_cache.set("model", f"model-{i}", rate_limit)

        # act
        stats = rate_limit_cache.get_stats()

        # assert
        assert stats["size"] == 5
        assert stats["max_size"] == 64
        assert stats["ttl_seconds"] == 30
        assert len(stats["entries"]) == 5

    def test_make_cache_key_format(self, rate_limit_cache):
        """Test _make_cache_key() creates correct key format."""
        # arrange & act
        key1 = rate_limit_cache._make_cache_key("model", "gpt-4")
        key2 = rate_limit_cache._make_cache_key("group_model", "eng:gpt-4")
        key3 = rate_limit_cache._make_cache_key("global", None)

        # assert
        assert key1 == "rate_limit:model:gpt-4"
        assert key2 == "rate_limit:group_model:eng:gpt-4"
        assert key3 == "rate_limit:global"

    def test_listener_thread_created_after_start(self, rate_limit_cache, mock_redis_client):
        """Test listener thread is created after start_listener() called."""
        # arrange
        mock_client, mock_pubsub = mock_redis_client

        # act
        rate_limit_cache.start_listener()

        # assert - check thread exists and is daemon
        assert hasattr(rate_limit_cache, '_pubsub_thread')
        assert rate_limit_cache._pubsub_thread is not None
        assert rate_limit_cache._pubsub_thread.daemon is True
        # Check subscription
        mock_pubsub.subscribe.assert_called_once_with("rate_limit_config_changes")

    def test_singleton_factory_returns_same_instance(self):
        """Test get_rate_limit_cache() returns same instance."""
        # arrange & act
        with patch('redis.Redis'):
            from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache import get_rate_limit_cache

            instance1 = get_rate_limit_cache()
            instance2 = get_rate_limit_cache()

        # assert
        assert instance1 is instance2
