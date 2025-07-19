"""Admin API endpoints."""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

@router.get("/health")
async def health_check():
    """Health check endpoint for admin operations."""
    return {"status": "healthy", "message": "Admin endpoint is operational"}

@router.get("/info")
async def get_admin_info():
    """Get admin information."""
    return {
        "message": "Admin endpoint - use /models and /groups endpoints for respective operations",
        "available_endpoints": {
            "models": "/models - Model management operations",
            "groups": "/groups - Group management operations"
        }
    }
