"""Middleware for capturing HTTP metrics."""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ....infrastructure.observability.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to capture HTTP request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and capture metrics.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        metrics_service = get_metrics_service()
        if not metrics_service:
            return await call_next(request)

        start_time = time.time()

        # Track request in progress
        with metrics_service.track_http_request_in_progress():
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception as e:
                logger.error(f"Request failed: {e}")
                status_code = 500
                raise
            finally:
                # Record metrics
                duration = time.time() - start_time
                endpoint = self._get_endpoint_pattern(request)

                metrics_service.record_http_request(
                    method=request.method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration
                )

        return response

    def _get_endpoint_pattern(self, request: Request) -> str:
        """Extract endpoint pattern from request.

        Args:
            request: HTTP request

        Returns:
            Endpoint pattern (e.g., /v1/chat/completions)
        """
        try:
            # Try to get route pattern if available
            if hasattr(request, "scope") and "route" in request.scope:
                route = request.scope["route"]
                if hasattr(route, "path"):
                    return route.path

            # Fallback to path
            return request.url.path
        except Exception:
            return "unknown"
