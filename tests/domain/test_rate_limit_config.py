"""Tests for rate limit configuration models."""
import sys
import os
from datetime import time
import pytest
from pydantic import ValidationError

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.rate_limit_config import (
    TimeWindowConfig,
    GlobalRateLimitConfig,
    RateLimitsConfig
)


class TestTimeWindowConfig:
    """Test suite for TimeWindowConfig model."""

    def test_valid_time_window_with_both_limits(self):
        """Test creating time window with both request and token limits."""
        # arrange & act
        window = TimeWindowConfig(
            from_time="09:00",
            to_time="17:00",
            max_requests=100,
            max_tokens=50000
        )

        # assert
        assert window.from_time == "09:00"
        assert window.to_time == "17:00"
        assert window.max_requests == 100
        assert window.max_tokens == 50000

    def test_valid_time_window_with_seconds(self):
        """Test time window with HH:MM:SS format."""
        # arrange & act
        window = TimeWindowConfig(
            from_time="09:30:45",
            to_time="17:15:30",
            max_requests=100,
            max_tokens=None
        )

        # assert
        assert window.from_time == "09:30:45"
        assert window.to_time == "17:15:30"

    def test_valid_time_window_with_only_requests(self):
        """Test time window with only max_requests limit."""
        # arrange & act
        window = TimeWindowConfig(
            from_time="00:00",
            to_time="23:59",
            max_requests=1000,
            max_tokens=None
        )

        # assert
        assert window.max_requests == 1000
        assert window.max_tokens is None

    def test_valid_time_window_with_only_tokens(self):
        """Test time window with only max_tokens limit."""
        # arrange & act
        window = TimeWindowConfig(
            from_time="00:00",
            to_time="23:59",
            max_requests=None,
            max_tokens=100000
        )

        # assert
        assert window.max_requests is None
        assert window.max_tokens == 100000

    def test_invalid_time_format_rejects_bad_hour(self):
        """Test validation rejects invalid hour."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="25:00",  # Invalid hour
                to_time="17:00",
                max_requests=100
            )

        assert "Time must be in HH:MM or HH:MM:SS format" in str(exc_info.value)

    def test_invalid_time_format_rejects_bad_minute(self):
        """Test validation rejects invalid minute."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="09:00",
                to_time="17:65",  # Invalid minute
                max_requests=100
            )

        assert "Time must be in HH:MM or HH:MM:SS format" in str(exc_info.value)

    def test_invalid_time_format_rejects_bad_second(self):
        """Test validation rejects invalid second."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="09:00:70",  # Invalid second
                to_time="17:00",
                max_requests=100
            )

        assert "Time must be in HH:MM or HH:MM:SS format" in str(exc_info.value)

    def test_invalid_time_format_rejects_non_time_string(self):
        """Test validation rejects non-time string."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="not-a-time",
                to_time="17:00",
                max_requests=100
            )

        assert "Time must be in HH:MM or HH:MM:SS format" in str(exc_info.value)

    def test_validation_requires_at_least_one_limit(self):
        """Test validation requires either max_requests or max_tokens."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="09:00",
                to_time="17:00",
                max_requests=None,
                max_tokens=None
            )

        assert "At least one of max_requests or max_tokens must be specified" in str(exc_info.value)

    def test_validation_rejects_zero_or_negative_requests(self):
        """Test validation rejects zero or negative max_requests."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="09:00",
                to_time="17:00",
                max_requests=0,
                max_tokens=None
            )

        assert "greater than or equal to 1" in str(exc_info.value)

    def test_validation_rejects_zero_or_negative_tokens(self):
        """Test validation rejects zero or negative max_tokens."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            TimeWindowConfig(
                from_time="09:00",
                to_time="17:00",
                max_requests=None,
                max_tokens=-100
            )

        assert "greater than or equal to 1" in str(exc_info.value)

    def test_get_from_time_converts_to_datetime_time(self):
        """Test get_from_time() converts string to time object."""
        # arrange
        window = TimeWindowConfig(
            from_time="09:30:15",
            to_time="17:00",
            max_requests=100
        )

        # act
        from_time_obj = window.get_from_time()

        # assert
        assert isinstance(from_time_obj, time)
        assert from_time_obj.hour == 9
        assert from_time_obj.minute == 30
        assert from_time_obj.second == 15

    def test_get_to_time_converts_to_datetime_time(self):
        """Test get_to_time() converts string to time object."""
        # arrange
        window = TimeWindowConfig(
            from_time="09:00",
            to_time="17:45:30",
            max_requests=100
        )

        # act
        to_time_obj = window.get_to_time()

        # assert
        assert isinstance(to_time_obj, time)
        assert to_time_obj.hour == 17
        assert to_time_obj.minute == 45
        assert to_time_obj.second == 30

    def test_get_time_handles_hh_mm_format_without_seconds(self):
        """Test get_from_time() handles HH:MM format (no seconds)."""
        # arrange
        window = TimeWindowConfig(
            from_time="09:30",
            to_time="17:00",
            max_requests=100
        )

        # act
        from_time_obj = window.get_from_time()

        # assert
        assert from_time_obj.hour == 9
        assert from_time_obj.minute == 30
        assert from_time_obj.second == 0  # Defaults to 0


class TestGlobalRateLimitConfig:
    """Test suite for GlobalRateLimitConfig model."""

    def test_valid_global_config_with_single_window(self):
        """Test creating global config with single time window."""
        # arrange & act
        config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="00:00",
                    to_time="23:59",
                    max_requests=1000,
                    max_tokens=500000
                )
            ]
        )

        # assert
        assert config.enabled is True
        assert len(config.windows) == 1
        assert config.windows[0].max_requests == 1000

    def test_valid_global_config_with_multiple_windows(self):
        """Test creating global config with multiple time windows."""
        # arrange & act
        config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="00:00",
                    to_time="08:00",
                    max_requests=100,
                    max_tokens=50000
                ),
                TimeWindowConfig(
                    from_time="08:00",
                    to_time="23:59",
                    max_requests=1000,
                    max_tokens=500000
                )
            ]
        )

        # assert
        assert len(config.windows) == 2

    def test_disabled_global_config_allows_empty_windows(self):
        """Test disabled config doesn't require windows."""
        # arrange & act
        config = GlobalRateLimitConfig(
            enabled=False,
            windows=[]
        )

        # assert
        assert config.enabled is False
        assert len(config.windows) == 0

    def test_validation_requires_windows_when_enabled(self):
        """Test enabled config requires at least one window."""
        # arrange & act & assert
        with pytest.raises(ValidationError) as exc_info:
            GlobalRateLimitConfig(
                enabled=True,
                windows=[]
            )

        assert "At least one time window must be defined" in str(exc_info.value)


class TestRateLimitsConfig:
    """Test suite for RateLimitsConfig model."""

    def test_valid_rate_limits_config_with_global_limits(self):
        """Test creating rate limits config with global limits."""
        # arrange & act
        config = RateLimitsConfig(
            global_limits=GlobalRateLimitConfig(
                enabled=True,
                windows=[
                    TimeWindowConfig(
                        from_time="00:00",
                        to_time="23:59",
                        max_requests=1000,
                        max_tokens=500000
                    )
                ]
            )
        )

        # assert
        assert config.global_limits is not None
        assert config.global_limits.enabled is True

    def test_valid_rate_limits_config_with_alias_global(self):
        """Test 'global' alias works for global_limits field."""
        # arrange
        config_dict = {
            "global": {
                "enabled": True,
                "windows": [
                    {
                        "from_time": "00:00",
                        "to_time": "23:59",
                        "max_requests": 1000,
                        "max_tokens": 500000
                    }
                ]
            }
        }

        # act
        config = RateLimitsConfig(**config_dict)

        # assert
        assert config.global_limits is not None
        assert config.global_limits.enabled is True

    def test_valid_rate_limits_config_without_global_limits(self):
        """Test rate limits config can be created without global limits."""
        # arrange & act
        config = RateLimitsConfig()

        # assert
        assert config.global_limits is None
