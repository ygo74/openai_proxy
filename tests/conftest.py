from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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