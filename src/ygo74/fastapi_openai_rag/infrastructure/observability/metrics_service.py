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

    def record_llm_request(
        self,
        provider: str,
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
            "provider": provider,
            "model": model,
            "success": str(success).lower()
        }

        self.llm_requests_total.add(1, attributes)
        self.llm_request_duration.record(duration, attributes)

        # Record token consumption
        token_attributes = {**attributes, "token_type": "input"}
        self.llm_tokens_consumed.add(tokens_in, token_attributes)

        token_attributes["token_type"] = "output"
        self.llm_tokens_consumed.add(tokens_out, token_attributes)

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
