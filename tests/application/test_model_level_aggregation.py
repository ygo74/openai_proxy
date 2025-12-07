"""Tests for model-level usage aggregation across groups (Phase 8 - US6).

These tests verify that model-level rate limits aggregate usage across all groups
that use the same model, ensuring the counter is shared and limits apply globally
per model regardless of which group makes the request.
"""
import pytest
from datetime import time, datetime
from unittest.mock import Mock, MagicMock
from typing import Optional

from src.ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from src.ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded


@pytest.fixture
def mock_uow():
    """Create a mock Unit of Work."""
    uow = MagicMock()
    uow.session = MagicMock()
    uow.__enter__ = MagicMock(return_value=uow)
    uow.__exit__ = MagicMock(return_value=False)
    return uow


@pytest.fixture
def mock_cache():
    """Create a mock rate limit cache."""
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock()
    return cache


@pytest.fixture
def mock_counter():
    """Create a mock rate limit counter."""
    counter = MagicMock()
    counter.increment_request_count = MagicMock(return_value=1)
    counter.increment_token_count = MagicMock(return_value=100)
    counter.get_current_count = MagicMock(return_value=0)
    return counter


@pytest.fixture
def mock_repository():
    """Create a mock repository for rate limits."""
    def repository_factory(session):
        repo = MagicMock()
        repo.get_by_scope = MagicMock(return_value=None)
        return repo
    return repository_factory


@pytest.fixture
def mock_config_service():
    """Create a mock config service that returns None for global rate limits."""
    config_service = MagicMock()
    config_service.get_global_rate_limits = MagicMock(return_value=None)
    return config_service


@pytest.fixture
def service(mock_uow, mock_cache, mock_counter, mock_repository, mock_config_service):
    """Create a RateLimitService with mocked dependencies."""
    return RateLimitService(
        uow=mock_uow,
        repository_factory=mock_repository,
        counter=mock_counter,
        cache=mock_cache,
        config_service=mock_config_service
    )


class TestModelLevelAggregation:
    """Test model-level aggregation across multiple groups."""

    def test_model_limit_uses_model_id_only_in_counter_key(self, service, mock_counter, mock_repository):
        """Test that model-level limits use only model_id in counter key (not group_id).

        Verifies T067: Counter key generation for model-level limits.
        """
        # Arrange: Create model-level rate limit
        model_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=100,
                    max_tokens=10000
                )
            ]
        )

        # Mock repository to return model limit (not group_model)
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect

        # Update service to use new repository
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter
        mock_counter.increment_request_count.return_value = 1

        # Act: Check limit with group_id and model_id
        service.check_request_limit(
            scope_type="model",
            scope_id="gpt-4",
            group_id="team-a",
            model_id="gpt-4"
        )

        # Assert: Counter was called with scope_type='model' and scope_id='gpt-4' (no group)
        mock_counter.increment_request_count.assert_called_once()
        call_args = mock_counter.increment_request_count.call_args
        assert call_args[0][0] == "model"  # scope_type
        assert call_args[0][1] == "gpt-4"  # scope_id (model_id only, no group)

    def test_multiple_groups_share_same_model_counter(self, service, mock_counter, mock_repository):
        """Test that different groups increment the same counter for model-level limits.

        Verifies T068: Model-level usage aggregation across groups.
        """
        # Arrange: Create model-level rate limit
        model_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=100,
                    max_tokens=10000
                )
            ]
        )

        # Mock repository
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter to return increasing counts
        call_count = 0
        def increment_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count

        mock_counter.increment_request_count.side_effect = increment_side_effect

        # Act: Group A sends 2 requests
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-a", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-a", model_id="gpt-4")

        # Act: Group B sends 1 request
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-b", model_id="gpt-4")

        # Assert: Counter was called 3 times with the same key (model:gpt-4)
        assert mock_counter.increment_request_count.call_count == 3

        # All calls should use the same scope_type and scope_id
        for call in mock_counter.increment_request_count.call_args_list:
            assert call[0][0] == "model"  # scope_type
            assert call[0][1] == "gpt-4"  # scope_id
            # Window start and duration should also be the same for all calls

    def test_model_limit_blocks_all_groups_when_exceeded(self, service, mock_counter, mock_repository):
        """Test that model limit blocks requests from all groups once exceeded.

        Verifies T068: Model limit enforcement applies across all groups.
        """
        # Arrange: Create model-level rate limit with low threshold
        model_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=5,  # Low limit for testing
                    max_tokens=10000
                )
            ]
        )

        # Mock repository
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter: Group A sends 3, Group B sends 2, Group C tries to send 1 (would be 6th)
        call_count = 0
        def increment_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count

        mock_counter.increment_request_count.side_effect = increment_side_effect

        # Act & Assert: First 5 requests should succeed
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-a", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-a", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-a", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-b", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-b", model_id="gpt-4")

        # 6th request from Group C should fail (limit exceeded)
        with pytest.raises(RateLimitExceeded) as exc_info:
            service.check_request_limit(scope_type="model", scope_id="gpt-4", group_id="team-c", model_id="gpt-4")

        # Assert exception details
        assert exc_info.value.scope_type == "model"
        assert exc_info.value.scope_id == "gpt-4"
        assert exc_info.value.limit_type == "requests"
        assert exc_info.value.limit == 5
        assert exc_info.value.current == 6

    def test_different_models_use_separate_counters(self, service, mock_counter, mock_repository):
        """Test that different models have independent counters.

        Verifies T068: Model limits don't interfere with other models.
        """
        # Arrange: Create model-level rate limits for two different models
        gpt4_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=100,
                    max_tokens=10000
                )
            ]
        )

        gpt35_limit = RateLimit(
            id=2,
            scope_type="model",
            scope_id="gpt-3.5-turbo",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=200,
                    max_tokens=20000
                )
            ]
        )

        # Mock repository
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return gpt4_limit
            elif scope_type == "model" and scope_id == "gpt-3.5-turbo":
                return gpt35_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter to return increasing counts per key
        counter_state = {}
        def increment_side_effect(scope_type, scope_id, window_start, window_duration):
            key = f"{scope_type}:{scope_id}"
            counter_state[key] = counter_state.get(key, 0) + 1
            return counter_state[key]

        mock_counter.increment_request_count.side_effect = increment_side_effect

        # Act: Send requests to different models
        service.check_request_limit(scope_type="model", scope_id="gpt-4", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-4", model_id="gpt-4")
        service.check_request_limit(scope_type="model", scope_id="gpt-3.5-turbo", model_id="gpt-3.5-turbo")

        # Assert: Different counters incremented
        assert counter_state.get("model:gpt-4") == 2
        assert counter_state.get("model:gpt-3.5-turbo") == 1

        # Assert: Counter was called with correct scope_ids
        calls = mock_counter.increment_request_count.call_args_list
        assert len(calls) == 3
        assert calls[0][0][1] == "gpt-4"
        assert calls[1][0][1] == "gpt-4"
        assert calls[2][0][1] == "gpt-3.5-turbo"

    def test_token_limit_aggregation_across_groups(self, service, mock_counter, mock_repository):
        """Test that model-level token limits aggregate usage across groups.

        Verifies T068: Token-based aggregation works the same as request-based.
        """
        # Arrange: Create model-level rate limit with token limit
        model_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=1000,
                    max_tokens=5000  # Low token limit
                )
            ]
        )

        # Mock repository
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter: Group A uses 3000 tokens, Group B uses 2500 tokens (would be 5500 total)
        token_count = 0
        def get_count_side_effect(scope_type, scope_id, metric, window_start):
            return token_count

        mock_counter.get_current_count.side_effect = get_count_side_effect

        # Act: Group A uses tokens (under limit)
        token_count = 3000
        service.check_token_limit(
            scope_type="model",
            scope_id="gpt-4",
            group_id="team-a",
            model_id="gpt-4",
            estimated_tokens=0  # Just checking current usage
        )

        # Act: Group B tries to use more tokens (would exceed limit)
        token_count = 5500  # Simulating total from both groups
        with pytest.raises(RateLimitExceeded) as exc_info:
            service.check_token_limit(
                scope_type="model",
                scope_id="gpt-4",
                group_id="team-b",
                model_id="gpt-4",
                estimated_tokens=0
            )

        # Assert: Exception raised with model scope
        assert exc_info.value.scope_type == "model"
        assert exc_info.value.scope_id == "gpt-4"
        assert exc_info.value.limit_type == "tokens"
        assert exc_info.value.limit == 5000
        assert exc_info.value.current == 5500

    def test_hierarchical_fallback_to_model_after_no_group_model(self, service, mock_counter, mock_repository):
        """Test that hierarchy falls back to model limit when no group/model limit exists.

        This verifies that the hierarchical evaluation correctly uses model-level
        aggregation when group/model limits aren't configured.
        """
        # Arrange: Only model-level limit exists (no group/model)
        model_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    from_time=time(0, 0, 0),
                    to_time=time(23, 59, 59),
                    max_requests=100,
                    max_tokens=10000
                )
            ]
        )

        # Mock repository to return model limit only
        def get_by_scope_side_effect(scope_type, scope_id):
            if scope_type == "model" and scope_id == "gpt-4":
                return model_limit
            return None

        mock_repository_instance = mock_repository(None)
        mock_repository_instance.get_by_scope.side_effect = get_by_scope_side_effect
        service._repository_factory = lambda session: mock_repository_instance

        # Mock counter with shared state
        counter_state = {}
        def increment_side_effect(scope_type, scope_id, window_start, window_duration):
            key = f"{scope_type}:{scope_id}"
            counter_state[key] = counter_state.get(key, 0) + 1
            return counter_state[key]

        mock_counter.increment_request_count.side_effect = increment_side_effect

        # Act: Multiple groups make requests (should fall back to model limit)
        service.check_request_limit(scope_type=None, scope_id=None, group_id="team-a", model_id="gpt-4")
        service.check_request_limit(scope_type=None, scope_id=None, group_id="team-b", model_id="gpt-4")
        service.check_request_limit(scope_type=None, scope_id=None, group_id="team-c", model_id="gpt-4")

        # Assert: All requests used the same model-level counter
        assert counter_state.get("model:gpt-4") == 3
        assert mock_counter.increment_request_count.call_count == 3

        # All calls should have used model scope
        for call in mock_counter.increment_request_count.call_args_list:
            assert call[0][0] == "model"
            assert call[0][1] == "gpt-4"
