import json
import time
import asyncio
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Awaitable

# ========================
# Forwarders
# ========================

class BaseForwarder:
    async def send(self, event: dict):
        raise NotImplementedError

class PrintForwarder(BaseForwarder):
    """Forwarder d'exemple: print"""
    async def send(self, event: dict):
        print("[FORWARDER]", json.dumps(event, ensure_ascii=False))

class HTTPForwarder(BaseForwarder):
    """Forwarder générique HTTP (Splunk, ES, etc.)"""
    def __init__(self, url: str, headers: dict):
        self.url = url
        self.headers = headers

    async def send(self, event: dict):
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.url, headers=self.headers, json=event, timeout=3)
            except Exception as e:
                print("[FORWARD ERROR]", e)

# ========================
# Middleware
# ========================

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, forwarders: list[BaseForwarder] = None):
        super().__init__(app)
        self.forwarders = forwarders or []

    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()

        # Capture du corps de requête
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8") if body_bytes else None
        request = Request(request.scope, receive=lambda: {"type": "http.request", "body": body_bytes})

        response = await call_next(request)

        # Capture du corps de réponse
        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk
        process_time = time.time() - start_time

        user_info = request.scope.get("authenticated_user")

        # 1️⃣ Audit interne minimal
        audit_log = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": request.method,
            "path": request.url.path,
            "user": getattr(user_info, "username", None),
            "auth_type": getattr(user_info, "type", None),
            "status_code": response.status_code,
            "duration_ms": round(process_time * 1000, 2)
        }
        await self.save_audit_to_db(audit_log)

        # 2️⃣ Full log vers collectors (seulement si LLM endpoint)
        if request.url.path.startswith("/v1/completions") or request.url.path.startswith("/v1/chat/completions"):
            full_event = {
                **audit_log,
                "request_body": body_text,
                "response_body": resp_body.decode("utf-8", errors="replace")
            }
            # Fire-and-forget via asyncio
            asyncio.create_task(self.forward_full_log(full_event))

        return Response(content=resp_body, status_code=response.status_code, headers=dict(response.headers))

    async def save_audit_to_db(self, log_data: dict):
        # 🔹 Ici logique DB interne
        print("[DB AUDIT]", log_data)

    async def forward_full_log(self, event: dict):
        for fwd in self.forwarders:
            try:
                await fwd.send(event)
            except Exception as e:
                print("[FORWARDER ERROR]", e)
