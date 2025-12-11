"""Admin API endpoints for rate limit management.

This module provides REST API endpoints for administrators to create, read,
update, and delete rate limit configurations dynamically without code deployments.

Endpoints:
- GET /admin/rate-limits - List all rate limits
- GET /admin/rate-limits/applicable - Query hierarchical limits for debugging
- GET /admin/rate-limits/{scope_type}/{scope_id} - Get specific rate limit
- GET /admin/rate-limits/global - Get global limits from config
- POST /admin/rate-limits/models/{model_id} - Create/update model limit
- POST /admin/rate-limits/groups/{group_id}/models/{model_id} - Create/update group+model limit
- PATCH /admin/rate-limits/{scope_type}/{scope_id} - Partial update (enabled and/or windows)
- DELETE /admin/rate-limits/{scope_type}/{scope_id} - Delete rate limit

Authentication:
- All endpoints require admin role via require_admin_role dependency
- Uses existing Keycloak/OAuth2 authentication
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.rate_limit_service import RateLimitService
from ..mappers.rate_limit_mapper import RateLimitApiMapper
from ....domain.models.rate_limit import RateLimit
from ....domain.models.autenticated_user import AuthenticatedUser
from ..security.auth import require_admin_role
from ..models.rate_limit_api import (
    CreateRateLimitRequest,
    UpdateRateLimitRequest,
    RateLimitResponse,
    RateLimitListResponse,
    RateLimitDeleteResponse,
    GlobalRateLimitResponse,
    ApplicableLimitsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rate-limits", tags=["admin", "rate-limits"])


def get_rate_limit_service(db: Session = Depends(get_db)) -> RateLimitService:
    """Create RateLimitService instance with Unit of Work.

    Args:
        db: Database session

    Returns:
        RateLimitService instance
    """
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return RateLimitService(uow)


@router.get("", response_model=RateLimitListResponse)
async def list_rate_limits(
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitListResponse:
    """List all configured rate limits.

    Returns all rate limit configurations from the database, including
    global, model, and group+model scopes.

    Args:
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        List of all rate limit configurations with total count

    Raises:
        HTTP 401: Unauthorized if not admin
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} listing all rate limits")

    # Delegate to service
    rate_limits = service.get_all_rate_limits()

    # Map domain models to API response
    response_limits = [
        RateLimitApiMapper.domain_to_response(rl)
        for rl in rate_limits
    ]

    return RateLimitListResponse(
        rate_limits=response_limits,
        total=len(response_limits)
    )


@router.get("/global", response_model=GlobalRateLimitResponse)
async def get_global_rate_limit(
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> GlobalRateLimitResponse:
    """Get global rate limit configuration from config.json.

    Global rate limits are read-only and configured via config.json.
    This endpoint provides visibility into the global limits.

    Args:
        admin_user: Authenticated admin user

    Returns:
        Global rate limit configuration from config file

    Raises:
        HTTP 401: Unauthorized if not admin
        HTTP 404: Global limits not configured
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} retrieving global rate limit")

    # TODO: Integrate with ConfigService when Phase 9 is implemented
    # For now, return placeholder response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Global rate limits from config.json will be available in Phase 9"
    )


@router.get("/applicable", response_model=ApplicableLimitsResponse)
async def get_applicable_limits(
    group_id: Optional[str] = None,
    model_id: Optional[str] = None,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> ApplicableLimitsResponse:
    """Query hierarchical rate limits for debugging and testing.

    Returns all applicable rate limits for a given group/model combination,
    showing the hierarchy of limits (group+model → model → global) and
    which one will actually be enforced.

    This endpoint is useful for:
    - Debugging rate limit configuration
    - Understanding which limit applies in specific scenarios
    - Testing hierarchical priority before sending actual requests

    Hierarchy priority (first non-null wins):
    1. Group+model limit (most specific) - requires both group_id and model_id
    2. Model limit (medium specificity) - requires model_id
    3. Global limit (fallback) - always checked

    Args:
        group_id: Optional group identifier
        model_id: Optional model identifier
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        ApplicableLimitsResponse with all hierarchy levels and effective limit

    Raises:
        HTTP 401: Unauthorized if not admin
        HTTP 500: Internal server error

    Examples:
        GET /admin/rate-limits/applicable?group_id=team-a&model_id=gpt-4
        → Returns group+model, model, and global limits for team-a:gpt-4

        GET /admin/rate-limits/applicable?model_id=gpt-4
        → Returns model and global limits (no group+model since group_id missing)

        GET /admin/rate-limits/applicable
        → Returns only global limit
    """
    logger.info(
        f"Admin {admin_user.username} querying applicable limits "
        f"(group_id={group_id}, model_id={model_id})"
    )

    # Delegate to service
    limits = service.get_applicable_limits(group_id=group_id, model_id=model_id)

    # Map domain models to API responses
    def to_response_optional(rl: Optional[RateLimit]) -> Optional[RateLimitResponse]:
        return RateLimitApiMapper.domain_to_response(rl) if rl else None

    group_model_response = to_response_optional(limits.get('group_model'))
    model_response = to_response_optional(limits.get('model'))
    global_response = to_response_optional(limits.get('global'))

    # Determine effective limit (first non-null in hierarchy)
    effective = group_model_response or model_response or global_response

    return ApplicableLimitsResponse(
        group_id=group_id,
        model_id=model_id,
        group_model_limit=group_model_response,
        model_limit=model_response,
        global_limit=global_response,
        effective_limit=effective
    )


@router.post("/models/{model_id}", response_model=RateLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_model_rate_limit(
    model_id: str,
    request_data: CreateRateLimitRequest,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitResponse:
    """Create or update rate limit for a specific model.

    Creates a new model-level rate limit or updates existing one.
    Model-level limits apply to all requests for that model across all groups.

    Args:
        model_id: Model identifier (e.g., "gpt-4", "claude-3")
        request_data: Rate limit configuration
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        Created or updated rate limit configuration

    Raises:
        HTTP 400: Invalid request data
        HTTP 401: Unauthorized if not admin
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} creating/updating rate limit for model {model_id}")

    # Map API request to domain model
    rate_limit = RateLimitApiMapper.create_request_to_domain(
        request_data,
        scope_type="model",
        scope_id=model_id
    )

    # Delegate to service
    created_limit = service.create_or_update_rate_limit(rate_limit)

    # Map domain response to API
    return RateLimitApiMapper.domain_to_response(created_limit)


@router.post("/groups/{group_id}/models/{model_id}", response_model=RateLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_group_model_rate_limit(
    group_id: str,
    model_id: str,
    request_data: CreateRateLimitRequest,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitResponse:
    """Create or update rate limit for a specific group+model combination.

    Creates a new group+model rate limit or updates existing one.
    Group+model limits are the most specific and take precedence over model and global limits.

    Args:
        group_id: Group identifier (e.g., "engineering", "marketing")
        model_id: Model identifier (e.g., "gpt-4", "claude-3")
        request_data: Rate limit configuration
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        Created or updated rate limit configuration

    Raises:
        HTTP 400: Invalid request data
        HTTP 401: Unauthorized if not admin
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} creating/updating rate limit for group {group_id}, model {model_id}")

    # Scope ID format: "group_id:model_id"
    scope_id = f"{group_id}:{model_id}"

    # Map API request to domain model
    rate_limit = RateLimitApiMapper.create_request_to_domain(
        request_data,
        scope_type="group_model",
        scope_id=scope_id
    )

    # Delegate to service
    created_limit = service.create_or_update_rate_limit(rate_limit)

    # Map domain response to API
    return RateLimitApiMapper.domain_to_response(created_limit)


@router.get("/{scope_type}/{scope_id}", response_model=RateLimitResponse)
async def get_rate_limit(
    scope_type: str,
    scope_id: str,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitResponse:
    """Get a specific rate limit configuration by scope.

    Retrieves a single rate limit configuration for the specified scope type and ID.

    Args:
        scope_type: Scope type ("model" or "group_model")
        scope_id: Scope identifier (model_id or "group_id:model_id")
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        Rate limit configuration

    Raises:
        HTTP 400: Invalid scope type
        HTTP 401: Unauthorized if not admin
        HTTP 404: Rate limit not found
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} retrieving rate limit: {scope_type}/{scope_id}")

    # Delegate to service (service will handle validation and errors)
    rate_limit = service.get_rate_limit(scope_type, scope_id)

    if not rate_limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rate limit not found for {scope_type}/{scope_id}"
        )

    # Map domain to API response
    return RateLimitApiMapper.domain_to_response(rate_limit)


@router.patch("/{scope_type}/{scope_id}", response_model=RateLimitResponse)
async def update_rate_limit(
    scope_type: str,
    scope_id: str,
    request_data: UpdateRateLimitRequest,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitResponse:
    """Update an existing rate limit configuration (partial update).

    Allows partial updates of rate limit configurations. You can update:
    - Only the enabled status
    - Only the time windows
    - Both enabled and time windows

    Args:
        scope_type: Scope type ("model" or "group_model")
        scope_id: Scope identifier (model_id or "group_id:model_id")
        request_data: Partial update data (enabled and/or windows)
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        Updated rate limit configuration

    Raises:
        HTTP 400: Invalid request data or scope type
        HTTP 401: Unauthorized if not admin
        HTTP 404: Rate limit not found
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} updating rate limit: {scope_type}/{scope_id}")

    # Validate at least one field is provided (Pydantic can't do this)
    if request_data.enabled is None and request_data.windows is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (enabled or windows) must be provided for update"
        )

    # Get existing rate limit
    existing = service.get_rate_limit(scope_type, scope_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rate limit not found for {scope_type}/{scope_id}"
        )

    # Prepare updated windows (use existing if not provided)
    if request_data.windows is not None:
        windows = [
            RateLimitApiMapper.window_request_to_domain(w)
            for w in request_data.windows
        ]
    else:
        windows = existing.windows

    # Prepare updated enabled status (use existing if not provided)
    enabled = request_data.enabled if request_data.enabled is not None else existing.enabled

    # Create updated domain model (reuse existing scope_type to preserve type)
    updated_limit = RateLimit(
        id=existing.id,
        scope_type=existing.scope_type,  # Use existing to preserve Literal type
        scope_id=scope_id,
        enabled=enabled,
        windows=windows
    )

    # Delegate to service
    result = service.create_or_update_rate_limit(updated_limit)

    # Map domain to API response
    return RateLimitApiMapper.domain_to_response(result)


@router.delete("/{scope_type}/{scope_id}", response_model=RateLimitDeleteResponse)
async def delete_rate_limit(
    scope_type: str,
    scope_id: str,
    service: RateLimitService = Depends(get_rate_limit_service),
    admin_user: AuthenticatedUser = Depends(require_admin_role)
) -> RateLimitDeleteResponse:
    """Delete a rate limit configuration.

    Removes a rate limit from the database. Once deleted, the system
    will fall back to less specific limits (e.g., global if model limit deleted).

    Args:
        scope_type: Scope type ("model" or "group_model")
        scope_id: Scope identifier (model_id or "group_id:model_id")
        service: Rate limit service
        admin_user: Authenticated admin user

    Returns:
        Deletion confirmation

    Raises:
        HTTP 400: Invalid scope type
        HTTP 401: Unauthorized if not admin
        HTTP 404: Rate limit not found
        HTTP 500: Internal server error
    """
    logger.info(f"Admin {admin_user.username} deleting rate limit: {scope_type}/{scope_id}")

    # Delegate to service
    deleted = service.delete_rate_limit(scope_type, scope_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rate limit not found for {scope_type}/{scope_id}"
        )

    return RateLimitDeleteResponse(
        success=True,
        message=f"Rate limit deleted successfully",
        scope_type=scope_type,
        scope_id=scope_id
    )
