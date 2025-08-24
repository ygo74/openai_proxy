"""SQLAlchemy session management."""
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator, Optional
import logging
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages SQLAlchemy database sessions."""

    _instance: Optional['SessionManager'] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    def __init__(self, database_url: str, echo: bool = False):
        """Initialize session manager with database URL.

        Args:
            database_url (str): SQLAlchemy database URL
            echo (bool): Whether to echo SQL statements
        """
        if not database_url:
            raise ValueError("Database URL is required")

        self._engine = create_engine(database_url, echo=echo)
        SQLAlchemyInstrumentor().instrument(engine=self._engine)
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )
        logger.info("Session manager initialized")

    @classmethod
    def initialize(cls, database_url: str, echo: bool = False) -> 'SessionManager':
        """Initialize the singleton instance.

        Args:
            database_url (str): SQLAlchemy database URL
            echo (bool): Whether to echo SQL statements

        Returns:
            SessionManager: Singleton instance
        """
        if not cls._instance:
            cls._instance = cls(database_url, echo=echo)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'SessionManager':
        """Get the singleton instance.

        Returns:
            SessionManager: Singleton instance

        Raises:
            RuntimeError: If manager not initialized
        """
        if not cls._instance:
            raise RuntimeError("Session manager not initialized")
        return cls._instance

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Create a context-managed database session.

        Yields:
            Session: Database session

        Raises:
            Exception: If session operations fail
        """
        if not self._session_factory:
            raise RuntimeError("Session factory not initialized")

        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

# FastAPI dependency for database sessions
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides database sessions.

    Yields:
        Session: Database session
    """
    session_manager = SessionManager.get_instance()
    with session_manager.session() as session:
        yield session