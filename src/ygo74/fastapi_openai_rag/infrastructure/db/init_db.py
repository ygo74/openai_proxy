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

    # Log all tables that will be created
    logger.info("Tables to be created:")
    for table_name, table in Base.metadata.tables.items():
        logger.info(f"  - {table_name}")
        logger.debug(f"    Columns: {[col.name for col in table.columns]}")

    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Verify tables were created by inspecting the database
        _verify_tables_created(engine)

    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

def _verify_tables_created(engine: Engine) -> None:
    """Verify that tables were actually created in the database.

    Args:
        engine (Engine): SQLAlchemy engine instance
    """
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        actual_tables = inspector.get_table_names()

        logger.info(f"Tables actually created in database: {actual_tables}")

        # Check if all expected tables were created
        expected_tables = set(Base.metadata.tables.keys())
        created_tables = set(actual_tables)

        missing_tables = expected_tables - created_tables
        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
        else:
            logger.info("All expected tables were created successfully")

    except Exception as e:
        logger.warning(f"Could not verify table creation: {e}")

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