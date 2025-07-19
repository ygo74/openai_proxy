"""API version 1 routes."""
from fastapi import APIRouter

from .endpoints import groups

router = APIRouter()

# Include the groups router
router.include_router(groups.router, prefix="/groups", tags=["groups"])