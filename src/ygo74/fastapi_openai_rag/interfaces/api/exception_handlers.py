"""Global exception handlers for the API."""
from typing import Any, Dict
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ...domain.exceptions.validation_error import ValidationError

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
            content={"detail": "Internal server error"}
        )
