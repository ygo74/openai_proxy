"""Decorator for tracking token usage in LLM requests."""
import logging
import uuid
import time
from functools import wraps
from typing import Callable, Any, Dict, Optional, Union, TypeVar, List, cast, Tuple
from fastapi import Request

from ....domain.models.chat_completion import ChatCompletionResponse, ChatCompletionRequest
from ....domain.models.completion import CompletionResponse, CompletionRequest
from ....domain.models.response import ResponsesCreatePayload
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.llm import TokenUsage
from ....application.services.token_usage_service import TokenUsageService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....infrastructure.observability.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)

# Define type variables for better type checking
T = TypeVar('T', bound=Callable[..., Any])
ResponseType = Union[ChatCompletionResponse, CompletionResponse, Any]

def _extract_request(*args: Any, **kwargs: Any) -> Optional[Request]:
    """Extract FastAPI Request object from function arguments.

    Args:
        *args: Positional arguments to check for Request objects
        **kwargs: Keyword arguments to check for Request objects

    Returns:
        Optional[Request]: The found Request object or None
    """
    # First check kwargs for request
    if "request" in kwargs and isinstance(kwargs["request"], Request):
        return kwargs["request"]
    elif "http_request" in kwargs and isinstance(kwargs["http_request"], Request):
        return kwargs["http_request"]
    else:
        # Fall back to searching in args
        for arg in args:
            if isinstance(arg, Request):
                return arg
    return None


def _extract_user(**kwargs: Any) -> Optional[AuthenticatedUser]:
    """Extract authenticated user from function arguments or request scope.

    Args:
        request: FastAPI Request object that may contain authenticated_user in scope
        **kwargs: Keyword arguments to check for user object

    Returns:
        Optional[AuthenticatedUser]: The authenticated user or None
    """
    # Check kwargs for user
    if "user" in kwargs:
        user_obj = kwargs.get("user")
        if isinstance(user_obj, AuthenticatedUser):
            return user_obj
    return None


def _extract_model_name(*args: Any, **kwargs: Any) -> str:
    """Extract model name from request parameters.

    Handles various request types including ChatCompletionRequest,
    CompletionRequest, and ResponsesCreatePayload.

    Args:
        *args: Positional arguments to check for model name
        **kwargs: Keyword arguments to check for model name

    Returns:
        str: The model name or "unknown" if not found
    """
    # Default model name
    model_name = "unknown"

    # Look for specific request types in kwargs
    if "chat_completion_request" in kwargs and isinstance(kwargs["chat_completion_request"], ChatCompletionRequest):
        model_name = kwargs["chat_completion_request"].model
        logger.debug(f"Found model in chat_completion_request: {model_name}")
    elif "completion_request" in kwargs and isinstance(kwargs["completion_request"], CompletionRequest):
        model_name = kwargs["completion_request"].model
        logger.debug(f"Found model in completion_request: {model_name}")
    elif "payload" in kwargs and isinstance(kwargs["payload"], ResponsesCreatePayload):
        model_name = kwargs["payload"].model
        logger.debug(f"Found model in responses_create_payload: {model_name}")
    elif "payload" in kwargs and hasattr(kwargs["payload"], "model"):
        # Handle ResponsesCreatePayload
        model_name = str(kwargs["payload"].model)
        logger.debug(f"Found model in ResponsesCreatePayload: {model_name}")
    # Check for direct model parameter
    elif "model" in kwargs:
        model_name = str(kwargs.get("model", "unknown"))
        logger.debug(f"Found model in kwargs: {model_name}")
    else:
        # Try to find model in args
        for arg in args:
            if isinstance(arg, (ChatCompletionRequest, CompletionRequest, ResponsesCreatePayload)) and hasattr(arg, "model"):
                model_name = str(getattr(arg, "model", "unknown"))
                logger.debug(f"Found model in args: {model_name}")
                break
            elif hasattr(arg, "model"):
                model_name = str(getattr(arg, "model", "unknown"))
                logger.debug(f"Found model attribute in args: {model_name}")
                break

    return model_name


def _extract_token_usage(response: Any) -> Optional[Dict[str, int]]:
    """Extract token usage information from a response object or dictionary.

    Handles different response types with their specific token usage property names:
    - Response: input_tokens, output_tokens, total_tokens
    - ChatCompletionResponse/CompletionResponse: prompt_tokens, completion_tokens, total_tokens
    - Dictionary variants of both

    Args:
        response: Response object or dictionary from LLM API

    Returns:
        Optional[Dict[str, int]]: Dictionary with prompt_tokens, completion_tokens, and total_tokens,
            or None if usage information cannot be extracted
    """
    # Check the type of response
    response_type = type(response).__name__
    logger.debug(f"Extracting token usage from response type: {response_type}")

    # Case 1: Response object from OpenAI responses API
    if response_type == "Response" or response_type.startswith("Response"):
        # OpenAI responses API uses input_tokens and output_tokens
        if hasattr(response, "usage"):
            usage_obj = getattr(response, "usage")
            if usage_obj:
                input_tokens = getattr(usage_obj, "input_tokens", 0)
                output_tokens = getattr(usage_obj, "output_tokens", 0)
                total_tokens = getattr(usage_obj, "total_tokens", input_tokens + output_tokens)
                return {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens
                }

    # Case 2: ChatCompletionResponse or CompletionResponse
    if response_type in ["ChatCompletionResponse", "CompletionResponse"]:
        if hasattr(response, "usage"):
            usage_obj = getattr(response, "usage")
            if usage_obj:
                prompt_tokens = getattr(usage_obj, "prompt_tokens", 0)
                completion_tokens = getattr(usage_obj, "completion_tokens", 0)
                total_tokens = getattr(usage_obj, "total_tokens", prompt_tokens + completion_tokens)
                return {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                }

    # Case 3: Direct object with usage attribute but non-standard type
    if hasattr(response, "usage"):
        usage_obj = getattr(response, "usage")
        if usage_obj:
            # Try both naming conventions
            # First prompt/completion naming
            if hasattr(usage_obj, "prompt_tokens") and hasattr(usage_obj, "completion_tokens"):
                return {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    "total_tokens": getattr(usage_obj, "total_tokens",
                                          getattr(usage_obj, "prompt_tokens", 0) +
                                          getattr(usage_obj, "completion_tokens", 0))
                }
            # Then input/output naming
            elif hasattr(usage_obj, "input_tokens") and hasattr(usage_obj, "output_tokens"):
                return {
                    "prompt_tokens": getattr(usage_obj, "input_tokens", 0),
                    "completion_tokens": getattr(usage_obj, "output_tokens", 0),
                    "total_tokens": getattr(usage_obj, "total_tokens",
                                          getattr(usage_obj, "input_tokens", 0) +
                                          getattr(usage_obj, "output_tokens", 0))
                }

    # Case 4: Dictionary-based response
    if isinstance(response, dict):
        # Direct usage in dictionary format
        if "usage" in response:
            usage_dict = response["usage"]
            if isinstance(usage_dict, dict):
                # Try both naming conventions for dictionary
                if "prompt_tokens" in usage_dict and "completion_tokens" in usage_dict:
                    return {
                        "prompt_tokens": usage_dict.get("prompt_tokens", 0),
                        "completion_tokens": usage_dict.get("completion_tokens", 0),
                        "total_tokens": usage_dict.get("total_tokens",
                                                     usage_dict.get("prompt_tokens", 0) +
                                                     usage_dict.get("completion_tokens", 0))
                    }
                elif "input_tokens" in usage_dict and "output_tokens" in usage_dict:
                    return {
                        "prompt_tokens": usage_dict.get("input_tokens", 0),
                        "completion_tokens": usage_dict.get("output_tokens", 0),
                        "total_tokens": usage_dict.get("total_tokens",
                                                     usage_dict.get("input_tokens", 0) +
                                                     usage_dict.get("output_tokens", 0))
                    }

        # Direct top-level token properties in Response
        if "input_tokens" in response and "output_tokens" in response:
            return {
                "prompt_tokens": response.get("input_tokens", 0),
                "completion_tokens": response.get("output_tokens", 0),
                "total_tokens": response.get("total_tokens",
                                           response.get("input_tokens", 0) +
                                           response.get("output_tokens", 0))
            }

    logger.debug(f"Could not extract token usage from response type: {response_type}")
    return None
def track_token_usage():
    """Decorator to track token usage for a user.

    Tracks and persists the number of tokens used in both prompt and completion.
    Works with both ChatCompletionResponse, CompletionResponse, and ResponsesCreatePayload.
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
            # Initialize variables
            response: Any = None
            start_time = time.time()
            success = True
            model_name = "unknown"

            try:
                # Extract request, user and model name using helper functions
                request = _extract_request(*args, **kwargs)
                user = _extract_user(**kwargs)
                model_name = _extract_model_name(*args, **kwargs)

                if not user:
                    # If no user found or not authenticated, proceed without tracking
                    logger.warning("No authenticated user found for token tracking")
                    return await func(*args, **kwargs)

                # Generate unique request ID
                request_id = str(uuid.uuid4())

                # Get metrics service
                metrics_service = get_metrics_service()

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

                # Extract token usage using our helper function
                token_usage = _extract_token_usage(response)

                if token_usage is None:
                    logger.debug("No usage data could be extracted from response")
                    return response

                # Update model name from response if available
                if hasattr(response, "model"):
                    model_name = str(getattr(response, "model", "unknown"))
                elif isinstance(response, dict) and "model" in response:
                    model_name = str(response.get("model", "unknown"))

                # Get endpoint path
                endpoint = request.url.path if request else "unknown"

                # Get token counts from extracted usage
                prompt_tokens = token_usage.get("prompt_tokens", 0)
                completion_tokens = token_usage.get("completion_tokens", 0)
                total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)

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