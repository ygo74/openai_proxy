"""Main FastAPI application module."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .interfaces.api.router import api_router
from .interfaces.api.exception_handlers import ExceptionHandlers
from .domain.exceptions.entity_not_found_exception import EntityNotFoundError
from .domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from .domain.exceptions.validation_error import ValidationError
from .application.services.config_service import config_service
from .config.logging_config import setup_logging

# Setup logging before anything else
setup_logging()

# Get logger after logging is configured
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="LLM Proxy API",
    description="A FastAPI proxy for various LLM providers with authentication and rate limiting",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)

# Register global exception handlers
app.add_exception_handler(EntityNotFoundError, ExceptionHandlers.entity_not_found_handler)
app.add_exception_handler(EntityAlreadyExistsError, ExceptionHandlers.entity_already_exists_handler)
app.add_exception_handler(ValidationError, ExceptionHandlers.validation_error_handler)
app.add_exception_handler(Exception, ExceptionHandlers.generic_exception_handler)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Load configuration at startup
        config_service.reload_config()
        logger.info("Application configuration loaded successfully")

        # Initialize database
        config_service.init_database()
        logger.info("Database initialized successfully!")

        # Other startup tasks...

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint called")
    return {"status": "healthy"}
