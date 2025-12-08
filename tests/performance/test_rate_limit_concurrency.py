"""Concurrency tests for rate limiting system.

These tests verify that the rate limiting system handles concurrent requests correctly:
- No race conditions in counter increments
- Accurate limit enforcement under load
- Thread-safe cache operations
- Correct behavior with 1000+ concurrent requests
"""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from unittest.mock import Mock

from src.ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from src.ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded
from src.ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_cache import InMemoryRateLimitCache
from src.ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_counter import InMemoryRateLimitCounter
from datetime import time as dt_time


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self):
        self.session = Mock()
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class TestRateLimitConcurrency:
    """Concurrency tests for rate limiting system."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository that returns test rate limits."""
        repository = Mock()

        # Create test rate limit with small max_requests for testing
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=100,  # Small limit for concurrency testing
                    max_tokens=10000
                )
            ],
            created_at=None,
            updated_at=None
        )

        repository.get_by_scope.return_value = rate_limit
        return repository

    @pytest.fixture
    def rate_limit_service(self, mock_repository):
        """Create RateLimitService with thread-safe counter."""
        uow = MockUnitOfWork()
        cache = InMemoryRateLimitCache(max_cache_size=64, ttl_seconds=30)
        counter = InMemoryRateLimitCounter()  # Thread-safe with locks

        def repository_factory(session):
            return mock_repository

        return RateLimitService(
            uow=uow,
            repository_factory=repository_factory,
            counter=counter,
            cache=cache
        )

    def test_concurrent_requests_no_race_conditions(self, rate_limit_service):
        """Test that concurrent requests don't cause race conditions in counter.

        1000 concurrent requests should result in exactly 1000 increments.
        """
        # Arrange: Prepare test data
        num_requests = 1000
        results = {"success": 0, "exceeded": 0, "errors": 0}
        lock = threading.Lock()

        def make_request(request_id: int):
            """Make a single request."""
            try:
                rate_limit_service.check_request_limit(
                    scope_type="model",
                    scope_id="gpt-4",
                    model_id="gpt-4"
                )
                with lock:
                    results["success"] += 1
            except RateLimitExceeded:
                with lock:
                    results["exceeded"] += 1
            except Exception as e:
                print(f"Unexpected error in request {request_id}: {e}")
                with lock:
                    results["errors"] += 1

        # Act: Execute concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in as_completed(futures):
                future.result()  # Wait for completion

        elapsed = time.time() - start_time

        # Assert: Verify results
        total_requests = results["success"] + results["exceeded"]

        print(f"\nConcurrent Requests Test:")
        print(f"  Total requests: {num_requests}")
        print(f"  Successful:     {results['success']}")
        print(f"  Rate limited:   {results['exceeded']}")
        print(f"  Errors:         {results['errors']}")
        print(f"  Time:           {elapsed:.2f}s")
        print(f"  Throughput:     {num_requests/elapsed:.0f} req/s")

        # All requests should be accounted for (no lost requests)
        assert total_requests == num_requests, \
            f"Lost requests: expected {num_requests}, got {total_requests}"

        # No errors should occur
        assert results["errors"] == 0, f"Unexpected errors occurred: {results['errors']}"

        # Exactly 100 should succeed (limit), rest should be exceeded
        assert results["success"] == 100, \
            f"Expected 100 successful requests, got {results['success']}"
        assert results["exceeded"] == 900, \
            f"Expected 900 rate limited requests, got {results['exceeded']}"

    def test_counter_accuracy_under_load(self, rate_limit_service):
        """Test that counter increments are accurate under concurrent load."""
        # Arrange: Prepare test
        num_requests = 500
        limit = 100

        # Update repository to return limit
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="test-model",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=limit,
                    max_tokens=10000
                )
            ],
            created_at=None,
            updated_at=None
        )

        # Act: Make concurrent requests
        exceeded_count = 0
        success_count = 0
        lock = threading.Lock()

        def make_request():
            nonlocal exceeded_count, success_count
            try:
                rate_limit_service.check_request_limit(
                    scope_type="model",
                    scope_id="test-model",
                    model_id="test-model"
                )
                with lock:
                    success_count += 1
            except RateLimitExceeded:
                with lock:
                    exceeded_count += 1

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                future.result()

        # Assert: Verify accurate enforcement
        print(f"\nCounter Accuracy Test:")
        print(f"  Limit:          {limit}")
        print(f"  Successful:     {success_count}")
        print(f"  Rate limited:   {exceeded_count}")
        print(f"  Total:          {success_count + exceeded_count}")

        # Should allow exactly 'limit' requests
        assert success_count == limit, \
            f"Expected {limit} successful requests, got {success_count}"
        assert exceeded_count == (num_requests - limit), \
            f"Expected {num_requests - limit} exceeded, got {exceeded_count}"

    def test_cache_thread_safety(self, rate_limit_service):
        """Test that cache operations are thread-safe."""
        # Arrange: Prepare multiple rate limits
        num_models = 50
        num_threads = 100

        def access_cache(thread_id: int):
            """Access cache from multiple threads."""
            model_id = f"model-{thread_id % num_models}"

            # Try to get rate limit (may trigger DB lookup)
            rate_limit_service.get_rate_limit_config("model", model_id)

            # Make a request (uses cache)
            try:
                rate_limit_service.check_request_limit(
                    scope_type="model",
                    scope_id=model_id,
                    model_id=model_id
                )
            except RateLimitExceeded:
                pass  # Expected after limit reached

        # Act: Execute concurrent cache operations
        errors = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(access_cache, i) for i in range(num_threads)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors.append(e)

        # Assert: No errors should occur
        assert len(errors) == 0, f"Cache thread safety errors: {errors}"

        # Verify cache statistics
        stats = rate_limit_service._cache.get_stats()
        print(f"\nCache Thread Safety Test:")
        print(f"  Cache size:   {stats['size']}")
        print(f"  Max size:     {stats['max_size']}")
        print(f"  Entries:      {len(stats['entries'])}")

        # Cache should have entries for accessed models (allow a few extra for global limits)
        assert stats['size'] > 0, "Cache should contain entries"
        assert stats['size'] <= num_models + 5, f"Cache size should be approximately number of models ({num_models}), got {stats['size']}"

    def test_1000_concurrent_requests(self, rate_limit_service):
        """Test system behavior with 1000+ concurrent requests.

        SLA: System should handle 1000+ concurrent requests without errors.
        """
        # Arrange: Prepare test with higher limit
        num_requests = 1000
        limit = 500

        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="high-volume-model",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=limit,
                    max_tokens=100000
                )
            ],
            created_at=None,
            updated_at=None
        )

        # Update mock repository
        rate_limit_service._uow.session = Mock()

        # Act: Execute 1000 concurrent requests
        results = {
            "success": 0,
            "exceeded": 0,
            "errors": 0,
            "latencies": []
        }
        lock = threading.Lock()

        def make_request(request_id: int):
            start = time.perf_counter()
            try:
                rate_limit_service.check_request_limit(
                    scope_type="model",
                    scope_id="high-volume-model",
                    model_id="high-volume-model"
                )
                with lock:
                    results["success"] += 1
            except RateLimitExceeded:
                with lock:
                    results["exceeded"] += 1
            except Exception as e:
                print(f"Error in request {request_id}: {e}")
                with lock:
                    results["errors"] += 1
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                with lock:
                    results["latencies"].append(elapsed_ms)

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in as_completed(futures):
                future.result()

        total_time = time.time() - start_time

        # Assert: Calculate statistics
        latencies = sorted(results["latencies"])
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"\n1000+ Concurrent Requests Test:")
        print(f"  Total requests: {num_requests}")
        print(f"  Successful:     {results['success']}")
        print(f"  Rate limited:   {results['exceeded']}")
        print(f"  Errors:         {results['errors']}")
        print(f"  Total time:     {total_time:.2f}s")
        print(f"  Throughput:     {num_requests/total_time:.0f} req/s")
        print(f"  Latency p50:    {p50:.2f}ms")
        print(f"  Latency p95:    {p95:.2f}ms")
        print(f"  Latency p99:    {p99:.2f}ms")

        # All requests should complete without errors
        assert results["errors"] == 0, f"Errors occurred: {results['errors']}"

        # All requests should be accounted for
        total = results["success"] + results["exceeded"]
        assert total == num_requests, f"Lost requests: {num_requests - total}"

        # Latency should remain reasonable under load
        assert p99 < 50.0, f"p99 latency {p99:.2f}ms too high under load"

    def test_multiple_models_concurrent_access(self, rate_limit_service, mock_repository):
        """Test concurrent access to different models."""
        # Arrange: Setup multiple models
        num_models = 10
        requests_per_model = 100
        total_requests = num_models * requests_per_model

        def get_by_scope(scope_type, scope_id):
            if scope_id is None:
                return None
            parts = scope_id.split("-")
            model_num = int(parts[1]) if len(parts) > 1 else 0
            return RateLimit(
                id=model_num,
                scope_type="model",
                scope_id=scope_id,
                enabled=True,
                windows=[
                    RateLimitWindow(
                        id=1,
                        from_time=dt_time(0, 0, 0),
                        to_time=dt_time(23, 59, 59),
                        max_requests=50,  # Each model has 50 req limit
                        max_tokens=10000
                    )
                ],
                created_at=None,
                updated_at=None
            )

        mock_repository.get_by_scope.side_effect = get_by_scope

        # Act: Make concurrent requests to different models
        results = {}
        lock = threading.Lock()

        def make_request(model_idx: int, request_idx: int):
            model_id = f"model-{model_idx}"
            try:
                rate_limit_service.check_request_limit(
                    scope_type="model",
                    scope_id=model_id,
                    model_id=model_id
                )
                with lock:
                    if model_id not in results:
                        results[model_id] = {"success": 0, "exceeded": 0}
                    results[model_id]["success"] += 1
            except RateLimitExceeded:
                with lock:
                    if model_id not in results:
                        results[model_id] = {"success": 0, "exceeded": 0}
                    results[model_id]["exceeded"] += 1

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for model_idx in range(num_models):
                for request_idx in range(requests_per_model):
                    futures.append(executor.submit(make_request, model_idx, request_idx))

            for future in as_completed(futures):
                future.result()

        # Assert: Each model should enforce its own limit independently
        print(f"\nMultiple Models Concurrent Access:")
        for model_id in sorted(results.keys()):
            model_results = results[model_id]
            print(f"  {model_id}: success={model_results['success']}, exceeded={model_results['exceeded']}")

            # Each model should allow exactly 50 requests (its limit)
            assert model_results["success"] == 50, \
                f"{model_id} should allow 50 requests, got {model_results['success']}"
            assert model_results["exceeded"] == 50, \
                f"{model_id} should exceed 50 requests, got {model_results['exceeded']}"

    def test_token_limit_concurrency(self, rate_limit_service, mock_repository):
        """Test concurrent token recording without race conditions."""
        # Arrange: Setup model with token limit
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="token-model",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=10000,  # High request limit
                    max_tokens=5000  # Low token limit for testing
                )
            ],
            created_at=None,
            updated_at=None
        )

        mock_repository.get_by_scope.return_value = rate_limit

        # Act: Record tokens concurrently
        num_recordings = 100
        tokens_per_recording = 100  # Total = 10,000 tokens (will exceed 5000 limit)

        results = {"success": 0, "exceeded": 0, "errors": 0}
        lock = threading.Lock()

        def record_tokens(recording_id: int):
            try:
                # Check token limit before recording
                rate_limit_service.check_token_limit(
                    scope_type="model",
                    scope_id="token-model",
                    model_id="token-model",
                    estimated_tokens=tokens_per_recording
                )

                # If check passed, record the tokens
                rate_limit_service.record_token_usage(
                    scope_type="model",
                    scope_id="token-model",
                    prompt_tokens=tokens_per_recording // 2,
                    completion_tokens=tokens_per_recording // 2
                )

                with lock:
                    results["success"] += 1
            except RateLimitExceeded:
                with lock:
                    results["exceeded"] += 1
            except Exception as e:
                print(f"Error in recording {recording_id}: {e}")
                with lock:
                    results["errors"] += 1

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(record_tokens, i) for i in range(num_recordings)]
            for future in as_completed(futures):
                future.result()

        # Assert: Verify token limit enforcement
        print(f"\nToken Limit Concurrency Test:")
        print(f"  Token limit:    5000")
        print(f"  Successful:     {results['success']}")
        print(f"  Rate limited:   {results['exceeded']}")
        print(f"  Errors:         {results['errors']}")

        # No errors should occur
        assert results["errors"] == 0, f"Errors occurred: {results['errors']}"

        # Some recordings should succeed, others should be rate limited
        # Exactly 50 should succeed (5000 tokens / 100 tokens per recording)
        assert results["success"] == 50, \
            f"Expected 50 successful recordings, got {results['success']}"
        assert results["exceeded"] == 50, \
            f"Expected 50 rate limited recordings, got {results['exceeded']}"


@pytest.mark.concurrency
class TestRateLimitStressTests:
    """Stress tests for rate limiting system."""

    def test_sustained_load(self):
        """Test system behavior under sustained load for 10 seconds."""
        # Arrange: Create service with realistic limits
        uow = MockUnitOfWork()
        cache = InMemoryRateLimitCache(max_cache_size=64, ttl_seconds=30)
        counter = InMemoryRateLimitCounter()

        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="stress-model",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=1000,
                    max_tokens=100000
                )
            ],
            created_at=None,
            updated_at=None
        )

        mock_repository = Mock()
        mock_repository.get_by_scope.return_value = rate_limit

        service = RateLimitService(
            uow=uow,
            repository_factory=lambda session: mock_repository,
            counter=counter,
            cache=cache
        )

        # Act: Send requests continuously for 10 seconds
        duration = 10  # seconds
        results = {"success": 0, "exceeded": 0, "errors": 0}
        lock = threading.Lock()
        stop_flag = threading.Event()

        def worker():
            while not stop_flag.is_set():
                try:
                    service.check_request_limit(
                        scope_type="model",
                        scope_id="stress-model",
                        model_id="stress-model"
                    )
                    with lock:
                        results["success"] += 1
                except RateLimitExceeded:
                    with lock:
                        results["exceeded"] += 1
                except Exception as e:
                    with lock:
                        results["errors"] += 1

        # Start workers
        workers = []
        num_workers = 20
        for _ in range(num_workers):
            t = threading.Thread(target=worker)
            t.start()
            workers.append(t)

        # Run for duration
        time.sleep(duration)
        stop_flag.set()

        # Wait for workers to finish
        for t in workers:
            t.join()

        # Assert: Calculate throughput
        total_requests = results["success"] + results["exceeded"]
        throughput = total_requests / duration

        print(f"\nSustained Load Test ({duration}s):")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful:     {results['success']}")
        print(f"  Rate limited:   {results['exceeded']}")
        print(f"  Errors:         {results['errors']}")
        print(f"  Throughput:     {throughput:.0f} req/s")

        # No errors should occur
        assert results["errors"] == 0, f"Errors occurred: {results['errors']}"

        # Should achieve reasonable throughput
        assert throughput > 100, f"Throughput too low: {throughput:.0f} req/s"


if __name__ == "__main__":
    # Run concurrency tests with verbose output
    pytest.main([__file__, "-v", "-s", "-m", "concurrency"])
