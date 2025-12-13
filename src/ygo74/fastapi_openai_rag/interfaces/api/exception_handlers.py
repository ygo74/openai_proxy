"""Global exception handlers for the API."""
from typing import Any, Dict
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timezone
import time
from zoneinfo import ZoneInfo

from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ...domain.exceptions.validation_error import ValidationError
from ...domain.exceptions.rate_limit_exception import RateLimitExceeded
from ...domain.models.rate_limit import FixedRateLimitViolation

logger = logging.getLogger(__name__)

class ExceptionHandlers:
    """Centralized exception handlers for the API."""

    @staticmethod
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        """Handle EntityNotFoundError exceptions.

        Args:
            request (Request): The FastAPI request object
            exc (EntityNotFoundError): The exception instance

        Returns:
            JSONResponse: HTTP 404 response
        """
        logger.warning(f"Entity not found: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)}
        )

    @staticmethod
    async def entity_already_exists_handler(request: Request, exc: EntityAlreadyExistsError) -> JSONResponse:
        """Handle EntityAlreadyExistsError exceptions.

        Args:
            request (Request): The FastAPI request object
            exc (EntityAlreadyExistsError): The exception instance

        Returns:
            JSONResponse: HTTP 409 response
        """
        logger.warning(f"Entity already exists: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)}
        )

    @staticmethod
    async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
        """Handle PermissionError exceptions.

        Args:
            request (Request): The FastAPI request object
            exc (PermissionError): The exception instance

        Returns:
            JSONResponse: HTTP 403 response
        """
        logger.warning(f"Permission denied: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": f"Permission denied: {str(exc)}"}
        )

    @staticmethod
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Handle ValidationError exceptions.

        Args:
            request (Request): The FastAPI request object
            exc (ValidationError): The exception instance

        Returns:
            JSONResponse: HTTP 400 response
        """
        logger.warning(f"Validation error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)}
        )

    @staticmethod
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle generic exceptions.

        Args:
            request (Request): The FastAPI request object
            exc (Exception): The exception instance

        Returns:
            JSONResponse: HTTP 500 response
        """
        logger.error(f"Unhandled exception on {request.url}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error - see logs for details: {str(exc)}"}
        )

    @staticmethod
    async def rate_limit_violation_handler(request: Request, exc: FixedRateLimitViolation) -> JSONResponse:
        """Handle rate limit violation exceptions."""
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": exc.message,
                    "type": "rate_limit_exceeded",
                    "param": None,
                    "code": "rate_limit_exceeded",
                    "details": {
                        "window": exc.window.value,
                        "limit": exc.limit,
                        "current_usage": exc.current_usage,
                        "reset_time": exc.reset_time.isoformat(),
                        "user_id": exc.user_id,
                        "group_name": exc.group_name,
                        "model_name": exc.model_name
                    }
                }
            },
            headers={
                "Retry-After": str(int((exc.reset_time - datetime.now(timezone.utc)).total_seconds())),
                "X-RateLimit-Limit": str(exc.limit),
                "X-RateLimit-Remaining": str(max(0, exc.limit - exc.current_usage)),
                "X-RateLimit-Reset": str(int(exc.reset_time.timestamp()))
            }
        )

    @staticmethod
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        """Handle rate limit exceeded exceptions (new time-window system).

        Returns HTTP 429 with OpenAI-compatible error response and rate limit headers.

        Args:
            request: The FastAPI request object
            exc: The RateLimitExceeded exception

        Returns:
            JSONResponse: HTTP 429 with proper headers and error body
        """
        logger.warning(
            f"Rate limit exceeded on {request.url.path}: "
            f"scope={exc.scope_type}:{exc.scope_id}, "
            f"type={exc.limit_type}, {exc.current}/{exc.limit}"
        )

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=exc.to_error_response(),
            headers=exc.to_http_headers()
        )
