"""Tests for hierarchical rate limit priority evaluation (T056, T057).

Tests verify:
- T056: Hierarchical priority (group/model → model → global)
- T057: Unlimited limit handling (-1 or None skips to next level)
"""
import sys
import os
from datetime import time
from unittest.mock import Mock, patch
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self):
        self.session = Mock()
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class TestHierarchicalPriority:
    """Test T056: Hierarchical limit priority evaluation."""

    @pytest.fixture
    def mock_uow(self):
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository_factory(self):
        return Mock()

    @pytest.fixture
    def mock_counter(self):
        """Mock counter that returns current count."""
        counter = Mock()
        counter.increment_request_count = Mock(return_value=50)  # Under limit
        counter.get_current_count = Mock(return_value=5000)  # Token count
        return counter

    @pytest.fixture
    def service(self, mock_uow, mock_repository_factory, mock_counter):
        return RateLimitService(
            mock_uow,
            mock_repository_factory,
            counter=mock_counter
        )

    def test_check_request_limit_uses_group_model_when_all_exist(self, service, mock_counter):
        """Test that group+model limit takes precedence when all three levels exist."""
        # Arrange
        group_model_limit = RateLimit(
            scope_type="group_model",
            scope_id="team-a:gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=100  # Most restrictive
            )]
        )

        model_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=500
            )]
        )

        global_limit = RateLimit(
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=1000
            )]
        )

        # Mock get_applicable_limits to return all three
        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': group_model_limit,
            'model': model_limit,
            'global': global_limit
        }):
            # Act
            result = service.check_request_limit(
                scope_type=None,  # Old API ignored when group_id/model_id provided
                scope_id=None,
                group_id="team-a",
                model_id="gpt-4"
            )

        # Assert
        assert result is True
        # Verify counter was called with group_model scope (highest priority)
        mock_counter.increment_request_count.assert_called_once()
        call_args = mock_counter.increment_request_count.call_args[0]
        assert call_args[0] == "group_model"  # scope_type
        assert call_args[1] == "team-a:gpt-4"  # scope_id

    def test_check_request_limit_falls_back_to_model_when_group_model_missing(self, service, mock_counter):
        """Test that model limit used when group+model limit doesn't exist."""
        # Arrange
        model_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=500
            )]
        )

        global_limit = RateLimit(
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=1000
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': None,  # Missing
            'model': model_limit,
            'global': global_limit
        }):
            # Act
            result = service.check_request_limit(
                scope_type=None,
                scope_id=None,
                group_id="team-a",
                model_id="gpt-4"
            )

        # Assert
        assert result is True
        call_args = mock_counter.increment_request_count.call_args[0]
        assert call_args[0] == "model"  # Fell back to model
        assert call_args[1] == "gpt-4"

    def test_check_request_limit_falls_back_to_global_when_only_global_exists(self, service, mock_counter):
        """Test that global limit used when no specific limits exist."""
        # Arrange
        global_limit = RateLimit(
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=1000
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': None,
            'model': None,
            'global': global_limit
        }):
            # Act
            result = service.check_request_limit(
                scope_type=None,
                scope_id=None,
                group_id="team-a",
                model_id="gpt-4"
            )

        # Assert
        assert result is True
        call_args = mock_counter.increment_request_count.call_args[0]
        assert call_args[0] == "global"  # Fell back to global
        assert call_args[1] is None


class TestUnlimitedLimitHandling:
    """Test T057: Unlimited limit handling (-1 or None)."""

    @pytest.fixture
    def mock_uow(self):
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository_factory(self):
        return Mock()

    @pytest.fixture
    def mock_counter(self):
        counter = Mock()
        counter.increment_request_count = Mock(return_value=50)
        counter.get_current_count = Mock(return_value=5000)
        return counter

    @pytest.fixture
    def service(self, mock_uow, mock_repository_factory, mock_counter):
        return RateLimitService(
            mock_uow,
            mock_repository_factory,
            counter=mock_counter
        )

    def test_unlimited_request_limit_skips_to_next_level(self, service, mock_counter):
        """Test that max_requests=-1 skips to next hierarchy level."""
        # Arrange - group/model has unlimited requests
        group_model_limit = RateLimit(
            scope_type="group_model",
            scope_id="team-a:gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=-1,  # Unlimited!
                max_tokens=10000
            )]
        )

        model_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=500  # This should be skipped
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': group_model_limit,
            'model': model_limit,
            'global': None
        }):
            # Act
            result = service.check_request_limit(
                scope_type=None,
                scope_id=None,
                group_id="team-a",
                model_id="gpt-4"
            )

        # Assert
        assert result is True
        # Counter should NOT be called since limit is unlimited
        mock_counter.increment_request_count.assert_not_called()

    def test_none_request_limit_allows_unlimited(self, service, mock_counter):
        """Test that max_requests=None is treated as unlimited."""
        # Arrange
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=None,  # Explicitly None
                max_tokens=10000
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': None,
            'model': rate_limit,
            'global': None
        }):
            # Act
            result = service.check_request_limit(
                scope_type=None,
                scope_id=None,
                model_id="gpt-4"
            )

        # Assert
        assert result is True
        mock_counter.increment_request_count.assert_not_called()

    def test_unlimited_token_limit_skips_check(self, service, mock_counter):
        """Test that max_tokens=-1 skips token limit check."""
        # Arrange
        rate_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=100,
                max_tokens=-1  # Unlimited tokens!
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': None,
            'model': rate_limit,
            'global': None
        }):
            # Act
            result = service.check_token_limit(
                scope_type=None,
                scope_id=None,
                model_id="gpt-4",
                estimated_tokens=999999  # Huge number, should still pass
            )

        # Assert
        assert result is True
        mock_counter.get_current_count.assert_not_called()

    def test_hierarchical_token_limits_with_unlimited_at_top(self, service, mock_counter):
        """Test token hierarchy where group/model is unlimited but model is limited."""
        # Arrange
        group_model_limit = RateLimit(
            scope_type="group_model",
            scope_id="team-a:gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=100,
                max_tokens=-1  # Unlimited at group level
            )]
        )

        model_limit = RateLimit(
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[RateLimitWindow(
                from_time=time(0, 0),
                to_time=time(23, 59),
                max_requests=500,
                max_tokens=50000  # Limited at model level (should be ignored)
            )]
        )

        with patch.object(service, 'get_applicable_limits', return_value={
            'group_model': group_model_limit,
            'model': model_limit,
            'global': None
        }):
            # Act
            result = service.check_token_limit(
                scope_type=None,
                scope_id=None,
                group_id="team-a",
                model_id="gpt-4",
                estimated_tokens=999999
            )

        # Assert - group/model's unlimited tokens takes precedence
        assert result is True
        mock_counter.get_current_count.assert_not_called()
