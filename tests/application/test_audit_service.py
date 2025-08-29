import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from typing import Dict, Any

from ygo74.fastapi_openai_rag.application.services.audit_service import AuditService
from ygo74.fastapi_openai_rag.domain.models.audit_log import AuditLog


class MockUnitOfWork:
    """Mock implementation of UnitOfWork for testing."""

    def __init__(self, session=None):
        """Initialize with optional session."""
        self.session = session
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type:
            self.rollback()
        else:
            self.commit()

    def commit(self):
        """Mock commit operation."""
        self.committed = True

    def rollback(self):
        """Mock rollback operation."""
        self.rolled_back = True


@pytest.fixture
def mock_session():
    """Create a mock session for testing."""
    return MagicMock()


@pytest.fixture
def mock_repository():
    """Create a mock repository for testing."""
    repo = MagicMock()
    repo.add = MagicMock()
    repo.get_recent = MagicMock()
    repo.get_by_id = MagicMock()
    return repo


@pytest.fixture
def mock_uow(mock_session):
    """Create a mock unit of work for testing."""
    return MockUnitOfWork(mock_session)


@pytest.fixture
def audit_service(mock_uow, mock_repository):
    """Create an audit service with a mock repository factory."""
    repository_factory = lambda session: mock_repository
    return AuditService(uow=mock_uow, repository_factory=repository_factory)


def test_audit_service_create_audit_log(audit_service, mock_repository):
    """
    Test that the audit service correctly creates an audit log.
    """
    # arrange
    test_timestamp = datetime.now(timezone.utc)
    log_data: Dict[str, Any] = {
        "timestamp": test_timestamp,
        "method": "GET",
        "path": "/v1/chat/completions",
        "user": "test_user",
        "auth_type": "api_key",
        "status_code": 200,
        "duration_ms": 42.5,
        "extra_field": "should_be_in_metadata"
    }

    # Setup mock repository to return a specific AuditLog
    expected_audit_log = AuditLog(
        id=1,
        timestamp=test_timestamp,
        method="GET",
        path="/v1/chat/completions",
        user="test_user",
        auth_type="api_key",
        status_code=200,
        duration_ms=42.5,
        metadata={"extra_field": "should_be_in_metadata"}
    )
    mock_repository.add.return_value = expected_audit_log

    # act
    result = audit_service.create_audit_log(log_data)

    # assert
    assert mock_repository.add.called, "Repository add method should be called"

    # Get the AuditLog that was passed to repository.add
    call_args = mock_repository.add.call_args
    created_log = call_args[0][0]

    assert isinstance(created_log, AuditLog)
    assert created_log.method == "GET"
    assert created_log.path == "/v1/chat/completions"
    assert created_log.user == "test_user"
    assert created_log.auth_type == "api_key"
    assert created_log.status_code == 200
    assert created_log.duration_ms == 42.5
    assert created_log.metadata == {"extra_field": "should_be_in_metadata"}

    # Check that the returned value is the expected AuditLog
    assert result == expected_audit_log
    assert result.id == 1


def test_audit_service_get_recent_logs(audit_service, mock_repository):
    """
    Test that the audit service correctly retrieves recent logs.
    """
    # arrange
    expected_logs = [
        AuditLog(id=2, method="POST", path="/v1/chat/completions", status_code=200, duration_ms=100),
        AuditLog(id=1, method="GET", path="/v1/models", status_code=200, duration_ms=15)
    ]
    mock_repository.get_recent.return_value = expected_logs

    # act
    result = audit_service.get_recent_logs(limit=5)

    # assert
    mock_repository.get_recent.assert_called_once_with(5)
    assert result == expected_logs
    assert len(result) == 2


def test_audit_service_get_log_by_id(audit_service, mock_repository):
    """
    Test that the audit service correctly retrieves a log by ID.
    """
    # arrange
    expected_log = AuditLog(id=42, method="GET", path="/v1/models", status_code=200, duration_ms=15)
    mock_repository.get_by_id.return_value = expected_log

    # act
    result = audit_service.get_log_by_id(42)

    # assert
    mock_repository.get_by_id.assert_called_once_with(42)
    assert result == expected_log


def test_audit_service_create_audit_log_with_error(audit_service, mock_repository):
    """
    Test that the audit service handles errors gracefully when creating a log.
    """
    # arrange
    log_data: Dict[str, Any] = {
        "method": "GET",
        "path": "/test",
        "status_code": 500,
        "duration_ms": 100
    }

    # Make repository throw an exception
    mock_repository.add.side_effect = Exception("Test error")

    # act
    result = audit_service.create_audit_log(log_data)

    # assert
    assert result is None, "Should return None when an error occurs"
    assert mock_repository.add.called, "Repository add method should be called despite error"
