"""Database initialization module."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text
from ..db.models.base import Base

logger = logging.getLogger(__name__)

def init_db(engine: Engine) -> None:
    """Initialize database tables and create initial data if needed.

    Args:
        engine (Engine): SQLAlchemy engine instance
    """
    logger.info("Initializing database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

def create_initial_data(session: Session) -> None:
    """Create initial data in database if needed.

    Args:
        session (Session): Database session
    """
    try:
        # Check if database is empty
        result = session.execute(text("SELECT 1 FROM models LIMIT 1"))
        if not result.first():
            logger.info("Database is empty, creating initial data...")
            # Add initial data here if needed
            pass

    except Exception as e:
        logger.error(f"Error creating initial data: {str(e)}")
        raise