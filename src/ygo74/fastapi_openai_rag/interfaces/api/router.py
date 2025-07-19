"""Main API router module."""
from fastapi import APIRouter
from .endpoints import models, groups, admin

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