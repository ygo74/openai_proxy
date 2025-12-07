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
from typing import List, Optional
from datetime import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.rate_limit_service import RateLimitService
from ....domain.models.rate_limit import RateLimit, RateLimitWindow
from ....domain.models.autenticated_user import AuthenticatedUser
from ..security.auth import require_admin_role
from ..models.rate_limit_api import (
    CreateRateLimitRequest,
    UpdateRateLimitRequest,
    RateLimitResponse,
    RateLimitListResponse,
    RateLimitDeleteResponse,
    GlobalRateLimitResponse,
    ApplicableLimitsResponse,
    RateLimitWindowResponse,
    RateLimitErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rate-limits", tags=["admin", "rate-limits"])


def time_to_str(t: time) -> str:
    """Convert datetime.time to string format HH:MM:SS.

    Args:
        t: Time object

    Returns:
        String in HH:MM:SS format
    """
    return t.strftime("%H:%M:%S")


def str_to_time(time_str: str) -> time:
    """Convert string HH:MM or HH:MM:SS to datetime.time.

    Args:
        time_str: Time string in HH:MM or HH:MM:SS format

    Returns:
        datetime.time object
    """
    parts = time_str.split(':')
    if len(parts) == 2:
        return time(int(parts[0]), int(parts[1]), 0)
    elif len(parts) == 3:
        return time(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM or HH:MM:SS")


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

    try:
        rate_limits = service.get_all_rate_limits()

        # Convert domain models to API response models
        response_limits = [
            RateLimitResponse(
                id=rl.id,
                scope_type=rl.scope_type,
                scope_id=rl.scope_id,
                enabled=rl.enabled,
                windows=[
                    RateLimitWindowResponse(
                        id=w.id,
                        from_time=time_to_str(w.from_time),
                        to_time=time_to_str(w.to_time),
                        max_requests=w.max_requests,
                        max_tokens=w.max_tokens
                    ) for w in rl.windows
                ]
            ) for rl in rate_limits
        ]

        return RateLimitListResponse(
            rate_limits=response_limits,
            total=len(response_limits)
        )

    except Exception as e:
        logger.error(f"Error listing rate limits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve rate limits: {str(e)}"
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

    try:
        # TODO: Integrate with ConfigService when Phase 9 is implemented
        # For now, return placeholder response
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Global rate limits from config.json will be available in Phase 9"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving global rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve global rate limit: {str(e)}"
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

    try:
        # Query all hierarchy levels
        limits = service.get_applicable_limits(group_id=group_id, model_id=model_id)

        # Helper function to convert RateLimit to RateLimitResponse
        def to_response(rl: Optional[RateLimit]) -> Optional["RateLimitResponse"]:
            if rl is None:
                return None
            return RateLimitResponse(
                id=rl.id,
                scope_type=rl.scope_type,
                scope_id=rl.scope_id,
                enabled=rl.enabled,
                windows=[
                    RateLimitWindowResponse(
                        id=w.id,
                        from_time=time_to_str(w.from_time),
                        to_time=time_to_str(w.to_time),
                        max_requests=w.max_requests,
                        max_tokens=w.max_tokens
                    ) for w in rl.windows
                ]
            )

        # Convert domain models to API responses
        group_model_response = to_response(limits.get('group_model'))
        model_response = to_response(limits.get('model'))
        global_response = to_response(limits.get('global'))

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

    except Exception as e:
        logger.error(
            f"Error querying applicable limits for group={group_id}, model={model_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query applicable limits: {str(e)}"
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

    try:
        # Convert API request to domain model
        windows = [
            RateLimitWindow(
                from_time=str_to_time(w.from_time),
                to_time=str_to_time(w.to_time),
                max_requests=w.max_requests if w.max_requests is not None else -1,
                max_tokens=w.max_tokens if w.max_tokens is not None else -1
            ) for w in request_data.windows
        ]

        rate_limit = RateLimit(
            scope_type="model",
            scope_id=model_id,
            enabled=request_data.enabled,
            windows=windows
        )

        # Create or update via service
        created_limit = service.create_or_update_rate_limit(rate_limit)

        # Convert domain model to API response
        return RateLimitResponse(
            id=created_limit.id,
            scope_type=created_limit.scope_type,
            scope_id=created_limit.scope_id,
            enabled=created_limit.enabled,
            windows=[
                RateLimitWindowResponse(
                    id=w.id,
                    from_time=time_to_str(w.from_time),
                    to_time=time_to_str(w.to_time),
                    max_requests=w.max_requests,
                    max_tokens=w.max_tokens
                ) for w in created_limit.windows
            ]
        )

    except ValueError as e:
        logger.warning(f"Invalid request data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating/updating model rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update rate limit: {str(e)}"
        )


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

    try:
        # Convert API request to domain model
        windows = [
            RateLimitWindow(
                from_time=str_to_time(w.from_time),
                to_time=str_to_time(w.to_time),
                max_requests=w.max_requests if w.max_requests is not None else -1,
                max_tokens=w.max_tokens if w.max_tokens is not None else -1
            ) for w in request_data.windows
        ]

        # Scope ID format: "group_id:model_id"
        scope_id = f"{group_id}:{model_id}"

        rate_limit = RateLimit(
            scope_type="group_model",
            scope_id=scope_id,
            enabled=request_data.enabled,
            windows=windows
        )

        # Create or update via service
        created_limit = service.create_or_update_rate_limit(rate_limit)

        # Convert domain model to API response
        return RateLimitResponse(
            id=created_limit.id,
            scope_type=created_limit.scope_type,
            scope_id=created_limit.scope_id,
            enabled=created_limit.enabled,
            windows=[
                RateLimitWindowResponse(
                    id=w.id,
                    from_time=time_to_str(w.from_time),
                    to_time=time_to_str(w.to_time),
                    max_requests=w.max_requests,
                    max_tokens=w.max_tokens
                ) for w in created_limit.windows
            ]
        )

    except ValueError as e:
        logger.warning(f"Invalid request data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating/updating group+model rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update rate limit: {str(e)}"
        )


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

    # Validate scope type
    if scope_type not in ["model", "group_model", "global"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope_type: {scope_type}. Must be 'model', 'group_model', or 'global'"
        )

    try:
        # Get rate limit from service
        rate_limit = service.get_rate_limit(scope_type, scope_id)

        if not rate_limit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rate limit not found for {scope_type}/{scope_id}"
            )

        # Convert domain model to API response
        return RateLimitResponse(
            id=rate_limit.id,
            scope_type=rate_limit.scope_type,
            scope_id=rate_limit.scope_id,
            enabled=rate_limit.enabled,
            windows=[
                RateLimitWindowResponse(
                    id=w.id,
                    from_time=time_to_str(w.from_time),
                    to_time=time_to_str(w.to_time),
                    max_requests=w.max_requests,
                    max_tokens=w.max_tokens
                ) for w in rate_limit.windows
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve rate limit: {str(e)}"
        )


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

    # Validate scope type
    if scope_type not in ["model", "group_model", "global"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope_type: {scope_type}. Must be 'model', 'group_model', or 'global'"
        )

    # Validate at least one field is provided
    if request_data.enabled is None and request_data.windows is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (enabled or windows) must be provided for update"
        )

    try:
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
                RateLimitWindow(
                    from_time=str_to_time(w.from_time),
                    to_time=str_to_time(w.to_time),
                    max_requests=w.max_requests if w.max_requests is not None else -1,
                    max_tokens=w.max_tokens if w.max_tokens is not None else -1
                ) for w in request_data.windows
            ]
        else:
            # Preserve existing windows
            windows = existing.windows

        # Prepare updated enabled status (use existing if not provided)
        enabled = request_data.enabled if request_data.enabled is not None else existing.enabled

        # Create updated rate limit
        updated_limit = RateLimit(
            id=existing.id,
            scope_type=scope_type,
            scope_id=scope_id,
            enabled=enabled,
            windows=windows
        )

        # Update via service
        result = service.create_or_update_rate_limit(updated_limit)

        # Convert domain model to API response
        return RateLimitResponse(
            id=result.id,
            scope_type=result.scope_type,
            scope_id=result.scope_id,
            enabled=result.enabled,
            windows=[
                RateLimitWindowResponse(
                    id=w.id,
                    from_time=time_to_str(w.from_time),
                    to_time=time_to_str(w.to_time),
                    max_requests=w.max_requests,
                    max_tokens=w.max_tokens
                ) for w in result.windows
            ]
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid request data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update rate limit: {str(e)}"
        )


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

    # Validate scope type
    if scope_type not in ["model", "group_model"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope_type: {scope_type}. Must be 'model' or 'group_model'"
        )

    try:
        # Attempt deletion
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rate limit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete rate limit: {str(e)}"
        )
