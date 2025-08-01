"""Main API router module."""
from fastapi import APIRouter
from .endpoints import models, groups, admin, chat_completions

# Create main API router
api_router = APIRouter(prefix="/v1")

# Include routers from endpoints
api_router.include_router(
    models.router,
    prefix="/models",
    tags=["models"]
)

api_router.include_router(
    groups.router,
    prefix="/groups",
    tags=["groups"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)

# Include the chat completions router (OpenAI-compatible)
api_router.include_router(
    chat_completions.router,
    prefix="",
    tags=["openai-compatible"]
)