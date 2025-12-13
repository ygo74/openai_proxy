"""Test time window overlap validation."""
import pytest
from datetime import time

from src.ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from src.ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow


def test_validate_time_windows_no_overlap():
    """Test validation passes with non-overlapping windows."""
    # Arrange
    service = RateLimitService(uow=None)  # No UOW needed for validation test

    windows = [
        RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(12, 0, 0),
            max_requests=100,
            max_tokens=10000
        ),
        RateLimitWindow(
            from_time=time(12, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=200,
            max_tokens=20000
        )
    ]

    # Act & Assert - should not raise
    service._validate_time_windows(windows)


def test_validate_time_windows_with_overlap():
    """Test validation fails with overlapping windows."""
    # Arrange
    service = RateLimitService(uow=None)

    windows = [
        RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=10000
        ),
        RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=10000
        )
    ]

    # Act & Assert
    with pytest.raises(ValueError, match="Time windows overlap"):
        service._validate_time_windows(windows)


def test_validate_time_windows_partial_overlap():
    """Test validation fails with partial overlap."""
    # Arrange
    service = RateLimitService(uow=None)

    windows = [
        RateLimitWindow(
            from_time=time(9, 0, 0),
            to_time=time(17, 0, 0),  # 9am-5pm
            max_requests=1000,
            max_tokens=100000
        ),
        RateLimitWindow(
            from_time=time(16, 0, 0),  # Starts at 4pm (before 5pm)
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=10000
        )
    ]

    # Act & Assert
    with pytest.raises(ValueError, match="Time windows overlap"):
        service._validate_time_windows(windows)


def test_validate_time_windows_invalid_range():
    """Test validation fails when from_time >= to_time (caught by Pydantic)."""
    # Arrange - Pydantic validation happens during model construction

    # Act & Assert - Pydantic raises ValidationError before we even call the service
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="to_time.*must be after from_time"):
        RateLimitWindow(
            from_time=time(17, 0, 0),
            to_time=time(9, 0, 0),  # to_time before from_time
            max_requests=100,
            max_tokens=10000
        )


def test_validate_time_windows_empty_list():
    """Test validation fails with empty windows list."""
    # Arrange
    service = RateLimitService(uow=None)

    # Act & Assert
    with pytest.raises(ValueError, match="At least one time window is required"):
        service._validate_time_windows([])


def test_validate_time_windows_three_windows_no_overlap():
    """Test validation with three non-overlapping windows."""
    # Arrange
    service = RateLimitService(uow=None)

    windows = [
        RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(8, 0, 0),
            max_requests=50,
            max_tokens=5000
        ),
        RateLimitWindow(
            from_time=time(8, 0, 0),
            to_time=time(18, 0, 0),
            max_requests=1000,
            max_tokens=100000
        ),
        RateLimitWindow(
            from_time=time(18, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=10000
        )
    ]

    # Act & Assert - should not raise
    service._validate_time_windows(windows)


def test_validate_time_windows_unsorted_input():
    """Test validation works with unsorted windows (internal sorting)."""
    # Arrange
    service = RateLimitService(uow=None)

    # Windows provided in reverse order
    windows = [
        RateLimitWindow(
            from_time=time(18, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=10000
        ),
        RateLimitWindow(
            from_time=time(8, 0, 0),
            to_time=time(18, 0, 0),
            max_requests=1000,
            max_tokens=100000
        ),
        RateLimitWindow(
            from_time=time(0, 0, 0),
            to_time=time(8, 0, 0),
            max_requests=50,
            max_tokens=5000
        )
    ]

    # Act & Assert - should not raise (internal sorting handles it)
    service._validate_time_windows(windows)
