"""Tests for rate limit domain models."""
import pytest
from datetime import time, datetime, timezone
from pydantic import ValidationError

from src.ygo74.fastapi_openai_rag.domain.models.rate_limit import (
    RateLimitWindow,
    RateLimit,
    RateLimitUsage,
    RateLimitErrorResponse,
    RateLimitErrorDetails
)


class TestRateLimitWindow:
    """Tests for RateLimitWindow domain model."""

    def test_rate_limit_window_creation_with_valid_time_range(self):
        """Test RateLimitWindow creation with valid time range."""
        # arrange
        from_time = time(9, 0, 0)
        to_time = time(17, 0, 0)
        max_requests = 1000
        max_tokens = 500000

        # act
        window = RateLimitWindow(
            from_time=from_time,
            to_time=to_time,
            max_requests=max_requests,
            max_tokens=max_tokens
        )

        # assert
        assert window.from_time == from_time
        assert window.to_time == to_time
        assert window.max_requests == max_requests
        assert window.max_tokens == max_tokens
        assert window.id is None  # Not yet persisted

    def test_rate_limit_window_rejects_invalid_time_ordering(self):
        """Test validation rejects to_time <= from_time."""
        # arrange
        from_time = time(17, 0, 0)
        to_time = time(9, 0, 0)  # Invalid: earlier than from_time

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimitWindow(
                from_time=from_time,
                to_time=to_time,
                max_requests=100
            )

        assert "must be after from_time" in str(exc_info.value)

    def test_rate_limit_window_rejects_equal_times(self):
        """Test validation rejects to_time == from_time."""
        # arrange
        same_time = time(12, 0, 0)

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimitWindow(
                from_time=same_time,
                to_time=same_time,
                max_requests=100
            )

        assert "must be after from_time" in str(exc_info.value)

    def test_rate_limit_window_requires_at_least_one_limit(self):
        """Test validation requires either max_requests or max_tokens."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59)
            )

        assert "At least one of max_requests or max_tokens must be set" in str(exc_info.value)

    def test_rate_limit_window_allows_unlimited_requests(self):
        """Test window can have unlimited requests (-1) with token limit."""
        # arrange & act
        window = RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=-1,  # Unlimited
            max_tokens=100000
        )

        # assert
        assert window.max_requests == -1
        assert window.max_tokens == 100000

    def test_rate_limit_window_allows_unlimited_tokens(self):
        """Test window can have unlimited tokens (-1) with request limit."""
        # arrange & act
        window = RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=-1  # Unlimited
        )

        # assert
        assert window.max_requests == 1000
        assert window.max_tokens == -1

    def test_rate_limit_window_is_active_at_within_range(self):
        """Test is_active_at() returns True when time is within window."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )

        # act & assert
        assert window.is_active_at(time(12, 30, 0)) is True

    def test_rate_limit_window_is_active_at_boundary_start(self):
        """Test is_active_at() includes from_time boundary."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )

        # act & assert
        assert window.is_active_at(time(9, 0, 0)) is True

    def test_rate_limit_window_is_active_at_boundary_end(self):
        """Test is_active_at() excludes to_time boundary."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )

        # act & assert
        assert window.is_active_at(time(17, 0, 0)) is False

    def test_rate_limit_window_is_active_at_before_range(self):
        """Test is_active_at() returns False when time is before window."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )

        # act & assert
        assert window.is_active_at(time(8, 59, 59)) is False

    def test_rate_limit_window_is_active_at_after_range(self):
        """Test is_active_at() returns False when time is after window."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )

        # act & assert
        assert window.is_active_at(time(17, 0, 1)) is False


class TestRateLimit:
    """Tests for RateLimit domain model."""

    def test_rate_limit_creation_for_global_scope(self):
        """Test RateLimit creation with global scope."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=10000,
                max_tokens=1000000
            )
        ]

        # act
        rate_limit = RateLimit(
            scope_type="global",
            windows=windows,
            enabled=True
        )

        # assert
        assert rate_limit.scope_type == "global"
        assert rate_limit.scope_id is None
        assert len(rate_limit.windows) == 1
        assert rate_limit.enabled is True

    def test_rate_limit_creation_for_model_scope(self):
        """Test RateLimit creation with model scope."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000
            )
        ]

        # act
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            windows=windows,
            enabled=True
        )

        # assert
        assert rate_limit.scope_type == "model"
        assert rate_limit.scope_id == "gpt-4"

    def test_rate_limit_creation_for_group_model_scope(self):
        """Test RateLimit creation with group_model scope."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=500
            )
        ]

        # act
        rate_limit = RateLimit(
            scope_type="group_model",
            scope_id="finance:gpt-4",
            windows=windows,
            enabled=True
        )

        # assert
        assert rate_limit.scope_type == "group_model"
        assert rate_limit.scope_id == "finance:gpt-4"

    def test_rate_limit_rejects_global_scope_with_scope_id(self):
        """Test validation rejects global scope with non-None scope_id."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=100
            )
        ]

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimit(
                scope_type="global",
                scope_id="invalid",  # Should be None for global
                windows=windows
            )

        assert "Global scope must have scope_id=None" in str(exc_info.value)

    def test_rate_limit_rejects_model_scope_without_scope_id(self):
        """Test validation rejects model scope with None scope_id."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=100
            )
        ]

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimit(
                scope_type="model",
                scope_id=None,  # Should be model name
                windows=windows
            )

        assert "scope requires scope_id to be set" in str(exc_info.value)

    def test_rate_limit_rejects_group_model_scope_without_scope_id(self):
        """Test validation rejects group_model scope with None scope_id."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=100
            )
        ]

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimit(
                scope_type="group_model",
                scope_id=None,
                windows=windows
            )

        assert "scope requires scope_id to be set" in str(exc_info.value)

    def test_rate_limit_rejects_invalid_group_model_format(self):
        """Test validation rejects group_model scope_id without colon separator."""
        # arrange
        windows = [
            RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=100
            )
        ]

        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimit(
                scope_type="group_model",
                scope_id="finance-gpt4",  # Missing colon
                windows=windows
            )

        assert "must follow 'group_name:model_name' format" in str(exc_info.value)

    def test_rate_limit_rejects_enabled_without_windows(self):
        """Test validation rejects enabled=True with empty windows."""
        # act & assert
        with pytest.raises(ValidationError) as exc_info:
            RateLimit(
                scope_type="global",
                windows=[],
                enabled=True
            )

        assert "window required when rate limit is enabled" in str(exc_info.value)

    def test_rate_limit_allows_disabled_without_windows(self):
        """Test disabled rate limit can have empty windows."""
        # act
        rate_limit = RateLimit(
            scope_type="global",
            windows=[],
            enabled=False
        )

        # assert
        assert rate_limit.enabled is False
        assert len(rate_limit.windows) == 0

    def test_rate_limit_get_active_window_returns_matching_window(self):
        """Test get_active_window() returns window matching current time."""
        # arrange
        morning_window = RateLimitWindow(
            from_time=time(6, 0, 0),
            to_time=time(12, 0, 0),
            max_requests=500
        )
        afternoon_window = RateLimitWindow(
            from_time=time(12, 0, 0),
            to_time=time(18, 0, 0),
            max_requests=1000
        )
        rate_limit = RateLimit(
            scope_type="global",
            windows=[morning_window, afternoon_window],
            enabled=True
        )

        # act
        active_window = rate_limit.get_active_window(time(10, 30, 0))

        # assert
        assert active_window == morning_window

    def test_rate_limit_get_active_window_returns_none_when_no_match(self):
        """Test get_active_window() returns None when no window matches."""
        # arrange
        window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=100
        )
        rate_limit = RateLimit(
            scope_type="global",
            windows=[window],
            enabled=True
        )

        # act
        active_window = rate_limit.get_active_window(time(22, 0, 0))

        # assert
        assert active_window is None

    def test_rate_limit_scope_identifier_for_global(self):
        """Test scope_identifier property for global scope."""
        # arrange
        rate_limit = RateLimit(
            scope_type="global",
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ]
        )

        # act & assert
        assert rate_limit.scope_identifier == "global"

    def test_rate_limit_scope_identifier_for_model(self):
        """Test scope_identifier property for model scope."""
        # arrange
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ]
        )

        # act & assert
        assert rate_limit.scope_identifier == "model:gpt-4"

    def test_rate_limit_scope_identifier_for_group_model(self):
        """Test scope_identifier property for group_model scope."""
        # arrange
        rate_limit = RateLimit(
            scope_type="group_model",
            scope_id="finance:gpt-4",
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ]
        )

        # act & assert
        assert rate_limit.scope_identifier == "group_model:finance:gpt-4"


class TestRateLimitUsage:
    """Tests for RateLimitUsage domain model."""

    def test_rate_limit_usage_creation(self):
        """Test RateLimitUsage creation with all fields."""
        # arrange
        scope_identifier = "model:gpt-4"
        metric = "requests"
        window_start = 1701936000
        window_duration = 3600
        current_count = 87
        limit = 100

        # act
        usage = RateLimitUsage(
            scope_identifier=scope_identifier,
            metric=metric,
            window_start=window_start,
            window_duration=window_duration,
            current_count=current_count,
            limit=limit
        )

        # assert
        assert usage.scope_identifier == scope_identifier
        assert usage.metric == metric
        assert usage.window_start == window_start
        assert usage.window_duration == window_duration
        assert usage.current_count == current_count
        assert usage.limit == limit

    def test_rate_limit_usage_is_exceeded_returns_true_when_at_limit(self):
        """Test is_exceeded() returns True when current_count >= limit."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=100,
            limit=100
        )

        # act & assert
        assert usage.is_exceeded() is True

    def test_rate_limit_usage_is_exceeded_returns_true_when_over_limit(self):
        """Test is_exceeded() returns True when current_count > limit."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=105,
            limit=100
        )

        # act & assert
        assert usage.is_exceeded() is True

    def test_rate_limit_usage_is_exceeded_returns_false_when_under_limit(self):
        """Test is_exceeded() returns False when current_count < limit."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=87,
            limit=100
        )

        # act & assert
        assert usage.is_exceeded() is False

    def test_rate_limit_usage_is_exceeded_returns_false_for_unlimited(self):
        """Test is_exceeded() returns False when limit is 0 (unlimited)."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=999999,
            limit=0  # Unlimited
        )

        # act & assert
        assert usage.is_exceeded() is False

    def test_rate_limit_usage_remaining_calculates_correctly(self):
        """Test remaining() returns correct remaining quota."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=87,
            limit=100
        )

        # act & assert
        assert usage.remaining() == 13

    def test_rate_limit_usage_remaining_returns_zero_when_exceeded(self):
        """Test remaining() returns 0 when limit exceeded."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=105,
            limit=100
        )

        # act & assert
        assert usage.remaining() == 0

    def test_rate_limit_usage_remaining_returns_zero_for_unlimited(self):
        """Test remaining() returns 0 for unlimited (convention)."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=500,
            limit=0  # Unlimited
        )

        # act & assert
        assert usage.remaining() == 0

    def test_rate_limit_usage_reset_at_calculates_correctly(self):
        """Test reset_at() returns correct window end timestamp."""
        # arrange
        window_start = 1701936000
        window_duration = 3600
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=window_start,
            window_duration=window_duration,
            current_count=50,
            limit=100
        )

        # act & assert
        assert usage.reset_at() == window_start + window_duration

    def test_rate_limit_usage_increment_increases_count(self):
        """Test increment() increases current_count by 1."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=87,
            limit=100
        )

        # act
        new_count = usage.increment()

        # assert
        assert new_count == 88
        assert usage.current_count == 88

    def test_rate_limit_usage_increment_with_custom_amount(self):
        """Test increment() with custom amount (for tokens)."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="tokens",
            window_start=1701936000,
            window_duration=3600,
            current_count=1000,
            limit=10000
        )

        # act
        new_count = usage.increment(amount=2500)

        # assert
        assert new_count == 3500
        assert usage.current_count == 3500


class TestRateLimitErrorResponse:
    """Tests for RateLimitErrorResponse domain model."""

    def test_rate_limit_error_response_from_usage_request_limit(self):
        """Test from_usage() creates correct error response for request limit."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="model:gpt-4",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=102,
            limit=100
        )

        # act
        error_response = RateLimitErrorResponse.from_usage(
            usage=usage,
            scope_type="model",
            scope_id="gpt-4"
        )

        # assert
        assert error_response.error.type == "rate_limit_exceeded"
        assert error_response.error.code == "model_rate_limit_exceeded"
        assert "gpt-4" in error_response.error.message
        assert error_response.error.details.scope_type == "model"
        assert error_response.error.details.scope_id == "gpt-4"
        assert error_response.error.details.limit_type == "requests"
        assert error_response.error.details.limit == 100
        assert error_response.error.details.window_seconds == 3600
        assert error_response.error.details.current_usage == 102

    def test_rate_limit_error_response_from_usage_token_limit(self):
        """Test from_usage() creates correct error response for token limit."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="global",
            metric="tokens",
            window_start=1701936000,
            window_duration=60,
            current_count=11000,
            limit=10000
        )

        # act
        error_response = RateLimitErrorResponse.from_usage(
            usage=usage,
            scope_type="global",
            scope_id=None
        )

        # assert
        assert error_response.error.type == "rate_limit_exceeded"
        assert error_response.error.code == "global_rate_limit_exceeded"
        assert "global" in error_response.error.message
        assert error_response.error.details.scope_type == "global"
        assert error_response.error.details.scope_id is None
        assert error_response.error.details.limit_type == "tokens"
        assert error_response.error.details.limit == 10000
        assert error_response.error.details.window_seconds == 60

    def test_rate_limit_error_response_from_usage_group_model_scope(self):
        """Test from_usage() creates correct error for group_model scope."""
        # arrange
        usage = RateLimitUsage(
            scope_identifier="group_model:finance:gpt-4",
            metric="requests",
            window_start=1701936000,
            window_duration=3600,
            current_count=51,
            limit=50
        )

        # act
        error_response = RateLimitErrorResponse.from_usage(
            usage=usage,
            scope_type="group_model",
            scope_id="finance:gpt-4"
        )

        # assert
        assert error_response.error.code == "group_model_rate_limit_exceeded"
        assert "finance:gpt-4" in error_response.error.message
        assert error_response.error.details.scope_type == "group_model"
        assert error_response.error.details.scope_id == "finance:gpt-4"

    def test_rate_limit_error_response_retry_after_calculation(self):
        """Test from_usage() calculates retry_after_seconds correctly."""
        # arrange
        current_timestamp = int(datetime.now(timezone.utc).timestamp())
        window_start = current_timestamp - 1800  # Started 30 minutes ago
        window_duration = 3600  # 1 hour window

        usage = RateLimitUsage(
            scope_identifier="global",
            metric="requests",
            window_start=window_start,
            window_duration=window_duration,
            current_count=105,
            limit=100
        )

        # act
        error_response = RateLimitErrorResponse.from_usage(
            usage=usage,
            scope_type="global"
        )

        # assert
        # Should have ~30 minutes remaining (allowing small timing variance)
        assert 1790 <= error_response.error.details.retry_after_seconds <= 1810
