"""Unit of Work pattern for managing database transactions."""
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    """Unit of Work protocol for managing database transactions."""

    def __enter__(self) -> "UnitOfWork":
        """Enter transaction context.

        Returns:
            UnitOfWork: Self reference for context manager
        """
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit transaction context with automatic rollback on exception.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        ...

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback the current transaction."""
        ...


class AbstractUnitOfWork(ABC):
    """Abstract base class for Unit of Work implementations."""

    def __enter__(self) -> "AbstractUnitOfWork":
        """Enter transaction context.

        Returns:
            AbstractUnitOfWork: Self reference for context manager
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit transaction context with automatic rollback on exception.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current transaction."""
        raise NotImplementedError
