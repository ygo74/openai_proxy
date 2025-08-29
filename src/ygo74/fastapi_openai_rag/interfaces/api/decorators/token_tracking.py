"""Decorator for tracking token usage in LLM requests."""
import logging
import uuid
import time
from functools import wraps
from typing import Callable, Any, Dict, Optional, Union, TypeVar, List, cast
from fastapi import Request

from ....domain.models.chat_completion import ChatCompletionResponse, ChatCompletionRequest
from ....domain.models.completion import CompletionResponse, CompletionRequest
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.llm import TokenUsage
from ....application.services.token_usage_service import TokenUsageService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....infrastructure.observability.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)

# Define type variables for better type checking
T = TypeVar('T', bound=Callable[..., Any])
ResponseType = Union[ChatCompletionResponse, CompletionResponse, Any]

def track_token_usage():
    """Decorator to track token usage for a user.

    Tracks and persists the number of tokens used in both prompt and completion.
    Works with both ChatCompletionResponse and CompletionResponse return types.
    Also sends metrics to OpenTelemetry if configured.
    Tracks number of in-progress requests per model.

    Returns:
        Callable: Decorated function that tracks token usage
    """
    def decorator(func: T) -> T:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function for token usage tracking.

            Returns:
                Any: Result of the endpoint function
            """
            # Extract request and user from arguments
            request: Optional[Request] = None
            user: Optional[AuthenticatedUser] = None
            model_name: str = "unknown"
            response: Any = None
            start_time = time.time()
            success = True

            try:
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
                    user_obj = kwargs.get("user")
                    if isinstance(user_obj, AuthenticatedUser):
                        user = user_obj
                elif request:
                    # Try to get from request scope if not in kwargs
                    user_obj = request.scope.get("authenticated_user")
                    if isinstance(user_obj, AuthenticatedUser):
                        user = user_obj

                if not user:
                    # If no user found or not authenticated, proceed without tracking
                    logger.warning("No authenticated user found for token tracking")
                    return await func(*args, **kwargs)

                # Generate unique request ID
                request_id = str(uuid.uuid4())

                # Get metrics service
                metrics_service = get_metrics_service()

                # Try to determine model name before making the request
                # Specifically look for chat_completion_request or completion_request parameters
                if "chat_completion_request" in kwargs and isinstance(kwargs["chat_completion_request"], ChatCompletionRequest):
                    model_name = kwargs["chat_completion_request"].model
                    logger.debug(f"Found model in chat_completion_request: {model_name}")
                elif "completion_request" in kwargs and isinstance(kwargs["completion_request"], CompletionRequest):
                    model_name = kwargs["completion_request"].model
                    logger.debug(f"Found model in completion_request: {model_name}")
                else:
                    # Check other kwargs
                    if "model" in kwargs:
                        model_name = str(kwargs.get("model", "unknown"))
                    else:
                        # Try to find model in args
                        for arg in args:
                            if isinstance(arg, (ChatCompletionRequest, CompletionRequest)) and hasattr(arg, "model"):
                                model_name = str(getattr(arg, "model", "unknown"))
                                logger.debug(f"Found model in args: {model_name}")
                                break
                            elif hasattr(arg, "model"):
                                model_name = str(getattr(arg, "model", "unknown"))
                                logger.debug(f"Found model attribute in args: {model_name}")
                                break

                # Use context manager if metrics service is available to track in-progress requests
                if metrics_service:
                    # Track the request in progress
                    with metrics_service.track_llm_request_in_progress(model_name):
                        response = await func(*args, **kwargs)
                else:
                    # Call the original function without tracking
                    response = await func(*args, **kwargs)

                # Calculate request duration
                duration = time.time() - start_time

                # If response doesn't have token usage, return original response
                if not hasattr(response, "usage"):
                    logger.debug("Response has no token usage information")
                    return response

                # Extract token usage info
                usage = getattr(response, "usage", None)
                if not usage:
                    logger.debug("No usage data in response")
                    return response

                # Update model name from response if available
                if hasattr(response, "model"):
                    model_name = str(getattr(response, "model", "unknown"))

                # Get endpoint path
                endpoint = request.url.path if request else "unknown"

                # Get token counts safely
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens)

                # Setup token usage service
                uow = SQLUnitOfWork()
                token_service = TokenUsageService(uow)

                # Record usage in database
                user_id = getattr(user, "username", "anonymous")
                if user_id is None:
                    user_id = "anonymous"

                token_service.record_token_usage(
                    user_id=user_id,
                    model=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    endpoint=endpoint,
                    request_id=request_id
                )

                # Record metrics in OpenTelemetry if metrics service is available
                if metrics_service:
                    metrics_service.record_llm_request(
                        model=model_name,
                        tokens_in=prompt_tokens,
                        tokens_out=completion_tokens,
                        duration=duration,
                        success=success
                    )

                logger.info(f"Recorded token usage for user {user_id}: {total_tokens} tokens")

            except Exception as e:
                # Log error but don't fail the request
                logger.error(f"Error recording token usage: {str(e)}", exc_info=True)
                success = False
                duration = time.time() - start_time

                # Try to record failure metric if metrics service is available
                metrics_service = get_metrics_service()
                if metrics_service:
                    try:
                        metrics_service.record_llm_request(
                            model=model_name,
                            tokens_in=0,  # No tokens on error
                            tokens_out=0,  # No tokens on error
                            duration=duration,
                            success=False
                        )
                    except Exception as metrics_error:
                        logger.error(f"Failed to record metrics for failed request: {str(metrics_error)}")

                # Re-raise the exception if it was during the function call
                if response is None:
                    raise

            return response

        # Use cast to satisfy the type checker
        return cast(T, wrapper)
    return decorator