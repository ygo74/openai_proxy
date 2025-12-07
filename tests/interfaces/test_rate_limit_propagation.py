"""Integration tests for rate limit configuration propagation across instances.

Tests verify that configuration changes propagate between multiple service
instances within 5 seconds via Redis pub/sub mechanism.
"""
import sys
import os
import time
import threading
from datetime import time as dt_time
from unittest.mock import MagicMock, patch
import pytest
import redis

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache import RateLimitCache
from ygo74.fastapi_openai_rag.infrastructure.db.unit_of_work import SQLUnitOfWork


@pytest.fixture
def redis_client():
    """Create real Redis client for integration tests."""
    client = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )

    # Clean up before test
    try:
        client.flushdb()
    except redis.exceptions.ConnectionError:
        pytest.skip("Redis not available for integration tests")

    yield client

    # Clean up after test
    try:
        client.flushdb()
    except:
        pass


@pytest.fixture
def mock_repository():
    """Mock repository for testing cache behavior."""
    mock_repo = MagicMock()

    # Default: no rate limit in DB
    mock_repo.get_by_scope.return_value = None
    mock_repo.upsert.return_value = None
    mock_repo.delete_by_scope.return_value = True

    return mock_repo


@pytest.fixture
def mock_uow(mock_repository):
    """Mock Unit of Work with repository."""
    mock_uow_instance = MagicMock(spec=SQLUnitOfWork)
    mock_uow_instance.session = MagicMock()
    mock_uow_instance.__enter__ = MagicMock(return_value=mock_uow_instance)
    mock_uow_instance.__exit__ = MagicMock(return_value=False)

    with patch('ygo74.fastapi_openai_rag.application.services.rate_limit_service.SQLUnitOfWork', return_value=mock_uow_instance):
        yield mock_uow_instance, mock_repository


class TestRateLimitPropagation:
    """Test suite for multi-instance rate limit propagation."""

    def test_cache_invalidation_propagates_between_instances(self, redis_client, mock_uow):
        """Test cache invalidation message propagates between two service instances."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        # Create two cache instances (simulating two gateway instances)
        cache1 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
        cache2 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)

        cache1.start_listener()
        cache2.start_listener()

        # Add entry to both caches
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        cache1.set("model", "gpt-4", rate_limit)
        cache2.set("model", "gpt-4", rate_limit)

        assert cache1.get("model", "gpt-4") is not None
        assert cache2.get("model", "gpt-4") is not None

        # act - instance 1 publishes invalidation
        cache1.publish_change("delete", "model", "gpt-4")

        # Wait for pub/sub propagation (should be <1s, but allow up to 3s)
        time.sleep(3)

        # assert - instance 2 should have invalidated its cache
        assert cache2.get("model", "gpt-4") is None

    def test_service_create_invalidates_other_instance_cache(self, redis_client, mock_uow):
        """Test that creating a rate limit via one service invalidates other instance caches."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        # Create two cache instances
        cache1 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
        cache2 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)

        cache1.start_listener()
        cache2.start_listener()

        # Create two service instances with their own caches
        def repo_factory(session):
            return mock_repository

        service1 = RateLimitService(
            uow=mock_uow_instance,
            repository_factory=repo_factory,
            cache=cache1
        )

        service2 = RateLimitService(
            uow=mock_uow_instance,
            repository_factory=repo_factory,
            cache=cache2
        )

        # Pre-populate cache2 with old value
        old_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=50,  # Old limit
                    max_tokens=25000
                )
            ]
        )
        cache2.set("model", "gpt-4", old_rate_limit)

        # act - service1 creates/updates rate limit
        new_rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=200,  # New limit
                    max_tokens=100000
                )
            ]
        )

        mock_repository.upsert.return_value = new_rate_limit
        service1.create_or_update_rate_limit(new_rate_limit)

        # Wait for pub/sub propagation
        time.sleep(3)

        # assert - cache2 should be invalidated
        cached_value = cache2.get("model", "gpt-4")
        assert cached_value is None  # Cache invalidated, will force DB fetch

    def test_service_delete_invalidates_other_instance_cache(self, redis_client, mock_uow):
        """Test that deleting a rate limit via one service invalidates other instance caches."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        # Create two cache instances
        cache1 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
        cache2 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)

        cache1.start_listener()
        cache2.start_listener()

        # Create two service instances
        def repo_factory(session):
            return mock_repository

        service1 = RateLimitService(
            uow=mock_uow_instance,
            repository_factory=repo_factory,
            cache=cache1
        )

        service2 = RateLimitService(
            uow=mock_uow_instance,
            repository_factory=repo_factory,
            cache=cache2
        )

        # Pre-populate both caches
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        cache1.set("model", "gpt-4", rate_limit)
        cache2.set("model", "gpt-4", rate_limit)

        assert cache2.get("model", "gpt-4") is not None

        # act - service1 deletes rate limit
        mock_repository.delete_by_scope.return_value = True
        service1.delete_rate_limit("model", "gpt-4")

        # Wait for pub/sub propagation
        time.sleep(3)

        # assert - cache2 should be invalidated
        assert cache2.get("model", "gpt-4") is None

    def test_propagation_latency_under_5_seconds(self, redis_client, mock_uow):
        """Test that cache invalidation propagates in under 5 seconds."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        cache1 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
        cache2 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)

        cache1.start_listener()
        cache2.start_listener()

        # Pre-populate cache2
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )
        cache2.set("model", "gpt-4", rate_limit)

        # act - measure propagation time
        start_time = time.time()
        cache1.publish_change("update", "model", "gpt-4")

        # Poll until cache2 is invalidated (max 5 seconds)
        max_wait = 5.0
        poll_interval = 0.1
        elapsed = 0.0

        while elapsed < max_wait:
            if cache2.get("model", "gpt-4") is None:
                break
            time.sleep(poll_interval)
            elapsed = time.time() - start_time

        propagation_time = time.time() - start_time

        # assert - propagation completed within 5 seconds
        assert cache2.get("model", "gpt-4") is None
        assert propagation_time < 5.0, f"Propagation took {propagation_time:.2f}s, expected <5s"

    def test_multiple_instances_all_receive_invalidation(self, redis_client, mock_uow):
        """Test that invalidation propagates to all instances (3+ instances)."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        # Create 4 cache instances (simulating 4 gateway instances)
        caches = [
            RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
            for _ in range(4)
        ]

        for cache in caches:
            cache.start_listener()

        # Pre-populate all caches
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        for cache in caches:
            cache.set("model", "gpt-4", rate_limit)
            assert cache.get("model", "gpt-4") is not None

        # act - first instance publishes invalidation
        caches[0].publish_change("delete", "model", "gpt-4")

        # Wait for propagation
        time.sleep(3)

        # assert - all other instances should have invalidated cache
        for i, cache in enumerate(caches[1:], start=1):
            assert cache.get("model", "gpt-4") is None, f"Cache {i} was not invalidated"

    def test_different_scopes_invalidate_independently(self, redis_client, mock_uow):
        """Test that invalidation of one scope doesn't affect other scopes."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        cache1 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
        cache2 = RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)

        cache1.start_listener()
        cache2.start_listener()

        # Pre-populate cache2 with two different rate limits
        rate_limit_gpt4 = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=100,
                    max_tokens=50000
                )
            ]
        )

        rate_limit_claude = RateLimit(
            id=2,
            scope_type="model",
            scope_id="claude-3",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=2,
                    from_time=dt_time(0, 0),
                    to_time=dt_time(23, 59),
                    max_requests=200,
                    max_tokens=100000
                )
            ]
        )

        cache2.set("model", "gpt-4", rate_limit_gpt4)
        cache2.set("model", "claude-3", rate_limit_claude)

        # act - invalidate only gpt-4
        cache1.publish_change("update", "model", "gpt-4")

        # Wait for propagation
        time.sleep(3)

        # assert - only gpt-4 should be invalidated
        assert cache2.get("model", "gpt-4") is None
        assert cache2.get("model", "claude-3") is not None

    def test_concurrent_invalidations_handled_correctly(self, redis_client, mock_uow):
        """Test that concurrent invalidations from multiple instances work correctly."""
        # arrange
        mock_uow_instance, mock_repository = mock_uow

        caches = [
            RateLimitCache(redis_host='localhost', redis_port=6379, redis_db=0)
            for _ in range(3)
        ]

        for cache in caches:
            cache.start_listener()

        # Pre-populate all caches with different models
        models = ["gpt-4", "gpt-3.5", "claude-3"]
        for i, (cache, model) in enumerate(zip(caches, models)):
            rate_limit = RateLimit(
                id=i+1,
                scope_type="model",
                scope_id=model,
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=i+1,
                        from_time=dt_time(0, 0),
                        to_time=dt_time(23, 59),
                        max_requests=100,
                        max_tokens=50000
                    )
                ]
            )
            for c in caches:
                c.set("model", model, rate_limit)

        # act - publish concurrent invalidations
        threads = []
        for cache, model in zip(caches, models):
            thread = threading.Thread(
                target=lambda c, m: c.publish_change("update", "model", m),
                args=(cache, model)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Wait for all propagations
        time.sleep(3)

        # assert - all caches should have invalidated all models
        for cache in caches:
            for model in models:
                assert cache.get("model", model) is None
