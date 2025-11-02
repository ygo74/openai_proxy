"""Rate limit management endpoints."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.rate_limit_service import TokenRateLimitService
from ....application.services.model_service import ModelService
from ....domain.models.autenticated_user import AuthenticatedUser
from ..decorators.decorators import endpoint_handler
from ..security.auth import auth_jwt_or_api_key

router = APIRouter()

def get_rate_limit_service(db: Session = Depends(get_db)) -> TokenRateLimitService:
    """Get rate limit service instance."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return TokenRateLimitService(uow)

def get_model_service(db: Session = Depends(get_db)) -> ModelService:
    """Get model service instance."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ModelService(uow)

@router.get("/rate-limits")
@endpoint_handler("get_user_rate_limits")
async def get_user_rate_limits(
    model_name: Optional[str] = Query(None, description="Specific model to check limits for"),
    rate_limit_service: TokenRateLimitService = Depends(get_rate_limit_service),
    model_service: ModelService = Depends(get_model_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, Any]:
    """Get current rate limit configuration and usage for the authenticated user.

    Args:
        model_name: Optional specific model name to check
        rate_limit_service: Rate limit service
        model_service: Model service
        user: Authenticated user

    Returns:
        Rate limit information including configuration and current usage
    """
    model = None
    if model_name:
        try:
            # Get model for model-specific rate limits
            models = model_service.get_all_models()
            model = next((m for m in models if m.name == model_name or m.technical_name == model_name), None)
        except Exception:
            pass  # Continue with global limits if model not found

    return rate_limit_service.get_rate_limit_info(user, model)

@router.get("/rate-limits/usage")
@endpoint_handler("get_user_rate_limit_usage")
async def get_user_rate_limit_usage(
    model_name: Optional[str] = Query(None, description="Specific model to check usage for"),
    rate_limit_service: TokenRateLimitService = Depends(get_rate_limit_service),
    model_service: ModelService = Depends(get_model_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, int]:
    """Get current rate limit usage for the authenticated user.

    Args:
        model_name: Optional specific model name to check
        rate_limit_service: Rate limit service
        model_service: Model service
        user: Authenticated user

    Returns:
        Current usage statistics for each time window
    """
    model = None
    if model_name:
        try:
            models = model_service.get_all_models()
            model = next((m for m in models if m.name == model_name or m.technical_name == model_name), None)
        except Exception:
            pass

    return rate_limit_service.get_current_usage(user, model)
