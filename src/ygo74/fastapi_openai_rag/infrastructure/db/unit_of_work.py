"""SQLAlchemy implementation of Unit of Work pattern."""
from typing import Callable, Union, Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ...domain.unit_of_work import AbstractUnitOfWork
from .session import SessionManager


class SQLUnitOfWork(AbstractUnitOfWork):
    """SQLAlchemy implementation of Unit of Work pattern.

    Attributes:
        session_factory (Callable[[], Session]): Factory function to create sessions
        session (Session): Current database session
    """

    def __init__(self, session_factory: Callable[[], Session] = None):
        """Initialize Unit of Work with session factory.

        Args:
            session_factory (Callable[[], Session], optional): Factory to create database sessions.
                If not provided, will use SessionManager.
        """
        self._session_factory = session_factory
        self._session: Session | None = None
        self._using_session_manager = session_factory is None
        self._manager_ctx = None

    @property
    def session(self) -> Session:
        """Get current database session.

        Returns:
            Session: Current SQLAlchemy session

        Raises:
            RuntimeError: If session is not initialized
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use within context manager.")
        return self._session

    def __enter__(self) -> "SQLUnitOfWork":
        """Enter transaction context and create session.

        Returns:
            SQLUnitOfWork: Self reference for context manager
        """
        if self._using_session_manager:
            # Get SessionManager instance and use its session
            session_manager = SessionManager.get_instance()
            # The session method returns a context manager, not a generator
            self._manager_ctx = session_manager.session()
            # Get the actual session from the context manager
            self._session = self._manager_ctx.__enter__()
        else:
            # Use provided session factory
            self._session = self._session_factory()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit transaction context with automatic cleanup.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            if self._using_session_manager and self._manager_ctx:
                # Let the manager's context manager handle closing
                self._manager_ctx.__exit__(exc_type, exc_val, exc_tb)
                self._manager_ctx = None
            elif self._session:
                self._session.close()

            self._session = None

    def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            SQLAlchemyError: If commit fails
        """
        try:
            if self._session:
                self._session.commit()
        except SQLAlchemyError:
            self.rollback()
            raise

    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self._session:
            self._session.rollback()
