"""Tests for Redis health check integration.

These tests verify that the Redis health check is properly integrated
into the global health endpoint and only runs when Redis is enabled.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.ygo74.fastapi_openai_rag.main import app
from src.ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig, RedisCacheConfig


class TestRedisHealthCheck:
    """Test Redis health check integration in global health endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_config_redis_enabled(self):
        """Mock configuration with Redis enabled."""
        config = MagicMock(spec=AppConfig)
        config.redis_cache = RedisCacheConfig(
            enabled=True,
            host="localhost",
            port=6379,
            db=0
        )
        config.db_type = "postgresql"
        return config

    @pytest.fixture
    def mock_config_redis_disabled(self):
        """Mock configuration with Redis disabled."""
        config = MagicMock(spec=AppConfig)
        config.redis_cache = RedisCacheConfig(
            enabled=False,
            host="localhost",
            port=6379,
            db=0
        )
        config.db_type = "postgresql"
        return config

    def test_health_check_includes_redis_when_enabled(self, client, mock_config_redis_enabled):
        """Test that Redis health check is included when Redis is enabled."""
        from src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter import RedisRateLimitCounter

        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_enabled

            # Mock the counter to return a Redis counter
            mock_counter = MagicMock(spec=RedisRateLimitCounter)
            mock_counter.increment_request_count = MagicMock(return_value=1)

            with patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory.get_rate_limit_counter') as mock_get_counter:
                mock_get_counter.return_value = mock_counter

                # Call detailed health check
                response = client.get("/v1/health/detailed")

                # Verify response
                assert response.status_code == 200
                data = response.json()

                # Check that redis_rate_limiting is in checks
                check_names = [check["name"] for check in data["checks"]]
                assert "redis_rate_limiting" in check_names

                # Find Redis check
                redis_check = next(c for c in data["checks"] if c["name"] == "redis_rate_limiting")
                assert redis_check["status"] == "healthy"
                assert "response_time_ms" in redis_check
                assert redis_check["details"]["host"] == "localhost"
                assert redis_check["details"]["port"] == 6379

    def test_health_check_skips_redis_when_disabled(self, client, mock_config_redis_disabled):
        """Test that Redis health check is skipped when Redis is disabled."""
        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_disabled

            # Call detailed health check
            response = client.get("/v1/health/detailed")

            # Verify response
            assert response.status_code == 200
            data = response.json()

            # Check that redis_rate_limiting is NOT in checks
            check_names = [check["name"] for check in data["checks"]]
            assert "redis_rate_limiting" not in check_names

            # Should still have other checks
            assert "database" in check_names
            assert "configuration" in check_names
            assert "dependencies" in check_names

    def test_health_check_handles_redis_failure_gracefully(self, client, mock_config_redis_enabled):
        """Test that Redis health check handles connection failures gracefully."""
        from src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter import RedisRateLimitCounter

        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_enabled

            # Mock the counter to raise an exception
            with patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory.get_rate_limit_counter') as mock_get_counter:
                mock_get_counter.side_effect = Exception("Redis connection failed")

                # Call detailed health check
                response = client.get("/v1/health/detailed")

                # Verify response - should still return 200 but with degraded status
                assert response.status_code == 200
                data = response.json()

                # Overall status should be degraded
                assert data["status"] in ["degraded", "unhealthy"]

                # Redis check should show unhealthy
                check_names = [check["name"] for check in data["checks"]]
                assert "redis_rate_limiting" in check_names

                redis_check = next(c for c in data["checks"] if c["name"] == "redis_rate_limiting")
                assert redis_check["status"] == "unhealthy"
                assert "Redis connection failed" in redis_check["message"]

    def test_health_check_skips_redis_for_in_memory_counter(self, client, mock_config_redis_enabled):
        """Test that Redis health check is skipped when using in-memory counter."""
        from src.ygo74.fastapi_openai_rag.infrastructure.cache.in_memory_rate_limit_counter import InMemoryRateLimitCounter

        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_enabled

            # Mock the counter to return an in-memory counter
            mock_counter = MagicMock(spec=InMemoryRateLimitCounter)

            with patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory.get_rate_limit_counter') as mock_get_counter:
                mock_get_counter.return_value = mock_counter

                # Call detailed health check
                response = client.get("/v1/health/detailed")

                # Verify response
                assert response.status_code == 200
                data = response.json()

                # Redis check should not be included (in-memory counter)
                check_names = [check["name"] for check in data["checks"]]
                assert "redis_rate_limiting" not in check_names

    def test_basic_health_check_not_affected(self, client):
        """Test that basic health check endpoint is not affected by Redis."""
        # Call basic health check
        response = client.get("/health")

        # Verify response - should work regardless of Redis
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" not in data  # Basic health check doesn't include detailed checks

    def test_readiness_check_not_affected_by_redis(self, client, mock_config_redis_disabled):
        """Test that readiness check doesn't depend on Redis."""
        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_disabled

            # Call readiness check
            response = client.get("/v1/health/ready")

            # Verify response - should work even if Redis is disabled
            assert response.status_code in [200, 503]  # 503 only if DB or config fails

    def test_redis_health_check_includes_connection_details(self, client, mock_config_redis_enabled):
        """Test that Redis health check includes connection details."""
        from src.ygo74.fastapi_openai_rag.infrastructure.cache.redis_rate_limit_counter import RedisRateLimitCounter

        with patch('src.ygo74.fastapi_openai_rag.application.services.config_service.config_service.get_config') as mock_get_config:
            mock_get_config.return_value = mock_config_redis_enabled

            mock_counter = MagicMock(spec=RedisRateLimitCounter)
            mock_counter.increment_request_count = MagicMock(return_value=1)

            with patch('src.ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter_factory.get_rate_limit_counter') as mock_get_counter:
                mock_get_counter.return_value = mock_counter

                # Call detailed health check
                response = client.get("/v1/health/detailed")

                assert response.status_code == 200
                data = response.json()

                redis_check = next(c for c in data["checks"] if c["name"] == "redis_rate_limiting")

                # Verify connection details are included
                assert "details" in redis_check
                assert redis_check["details"]["host"] == "localhost"
                assert redis_check["details"]["port"] == 6379
                assert redis_check["details"]["db"] == 0
                assert "response_time_ms" in redis_check
