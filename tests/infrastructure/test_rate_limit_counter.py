"""Tests for RateLimitCounter Redis operations."""
import pytest
from unittest.mock import Mock, patch
from redis.exceptions import ConnectionError, TimeoutError
import time

from src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter import RateLimitCounter


class TestRateLimitCounter:
    """Test suite for RateLimitCounter Redis operations."""

    @pytest.fixture
    def mock_redis_setup(self):
        """Create mock Redis client and pipeline for testing."""
        # Mock pipeline for atomic operations
        mock_pipeline = Mock()
        mock_pipeline.incr = Mock(return_value=mock_pipeline)
        mock_pipeline.incrby = Mock(return_value=mock_pipeline)
        mock_pipeline.expire = Mock(return_value=mock_pipeline)
        mock_pipeline.execute = Mock(return_value=[5, True])  # [count, expire_result]

        # Mock Redis client
        mock_redis = Mock()
        mock_redis.pipeline = Mock(return_value=mock_pipeline)
        mock_redis.get = Mock(return_value="10")  # decode_responses=True returns strings
        mock_redis.ping = Mock(return_value=True)

        # Mock connection pool
        mock_pool = Mock()
        mock_pool.disconnect = Mock()

        return mock_redis, mock_pipeline, mock_pool

    @pytest.fixture
    def counter_with_mock(self, mock_redis_setup):
        """Create counter instance with mocked Redis."""
        mock_redis, mock_pipeline, mock_pool = mock_redis_setup

        with patch('redis.ConnectionPool', return_value=mock_pool), \
             patch('redis.Redis', return_value=mock_redis):
            counter = RateLimitCounter()
            yield counter, mock_redis, mock_pipeline, mock_pool

    def test_counter_initialization(self):
        """Test counter initializes with correct Redis configuration."""
        with patch('redis.ConnectionPool') as mock_pool:
            counter = RateLimitCounter(
                host="localhost",
                port=6379,
                db=0,
                password=None,
                connection_timeout=0.5,
                socket_timeout=0.5,
                retry_count=1,
                retry_backoff_ms=100,
                fail_open=True
            )

            # Verify connection pool created with correct parameters
            mock_pool.assert_called_once()
            call_kwargs = mock_pool.call_args.kwargs
            assert call_kwargs["host"] == "localhost"
            assert call_kwargs["port"] == 6379
            assert call_kwargs["db"] == 0
            assert call_kwargs["socket_connect_timeout"] == 0.5
            assert call_kwargs["socket_timeout"] == 0.5
            assert call_kwargs["max_connections"] == 50

    def test_increment_request_count_success(self, mock_redis_setup):
        """Test successful request count increment."""
        mock_redis, mock_pipeline, mock_pool = mock_redis_setup

        with patch('redis.ConnectionPool', return_value=mock_pool), \
             patch('redis.Redis', return_value=mock_redis):
            counter = RateLimitCounter()
            window_start = int(time.time())
            window_duration = 60  # 1 minute

            result = counter.increment_request_count("global", None, window_start, window_duration)

            # Verify pipeline operations
            mock_pipeline.incr.assert_called_once()
            mock_pipeline.expire.assert_called_once()
            mock_pipeline.execute.assert_called_once()

            # Verify result
            assert result == 5

    def test_increment_token_count_success(self, mock_redis_setup):
        """Test successful token count increment."""
        mock_redis, mock_pipeline, mock_pool = mock_redis_setup

        with patch('redis.ConnectionPool', return_value=mock_pool), \
             patch('redis.Redis', return_value=mock_redis):
            counter = RateLimitCounter()
            window_start = int(time.time())
            window_duration = 60
            token_count = 150

            result = counter.increment_token_count("model", "gpt-4", window_start, window_duration, token_count)

            # Verify pipeline operations with token amount
            mock_pipeline.incrby.assert_called_once()
            # Check the first positional argument (key) and second (amount)
            call_args = mock_pipeline.incrby.call_args
            assert call_args[0][1] == token_count  # Second positional arg is the amount

            mock_pipeline.expire.assert_called_once()
            mock_pipeline.execute.assert_called_once()

            assert result == 5

    def test_get_current_count(self, mock_redis):
        """Test reading current count without incrementing."""
        mock_client, _ = mock_redis
        mock_client.get.return_value = b"42"

        counter = RateLimitCounter()
        window_start = int(time.time())

        result = counter.get_current_count("global", None, "requests", window_start)

        # Verify GET operation (not INCR)
        mock_client.get.assert_called_once()
        assert result == 42

    def test_get_current_count_key_not_exists(self, mock_redis):
        """Test reading count when key doesn't exist returns 0."""
        mock_client, _ = mock_redis
        mock_client.get.return_value = None

        counter = RateLimitCounter()
        window_start = int(time.time())

        result = counter.get_current_count("global", None, "requests", window_start)

        assert result == 0

    def test_build_key_global_scope(self):
        """Test Redis key format for global scope."""
        counter = RateLimitCounter()
        window_start = 1700000000

        key = counter._build_key("global", None, "requests", window_start)

        assert key == "rate_limit:global:requests:1700000000"

    def test_build_key_model_scope(self):
        """Test Redis key format for model scope."""
        counter = RateLimitCounter()
        window_start = 1700000000

        key = counter._build_key("model", "gpt-4", "tokens", window_start)

        assert key == "rate_limit:model:gpt-4:tokens:1700000000"

    def test_build_key_group_model_scope(self):
        """Test Redis key format for group+model scope."""
        counter = RateLimitCounter()
        window_start = 1700000000

        key = counter._build_key("group_model", "team1:gpt-4", "requests", window_start)

        assert key == "rate_limit:group_model:team1:gpt-4:requests:1700000000"

    def test_ttl_calculation(self, mock_redis):
        """Test TTL is set to 2x window duration."""
        mock_client, mock_pipeline = mock_redis

        counter = RateLimitCounter()
        window_start = int(time.time())
        window_duration = 300  # 5 minutes

        counter.increment_request_count("global", None, window_start, window_duration)

        # Verify expire called with 2x duration
        mock_pipeline.expire.assert_called_once()
        call_args = mock_pipeline.expire.call_args
        ttl_arg = call_args[0][1]  # Second positional arg is TTL
        assert ttl_arg == 600  # 2 * 300

    def test_connection_error_with_retry(self, mock_redis):
        """Test retry logic on connection error."""
        mock_client, mock_pipeline = mock_redis

        # First call fails, second succeeds
        mock_pipeline.execute.side_effect = [ConnectionError("Connection lost"), [3, True]]

        counter = RateLimitCounter(retry_count=1, retry_backoff_ms=10)
        window_start = int(time.time())

        result = counter.increment_request_count("global", None, window_start, 60)

        # Verify retry happened
        assert mock_pipeline.execute.call_count == 2
        assert result == 3

    def test_connection_error_with_fail_open(self, mock_redis):
        """Test fail-open behavior allows request on Redis failure."""
        mock_client, mock_pipeline = mock_redis

        # All retries fail
        mock_pipeline.execute.side_effect = ConnectionError("Connection lost")

        counter = RateLimitCounter(retry_count=1, retry_backoff_ms=10, fail_open=True)
        window_start = int(time.time())

        result = counter.increment_request_count("global", None, window_start, 60)

        # Verify returns None (allow request)
        assert result is None

    def test_connection_error_with_fail_close(self, mock_redis):
        """Test fail-close behavior raises exception on Redis failure."""
        mock_client, mock_pipeline = mock_redis

        # All retries fail
        mock_pipeline.execute.side_effect = ConnectionError("Connection lost")

        counter = RateLimitCounter(retry_count=1, retry_backoff_ms=10, fail_open=False)
        window_start = int(time.time())

        with pytest.raises(ConnectionError):
            counter.increment_request_count("global", None, window_start, 60)

    def test_timeout_error_with_retry(self, mock_redis):
        """Test retry logic on timeout error."""
        mock_client, mock_pipeline = mock_redis

        # First call times out, second succeeds
        mock_pipeline.execute.side_effect = [TimeoutError("Timeout"), [7, True]]

        counter = RateLimitCounter(retry_count=1, retry_backoff_ms=10)
        window_start = int(time.time())

        result = counter.increment_request_count("global", None, window_start, 60)

        # Verify retry happened
        assert mock_pipeline.execute.call_count == 2
        assert result == 7

    def test_health_check_success(self, mock_redis):
        """Test health check succeeds when Redis is available."""
        mock_client, _ = mock_redis
        mock_client.ping.return_value = True

        counter = RateLimitCounter()

        result = counter.health_check()

        mock_client.ping.assert_called_once()
        assert result is True

    def test_health_check_failure(self, mock_redis):
        """Test health check returns False on Redis failure."""
        mock_client, _ = mock_redis
        mock_client.ping.side_effect = ConnectionError("Cannot connect")

        counter = RateLimitCounter()

        result = counter.health_check()

        assert result is False

    def test_close_connection(self, mock_redis):
        """Test close properly cleans up Redis connection."""
        mock_client, _ = mock_redis

        counter = RateLimitCounter()
        counter.close()

        mock_client.close.assert_called_once()

    def test_concurrent_increments_atomic(self, mock_redis):
        """Test concurrent increments use atomic pipeline operations."""
        mock_client, mock_pipeline = mock_redis

        # Simulate concurrent calls
        mock_pipeline.execute.side_effect = [[1, True], [2, True], [3, True]]

        counter = RateLimitCounter()
        window_start = int(time.time())

        # Simulate 3 concurrent requests
        results = [
            counter.increment_request_count("global", None, window_start, 60),
            counter.increment_request_count("global", None, window_start, 60),
            counter.increment_request_count("global", None, window_start, 60)
        ]

        # Verify all operations completed
        assert results == [1, 2, 3]
        assert mock_pipeline.execute.call_count == 3

    def test_different_scopes_different_keys(self, mock_redis):
        """Test different scopes generate different Redis keys."""
        mock_client, mock_pipeline = mock_redis

        counter = RateLimitCounter()
        window_start = int(time.time())

        # Increment for different scopes
        counter.increment_request_count("global", None, window_start, 60)
        counter.increment_request_count("model", "gpt-4", window_start, 60)
        counter.increment_request_count("group_model", "team1:gpt-4", window_start, 60)

        # Verify 3 different pipeline executions (different keys)
        assert mock_pipeline.execute.call_count == 3

        # Verify different keys were used in incr calls
        incr_calls = mock_pipeline.incr.call_args_list
        keys = [call[0][0] for call in incr_calls]

        assert len(set(keys)) == 3  # All keys unique
        assert "global" in keys[0]
        assert "gpt-4" in keys[1]
        assert "team1" in keys[2]

    def test_window_boundaries(self, mock_redis):
        """Test different window starts create different keys."""
        mock_client, mock_pipeline = mock_redis

        counter = RateLimitCounter()

        # Two different time windows
        window1 = 1700000000
        window2 = 1700000060  # 1 minute later

        counter.increment_request_count("global", None, window1, 60)
        counter.increment_request_count("global", None, window2, 60)

        # Verify 2 different pipeline executions
        assert mock_pipeline.execute.call_count == 2

        # Verify different keys were used (different window_start)
        incr_calls = mock_pipeline.incr.call_args_list
        keys = [call[0][0] for call in incr_calls]

        assert keys[0] != keys[1]
        assert str(window1) in keys[0]
        assert str(window2) in keys[1]
