"""Tests for RateLimitService integration with global config fallback."""
import sys
import os
from unittest.mock import Mock, MagicMock, patch
import pytest
from datetime import time as dt_time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.domain.models.rate_limit_config import (
    TimeWindowConfig,
    GlobalRateLimitConfig
)


class TestRateLimitServiceGlobalConfigFallback:
    """Test suite for RateLimitService global config fallback integration."""

    @pytest.fixture
    def mock_uow(self):
        """Create mock Unit of Work."""
        uow = MagicMock()
        uow.__enter__ = Mock(return_value=uow)
        uow.__exit__ = Mock(return_value=False)
        uow.session = Mock()
        return uow

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return Mock()

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        cache = Mock()
        cache.get = Mock(return_value=None)  # Default: cache miss
        cache.set = Mock()
        return cache

    @pytest.fixture
    def mock_counter(self):
        """Create mock counter."""
        counter = Mock()
        counter.increment_requests = Mock(return_value=1)
        counter.increment_tokens = Mock(return_value=100)
        return counter

    @pytest.fixture
    def mock_config_service(self):
        """Create mock ConfigService."""
        return Mock()

    @pytest.fixture
    def rate_limit_service(self, mock_uow, mock_repository, mock_cache, mock_counter, mock_config_service):
        """Create RateLimitService with mocked dependencies."""
        repository_factory = lambda session: mock_repository
        service = RateLimitService(
            uow=mock_uow,
            repository_factory=repository_factory,
            counter=mock_counter,
            cache=mock_cache,
            config_service=mock_config_service
        )
        return service

    def test_get_rate_limit_config_returns_db_config_when_available(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test that database config takes priority over global config."""
        # arrange
        db_rate_limit = RateLimit(
            id=1,
            scope_type="global",
            scope_id=None,
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=500,  # Different from config
                    max_tokens=250000
                )
            ]
        )
        mock_repository.get_by_scope = Mock(return_value=db_rate_limit)
        mock_cache.get = Mock(return_value=None)  # Cache miss

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert result.id == 1
        assert result.windows[0].max_requests == 500
        mock_repository.get_by_scope.assert_called_once_with("global", None)
        mock_config_service.get_global_rate_limits.assert_not_called()  # Should not check config

    def test_get_rate_limit_config_falls_back_to_global_config_when_db_empty(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test fallback to config.json when no database config exists."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)  # DB has no config
        mock_cache.get = Mock(return_value=None)  # Cache miss

        global_config = GlobalRateLimitConfig(
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
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert result.scope_type == "global"
        assert result.scope_id is None
        assert result.enabled is True
        assert len(result.windows) == 1
        assert result.windows[0].max_requests == 1000
        assert result.windows[0].max_tokens == 500000
        mock_repository.get_by_scope.assert_called_once_with("global", None)
        mock_config_service.get_global_rate_limits.assert_called_once()

    def test_get_rate_limit_config_returns_none_when_no_config_anywhere(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test returns None when no config in DB or config.json."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)
        mock_config_service.get_global_rate_limits = Mock(return_value=None)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is None

    def test_get_rate_limit_config_fallback_only_for_global_scope(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test global config fallback only applies to 'global' scope."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="00:00",
                    to_time="23:59",
                    max_requests=1000,
                    max_tokens=None
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("model", "model-123")

        # assert
        assert result is None
        mock_config_service.get_global_rate_limits.assert_not_called()  # Should not check for non-global

    def test_get_rate_limit_config_caches_converted_global_config(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test that converted global config is cached."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="09:00",
                    to_time="17:00",
                    max_requests=500,
                    max_tokens=None
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        mock_cache.set.assert_called_once()
        # Verify cached value has correct structure
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "global"  # scope_type
        assert call_args[0][1] is None       # scope_id
        cached_rate_limit = call_args[0][2]
        assert cached_rate_limit.scope_type == "global"

    def test_convert_global_config_with_multiple_windows(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test conversion handles multiple time windows correctly."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
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
                    to_time="17:00",
                    max_requests=1000,
                    max_tokens=500000
                ),
                TimeWindowConfig(
                    from_time="17:00",
                    to_time="23:59",
                    max_requests=200,
                    max_tokens=100000
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert len(result.windows) == 3
        assert result.windows[0].max_requests == 100
        assert result.windows[1].max_requests == 1000
        assert result.windows[2].max_requests == 200

    def test_convert_global_config_with_time_seconds(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test conversion handles HH:MM:SS time format."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="09:30:15",
                    to_time="17:45:30",
                    max_requests=500,
                    max_tokens=None
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert result.windows[0].from_time.hour == 9
        assert result.windows[0].from_time.minute == 30
        assert result.windows[0].from_time.second == 15
        assert result.windows[0].to_time.hour == 17
        assert result.windows[0].to_time.minute == 45
        assert result.windows[0].to_time.second == 30

    def test_convert_global_config_with_only_token_limits(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test conversion handles windows with only token limits."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="00:00",
                    to_time="23:59",
                    max_requests=None,
                    max_tokens=1000000
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert result.windows[0].max_requests is None
        assert result.windows[0].max_tokens == 1000000

    def test_convert_global_config_sets_no_db_fields(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test converted config has no DB-specific fields (id, timestamps)."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=True,
            windows=[
                TimeWindowConfig(
                    from_time="00:00",
                    to_time="23:59",
                    max_requests=1000,
                    max_tokens=None
                )
            ]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is not None
        assert result.id is None
        assert result.created_at is None
        assert result.updated_at is None

    def test_ignores_disabled_global_config(
        self, rate_limit_service, mock_repository, mock_cache, mock_config_service
    ):
        """Test disabled global config is not used as fallback."""
        # arrange
        mock_repository.get_by_scope = Mock(return_value=None)
        mock_cache.get = Mock(return_value=None)

        global_config = GlobalRateLimitConfig(
            enabled=False,  # Disabled
            windows=[]
        )
        mock_config_service.get_global_rate_limits = Mock(return_value=global_config)

        # act
        result = rate_limit_service.get_rate_limit_config("global", None)

        # assert
        assert result is None  # Should not use disabled config
