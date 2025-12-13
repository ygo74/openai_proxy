"""Custom metrics service for FastAPI application monitoring."""
import time
import logging
from typing import Dict, Optional
from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for managing custom application metrics."""

    def __init__(self, service_name: str = "fastapi-openai-rag"):
        """Initialize metrics service.

        Args:
            service_name: Name of the service for metrics
        """
        self.service_name = service_name
        self.meter = metrics.get_meter(service_name)
        self._initialize_metrics()

    def _initialize_metrics(self) -> None:
        """Initialize all custom metrics."""
        # HTTP Request metrics
        self.http_requests_total = self.meter.create_counter(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="1"
        )

        self.http_request_duration = self.meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s"
        )

        self.http_requests_in_progress = self.meter.create_up_down_counter(
            name="http_requests_in_progress",
            description="Number of HTTP requests currently in progress",
            unit="1"
        )

        # Authentication metrics
        self.auth_attempts_total = self.meter.create_counter(
            name="auth_attempts_total",
            description="Total number of authentication attempts",
            unit="1"
        )

        # LLM specific metrics
        self.llm_requests_total = self.meter.create_counter(
            name="llm_requests_total",
            description="Total number of LLM requests",
            unit="1"
        )

        self.llm_tokens_consumed = self.meter.create_counter(
            name="llm_tokens_consumed_total",
            description="Total number of tokens consumed",
            unit="1"
        )

        self.llm_request_duration = self.meter.create_histogram(
            name="llm_request_duration_seconds",
            description="LLM request duration in seconds",
            unit="s"
        )

        self.llm_requests_in_progress = self.meter.create_up_down_counter(
            name="llm_requests_in_progress",
            description="Number of LLM requests currently in progress",
            unit="1"
        )

        # Database metrics
        self.db_queries_total = self.meter.create_counter(
            name="db_queries_total",
            description="Total number of database queries",
            unit="1"
        )

        self.db_query_duration = self.meter.create_histogram(
            name="db_query_duration_seconds",
            description="Database query duration in seconds",
            unit="s"
        )

        # Rate limiting metrics
        self.rate_limit_evaluations_total = self.meter.create_counter(
            name="rate_limit_evaluations_total",
            description="Total number of rate limit evaluations",
            unit="1"
        )

        self.rate_limit_evaluation_duration = self.meter.create_histogram(
            name="rate_limit_evaluation_duration_ms",
            description="Rate limit evaluation duration in milliseconds",
            unit="ms"
        )

        self.rate_limit_exceeded_total = self.meter.create_counter(
            name="rate_limit_exceeded_total",
            description="Total number of rate limit exceeded events",
            unit="1"
        )

        self.rate_limit_cache_hits_total = self.meter.create_counter(
            name="rate_limit_cache_hits_total",
            description="Total number of rate limit cache hits",
            unit="1"
        )

        self.rate_limit_cache_misses_total = self.meter.create_counter(
            name="rate_limit_cache_misses_total",
            description="Total number of rate limit cache misses",
            unit="1"
        )

        logger.info("Custom metrics initialized")

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float
    ) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        attributes = {
            "method": method,
            "endpoint": endpoint,
            "status_code": str(status_code),
            "status_class": f"{status_code // 100}xx"
        }

        self.http_requests_total.add(1, attributes)
        self.http_request_duration.record(duration, attributes)

    @contextmanager
    def track_http_request_in_progress(self):
        """Context manager to track requests in progress."""
        self.http_requests_in_progress.add(1)
        try:
            yield
        finally:
            self.http_requests_in_progress.add(-1)

    def record_auth_attempt(self, auth_type: str, success: bool, username: Optional[str] = None) -> None:
        """Record authentication attempt.

        Args:
            auth_type: Type of authentication (api_key, jwt, oauth)
            success: Whether authentication was successful
            username: Username if available
        """
        attributes = {
            "auth_type": auth_type,
            "success": str(success).lower(),
        }
        if username:
            attributes["username"] = username

        self.auth_attempts_total.add(1, attributes)

    @contextmanager
    def track_llm_request_in_progress(self, model: str):
        """Context manager to track LLM requests in progress.

        Args:
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name

        Yields:
            None
        """
        attributes = {
            "model": model
        }
        self.llm_requests_in_progress.add(1, attributes)

        try:
            yield
        finally:
            self.llm_requests_in_progress.add(-1, attributes)

    def record_llm_request(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration: float,
        success: bool
    ) -> None:
        """Record LLM request metrics.

        Args:
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name
            tokens_in: Input tokens
            tokens_out: Output tokens
            duration: Request duration in seconds
            success: Whether request was successful
        """
        attributes = {
            "model": model,
            "success": str(success).lower()
        }

        self.llm_requests_total.add(1, attributes)
        self.llm_request_duration.record(duration, attributes)

        # Create separate attribute dictionaries for input and output tokens
        # to avoid overwriting the token_type
        input_token_attributes = {**attributes, "token_type": "input"}
        output_token_attributes = {**attributes, "token_type": "output"}

        # Record input token consumption with input-specific attributes
        self.llm_tokens_consumed.add(tokens_in, input_token_attributes)
        logger.debug(f"Recorded {tokens_in} input tokens for model {model}")

        # Record output token consumption with output-specific attributes
        self.llm_tokens_consumed.add(tokens_out, output_token_attributes)
        logger.debug(f"Recorded {tokens_out} output tokens for model {model}")

    def record_db_query(self, operation: str, table: str, duration: float, success: bool) -> None:
        """Record database query metrics.

        Args:
            operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
            table: Table name
            duration: Query duration in seconds
            success: Whether query was successful
        """
        attributes = {
            "operation": operation.upper(),
            "table": table,
            "success": str(success).lower()
        }

        self.db_queries_total.add(1, attributes)
        self.db_query_duration.record(duration, attributes)

    def record_rate_limit_evaluation(
        self,
        scope_type: str,
        limit_type: str,
        duration_ms: float,
        exceeded: bool,
        scope_id: Optional[str] = None
    ) -> None:
        """Record rate limit evaluation metrics.

        Args:
            scope_type: Type of scope (global, model, group_model)
            limit_type: Type of limit (requests, tokens)
            duration_ms: Evaluation duration in milliseconds
            exceeded: Whether the rate limit was exceeded
            scope_id: Optional scope identifier
        """
        attributes = {
            "scope_type": scope_type,
            "limit_type": limit_type,
            "exceeded": str(exceeded).lower()
        }
        if scope_id:
            attributes["scope_id"] = scope_id

        self.rate_limit_evaluations_total.add(1, attributes)
        self.rate_limit_evaluation_duration.record(duration_ms, attributes)

        if exceeded:
            self.rate_limit_exceeded_total.add(1, attributes)

    def record_rate_limit_cache_access(self, hit: bool, scope_type: str, scope_id: Optional[str] = None) -> None:
        """Record rate limit cache access metrics.

        Args:
            hit: Whether the cache access was a hit
            scope_type: Type of scope (global, model, group_model)
            scope_id: Optional scope identifier
        """
        attributes = {
            "scope_type": scope_type
        }
        if scope_id:
            attributes["scope_id"] = scope_id

        if hit:
            self.rate_limit_cache_hits_total.add(1, attributes)
        else:
            self.rate_limit_cache_misses_total.add(1, attributes)


# Global metrics service instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> Optional[MetricsService]:
    """Get the global metrics service instance.

    Returns:
        MetricsService instance or None if not initialized
    """
    return _metrics_service


def initialize_metrics_service(service_name: str = "fastapi-openai-rag") -> MetricsService:
    """Initialize global metrics service.

    Args:
        service_name: Name of the service

    Returns:
        Initialized MetricsService instance
    """
    global _metrics_service
    _metrics_service = MetricsService(service_name)
    return _metrics_service
