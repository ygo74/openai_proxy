"""Main FastAPI application module."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .domain.models.configuration import AppConfig
from .infrastructure.db.session import SessionManager
from .infrastructure.db.init_db import init_db, create_initial_data
from .interfaces.api.router import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
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

@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("Initializing application...")

    # Load configuration
    config = AppConfig.load_from_json()
    logger.info(f"Loaded configuration with database type: {config.db_type}")

    # Initialize database connection
    if config.db_type == "sqlite":
        db_url = "sqlite:///./models.db"
    elif config.db_type == "postgres":
        # TODO: Add PostgreSQL support
        raise NotImplementedError("PostgreSQL support is not implemented yet")
    else:
        raise ValueError(f"Unsupported database type: {config.db_type}")

    # Initialize session manager
    session_manager = SessionManager.initialize(db_url)

    # Create database structure and initial data
    init_db(session_manager._engine)
    with session_manager.session() as session:
        create_initial_data(session)

    logger.info("Application initialization completed")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
