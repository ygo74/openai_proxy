"""Tests for rate limit counter protocol-based architecture."""
import pytest
from unittest.mock import Mock, MagicMock, patch
from ygo74.fastapi_openai_rag.domain.models.configuration import RedisCacheConfig
from ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_counter import InMemoryRateLimitCounter
from ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter import RedisRateLimitCounter
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory import (
    create_rate_limit_counter,
    get_rate_limit_counter,
    reset_counter_singleton
)


class TestInMemoryRateLimitCounter:
    """Test InMemory counter implementation."""

    def test_increment_request_count(self):
        """Should increment request counter correctly."""
        # Arrange
        counter = InMemoryRateLimitCounter()

        # Act
        count1 = counter.increment_request_count("global", None, 1701880800, 3600)
        count2 = counter.increment_request_count("global", None, 1701880800, 3600)
        count3 = counter.increment_request_count("model", "gpt-4", 1701880800, 3600)

        # Assert
        assert count1 == 1
        assert count2 == 2
        assert count3 == 1

    def test_increment_token_count(self):
        """Should increment token counter correctly."""
        # Arrange
        counter = InMemoryRateLimitCounter()

        # Act
        count1 = counter.increment_token_count("global", None, 1701880800, 3600, 150)
        count2 = counter.increment_token_count("global", None, 1701880800, 3600, 200)

        # Assert
        assert count1 == 150
        assert count2 == 350

    def test_get_current_count(self):
        """Should retrieve current count correctly."""
        # Arrange
        counter = InMemoryRateLimitCounter()
        counter.increment_request_count("model", "gpt-4", 1701880800, 3600)

        # Act
        count = counter.get_current_count("model", "gpt-4", "requests", 1701880800)

        # Assert
        assert count == 1

    def test_get_nonexistent_count(self):
        """Should return 0 for non-existent counter."""
        # Arrange
        counter = InMemoryRateLimitCounter()

        # Act
        count = counter.get_current_count("model", "gpt-4", "requests", 1701880800)

        # Assert
        assert count == 0

    def test_expiry_handling(self):
        """Should handle counter expiry correctly."""
        # Arrange
        counter = InMemoryRateLimitCounter()

        # Use direct internal method to test expiry
        import time
        current_time = time.time()

        # Manually set an expired counter
        with counter._lock:
            counter._counters["test:key:requests:1701880800"] = (5, current_time - 1)  # Already expired

        # Act
        count = counter.get_current_count("test", "key", "requests", 1701880800)

        # Assert
        assert count == 0

    def test_separate_scopes(self):
        """Should keep separate counters for different scopes."""
        # Arrange
        counter = InMemoryRateLimitCounter()

        # Act
        count1 = counter.increment_request_count("global", None, 1701880800, 3600)
        count2 = counter.increment_request_count("model", "gpt-4", 1701880800, 3600)
        count3 = counter.increment_request_count("model", "gpt-3.5", 1701880800, 3600)

        # Assert
        assert count1 == 1
        assert count2 == 1
        assert count3 == 1

    def test_get_stats(self):
        """Should return counter statistics."""
        # Arrange
        counter = InMemoryRateLimitCounter(max_size=100)
        counter.increment_request_count("global", None, 1701880800, 3600)

        # Act
        stats = counter.get_stats()

        # Assert
        assert stats["total_counters"] == 1
        assert stats["max_size"] == 100

    def test_close(self):
        """Should close and cleanup resources."""
        # Arrange
        counter = InMemoryRateLimitCounter()
        counter.increment_request_count("global", None, 1701880800, 3600)

        # Act
        counter.close()
        stats = counter.get_stats()

        # Assert
        assert stats["total_counters"] == 0


class TestRedisRateLimitCounter:
    """Test Redis counter implementation."""

    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.Redis')
    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.ConnectionPool')
    def test_initialization_success(self, mock_pool_class, mock_redis_class):
        """Should initialize Redis counter successfully."""
        # Arrange
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        # Act
        counter = RedisRateLimitCounter(host="localhost", port=6379)

        # Assert
        mock_pool_class.assert_called_once()
        mock_redis.ping.assert_called_once()

    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.Redis')
    @patch('ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.ConnectionPool')
    def test_increment_request_count(self, mock_pool_class, mock_redis_class):
        """Should increment request counter in Redis."""
        # Arrange
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_pipe = Mock()
        mock_pipe.execute.return_value = [5, True]  # INCR result, EXPIRE result

        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis_class.return_value = mock_redis

        counter = RedisRateLimitCounter()

        # Act
        count = counter.increment_request_count("global", None, 1701880800, 3600)

        # Assert
        assert count == 5
        mock_pipe.incr.assert_called_once()
        mock_pipe.expire.assert_called_once()

    @patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.Redis')
    @patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter.ConnectionPool')
    def test_initialization_failure_with_fail_open(self, mock_pool_class, mock_redis_class):
        """Should handle initialization failure gracefully with fail_open=True."""
        # Arrange - simulate Redis unavailable
        redis_config = RedisCacheConfig(enabled=True, host="localhost", port=6379)

        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        mock_redis_instance = MagicMock()
        # health_check fails (Redis unavailable)
        mock_redis_instance.ping.side_effect = Exception("Connection refused")
        mock_redis_class.return_value = mock_redis_instance

        # Act - should not raise with fail_open=True
        counter = RedisRateLimitCounter(
            host=redis_config.host,
            port=redis_config.port,
            fail_open=True
        )

        # Assert - counter created, operations should fail open
        assert counter is not None

        # Test fail open behavior - increment returns inf
        count = counter.increment_request_count("global", None, 1701880800, 3600)
        assert count == float('inf')


class TestRateLimitCounterFactory:
    """Test counter factory."""

    def teardown_method(self):
        """Cleanup after each test."""
        reset_counter_singleton()

    def test_create_with_no_config(self):
        """Should create InMemory counter when no config provided."""
        # Act
        counter = create_rate_limit_counter(None)

        # Assert
        assert isinstance(counter, InMemoryRateLimitCounter)

    def test_create_with_disabled_config(self):
        """Should create InMemory counter when Redis disabled."""
        # Arrange
        config = RedisCacheConfig(enabled=False)

        # Act
        counter = create_rate_limit_counter(config)

        # Assert
        assert isinstance(counter, InMemoryRateLimitCounter)

    def test_create_with_enabled_config_unavailable(self):
        """Should create Redis counter (with fail_open) when Redis unavailable."""
        # Arrange
        config = RedisCacheConfig(
            enabled=True,
            host="invalid-host-for-testing",
            port=9999
        )

        # Act - creates Redis counter with fail_open=True
        # Redis counter handles unavailability gracefully
        counter = create_rate_limit_counter(config)

        # Assert - should be Redis counter (it will fail open on operations)
        assert isinstance(counter, RedisRateLimitCounter)

        # Test that operations fail open (return inf instead of raising)
        count = counter.increment_request_count("test", None, 1701880800, 3600)
        assert count == float('inf')

    def test_get_counter_singleton(self):
        """Should return singleton instance."""
        # Arrange
        config = RedisCacheConfig(enabled=False)

        # Act
        counter1 = get_rate_limit_counter(config)
        counter2 = get_rate_limit_counter(config)

        # Assert
        assert counter1 is counter2

    def test_reset_counter_singleton(self):
        """Should reset singleton instance."""
        # Arrange
        config = RedisCacheConfig(enabled=False)
        counter1 = get_rate_limit_counter(config)

        # Act
        reset_counter_singleton()
        counter2 = get_rate_limit_counter(config)

        # Assert
        assert counter1 is not counter2


class TestCounterProtocolCompliance:
    """Test that both implementations comply with the protocol."""

    @pytest.mark.parametrize("counter_class", [
        InMemoryRateLimitCounter,
    ])
    def test_protocol_compliance(self, counter_class):
        """Should implement all protocol methods."""
        # Arrange
        counter = counter_class()

        # Assert - check all protocol methods exist
        assert hasattr(counter, 'increment_request_count')
        assert hasattr(counter, 'increment_token_count')
        assert hasattr(counter, 'get_current_count')
        assert hasattr(counter, 'close')

    @pytest.mark.parametrize("counter_class", [
        InMemoryRateLimitCounter,
    ])
    def test_basic_operations(self, counter_class):
        """Should perform basic counter operations."""
        # Arrange
        counter = counter_class()

        # Act
        count1 = counter.increment_request_count("test", "1", 1701880800, 3600)
        count2 = counter.increment_request_count("test", "1", 1701880800, 3600)
        current = counter.get_current_count("test", "1", "requests", 1701880800)

        # Assert
        assert count1 == 1
        assert count2 == 2
        assert current == 2
