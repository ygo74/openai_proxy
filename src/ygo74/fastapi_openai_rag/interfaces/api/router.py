"""Main API router module."""
import os
from fastapi import APIRouter
from .endpoints import models, groups, chat_completions, users, debug_auth, health, metrics

# Create main API router
api_router = APIRouter(prefix="/v1")

# Include the chat completions router (OpenAI-compatible)
api_router.include_router(chat_completions.router, tags=["openai-compatible"])

# Health endpoints (no auth required)
api_router.include_router(health.router, tags=["health"])

# Include routers from endpoints
api_router.include_router(models.router, prefix="/admin/models", tags=["models"])

# Include routers with prefixes
api_router.include_router(groups.router, prefix="/admin/groups", tags=["groups"])
api_router.include_router(users.router, prefix="/admin/users", tags=["users"])

# Debug endpoints (development only)
if os.environ.get('DEVELOPMENT_MODE', '').lower() == 'true':
    api_router.include_router(debug_auth.router, prefix="/debug", tags=["debug-auth"])

# Include metrics router for observability
api_router.include_router(
    metrics.router,
    tags=["metrics"]
)