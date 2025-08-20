"""Decorators for API endpoints."""
from functools import wraps
from typing import Callable, Any, List, Optional
import logging
from fastapi import HTTPException, Request, status

from .security.autenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

def endpoint_handler(operation_name: str = ""):
    """Decorator to handle common endpoint operations.

    Args:
        operation_name (str): Name of the operation for logging

    Returns:
        Callable: Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            """Wrapper function for endpoint handling.

            Returns:
                Any: Result of the endpoint function
            """
            op_name = operation_name or func.__name__
            logger.debug(f"Starting {op_name}")

            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Completed {op_name} successfully")
                return result
            except Exception as e:
                logger.error(f"Error in {op_name}: {str(e)}")
                # Re-raise the exception to let the global handlers deal with it
                raise

        return wrapper
    return decorator

def require_oauth_role(required_roles: List[str]):
    """Require specific roles for access to an endpoint.

    Args:
        required_roles: List of roles required for access

    Returns:
        Decorator function that checks user's roles
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get authenticated user from request scope
            user: Optional[AuthenticatedUser] = request.scope.get("authenticated_user")

            if not user:
                logger.warning("Access denied: No authenticated user")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Check if user has any of the required roles
            user_groups = user.groups or []
            has_role = any(role in user_groups for role in required_roles)

            if not has_role:
                logger.warning(f"Access denied for user {user.username}: Required roles {required_roles}, has roles {user_groups}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {required_roles}"
                )

            # User has required role, proceed
            logger.info(f"Access granted for user {user.username} with roles {user_groups}")

            # Pass the user to the endpoint function
            kwargs["user"] = user
            return await func(*args, **kwargs)

        return wrapper

    return decorator

def require_apikey_or_bearer():
    """Require API key or Bearer token authentication.

    Returns:
        Decorator function that ensures authentication
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get authenticated user from request scope
            user: Optional[AuthenticatedUser] = request.scope.get("authenticated_user")

            if not user:
                logger.warning("Access denied: No authenticated user")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # User is authenticated, proceed
            logger.debug(f"Access granted for user {user.username}")

            # Pass the user to the endpoint function
            kwargs["user"] = user
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
