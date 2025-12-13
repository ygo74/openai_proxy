"""Tests for rate limit cache factory and configuration-based instantiation."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from ygo74.fastapi_openai_rag.domain.models.configuration import RedisCacheConfig
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory import (
    create_rate_limit_cache,
    reset_cache_singleton
)
from ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_cache import (
    InMemoryRateLimitCache
)
from ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_cache import (
    RedisRateLimitCache
)


class TestRedisCacheConfig:
    """Tests for RedisCacheConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RedisCacheConfig()

        assert config.enabled is False
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.max_cache_size == 64
        assert config.ttl_seconds == 30

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RedisCacheConfig(
            enabled=True,
            host="redis.example.com",
            port=6380,
            db=1,
            password="secret",
            max_cache_size=128,
            ttl_seconds=60
        )

        assert config.enabled is True
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == "secret"
        assert config.max_cache_size == 128
        assert config.ttl_seconds == 60


class TestCreateRateLimitCache:
    """Tests for create_rate_limit_cache factory function."""

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_cache_singleton()

    def test_no_config_creates_in_memory(self):
        """Test that no config creates in-memory cache."""
        cache = create_rate_limit_cache(redis_config=None)

        assert isinstance(cache, InMemoryRateLimitCache)

    def test_disabled_config_creates_in_memory(self):
        """Test that disabled Redis config creates in-memory cache."""
        config = RedisCacheConfig(enabled=False)
        cache = create_rate_limit_cache(redis_config=config)

        assert isinstance(cache, InMemoryRateLimitCache)

    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory.RedisRateLimitCache')
    def test_enabled_config_creates_redis(self, mock_redis_class):
        """Test that enabled Redis config creates Redis cache."""
        # Mock successful Redis connection
        mock_redis_instance = Mock()
        mock_redis_class.return_value = mock_redis_instance

        config = RedisCacheConfig(
            enabled=True,
            host="localhost",
            port=6379,
            db=0,
            max_cache_size=128,
            ttl_seconds=60
        )

        cache = create_rate_limit_cache(redis_config=config)

        # Verify Redis cache was created with correct parameters
        mock_redis_class.assert_called_once_with(
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
            redis_password=None,
            max_cache_size=128,
            ttl_seconds=60
        )
        assert cache == mock_redis_instance

    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory.RedisRateLimitCache')
    def test_redis_connection_failure_falls_back_to_in_memory(self, mock_redis_class):
        """Test that Redis connection failure falls back to in-memory cache."""
        # Mock Redis connection failure
        mock_redis_class.side_effect = Exception("Connection refused")

        config = RedisCacheConfig(
            enabled=True,
            host="unreachable-host",
            port=6379
        )

        cache = create_rate_limit_cache(redis_config=config)

        # Should fallback to in-memory cache
        assert isinstance(cache, InMemoryRateLimitCache)


class TestCacheProtocolCompliance:
    """Test that both implementations comply with the cache protocol."""

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_cache_singleton()

    def test_in_memory_cache_protocol_compliance(self):
        """Test that InMemoryRateLimitCache implements all protocol methods."""
        cache = InMemoryRateLimitCache()

        # Test all protocol methods exist and are callable
        assert callable(cache.get)
        assert callable(cache.set)
        assert callable(cache.publish_change)
        assert callable(cache.clear)
        assert callable(cache.get_stats)
        assert callable(cache.start_listener)
        assert callable(cache.stop_listener)

    def test_in_memory_cache_basic_operations(self):
        """Test basic cache operations work correctly."""
        cache = InMemoryRateLimitCache()

        # Test set/get
        test_value = {"max_requests": 100}
        cache.set("model", "1", test_value)

        result = cache.get("model", "1")
        assert result == test_value

        # Test miss
        assert cache.get("model", "999") is None

        # Test clear
        cache.clear()
        assert cache.get("model", "1") is None

    def test_in_memory_cache_stats(self):
        """Test cache statistics."""
        cache = InMemoryRateLimitCache(max_cache_size=10, ttl_seconds=60)

        stats = cache.get_stats()
        assert stats['implementation'] == 'in-memory'
        assert stats['max_size'] == 10
        assert stats['ttl_seconds'] == 60
        assert stats['size'] == 0

        # Add entry
        cache.set("model", "1", {"max_requests": 100})
        stats = cache.get_stats()
        assert stats['size'] == 1

    @patch('redis.Redis')
    def test_redis_cache_protocol_compliance(self, mock_redis_class):
        """Test that RedisRateLimitCache implements all protocol methods."""
        # Mock successful Redis connection
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = RedisRateLimitCache()

        # Test all protocol methods exist and are callable
        assert callable(cache.get)
        assert callable(cache.set)
        assert callable(cache.publish_change)
        assert callable(cache.clear)
        assert callable(cache.get_stats)
        assert callable(cache.start_listener)
        assert callable(cache.stop_listener)

    @patch('redis.Redis')
    def test_redis_cache_basic_operations(self, mock_redis_class):
        """Test basic cache operations work correctly."""
        # Mock successful Redis connection
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = RedisRateLimitCache()

        # Test set/get
        test_value = {"max_requests": 100}
        cache.set("model", "1", test_value)

        result = cache.get("model", "1")
        assert result == test_value

        # Test miss
        assert cache.get("model", "999") is None

    @patch('redis.Redis')
    def test_redis_cache_stats(self, mock_redis_class):
        """Test cache statistics."""
        # Mock successful Redis connection
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        cache = RedisRateLimitCache(max_cache_size=10, ttl_seconds=60)

        stats = cache.get_stats()
        assert stats['implementation'] == 'redis'
        assert stats['redis_connected'] is True
        assert stats['max_size'] == 10
        assert stats['ttl_seconds'] == 60
