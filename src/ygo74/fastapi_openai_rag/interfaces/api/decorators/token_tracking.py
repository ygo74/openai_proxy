"""Decorator for tracking token usage in LLM requests."""
import logging
import uuid
from functools import wraps
from typing import Callable, Any, Dict, Optional, Union
import inspect
from fastapi import Request

from ....domain.models.chat_completion import ChatCompletionResponse
from ....domain.models.completion import CompletionResponse
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.llm import TokenUsage
from ....application.services.token_usage_service import TokenUsageService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork

logger = logging.getLogger(__name__)

def track_token_usage():
    """Decorator to track token usage for a user.

    Tracks and persists the number of tokens used in both prompt and completion.
    Works with both ChatCompletionResponse and CompletionResponse return types.

    Returns:
        Callable: Decorated function that tracks token usage
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            """Wrapper function for token usage tracking.

            Returns:
                Any: Result of the endpoint function
            """
            # Extract request and user from arguments
            request = None
            user = None

            # First check kwargs for request
            if "request" in kwargs and isinstance(kwargs["request"], Request):
                request = kwargs["request"]
            elif "http_request" in kwargs and isinstance(kwargs["http_request"], Request):
                request = kwargs["http_request"]
            else:
                # Fall back to searching in args
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            # Check kwargs for user
            if "user" in kwargs:
                user = kwargs.get("user")
            elif not user and request:
                # Try to get from request scope if not in kwargs
                user = request.scope.get("authenticated_user")

            if not user or not isinstance(user, AuthenticatedUser):
                # If no user found or not authenticated, proceed without tracking
                logger.warning("No authenticated user found for token tracking")
                return await func(*args, **kwargs)

            # Generate unique request ID
            request_id = str(uuid.uuid4())

            # Call the original function
            response: ChatCompletionResponse = await func(*args, **kwargs)

            # If response doesn't have token usage, return original response
            if not hasattr(response, "usage"):
                logger.debug("Response has no token usage information")
                return response

            try:
                # Extract token usage info
                usage: TokenUsage = response.usage
                if not usage:
                    logger.debug("No usage data in response")
                    return response

                model = None
                if hasattr(response, "model"):
                    model = response.model
                else:
                    # Try to extract from request
                    for arg in args:
                        if hasattr(arg, "model"):
                            model = arg.model
                            break

                # If we couldn't determine the model, use a placeholder
                if not model:
                    logger.warning("Could not determine model for token tracking")
                    model = "unknown"

                # Get endpoint path
                endpoint = request.url.path if request else "unknown"

                # Setup token usage service
                uow = SQLUnitOfWork()
                token_service = TokenUsageService(uow)

                # Record usage
                token_service.record_token_usage(
                    user_id=user.username,
                    model=model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    endpoint=endpoint,
                    request_id=request_id
                )

                logger.info(f"Recorded token usage for user {user.username}: {usage.total_tokens} tokens")

            except Exception as e:
                # Log error but don't fail the request
                logger.error(f"Error recording token usage: {str(e)}", exc_info=True)

            return response

        return wrapper
    return decorator
