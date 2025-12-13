"""Performance tests for rate limiting system.

These tests verify that the rate limiting system meets performance requirements:
- p99 latency < 10ms for rate limit evaluations
- Cache hit rate > 95%
- Minimal overhead on chat completion requests
"""
import pytest
import time
import statistics
from typing import List
from unittest.mock import Mock, patch

from src.ygo74.fastapi_openai_rag.application.services.rate_limit_service import RateLimitService
from src.ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
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


class TestRateLimitPerformance:
    """Performance tests for rate limiting system."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository that returns test rate limits."""
        repository = Mock()

        # Create test rate limit
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
                    max_requests=1000,
                    max_tokens=100000
                )
            ],
            created_at=None,
            updated_at=None
        )

        repository.get_by_scope.return_value = rate_limit
        return repository

    @pytest.fixture
    def rate_limit_service(self, mock_repository):
        """Create RateLimitService with in-memory cache and counter."""
        uow = MockUnitOfWork()
        cache = InMemoryRateLimitCache(max_cache_size=64, ttl_seconds=30)
        counter = InMemoryRateLimitCounter()

        def repository_factory(session):
            return mock_repository

        return RateLimitService(
            uow=uow,
            repository_factory=repository_factory,
            counter=counter,
            cache=cache
        )

    def measure_execution_time(self, func, iterations: int = 100) -> List[float]:
        """Measure execution time for multiple iterations.

        Args:
            func: Function to measure
            iterations: Number of iterations to run

        Returns:
            List of execution times in milliseconds
        """
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms
        return times

    def test_rate_limit_evaluation_latency_p99(self, rate_limit_service):
        """Test that rate limit evaluation p99 latency is under 10ms.

        SLA: p99 < 10ms for rate limit checks
        """
        # Arrange: Define test function
        def check_limit():
            rate_limit_service.check_request_limit(
                scope_type="model",
                scope_id="gpt-4",
                model_id="gpt-4"
            )

        # Act: Measure 1000 iterations
        times = self.measure_execution_time(check_limit, iterations=1000)

        # Assert: Calculate percentiles
        p50 = statistics.quantiles(times, n=100)[49]  # 50th percentile
        p95 = statistics.quantiles(times, n=100)[94]  # 95th percentile
        p99 = statistics.quantiles(times, n=100)[98]  # 99th percentile
        mean = statistics.mean(times)

        print(f"\nRate Limit Evaluation Latency:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  p50:  {p50:.2f}ms")
        print(f"  p95:  {p95:.2f}ms")
        print(f"  p99:  {p99:.2f}ms")

        # SLA: p99 must be under 10ms
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms SLA"

        # Also check other percentiles for good measure
        assert p95 < 8.0, f"p95 latency {p95:.2f}ms exceeds 8ms threshold"
        assert mean < 5.0, f"Mean latency {mean:.2f}ms exceeds 5ms threshold"

    def test_cache_hit_rate_above_95_percent(self, rate_limit_service):
        """Test that cache hit rate is above 95% after warmup.

        SLA: Cache hit rate > 95%
        """
        # Arrange: Warmup cache with initial requests
        for _ in range(10):
            rate_limit_service.check_request_limit(
                scope_type="model",
                scope_id="gpt-4",
                model_id="gpt-4"
            )

        # Act: Make 1000 requests and track cache stats
        initial_stats = rate_limit_service._cache.get_stats()

        for _ in range(1000):
            rate_limit_service.check_request_limit(
                scope_type="model",
                scope_id="gpt-4",
                model_id="gpt-4"
            )

        final_stats = rate_limit_service._cache.get_stats()

        # Calculate hit rate for this test run
        hits = final_stats["hits"] - initial_stats["hits"]
        misses = final_stats["misses"] - initial_stats["misses"]
        total = hits + misses
        hit_rate = (hits / total) * 100 if total > 0 else 0

        print(f"\nCache Performance:")
        print(f"  Hits:     {hits}")
        print(f"  Misses:   {misses}")
        print(f"  Hit Rate: {hit_rate:.2f}%")

        # SLA: Hit rate must be above 95%
        assert hit_rate > 95.0, f"Cache hit rate {hit_rate:.2f}% is below 95% SLA"

    def test_token_limit_evaluation_latency(self, rate_limit_service):
        """Test that token limit evaluation is fast (<10ms p99)."""
        # Arrange: Define test function
        def check_token_limit():
            rate_limit_service.check_token_limit(
                scope_type="model",
                scope_id="gpt-4",
                model_id="gpt-4",
                estimated_tokens=1000
            )

        # Act: Measure 1000 iterations
        times = self.measure_execution_time(check_token_limit, iterations=1000)

        # Assert: Calculate percentiles
        p99 = statistics.quantiles(times, n=100)[98]
        mean = statistics.mean(times)

        print(f"\nToken Limit Evaluation Latency:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  p99:  {p99:.2f}ms")

        # SLA: p99 must be under 10ms
        assert p99 < 10.0, f"Token limit p99 latency {p99:.2f}ms exceeds 10ms SLA"

    def test_hierarchical_evaluation_overhead(self, rate_limit_service, mock_repository):
        """Test that hierarchical evaluation adds minimal overhead.

        Hierarchical evaluation (group+model → model → global) should not
        significantly increase latency compared to direct lookup.
        """
        # Arrange: Setup repository to return limits at all levels
        def get_by_scope(scope_type, scope_id):
            if scope_type == "group_model":
                return RateLimit(
                    id=1,
                    scope_type="group_model",
                    scope_id="team:gpt-4",
                    enabled=True,
                    windows=[RateLimitWindow(
                        id=1,
                        from_time=dt_time(0, 0, 0),
                        to_time=dt_time(23, 59, 59),
                        max_requests=500,
                        max_tokens=50000
                    )],
                    created_at=None,
                    updated_at=None
                )
            elif scope_type == "model":
                return RateLimit(
                    id=2,
                    scope_type="model",
                    scope_id="gpt-4",
                    enabled=True,
                    windows=[RateLimitWindow(
                        id=2,
                        from_time=dt_time(0, 0, 0),
                        to_time=dt_time(23, 59, 59),
                        max_requests=1000,
                        max_tokens=100000
                    )],
                    created_at=None,
                    updated_at=None
                )
            return None

        mock_repository.get_by_scope.side_effect = get_by_scope

        # Act: Measure hierarchical evaluation (with group_id and model_id)
        def check_hierarchical():
            rate_limit_service.check_request_limit(
                scope_type="group_model",
                scope_id="team:gpt-4",
                group_id="team",
                model_id="gpt-4"
            )

        hierarchical_times = self.measure_execution_time(check_hierarchical, iterations=500)

        # Act: Measure direct evaluation (without hierarchy)
        def check_direct():
            rate_limit_service.check_request_limit(
                scope_type="model",
                scope_id="gpt-4",
                model_id="gpt-4"
            )

        direct_times = self.measure_execution_time(check_direct, iterations=500)

        # Assert: Compare latencies
        hierarchical_p99 = statistics.quantiles(hierarchical_times, n=100)[98]
        direct_p99 = statistics.quantiles(direct_times, n=100)[98]
        overhead = hierarchical_p99 - direct_p99
        overhead_percent = (overhead / direct_p99) * 100 if direct_p99 > 0 else 0

        print(f"\nHierarchical Evaluation Overhead:")
        print(f"  Direct p99:       {direct_p99:.2f}ms")
        print(f"  Hierarchical p99: {hierarchical_p99:.2f}ms")
        print(f"  Overhead:         {overhead:.2f}ms ({overhead_percent:.1f}%)")

        # Overhead should be less than 3ms or 50% increase
        assert overhead < 3.0, f"Hierarchical overhead {overhead:.2f}ms exceeds 3ms threshold"
        assert overhead_percent < 50.0, f"Hierarchical overhead {overhead_percent:.1f}% exceeds 50% threshold"

    def test_counter_increment_performance(self, rate_limit_service):
        """Test that counter increment operations are fast."""
        # Act: Measure counter increment times
        def increment_counter():
            rate_limit_service._counter.increment_request_count(
                scope_type="model",
                scope_id="gpt-4",
                window_start=int(time.time()),
                window_duration=3600
            )

        times = self.measure_execution_time(increment_counter, iterations=1000)

        # Assert: Calculate percentiles
        p99 = statistics.quantiles(times, n=100)[98]
        mean = statistics.mean(times)

        print(f"\nCounter Increment Latency:")
        print(f"  Mean: {mean:.2f}ms")
        print(f"  p99:  {p99:.2f}ms")

        # Counter operations should be very fast (<5ms p99)
        assert p99 < 5.0, f"Counter increment p99 {p99:.2f}ms exceeds 5ms threshold"
        assert mean < 2.0, f"Counter increment mean {mean:.2f}ms exceeds 2ms threshold"

    def test_cache_lookup_performance(self, rate_limit_service):
        """Test that cache lookups are fast."""
        # Arrange: Warmup cache
        rate_limit_service.get_rate_limit_config("model", "gpt-4")

        # Act: Measure cache lookup times
        def lookup_cache():
            rate_limit_service._cache.get("model", "gpt-4")

        times = self.measure_execution_time(lookup_cache, iterations=10000)

        # Assert: Calculate percentiles
        p99 = statistics.quantiles(times, n=100)[98]
        mean = statistics.mean(times)

        print(f"\nCache Lookup Latency:")
        print(f"  Mean: {mean:.4f}ms")
        print(f"  p99:  {p99:.4f}ms")

        # Cache lookups should be extremely fast (<1ms p99)
        assert p99 < 1.0, f"Cache lookup p99 {p99:.4f}ms exceeds 1ms threshold"
        assert mean < 0.5, f"Cache lookup mean {mean:.4f}ms exceeds 0.5ms threshold"

    def test_window_selection_performance(self):
        """Test that time window selection is fast."""
        # Arrange: Create rate limit with multiple windows
        rate_limit = RateLimit(
            id=1,
            scope_type="model",
            scope_id="gpt-4",
            enabled=True,
            windows=[
                RateLimitWindow(
                    id=1,
                    from_time=dt_time(0, 0, 0),
                    to_time=dt_time(8, 0, 0),
                    max_requests=100,
                    max_tokens=10000
                ),
                RateLimitWindow(
                    id=2,
                    from_time=dt_time(8, 0, 0),
                    to_time=dt_time(17, 0, 0),
                    max_requests=1000,
                    max_tokens=100000
                ),
                RateLimitWindow(
                    id=3,
                    from_time=dt_time(17, 0, 0),
                    to_time=dt_time(23, 59, 59),
                    max_requests=500,
                    max_tokens=50000
                )
            ],
            created_at=None,
            updated_at=None
        )

        # Act: Measure window selection times
        def select_window():
            current_time = dt_time(10, 30, 0)  # 10:30 AM - should match window 2
            rate_limit.get_active_window(current_time)

        times = self.measure_execution_time(select_window, iterations=10000)

        # Assert: Calculate percentiles
        p99 = statistics.quantiles(times, n=100)[98]
        mean = statistics.mean(times)

        print(f"\nWindow Selection Latency:")
        print(f"  Mean: {mean:.4f}ms")
        print(f"  p99:  {p99:.4f}ms")

        # Window selection should be very fast (<0.5ms p99)
        assert p99 < 0.5, f"Window selection p99 {p99:.4f}ms exceeds 0.5ms threshold"
        assert mean < 0.2, f"Window selection mean {mean:.4f}ms exceeds 0.2ms threshold"


@pytest.mark.performance
class TestRateLimitMemoryUsage:
    """Memory usage tests for rate limiting system."""

    def test_cache_memory_bounded(self):
        """Test that cache memory usage is bounded by max_size."""
        # Arrange: Create cache with small max_size
        cache = InMemoryRateLimitCache(max_cache_size=10, ttl_seconds=30)

        # Act: Add 100 entries (should evict oldest)
        for i in range(100):
            rate_limit = RateLimit(
                id=i,
                scope_type="model",
                scope_id=f"model-{i}",
                enabled=True,
                windows=[],
                created_at=None,
                updated_at=None
            )
            cache.set("model", f"model-{i}", rate_limit)

        # Assert: Cache should only contain max_size entries
        stats = cache.get_stats()
        assert stats["size"] <= 10, f"Cache size {stats['size']} exceeds max_size of 10"

        print(f"\nCache Memory Usage:")
        print(f"  Size: {stats['size']}/10 entries")
        print(f"  Evictions: {stats['evictions']}")

    def test_counter_memory_bounded(self):
        """Test that counter memory usage is reasonable for many keys."""
        # Arrange: Create counter
        counter = InMemoryRateLimitCounter()

        # Act: Create 1000 unique counter keys
        window_start = int(time.time())
        for i in range(1000):
            counter.increment_request_count(
                scope_type="model",
                scope_id=f"model-{i}",
                window_start=window_start,
                window_duration=3600
            )

        # Assert: Counter should track all keys efficiently
        stats = counter.get_stats()
        print(f"\nCounter Memory Usage:")
        print(f"  Active keys: {stats['active_keys']}")
        print(f"  Total increments: {stats['total_increments']}")

        # Should handle 1000 keys without issues
        assert stats['active_keys'] == 1000, "Counter did not track all keys"


if __name__ == "__main__":
    # Run performance tests with verbose output
    pytest.main([__file__, "-v", "-s", "-m", "performance"])
