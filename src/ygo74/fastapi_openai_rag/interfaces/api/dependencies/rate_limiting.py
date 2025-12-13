"""FastAPI dependency for rate limiting enforcement.

This module provides FastAPI dependencies that can be injected into endpoints
to enforce rate limits before processing requests. It integrates with the
RateLimitService and handles scope determination based on request context.
"""
import logging
from typing import Optional
from fastapi import Request, Depends
from ....domain.unit_of_work import UnitOfWork
from ....infrastructure.db.session import SessionManager
from ....application.services.rate_limit_service import RateLimitService
from ....domain.exceptions.rate_limit_exception import RateLimitExceeded

logger = logging.getLogger(__name__)


def get_rate_limit_service() -> RateLimitService:
    """Create RateLimitService instance with dependencies.

    This is a factory function that creates the service with proper
    Unit of Work and counter instances. Called once per request.

    Returns:
        RateLimitService: Configured service instance
    """
    from ....infrastructure.db.unit_of_work import SQLUnitOfWork

    # Create Unit of Work with session
    session_manager = SessionManager()
    session = session_manager.get_session()
    uow = SQLUnitOfWork(session)

    # Create service (counter will be created with default Redis config)
    service = RateLimitService(uow)

    return service


async def check_rate_limit(
    request: Request,
    service: RateLimitService = Depends(get_rate_limit_service)
) -> None:
    """FastAPI dependency to check rate limits before request processing.

    This dependency is injected into endpoints to enforce rate limits.
    It determines the scope (global, model, group/model) from request context
    and checks if the request is allowed.

    Args:
        request: FastAPI request object
        service: RateLimitService instance (injected)

    Raises:
        RateLimitExceeded: If rate limit is exceeded (handled by exception handler)
    """
    # Extract scope information from request
    # For now, we'll use global scope as default
    # In a real implementation, this would extract:
    # - model_id from request body or path parameters
    # - group_id from authenticated user context

    scope_type = "global"
    scope_id = None
    user_id = None

    # Try to extract model from request path or body
    if request.url.path.startswith("/v1/"):
        # For chat completions, try to get model from body
        if hasattr(request, "_json"):
            body = request._json
            if isinstance(body, dict) and "model" in body:
                scope_type = "model"
                scope_id = body["model"]

    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user"):
        user = request.state.user
        if hasattr(user, "username"):
            user_id = user.username
        # Check if we should use group/model scope
        if hasattr(user, "groups") and user.groups and scope_type == "model":
            # Use first group for group/model scope
            group_id = user.groups[0]
            scope_type = "group_model"
            scope_id = f"{group_id}:{scope_id}"

    logger.debug(
        f"Checking rate limit: scope={scope_type}, id={scope_id}, "
        f"user={user_id}, path={request.url.path}"
    )

    # Check request-based rate limit (will raise RateLimitExceeded if exceeded)
    service.check_request_limit(scope_type, scope_id, user_id)

    # Check token-based rate limit (pre-flight check without estimated tokens)
    # This checks if we're already over the token limit from previous requests
    service.check_token_limit(scope_type, scope_id, user_id, estimated_tokens=None)


async def check_rate_limit_for_model(
    model_id: str,
    request: Request,
    service: RateLimitService = Depends(get_rate_limit_service)
) -> None:
    """Check rate limit for a specific model.

    This is a convenience dependency for endpoints where the model
    is provided as a path parameter rather than in the request body.

    Args:
        model_id: Model identifier from path parameter
        request: FastAPI request object
        service: RateLimitService instance (injected)

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    user_id = None
    scope_type = "model"
    scope_id = model_id

    # Try to get user and check for group/model scope
    if hasattr(request.state, "user"):
        user = request.state.user
        if hasattr(user, "username"):
            user_id = user.username
        if hasattr(user, "groups") and user.groups:
            group_id = user.groups[0]
            scope_type = "group_model"
            scope_id = f"{group_id}:{model_id}"

    logger.debug(
        f"Checking model rate limit: scope={scope_type}, id={scope_id}, user={user_id}"
    )

    service.check_request_limit(scope_type, scope_id, user_id)


async def check_global_rate_limit(
    request: Request,
    service: RateLimitService = Depends(get_rate_limit_service)
) -> None:
    """Check global rate limit only.

    This dependency only checks the global rate limit, ignoring
    model-specific and group/model-specific limits.

    Args:
        request: FastAPI request object
        service: RateLimitService instance (injected)

    Raises:
        RateLimitExceeded: If global rate limit is exceeded
    """
    user_id = None
    if hasattr(request.state, "user") and hasattr(request.state.user, "username"):
        user_id = request.state.user.username

    logger.debug(f"Checking global rate limit for user={user_id}")

    service.check_request_limit("global", None, user_id)
