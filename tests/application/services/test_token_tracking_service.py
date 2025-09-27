"""Tests for TokenTrackingService."""
import pytest
from unittest.mock import MagicMock, patch
import time
from datetime import datetime, timezone
import uuid

from src.ygo74.fastapi_openai_rag.application.services.token_tracking_service import TokenTrackingService
from src.ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser
from src.ygo74.fastapi_openai_rag.domain.models.llm import TokenUsage

# Sample responses for testing
CHAT_COMPLETION_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677652288,
    "model": "gpt-4",
    "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "index": 0}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
}

RESPONSE_API_RESPONSE = {
    "id": "resp-123",
    "created_at": 1677652288,
    "model": "gpt-4",
    "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
}

@pytest.fixture
def mock_uow():
    """Mock unit of work for testing."""
    uow = MagicMock()
    uow.__enter__ = MagicMock(return_value=uow)
    uow.__exit__ = MagicMock(return_value=None)
    return uow

@pytest.fixture
def mock_token_service():
    """Mock token service for testing."""
    with patch("src.ygo74.fastapi_openai_rag.application.services.token_usage_service.TokenUsageService") as mock:
        yield mock.return_value

@pytest.fixture
def mock_metrics_service():
    """Mock metrics service for testing."""
    with patch("src.ygo74.fastapi_openai_rag.application.services.token_tracking_service.get_metrics_service") as mock:
        metrics = MagicMock()
        metrics.track_llm_request_in_progress.return_value.__enter__ = MagicMock(return_value=None)
        metrics.track_llm_request_in_progress.return_value.__exit__ = MagicMock(return_value=None)
        mock.return_value = metrics
        yield metrics

@pytest.fixture
def token_tracking_service(mock_uow, mock_token_service, mock_metrics_service):
    """Create token tracking service with mocks for testing."""
    service = TokenTrackingService(mock_uow)
    service._token_service = mock_token_service
    return service

@pytest.fixture
def mock_user():
    """Mock authenticated user for testing."""
    user = MagicMock(spec=AuthenticatedUser)
    user.username = "test_user"
    return user

def test_extract_token_usage_chat_completion(token_tracking_service):
    """Test token usage extraction from chat completion response."""
    usage = token_tracking_service.extract_token_usage(CHAT_COMPLETION_RESPONSE)

    assert usage is not None
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 5
    assert usage["total_tokens"] == 15

def test_extract_token_usage_response_api(token_tracking_service):
    """Test token usage extraction from Response API response."""
    usage = token_tracking_service.extract_token_usage(RESPONSE_API_RESPONSE)

    assert usage is not None
    assert usage["prompt_tokens"] == 12
    assert usage["completion_tokens"] == 8
    assert usage["total_tokens"] == 20

def test_track_completion(token_tracking_service, mock_user, mock_token_service, mock_metrics_service):
    """Test tracking completion with token usage."""
    # Arrange
    start_time = time.time() - 1.0  # 1 second ago
    endpoint = "/v1/completions"

    # Act
    token_tracking_service.track_completion(
        response=CHAT_COMPLETION_RESPONSE,
        user=mock_user,
        endpoint=endpoint,
        start_time=start_time
    )

    # Assert - token service call
    mock_token_service.record_token_usage.assert_called_once()
    call_args = mock_token_service.record_token_usage.call_args[1]
    assert call_args["user_id"] == "test_user"
    assert call_args["model"] == "gpt-4"
    assert call_args["prompt_tokens"] == 10
    assert call_args["completion_tokens"] == 5
    assert call_args["endpoint"] == endpoint

    # Assert - metrics service call
    mock_metrics_service.record_llm_request.assert_called_once()
    metrics_args = mock_metrics_service.record_llm_request.call_args[1]
    assert metrics_args["model"] == "gpt-4"
    assert metrics_args["tokens_in"] == 10
    assert metrics_args["tokens_out"] == 5
    assert metrics_args["success"] is True
    assert isinstance(metrics_args["duration"], float)

def test_track_stream_completion(token_tracking_service, mock_user):
    """Test tracking token usage from stream completion event."""
    # Arrange
    event = MagicMock()
    event.type = "response.completed"
    event.response = RESPONSE_API_RESPONSE

    with patch.object(token_tracking_service, 'track_completion') as mock_track:
        # Act
        result = token_tracking_service.track_stream_completion(
            event=event,
            user=mock_user,
            endpoint="/v1/responses",
            model="gpt-4",
            start_time=time.time()
        )

        # Assert
        assert result is True
        mock_track.assert_called_once()

def test_track_stream_completion_wrong_event_type(token_tracking_service, mock_user):
    """Test that stream completion tracking ignores non-completed events."""
    # Arrange
    event = MagicMock()
    event.type = "response.data"  # Not a completion event

    with patch.object(token_tracking_service, 'track_completion') as mock_track:
        # Act
        result = token_tracking_service.track_stream_completion(
            event=event,
            user=mock_user,
            endpoint="/v1/responses",
            model="gpt-4"
        )

        # Assert
        assert result is False
        mock_track.assert_not_called()

def test_extract_token_usage_no_usage(token_tracking_service):
    """Test token usage extraction when no usage data is available."""
    # Arrange
    response = {"id": "resp-123", "model": "gpt-4"}  # No usage data

    # Act
    usage = token_tracking_service.extract_token_usage(response)

    # Assert
    assert usage is None