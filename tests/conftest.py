"""Global test configuration and fixtures."""
import pytest
import logging
import sys
import os
from pathlib import Path
from typing import List, Optional, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound
from ygo74.fastapi_openai_rag.main import app
from ygo74.fastapi_openai_rag.infrastructure.db.models.base import Base
from ygo74.fastapi_openai_rag.infrastructure.db.session import get_db
from unittest.mock import MagicMock

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_test_logging(request):
    """Configure logging for tests based on pytest arguments."""
    # Check if --log-cli-level=DEBUG was passed by looking at pytest config
    log_cli_level = None
    if hasattr(request.config, 'getoption'):
        try:
            log_cli_level = request.config.getoption('--log-cli-level', default=None)
        except ValueError:
            # Option might not exist in some pytest versions
            pass

    # Alternative check: look at environment or pytest arguments
    is_debug_mode = (
        log_cli_level == 'DEBUG' or
        log_cli_level == 'debug' or
        '--log-cli-level=DEBUG' in sys.argv or
        '--log-cli-level=debug' in sys.argv
    )

    if is_debug_mode:
        print("Test logging configured - application modules set to DEBUG")

        # Set debug level for our application modules only when in debug mode
        app_logger = logging.getLogger('src.ygo74.fastapi_openai_rag')
        app_logger.setLevel(logging.DEBUG)

        # Specifically enable debug for key modules
        model_service_logger = logging.getLogger('src.ygo74.fastapi_openai_rag.application.services.model_service')
        model_service_logger.setLevel(logging.DEBUG)

        llm_factory_logger = logging.getLogger('src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory')
        llm_factory_logger.setLevel(logging.DEBUG)

        http_factory_logger = logging.getLogger('src.ygo74.fastapi_openai_rag.infrastructure.llm.http_client_factory')
        http_factory_logger.setLevel(logging.DEBUG)

    # Always reduce noise from external libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return is_debug_mode


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(request):
    """Setup test environment - runs once per test session."""
    print("Setting up test environment...")

    # Configure logging based on current pytest settings
    is_debug = configure_test_logging(request)

    # Additional test environment setup can go here
    yield

    print("Tearing down test environment...")


@pytest.fixture(autouse=True)
def enable_debug_logging(caplog, request):
    """Enable debug logging for application modules when needed."""
    # Check if we're in debug mode using the same logic as configure_test_logging
    log_cli_level = None
    if hasattr(request.config, 'getoption'):
        try:
            log_cli_level = request.config.getoption('--log-cli-level', default=None)
        except ValueError:
            pass

    is_debug_mode = (
        log_cli_level == 'DEBUG' or
        log_cli_level == 'debug' or
        '--log-cli-level=DEBUG' in sys.argv or
        '--log-cli-level=debug' in sys.argv
    )

    # Set the log level to DEBUG for the test capture only if we're in debug mode
    if is_debug_mode:
        caplog.set_level(logging.DEBUG)

        # Ensure our application loggers are in DEBUG mode
        app_logger = logging.getLogger('src.ygo74.fastapi_openai_rag')
        app_logger.setLevel(logging.DEBUG)

    yield

    # Optional: Print captured logs only when running with debug enabled
    if is_debug_mode and caplog.records:
        print(f"\n--- Captured logs for current test ---")
        for record in caplog.records:
            if record.name.startswith('src.ygo74.fastapi_openai_rag'):
                print(f"{record.levelname}: {record.name}: {record.message}")
        print("--- End of captured logs ---\n")


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
        """Initialize mock session."""
        self.query_result: List[Any] = []
        self.added_items: List[Any] = []
        self.merged_items: List[Any] = []
        self.deleted: bool = False
        self.execute_result: Any = MagicMock()
        self.committed: bool = False
        self.get_result: Optional[Any] = None

        # Create a mock query object
        self.query = MagicMock()

    def set_query_result(self, result: List[Any]) -> None:
        """Set result for query method.

        Args:
            result: Result to return from query
        """
        # Ensure we have a proper MagicMock for query
        self.query = MagicMock()
        self.query.all.return_value = result
        self.query.first.return_value = result[0] if result else None
        self.query.filter.return_value = self.query
        self.query.filter_by.return_value = self.query
        self.query.options.return_value = self.query
        self.query.join.return_value = self.query
        self.query.where.return_value = self.query

        # Add method to handle get with ID
        self.query.get.side_effect = lambda id: next((item for item in result if item.id == id), None)

    def set_execute_result(self, result: MagicMock) -> None:
        """Set result for execute method.

        Args:
            result: Mock result to return from execute
        """
        self.execute_result = result

    def add(self, item):
        """Mock add method.

        Args:
            item: Item to add
        """
        self.added_items.append(item)
        # Set ID if not already set
        if not hasattr(item, 'id') or item.id is None:
            item.id = len(self.added_items)

    def merge(self, item):
        """Mock merge method.

        Args:
            item: Item to merge
        """
        self.merged_items.append(item)
        return item

    def delete(self, item):
        """Mock delete method.

        Args:
            item: Item to delete
        """
        self.deleted = True

    def commit(self):
        """Mock commit method."""
        self.committed = True

    def rollback(self):
        """Mock rollback method."""
        pass

    def flush(self):
        """Mock flush method."""
        pass

    def refresh(self, item):
        """Mock refresh method.

        Args:
            item: Item to refresh
        """
        pass

    def execute(self, stmt):
        """Mock execute method.

        Args:
            stmt: Statement to execute

        Returns:
            Mock result
        """
        return self.execute_result

    def get(self, model_class, entity_id):
        """Mock get method.

        Args:
            model_class: Model class to get
            entity_id: Entity ID to get

        Returns:
            Entity if found, None otherwise
        """
        return self.get_result


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