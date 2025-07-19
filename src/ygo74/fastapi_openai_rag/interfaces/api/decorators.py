"""Decorators for API endpoints."""
from functools import wraps
from typing import Callable, Any
import logging

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
