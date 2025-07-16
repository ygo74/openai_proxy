from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound
from src.main import app
from src.infrastructure.db.models.base import Base
from src.infrastructure.database import get_db
import pytest

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
def session():
    """Mock SQLAlchemy session for testing.

    This fixture provides a mock session that can be used by repository tests
    to simulate database operations without actually connecting to a database.

    Returns:
        MockSession: A mock session object that simulates SQLAlchemy session behavior
    """
    class MockSession:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.added_items = []
            self._query_results = []
            self._deleted = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def add(self, item):
            self.added_items.append(item)

        def refresh(self, item):
            pass

        def query(self, *args):
            return self

        def filter(self, *args):
            return self

        def first(self):
            return self._query_results[0] if self._query_results else None

        def all(self):
            return self._query_results

        def update(self, values):
            if self._query_results:
                for key, value in values.items():
                    setattr(self._query_results[0], key.key, value)
                return 1
            return 0

        def delete(self):
            if self._deleted:
                return 1
            return 0

        def one(self):
            if self._query_results:
                return self._query_results[0]
            raise NoResultFound()

        def set_query_result(self, results):
            self._query_results = results

        def set_deleted(self, deleted):
            self._deleted = deleted

    return MockSession()