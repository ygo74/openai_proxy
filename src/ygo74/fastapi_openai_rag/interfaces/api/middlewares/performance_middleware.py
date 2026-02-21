"""Performance monitoring middleware for detailed timing analysis."""
import time
import logging
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to log detailed timing information for each request phase."""

    def __init__(self, app: ASGIApp, enable_detailed_logs: bool = True):
        """Initialize the performance middleware.

        Args:
            app: The ASGI application
            enable_detailed_logs: Whether to log detailed timing for each phase
        """
        super().__init__(app)
        self.enable_detailed_logs = enable_detailed_logs

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with detailed timing measurements.

        Args:
            request: The incoming request
            call_next: The next middleware or endpoint handler

        Returns:
            The response to return to the client
        """
        # 1. Start timing - request received
        t_start = time.perf_counter()

        # 2. Read request body (if any)
        t_body_start = time.perf_counter()
        try:
            # Force read body to measure parsing time
            await request.body()
        except:
            pass
        t_body_end = time.perf_counter()
        body_parse_ms = (t_body_end - t_body_start) * 1000

        # 3. Call next middleware/endpoint (includes auth, business logic, LLM call)
        t_handler_start = time.perf_counter()
        response = await call_next(request)
        t_handler_end = time.perf_counter()
        handler_ms = (t_handler_end - t_handler_start) * 1000

        # 4. End timing - response ready to send
        t_end = time.perf_counter()
        total_ms = (t_end - t_start) * 1000

        # Calculate overhead (time spent outside handler)
        overhead_ms = total_ms - handler_ms - body_parse_ms

        # Log detailed timing
        if self.enable_detailed_logs:
            timing_info = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "path": request.url.path,
                "total_ms": round(total_ms, 2),
                "body_parse_ms": round(body_parse_ms, 2),
                "handler_ms": round(handler_ms, 2),  # Business logic + LLM call
                "overhead_ms": round(overhead_ms, 2),  # Middleware overhead
                "overhead_percent": round((overhead_ms / total_ms * 100) if total_ms > 0 else 0, 1)
            }

            logger.info(f"[PERF] {timing_info}")

        # Add timing headers to response
        response.headers["X-Request-Time-Total-Ms"] = str(round(total_ms, 2))
        response.headers["X-Request-Time-Handler-Ms"] = str(round(handler_ms, 2))
        response.headers["X-Request-Time-Overhead-Ms"] = str(round(overhead_ms, 2))

        return response
