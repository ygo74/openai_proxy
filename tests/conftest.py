from typing import List, Optional, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound
from ygo74.fastapi_openai_rag.main import app
from ygo74.fastapi_openai_rag.infrastructure.db.models.base import Base
from ygo74.fastapi_openai_rag.infrastructure.db.session import get_db
import pytest

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MockQuery:
    """Mock SQLAlchemy query for testing."""

    def __init__(self, result: List[Any]) -> None:
        self.result: List[Any] = result

    def filter(self, *args: Any) -> 'MockQuery':
        """Mock filter method."""
        return self

    def first(self) -> Optional[Any]:
        """Mock first method."""
        return self.result[0] if self.result else None

    def get(self, id: int) -> Optional[Any]:
        """Mock get method."""
        return self.result[0] if self.result else None

    def all(self) -> List[Any]:
        """Mock all method."""
        return self.result

    def one(self) -> Any:
        """Mock one method."""
        if self.result:
            return self.result[0]
        raise NoResultFound()


class MockSession:
    """Mock SQLAlchemy session for testing."""

    def __init__(self) -> None:
        self.committed: bool = False
        self.rolled_back: bool = False
        self.added_items: List[Any] = []
        self.commit_error: Optional[Exception] = None
        self.query_result: List[Any] = []
        self.execute_result: Optional[Any] = None
        self.execute_error: Optional[Exception] = None
        self.deleted: bool = False
        self.deleted_items: List[Any] = []

    def add(self, item: Any) -> None:
        """Mock add method."""
        self.added_items.append(item)

    def commit(self) -> None:
        """Mock commit method."""
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def rollback(self) -> None:
        """Mock rollback method."""
        self.rolled_back = True

    def flush(self) -> None:
        """Mock flush method."""
        pass

    def refresh(self, item: Any) -> None:
        """Mock refresh method."""
        pass

    def query(self, model_class: type) -> MockQuery:
        """Mock query method."""
        return MockQuery(self.query_result)

    def execute(self, stmt: Any) -> Any:
        """Mock execute method."""
        if self.execute_error:
            raise self.execute_error
        return self.execute_result

    def delete(self, item: Any) -> None:
        """Mock delete method."""
        self.deleted_items.append(item)
        self.deleted = True

    def update(self, values: dict) -> int:
        """Mock update method."""
        if self.query_result:
            for key, value in values.items():
                setattr(self.query_result[0], key.key, value)
            return 1
        return 0

    def one(self) -> Any:
        """Mock one method."""
        if self.query_result:
            return self.query_result[0]
        raise NoResultFound()

    def merge(self, instance):
        """Mock merge method."""
        if hasattr(self, '_merge_mock'):
            return self._merge_mock(instance)
        return instance

    # Helper methods for test configuration
    def set_commit_error(self, error: Exception) -> None:
        """Set error to raise on commit."""
        self.commit_error = error

    def set_query_result(self, result: List[Any]) -> None:
        """Set result for query operations."""
        self.query_result = result

    def set_execute_result(self, result: Any) -> None:
        """Set result for execute operations."""
        self.execute_result = result

    def set_execute_error(self, error: Exception) -> None:
        """Set error to raise on execute."""
        self.execute_error = error

    def set_deleted(self, deleted: bool) -> None:
        """Set deleted flag."""
        self.deleted = deleted


@pytest.fixture(autouse=True)
def test_db():
    """Create a fresh database for each test.

    This fixture will automatically run before each test, creating a new database
    and dropping it after the test completes.

    Yields:
        None
    """
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    # Override the get_db dependency
    app.dependency_overrides[get_db] = override_get_db

    yield  # Run the test

    # Clean up
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def session() -> MockSession:
    """Mock SQLAlchemy session for testing.

    This fixture provides a mock session that can be used by repository tests
    to simulate database operations without actually connecting to a database.

    Returns:
        MockSession: A mock session object that simulates SQLAlchemy session behavior
    """
    return MockSession()