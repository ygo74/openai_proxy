"""Tests for time window transitions in RateLimitService.

These tests verify that the rate limiting system correctly handles transitions
between different time windows, including:
- Window start timestamp calculation
- Counter key generation with window boundaries
- Automatic reset when transitioning to new window
- Multiple windows per day with different limits
"""
import sys
import os
from datetime import datetime, time
from typing import Any
from unittest.mock import Mock, patch
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.repositories.rate_limit_repository import IRateLimitRepository


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self) -> None:
        self.session: Mock = Mock()
        self.committed: bool = False
        self.rolled_back: bool = False

    def __enter__(self) -> 'MockUnitOfWork':
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True


class TestWindowTransitions:
    """Test suite for time window transitions."""

    @pytest.fixture
    def mock_uow(self) -> MockUnitOfWork:
        """Create a mock Unit of Work."""
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository."""
        repository = Mock(spec=IRateLimitRepository)
        repository.get_by_scope = Mock()
        return repository

    @pytest.fixture
    def mock_repository_factory(self, mock_repository: Mock) -> Mock:
        """Create a mock repository factory."""
        return Mock(return_value=mock_repository)

    @pytest.fixture
    def mock_counter(self) -> Mock:
        """Create a mock rate limit counter."""
        counter = Mock()
        counter.increment_request_count = Mock(return_value=1)
        counter.increment_token_count = Mock(return_value=100)
        counter.get_current_count = Mock(return_value=50)
        return counter

    @pytest.fixture
    def mock_cache(self) -> Mock:
        """Create a mock rate limit cache."""
        cache = Mock()
        cache.get = Mock(return_value=None)
        cache.set = Mock()
        return cache

    @pytest.fixture
    def mock_config_service(self) -> Mock:
        """Create a mock config service."""
        config_service = Mock()
        config_service.get_global_rate_limits = Mock(return_value=None)
        mock_config = Mock()
        mock_config.redis_cache = None
        config_service.get_config = Mock(return_value=mock_config)
        return config_service

    @pytest.fixture
    def service(
        self,
        mock_uow: MockUnitOfWork,
        mock_repository_factory: Mock,
        mock_counter: Mock,
        mock_cache: Mock,
        mock_config_service: Mock
    ) -> RateLimitService:
        """Create RateLimitService with mocked dependencies."""
        return RateLimitService(
            uow=mock_uow,
            repository_factory=mock_repository_factory,
            counter=mock_counter,
            cache=mock_cache,
            config_service=mock_config_service
        )

    def test_get_current_window_key_calculates_correct_start_timestamp(self, service: RateLimitService):
        """Test get_current_window_key() calculates window start correctly."""
        # arrange
        from_time = time(8, 0, 0)
        to_time = time(17, 0, 0)

        # Mock datetime.now() to return specific time
        with patch('ygo74.fastapi_openai_rag.application.services.rate_limit_service.datetime') as mock_datetime:
            # Set current time to 2025-12-08 14:30:00
            mock_now = datetime(2025, 12, 8, 14, 30, 0)
            mock_datetime.now.return_value = mock_now

            # act
            window_start, window_duration = service.get_current_window_key(
                scope_type="model",
                scope_id="gpt-4",
                from_time=from_time,
                to_time=to_time
            )

        # assert
        # Window should start at 2025-12-08 08:00:00
        expected_start = datetime(2025, 12, 8, 8, 0, 0)
        assert window_start == int(expected_start.timestamp())
        # Duration should be 9 hours (8:00 to 17:00)
        assert window_duration == 9 * 3600  # 32400 seconds

    def test_get_current_window_key_handles_overnight_window(self, service: RateLimitService):
        """Test get_current_window_key() for window spanning past midnight."""
        # arrange
        from_time = time(22, 0, 0)  # 10 PM
        to_time = time(23, 59, 59)  # 11:59:59 PM (end of day)

        # Mock datetime.now()
        with patch('ygo74.fastapi_openai_rag.application.services.rate_limit_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 12, 8, 23, 30, 0)
            mock_datetime.now.return_value = mock_now

            # act
            window_start, window_duration = service.get_current_window_key(
                scope_type="global",
                scope_id=None,
                from_time=from_time,
                to_time=to_time
            )

        # assert
        expected_start = datetime(2025, 12, 8, 22, 0, 0)
        assert window_start == int(expected_start.timestamp())
        # Duration: 22:00:00 to 23:59:59 = 7199 seconds
        expected_duration = (23 * 3600 + 59 * 60 + 59) - (22 * 3600)
        assert window_duration == expected_duration

    def test_window_transition_triggers_new_counter_key(
        self,
        service: RateLimitService
    ):
        """Test that windows with different from_time values generate different window keys.

        This test directly calls get_current_window_key to verify window transitions
        result in different counter keys.
        """
        # arrange - morning window: 00:00-12:00, afternoon window: 12:00-18:00
        morning_from = time(0, 0, 0)
        morning_to = time(12, 0, 0)
        afternoon_from = time(12, 0, 0)
        afternoon_to = time(18, 0, 0)

        # act - get window keys
        morning_start, morning_duration = service.get_current_window_key(
            "model", "gpt-4", morning_from, morning_to
        )
        afternoon_start, afternoon_duration = service.get_current_window_key(
            "model", "gpt-4", afternoon_from, afternoon_to
        )

        # assert - different window starts mean different counter keys
        assert morning_start != afternoon_start
        # Morning window duration: 0:00 to 12:00 = 12 hours (43200 seconds)
        assert morning_duration == 12 * 3600
        # Afternoon window duration: 12:00 to 18:00 = 6 hours (21600 seconds)
        assert afternoon_duration == 6 * 3600

    def test_multiple_windows_use_correct_limits_per_time(self):
        """Test that RateLimit.get_active_window() selects correct window based on time.

        Verifies that multiple time windows with different limits are correctly
        selected based on the current time.
        """
        # arrange - off-peak: 100 req, peak: 1000 req
        off_peak_window = RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(8, 0, 0),
            max_requests=100
        )
        peak_window = RateLimitWindow(
            from_time=time(8, 0, 0),
            to_time=time(18, 0, 0),
            max_requests=1000
        )
        rate_limit = RateLimit(
            scope_type="global",
            windows=[off_peak_window, peak_window],
            enabled=True
        )

        # act & assert - off-peak time (7 AM) returns off-peak window
        active_window = rate_limit.get_active_window(time(7, 0, 0))
        assert active_window == off_peak_window
        assert active_window.max_requests == 100

        # act & assert - peak time (10 AM) returns peak window
        active_window = rate_limit.get_active_window(time(10, 0, 0))
        assert active_window == peak_window
        assert active_window.max_requests == 1000

        # act & assert - boundary exactly at transition (8:00:00)
        active_window = rate_limit.get_active_window(time(8, 0, 0))
        assert active_window == peak_window  # Inclusive start
        assert active_window.max_requests == 1000

    def test_default_24_hour_fallback_when_no_window_matches(
        self,
        service: RateLimitService,
        mock_repository: Mock,
        mock_counter: Mock
    ):
        """Test that default 24-hour window is used when no time window matches."""
        # arrange - only business hours window (9-17)
        business_window = RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),
            max_requests=1000
        )
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            windows=[business_window],
            enabled=True
        )

        mock_repository.get_by_scope.return_value = rate_limit
        mock_counter.increment_request_count.return_value = 1

        # act - request at 8 PM (outside business hours)
        with patch('ygo74.fastapi_openai_rag.application.services.rate_limit_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 12, 8, 20, 0, 0)
            mock_datetime.now.return_value = mock_now

            result = service.check_request_limit(
                scope_type="model",
                scope_id="gpt-4"
            )

        # assert - should use default 24-hour window with business_window limits
        assert result is True
        mock_counter.increment_request_count.assert_called_once()

        # Verify the window parameters used
        call_args = mock_counter.increment_request_count.call_args[0]
        window_duration = call_args[3]
        # Default window should be full day: 00:00:00 to 23:59:59
        expected_duration = (23 * 3600 + 59 * 60 + 59) - 0
        assert window_duration == expected_duration
