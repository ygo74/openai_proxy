import json
import time
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp, Message
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Awaitable

from ygo74.fastapi_openai_rag.application.services.audit_service import AuditService
from ..utils.json_encoder import DateTimeEncoder

logger = logging.getLogger(__name__)

# ========================
# Forwarders
# ========================

class BaseForwarder:
    """Base forwarder interface for audit events."""

    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send an audit event to the target system.

        Args:
            event: The event data to send
        """
        raise NotImplementedError("Subclasses must implement send()")

class PrintForwarder(BaseForwarder):
    """Simple forwarder that prints events to console."""

    def __init__(self, level: str = "info"):
        """
        Initialize the print forwarder.

        Args:
            level: Logging level (info, debug, warning, error)
        """
        self.level = level.lower()

    async def send(self, event: Dict[str, Any]) -> None:
        """
        Print the event as JSON.

        Args:
            event: The event data to print
        """
        if self.level == "debug":
            print("[FORWARDER]", json.dumps(event, cls=DateTimeEncoder, ensure_ascii=False))

class HTTPForwarder(BaseForwarder):
    """Forwarder that sends events to an HTTP endpoint."""

    def __init__(self, url: str, headers: Dict[str, str]):
        """
        Initialize the HTTP forwarder.

        Args:
            url: The target URL
            headers: HTTP headers to include in the request
        """
        self.url = url
        self.headers = headers

    async def send(self, event: Dict[str, Any]) -> None:
        """
        Send the event via HTTP POST.

        Args:
            event: The event data to send
        """
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.url, headers=self.headers, json=event, timeout=3)
            except Exception as e:
                logger.error(f"HTTP forward error: {e}")

# ========================
# Middleware
# ========================

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for auditing API requests and responses.
    Can store minimal audit logs in the database and optionally
    forward full request/response data to external collectors.
    Supports streaming responses without breaking SSE.
    """

    def __init__(
        self,
        app: ASGIApp,
        audit_service: Optional[AuditService] = None,
        forwarders: Optional[List[BaseForwarder]] = None
    ):
        """
        Initialize the audit middleware.

        Args:
            app: The ASGI application
            audit_service: The service for persisting audit logs
            forwarders: List of forwarders for full event data
        """
        super().__init__(app)
        self.audit_service = audit_service
        self.forwarders = forwarders or []

    def _is_auditable_llm_path(self, path: str) -> bool:
        """
        Check if the request path is an LLM endpoint that requires full audit.

        Args:
            path: The URL path to check

        Returns:
            True if the path should be fully audited
        """
        return (
            path.startswith("/v1/completions")
            or path.startswith("/v1/chat/completions")
            or path.startswith("/v1/responses")
        )

    def _is_streaming_response(self, response: Response) -> bool:
        """
        Determine if a response is a streaming (SSE) response.

        Args:
            response: The response object

        Returns:
            True if the response is streaming
        """
        content_type = response.headers.get("content-type", "")
        return "text/event-stream" in content_type

    async def _wrap_streaming_body(
        self,
        body_iterator: AsyncIterator[bytes],
        audit_log: Dict[str, Any],
        body_text: Optional[str],
        needs_full_audit: bool,
        start_time: float,
    ) -> AsyncIterator[bytes]:
        """
        Async generator that yields chunks in real-time while
        accumulating them for audit forwarding after the stream ends.

        Args:
            body_iterator: The original response body iterator
            audit_log: The minimal audit log dict
            body_text: The original request body text
            needs_full_audit: Whether to forward the full event after streaming
            start_time: The timestamp when the request started, used to compute total duration

        Yields:
            Response body chunks as they arrive
        """
        collected_chunks: List[bytes] = []
        try:
            async for chunk in body_iterator:
                collected_chunks.append(chunk)
                yield chunk
        finally:
            # Recompute total duration including streaming time
            total_duration_ms: float = round((time.time() - start_time) * 1000, 2)
            audit_log["duration_ms"] = total_duration_ms

            if needs_full_audit:
                resp_body: bytes = b"".join(collected_chunks)
                full_event: Dict[str, Any] = {
                    **audit_log,
                    "request_body": body_text,
                    "response_body": resp_body.decode("utf-8", errors="replace") if resp_body else "",
                }
                asyncio.create_task(self.forward_full_log(full_event))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process the request, capture timing and data for auditing.
        Preserves streaming for SSE responses.

        Args:
            request: The incoming request
            call_next: The next middleware or endpoint handler

        Returns:
            The response to return to the client
        """
        start_time = time.time()

        # Capture request body
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8") if body_bytes else None

        # Create a new request with the same body
        async def receive() -> Message:
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request_with_body = Request(request.scope, receive=receive)

        # Process the request
        response = await call_next(request_with_body)

        # Calculate timing
        process_time = time.time() - start_time

        # Get user information from the request scope
        user_info = request.scope.get("authenticated_user")

        # 1️⃣ Create minimal audit log
        audit_log: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc),
            "method": request.method,
            "path": request.url.path,
            "user": getattr(user_info, "username", None),
            "auth_type": getattr(user_info, "type", None),
            "status_code": response.status_code,
            "duration_ms": round(process_time * 1000, 2),
        }

        # Save minimal audit to database
        self.save_audit_to_db(audit_log)

        needs_full_audit = self._is_auditable_llm_path(request.url.path)

        # 2️⃣ Streaming response — wrap the iterator, don't buffer
        if self._is_streaming_response(response):
            body_iterator = response.__dict__.get("body_iterator")
            wrapped_iterator = self._wrap_streaming_body(
                body_iterator,
                audit_log,
                body_text,
                needs_full_audit,
                start_time,
            )
            return StreamingResponse(
                content=wrapped_iterator,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # 3️⃣ Non-streaming response — buffer entire body then return
        resp_body = b""
        body_iterator = response.__dict__.get("body_iterator")
        if body_iterator:
            async for chunk in body_iterator:
                resp_body += chunk

        if needs_full_audit:
            full_event: Dict[str, Any] = {
                **audit_log,
                "request_body": body_text,
                "response_body": resp_body.decode("utf-8", errors="replace") if resp_body else "",
            }
            asyncio.create_task(self.forward_full_log(full_event))

        return Response(
            content=resp_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def save_audit_to_db(self, log_data: Dict[str, Any]) -> None:
        """
        Save audit log to database using the AuditService if available.

        Args:
            log_data: The audit data to be saved
        """
        if self.audit_service:
            try:
                self.audit_service.create_audit_log(log_data)
            except Exception as e:
                logger.error(f"Failed to save audit log: {str(e)}", exc_info=True)
        else:
            # Fallback to logging if no service is available
            logger.info(f"AUDIT LOG: {log_data}")

    async def forward_full_log(self, event: Dict[str, Any]) -> None:
        """
        Forward a full log event to all registered forwarders.

        Args:
            event: The complete event data to forward
        """
        for fwd in self.forwarders:
            try:
                await fwd.send(event)
            except Exception as e:
                logger.error(f"Forwarder error: {str(e)}", exc_info=True)
