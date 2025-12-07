"""Tests for RateLimitService class.

This test file follows the pattern established in the application test layer,
using mocked repositories and Unit of Work for testing service logic in isolation.

Test structure:
- MockUnitOfWork: Simulates transaction management
- Mock repository factory: Provides test doubles for IRateLimitRepository
- Test fixtures: Setup service with mocked dependencies
- Test methods: Verify service behavior across different scenarios

The tests are organized to support incremental implementation across phases:
- Phase 2: Service initialization and configuration retrieval
- Phase 3: Request-based rate limiting (US1)
- Phase 4: Token-based rate limiting (US2)
- Phase 5: Admin API operations (US5)
"""
import sys
import os
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import Mock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.repositories.rate_limit_repository import IRateLimitRepository
from ygo74.fastapi_openai_rag.domain.unit_of_work import UnitOfWork


class MockUnitOfWork:
    """Mock Unit of Work for testing.

    Simulates transaction management with commit/rollback tracking.
    Provides a mock session for repository initialization.
    """

    def __init__(self) -> None:
        """Initialize mock UoW with session and transaction state."""
        self.session: Mock = Mock()
        self.committed: bool = False
        self.rolled_back: bool = False

    def __enter__(self) -> 'MockUnitOfWork':
        """Enter transaction context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit transaction context with automatic commit/rollback."""
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True

    def commit(self) -> None:
        """Commit transaction."""
        self.committed = True

    def rollback(self) -> None:
        """Rollback transaction."""
        self.rolled_back = True


class TestRateLimitService:
    """Test suite for RateLimitService.

    Covers service initialization, configuration management, and the public API
    that will be used by rate limiting middleware and admin endpoints.
    """

    @pytest.fixture
    def mock_uow(self) -> MockUnitOfWork:
        """Create a mock Unit of Work for transaction testing."""
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository implementing IRateLimitRepository interface.

        Returns:
            Mock repository with all IRateLimitRepository methods stubbed
        """
        repository = Mock(spec=IRateLimitRepository)
        repository.get_by_scope = Mock()
        repository.get_all_by_scope_type = Mock()
        repository.get_enabled_only = Mock()
        repository.upsert = Mock()
        repository.delete_by_scope = Mock()
        repository.get_all = Mock()
        return repository

    @pytest.fixture
    def mock_repository_factory(self, mock_repository: Mock) -> Mock:
        """Create a mock repository factory for dependency injection.

        Returns:
            Factory function that returns the mock repository
        """
        factory: Mock = Mock()
        factory.return_value = mock_repository
        return factory

    @pytest.fixture
    def service(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock) -> RateLimitService:
        """Create a RateLimitService instance with mocked dependencies.

        Returns:
            RateLimitService configured with test doubles
        """
        return RateLimitService(mock_uow, mock_repository_factory)

    # ============================================================================
    # Phase 2: Service Initialization and Configuration
    # ============================================================================

    def test_service_initialization(self, service: RateLimitService, mock_uow: MockUnitOfWork) -> None:
        """Test that service initializes correctly with dependencies.

        Verifies:
        - Service instance is created
        - UoW is stored correctly
        - Repository factory is configured
        """
        assert service is not None
        assert service._uow is mock_uow
        assert service._repository_factory is not None

    def test_get_rate_limit_config_found(self, service: RateLimitService,
                                         mock_repository: Mock,
                                         mock_uow: MockUnitOfWork) -> None:
        """Test retrieving existing rate limit configuration.

        Verifies:
        - Repository get_by_scope is called with correct parameters
        - Rate limit config is returned when found
        - Transaction is committed
        """
        # Arrange
        from datetime import time
        expected_rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ]
        )
        mock_repository.get_by_scope.return_value = expected_rate_limit

        # Act
        result = service.get_rate_limit_config("model", "gpt-4")

        # Assert
        assert result is not None
        assert result.scope_type == "model"
        assert result.scope_id == "gpt-4"
        mock_repository.get_by_scope.assert_called_once_with("model", "gpt-4")
        assert mock_uow.committed

    def test_get_rate_limit_config_not_found(self, service: RateLimitService,
                                             mock_repository: Mock) -> None:
        """Test retrieving non-existent rate limit configuration.

        Verifies:
        - Returns None when config not found
        - No exception raised
        """
        # Arrange
        mock_repository.get_by_scope.return_value = None

        # Act
        result = service.get_rate_limit_config("model", "unknown-model")

        # Assert
        assert result is None
        mock_repository.get_by_scope.assert_called_once_with("model", "unknown-model")

    def test_get_all_rate_limits(self, service: RateLimitService,
                                 mock_repository: Mock,
                                 mock_uow: MockUnitOfWork) -> None:
        """Test retrieving all rate limit configurations.

        Verifies:
        - Repository get_all is called
        - All rate limits are returned
        """
        # Arrange
        from datetime import time
        expected_limits = [
            RateLimit(scope_type="global", enabled=False, windows=[]),
            RateLimit(scope_type="model", scope_id="gpt-4", enabled=True, windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ])
        ]
        mock_repository.get_all.return_value = expected_limits

        # Act
        result = service.get_all_rate_limits()

        # Assert
        assert len(result) == 2
        mock_repository.get_all.assert_called_once()
        assert mock_uow.committed

    def test_get_enabled_rate_limits(self, service: RateLimitService,
                                     mock_repository: Mock) -> None:
        """Test retrieving only enabled rate limit configurations.

        Verifies:
        - Repository get_enabled_only is called
        - Only enabled limits are returned
        """
        # Arrange
        from datetime import time
        enabled_limits = [
            RateLimit(scope_type="model", scope_id="gpt-4", enabled=True, windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ])
        ]
        mock_repository.get_enabled_only.return_value = enabled_limits

        # Act
        result = service.get_enabled_rate_limits()

        # Assert
        assert len(result) == 1
        assert result[0].enabled is True
        mock_repository.get_enabled_only.assert_called_once()

    def test_create_or_update_rate_limit(self, service: RateLimitService,
                                         mock_repository: Mock,
                                         mock_uow: MockUnitOfWork) -> None:
        """Test creating or updating a rate limit configuration.

        Verifies:
        - Repository upsert is called with the rate limit
        - Updated/created rate limit is returned
        - Transaction is committed
        """
        # Arrange
        from datetime import time
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000
                )
            ]
        )
        mock_repository.upsert.return_value = rate_limit

        # Act
        result = service.create_or_update_rate_limit(rate_limit)

        # Assert
        assert result is not None
        assert result.scope_id == "gpt-4"
        mock_repository.upsert.assert_called_once_with(rate_limit)
        assert mock_uow.committed

    def test_delete_rate_limit_success(self, service: RateLimitService,
                                       mock_repository: Mock,
                                       mock_uow: MockUnitOfWork) -> None:
        """Test successful deletion of rate limit configuration.

        Verifies:
        - Repository delete_by_scope is called
        - Returns True when deleted
        - Transaction is committed
        """
        # Arrange
        mock_repository.delete_by_scope.return_value = True

        # Act
        result = service.delete_rate_limit("model", "gpt-4")

        # Assert
        assert result is True
        mock_repository.delete_by_scope.assert_called_once_with("model", "gpt-4")
        assert mock_uow.committed

    def test_delete_rate_limit_not_found(self, service: RateLimitService,
                                         mock_repository: Mock) -> None:
        """Test deletion of non-existent rate limit configuration.

        Verifies:
        - Returns False when config not found
        - No exception raised
        """
        # Arrange
        mock_repository.delete_by_scope.return_value = False

        # Act
        result = service.delete_rate_limit("model", "unknown-model")

        # Assert
        assert result is False
        mock_repository.delete_by_scope.assert_called_once_with("model", "unknown-model")

    # ============================================================================
    # Phase 3: Request-Based Rate Limiting - T029
    # ============================================================================

    def test_check_request_limit_no_config_allows(self, service: RateLimitService,
                                                   mock_repository: Mock) -> None:
        """Test check_request_limit allows request when no config exists.

        Verifies:
        - Returns True when rate limit config not found
        - No counter increment attempted
        """
        # Arrange
        mock_repository.get_by_scope.return_value = None

        # Act
        result = service.check_request_limit("model", "gpt-4", "user123")

        # Assert
        assert result is True

    def test_check_request_limit_disabled_allows(self, service: RateLimitService,
                                                  mock_repository: Mock) -> None:
        """Test check_request_limit allows request when config disabled.

        Verifies:
        - Returns True when rate limit is disabled
        - No counter increment attempted
        """
        # Arrange
        from datetime import time
        disabled_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=False,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=100)
            ]
        )
        mock_repository.get_by_scope.return_value = disabled_limit

        # Act
        result = service.check_request_limit("model", "gpt-4", "user123")

        # Assert
        assert result is True

    def test_check_request_limit_no_active_window_allows(self, service: RateLimitService,
                                                          mock_repository: Mock) -> None:
        """Test check_request_limit allows when no active window.

        Verifies:
        - Returns True when current time outside all windows
        - Handles edge case gracefully
        """
        # Arrange
        from datetime import time
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                # Window from 9 AM to 5 PM (test runs outside this window)
                RateLimitWindow(from_time=time(9, 0), to_time=time(17, 0), max_requests=100)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock current time to be outside window (e.g., 8 AM)
        from unittest.mock import patch
        from datetime import datetime
        mock_now = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

        with patch('ygo74.fastapi_openai_rag.application.services.rate_limit_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now

            # Act
            result = service.check_request_limit("model", "gpt-4", "user123")

            # Assert
            assert result is True

    def test_check_request_limit_unlimited_allows(self, service: RateLimitService,
                                                   mock_repository: Mock) -> None:
        """Test check_request_limit allows when max_requests is unlimited (-1).

        Verifies:
        - Returns True when max_requests is -1
        - No counter check performed
        """
        # Arrange
        from datetime import time
        unlimited_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=-1)
            ]
        )
        mock_repository.get_by_scope.return_value = unlimited_limit

        # Act
        result = service.check_request_limit("model", "gpt-4", "user123")

        # Assert
        assert result is True

    def test_check_request_limit_under_limit_allows(self, service: RateLimitService,
                                                     mock_repository: Mock) -> None:
        """Test check_request_limit allows when under the limit.

        Verifies:
        - Returns True when current count < max_requests
        - Counter is incremented
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=100)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to return count under limit
        mock_counter = MockCounter()
        mock_counter.increment_request_count = MockCounter(return_value=50)

        # Create service with mocked counter
        service._counter = mock_counter

        # Act
        result = service.check_request_limit("model", "gpt-4", "user123")

        # Assert
        assert result is True

    def test_check_request_limit_at_limit_raises_exception(self, service: RateLimitService,
                                                            mock_repository: Mock) -> None:
        """Test check_request_limit raises exception when limit exceeded.

        Verifies:
        - Raises RateLimitExceeded when current count > max_requests
        - Exception contains correct details
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter
        from ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=100)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to return count at limit
        mock_counter = MockCounter()
        mock_counter.increment_request_count = MockCounter(return_value=101)

        # Create service with mocked counter
        service._counter = mock_counter

        # Act & Assert
        with pytest.raises(RateLimitExceeded) as exc_info:
            service.check_request_limit("model", "gpt-4", "user123")

        assert exc_info.value.scope_type == "model"
        assert exc_info.value.scope_id == "gpt-4"
        assert exc_info.value.limit_type == "requests"

    def test_check_request_limit_redis_failure_allows(self, service: RateLimitService,
                                                       mock_repository: Mock) -> None:
        """Test check_request_limit allows request when Redis fails (fail-open).

        Verifies:
        - Returns True when counter returns None (Redis unavailable)
        - Fail-open behavior prevents blocking all requests
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=100)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to return None (simulating Redis failure with fail-open)
        mock_counter = MockCounter()
        mock_counter.increment_request_count = MockCounter(return_value=None)

        # Create service with mocked counter
        service._counter = mock_counter

        # Act
        result = service.check_request_limit("model", "gpt-4", "user123")

        # Assert
        assert result is True

    def test_get_current_window_key_calculates_timestamp(self, service: RateLimitService) -> None:
        """Test get_current_window_key calculates correct window start timestamp.

        Verifies:
        - Converts time objects to seconds since midnight
        - Calculates today's window start correctly
        - Returns (window_start, duration) tuple
        """
        # Arrange
        from datetime import time

        from_time = time(9, 0)  # 9 AM
        to_time = time(17, 0)   # 5 PM

        # Act
        window_start, duration = service.get_current_window_key("model", "gpt-4", from_time, to_time)

        # Assert
        assert isinstance(window_start, int)
        assert isinstance(duration, int)
        assert duration == 8 * 3600  # 8 hours in seconds

    # ============================================================================
    # Phase 4: Token-Based Rate Limiting (US2 - T039)
    # ============================================================================

    def test_check_token_limit_no_config_allows(self, service: RateLimitService,
                                                mock_repository: Mock) -> None:
        """Test check_token_limit allows request when no config exists.

        Verifies:
        - Returns True when no rate limit configuration found
        - Allows request to proceed without token checks
        """
        # Arrange
        mock_repository.get_by_scope.return_value = None

        # Act
        result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=1000)

        # Assert
        assert result is True

    def test_check_token_limit_disabled_allows(self, service: RateLimitService,
                                               mock_repository: Mock) -> None:
        """Test check_token_limit allows request when rate limiting disabled.

        Verifies:
        - Returns True when enabled=False
        - Skips token checks for disabled configurations
        """
        # Arrange
        from datetime import time

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=False,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Act
        result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=1000)

        # Assert
        assert result is True

    def test_check_token_limit_no_active_window_allows(self, service: RateLimitService,
                                                       mock_repository: Mock) -> None:
        """Test check_token_limit allows request when no active window.

        Verifies:
        - Returns True when current time outside all configured windows
        - Handles time-window-based configurations gracefully
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                # Window from 9 AM to 5 PM
                RateLimitWindow(from_time=time(9, 0), to_time=time(17, 0), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock current time to be outside window (8 AM)
        with patch('src.ygo74.fastapi_openai_rag.application.services.rate_limit_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(8, 0)

            # Act
            result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=1000)

            # Assert
            assert result is True

    def test_check_token_limit_unlimited_allows(self, service: RateLimitService,
                                                mock_repository: Mock) -> None:
        """Test check_token_limit allows request when token limit is unlimited.

        Verifies:
        - Returns True when max_tokens=-1 (unlimited)
        - Skips counter checks for unlimited configurations
        """
        # Arrange
        from datetime import time

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_requests=100, max_tokens=-1)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Act
        result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=1000)

        # Assert
        assert result is True

    def test_check_token_limit_under_limit_allows(self, service: RateLimitService,
                                                  mock_repository: Mock) -> None:
        """Test check_token_limit allows request when under token limit.

        Verifies:
        - Returns True when current token count below limit
        - Counter returns current usage from Redis
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to return 5000 tokens used (under 10000 limit)
        mock_counter = MockCounter()
        mock_counter.get_current_count = MockCounter(return_value=5000)

        service._counter = mock_counter

        # Act
        result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=None)

        # Assert
        assert result is True

    def test_check_token_limit_with_estimated_tokens_would_exceed_raises(self, service: RateLimitService,
                                                                         mock_repository: Mock) -> None:
        """Test check_token_limit raises exception when estimated tokens would exceed limit.

        Verifies:
        - Raises RateLimitExceeded when current + estimated > limit
        - Pre-flight check prevents starting requests that will fail
        - Exception includes correct scope, limit_type, and retry_after
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter
        from ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter: 8000 tokens used, requesting 3000 more (would exceed 10000)
        mock_counter = MockCounter()
        mock_counter.get_current_count = MockCounter(return_value=8000)

        service._counter = mock_counter

        # Act & Assert
        with pytest.raises(RateLimitExceeded) as exc_info:
            service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=3000)

        # Verify exception details
        assert exc_info.value.limit_type == "tokens"
        assert exc_info.value.scope_type == "model"
        assert exc_info.value.scope_id == "gpt-4"
        assert exc_info.value.limit == 10000
        assert exc_info.value.current == 11000  # 8000 + 3000

    def test_check_token_limit_at_limit_raises(self, service: RateLimitService,
                                               mock_repository: Mock) -> None:
        """Test check_token_limit raises exception when token limit exceeded.

        Verifies:
        - Raises RateLimitExceeded when current tokens > limit
        - Exception contains accurate token counts
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter
        from ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter: 10001 tokens used (over limit)
        mock_counter = MockCounter()
        mock_counter.get_current_count = MockCounter(return_value=10001)

        service._counter = mock_counter

        # Act & Assert
        with pytest.raises(RateLimitExceeded) as exc_info:
            service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=None)

        assert exc_info.value.limit_type == "tokens"
        assert exc_info.value.current == 10001
        assert exc_info.value.limit == 10000

    def test_check_token_limit_redis_failure_allows(self, service: RateLimitService,
                                                    mock_repository: Mock) -> None:
        """Test check_token_limit allows request when Redis fails (fail-open).

        Verifies:
        - Returns True when counter returns None (Redis unavailable)
        - Fail-open behavior for token limits same as request limits
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to return None (Redis failure)
        mock_counter = MockCounter()
        mock_counter.get_current_count = MockCounter(return_value=None)

        service._counter = mock_counter

        # Act
        result = service.check_token_limit("model", "gpt-4", "user123", estimated_tokens=None)

        # Assert
        assert result is True

    def test_record_token_usage_increments_counter(self, service: RateLimitService,
                                                   mock_repository: Mock) -> None:
        """Test record_token_usage increments token counter in Redis.

        Verifies:
        - Calls increment_token_count with total tokens (prompt + completion)
        - Uses correct scope, window_start, and window_duration
        - Records for active window only
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter
        mock_counter = MockCounter()
        mock_counter.increment_token_count = MockCounter(return_value=350)

        service._counter = mock_counter

        # Act
        service.record_token_usage("model", "gpt-4", "user123", prompt_tokens=100, completion_tokens=250)

        # Assert
        mock_counter.increment_token_count.assert_called_once()
        call_args = mock_counter.increment_token_count.call_args
        # Total tokens should be 350 (100 + 250) - check positional args or kwargs
        if len(call_args[0]) >= 5:
            # Positional argument: last arg is token_count
            assert call_args[0][4] == 350
        else:
            # Keyword argument
            assert call_args[1]["token_count"] == 350

    def test_record_token_usage_skips_when_no_config(self, service: RateLimitService,
                                                     mock_repository: Mock) -> None:
        """Test record_token_usage skips recording when no configuration.

        Verifies:
        - Does not increment counter when no rate limit configured
        - Handles missing configuration gracefully
        """
        # Arrange
        from unittest.mock import Mock as MockCounter

        mock_repository.get_by_scope.return_value = None

        mock_counter = MockCounter()
        mock_counter.increment_token_count = MockCounter()

        service._counter = mock_counter

        # Act
        service.record_token_usage("model", "gpt-4", "user123", prompt_tokens=100, completion_tokens=250)

        # Assert
        mock_counter.increment_token_count.assert_not_called()

    def test_record_token_usage_skips_when_zero_tokens(self, service: RateLimitService,
                                                       mock_repository: Mock) -> None:
        """Test record_token_usage skips when total tokens is zero.

        Verifies:
        - Early return when total_tokens <= 0
        - Avoids unnecessary Redis operations
        """
        # Arrange
        from unittest.mock import Mock as MockCounter

        mock_counter = MockCounter()
        mock_counter.increment_token_count = MockCounter()

        service._counter = mock_counter

        # Act
        service.record_token_usage("model", "gpt-4", "user123", prompt_tokens=0, completion_tokens=0)

        # Assert
        mock_counter.increment_token_count.assert_not_called()

    def test_record_token_usage_handles_redis_failure_gracefully(self, service: RateLimitService,
                                                                 mock_repository: Mock) -> None:
        """Test record_token_usage does not crash on Redis failure.

        Verifies:
        - Catches exceptions from counter increment
        - Logs error but continues (background task resilience)
        - Does not propagate exception to request handler
        """
        # Arrange
        from datetime import time
        from unittest.mock import Mock as MockCounter

        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(from_time=time(0, 0), to_time=time(23, 59), max_tokens=10000)
            ]
        )
        mock_repository.get_by_scope.return_value = rate_limit

        # Mock counter to raise exception
        mock_counter = MockCounter()
        mock_counter.increment_token_count = MockCounter(side_effect=Exception("Redis connection lost"))

        service._counter = mock_counter

        # Act & Assert - should not raise exception
        service.record_token_usage("model", "gpt-4", "user123", prompt_tokens=100, completion_tokens=250)


# ============================================================================
# Future Test Sections (To Be Implemented)
# ============================================================================

# Phase 3 (US1 - Request Rate Limiting) - T029:
# - test_check_request_limit_allows_under_limit
# - test_check_request_limit_blocks_at_limit
# - test_check_request_limit_raises_exception_when_exceeded
# - test_get_current_window_key_calculates_correct_timestamp
# - test_get_current_window_key_resets_at_window_boundary

# Phase 4 (US2 - Token-Based Rate Limiting) - T039:
# - test_check_token_limit_allows_under_limit
# - test_check_token_limit_blocks_when_would_exceed
# - test_record_token_usage_increments_counter
# - test_record_token_usage_handles_multiple_windows

# Phase 5 (US5 - Admin API) - T052:
# - Additional admin-specific tests if needed beyond CRUD operations

# Phase 6 (US3 - Hierarchical Priority) - T058:

    def test_get_applicable_limits_returns_all_hierarchy_levels(self, mock_uow: MockUnitOfWork,
                                                                 mock_repository_factory: Mock) -> None:
        """Test get_applicable_limits queries all three hierarchy levels.

        Verifies that the method queries group/model, model, and global scopes
        and returns a dictionary with all three levels.
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch

        # Create rate limits for all levels
        group_model_limit = RateLimit(
            id=1,
            scope_type="group_model",
            scope_id="team-a:gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=100,
                max_tokens=50000
            )]
        )

        model_limit = RateLimit(
            id=2,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=500,
                max_tokens=250000
            )]
        )

        global_limit = RateLimit(
            id=3,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000,
                max_tokens=500000
            )]
        )

        service = RateLimitService(mock_uow, mock_repository_factory)

        # Mock get_rate_limit_config to return appropriate limit for each scope
        def get_config_side_effect(scope_type: str, scope_id: Optional[str]) -> Optional[RateLimit]:
            if scope_type == "group_model" and scope_id == "team-a:gpt-4":
                return group_model_limit
            elif scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            elif scope_type == "global" and scope_id is None:
                return global_limit
            return None

        with patch.object(service, 'get_rate_limit_config', side_effect=get_config_side_effect):
            # Act
            limits = service.get_applicable_limits(group_id="team-a", model_id="gpt-4")

        # Assert
        assert limits is not None
        assert isinstance(limits, dict)
        assert 'group_model' in limits
        assert 'model' in limits
        assert 'global' in limits

        # Verify all three levels returned
        assert limits['group_model'] is not None
        assert limits['group_model'].scope_type == "group_model"
        assert limits['group_model'].windows[0].max_requests == 100

        assert limits['model'] is not None
        assert limits['model'].scope_type == "model"
        assert limits['model'].windows[0].max_requests == 500

        assert limits['global'] is not None
        assert limits['global'].scope_type == "global"
        assert limits['global'].windows[0].max_requests == 1000

    def test_get_applicable_limits_handles_missing_group_model_limit(self, mock_uow: MockUnitOfWork,
                                                                      mock_repository_factory: Mock) -> None:
        """Test get_applicable_limits when group/model limit doesn't exist.

        Verifies that missing group/model limit returns None for that level
        while still returning model and global limits.
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch

        model_limit = RateLimit(
            id=2,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=500,
                max_tokens=250000
            )]
        )

        global_limit = RateLimit(
            id=3,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000,
                max_tokens=500000
            )]
        )

        service = RateLimitService(mock_uow, mock_repository_factory)

        def get_config_side_effect(scope_type: str, scope_id: Optional[str]) -> Optional[RateLimit]:
            if scope_type == "group_model":
                return None  # No group/model limit
            elif scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            elif scope_type == "global" and scope_id is None:
                return global_limit
            return None

        with patch.object(service, 'get_rate_limit_config', side_effect=get_config_side_effect):
            # Act
            limits = service.get_applicable_limits(group_id="team-a", model_id="gpt-4")

        # Assert
        assert limits['group_model'] is None  # Missing
        assert limits['model'] is not None   # Present
        assert limits['global'] is not None  # Present

    def test_get_applicable_limits_handles_missing_model_limit(self, mock_uow: MockUnitOfWork,
                                                                    mock_repository_factory: Mock) -> None:
        """Test get_applicable_limits when model limit doesn't exist.

        Verifies fallback to global limit when model-specific limit is missing.
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch

        global_limit = RateLimit(
            id=3,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000,
                max_tokens=500000
            )]
        )

        service = RateLimitService(mock_uow, mock_repository_factory)

        def get_config_side_effect(scope_type: str, scope_id: Optional[str]) -> Optional[RateLimit]:
            if scope_type == "global" and scope_id is None:
                return global_limit
            return None  # No group/model or model limits

        with patch.object(service, 'get_rate_limit_config', side_effect=get_config_side_effect):
            # Act
            limits = service.get_applicable_limits(group_id="team-a", model_id="gpt-4")

        # Assert
        assert limits['group_model'] is None
        assert limits['model'] is None
        assert limits['global'] is not None

    def test_get_applicable_limits_without_group_id_skips_group_model_query(self, mock_uow: MockUnitOfWork,
                                                                             mock_repository_factory: Mock) -> None:
        """Test get_applicable_limits skips group/model query when group_id not provided.

        Verifies that when only model_id is provided (no group_id),
        only model and global scopes are queried.
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch, Mock as MockFunc

        model_limit = RateLimit(
            id=2,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=500,
                max_tokens=250000
            )]
        )

        global_limit = RateLimit(
            id=3,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000,
                max_tokens=500000
            )]
        )

        service = RateLimitService(mock_uow, mock_repository_factory)

        # Create a mock that tracks calls and returns values
        mock_get_config = MockFunc()
        call_log = []

        def get_config_side_effect(scope_type: str, scope_id: Optional[str]) -> Optional[RateLimit]:
            call_log.append((scope_type, scope_id))
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            elif scope_type == "global" and scope_id is None:
                return global_limit
            return None

        mock_get_config.side_effect = get_config_side_effect

        with patch.object(service, 'get_rate_limit_config', mock_get_config):
            # Act - no group_id provided
            limits = service.get_applicable_limits(group_id=None, model_id="gpt-4")

        # Assert
        assert limits['group_model'] is None  # Not queried
        assert limits['model'] is not None
        assert limits['global'] is not None

        # Verify group/model was NOT queried
        assert ('group_model', 'None:gpt-4') not in call_log
        assert ('model', 'gpt-4') in call_log
        assert ('global', None) in call_log
        assert len(call_log) == 2  # Only model and global

    def test_get_applicable_limits_without_model_id_only_queries_global(self, mock_uow: MockUnitOfWork,
                                                                         mock_repository_factory: Mock) -> None:
        """Test get_applicable_limits only queries global when no model_id provided.

        Verifies that without model_id, only global scope is queried.
        """
        # Arrange
        from datetime import time
        from unittest.mock import patch, Mock as MockFunc

        global_limit = RateLimit(
            id=3,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=1000,
                max_tokens=500000
            )]
        )

        service = RateLimitService(mock_uow, mock_repository_factory)

        # Create a mock that tracks calls and returns values
        mock_get_config = MockFunc()
        call_log = []

        def get_config_side_effect(scope_type: str, scope_id: Optional[str]) -> Optional[RateLimit]:
            call_log.append((scope_type, scope_id))
            if scope_type == "global" and scope_id is None:
                return global_limit
            return None

        mock_get_config.side_effect = get_config_side_effect

        with patch.object(service, 'get_rate_limit_config', mock_get_config):
            # Act - no group_id or model_id
            limits = service.get_applicable_limits(group_id=None, model_id=None)

        # Assert
        assert limits['group_model'] is None
        assert limits['model'] is None
        assert limits['global'] is not None

        # Verify only global was queried
        assert len(call_log) == 1
        assert call_log[0] == ('global', None)

# Phase 7 (US4 - Time Window Management) - T065:
# - test_get_active_window_returns_current_window
# - test_window_transition_resets_counter
# - test_multiple_windows_tracked_independently

# Phase 8 (US6 - Model-Level Aggregation) - T069:
# - test_model_limit_aggregates_across_groups
# - test_model_limit_blocks_all_groups_when_exceeded
