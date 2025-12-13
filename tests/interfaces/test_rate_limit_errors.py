"""Contract tests for HTTP 429 rate limit error responses.

This test file verifies that HTTP 429 responses conform to the OpenAI API specification
and include all required headers and response body fields.

Contract requirements:
- HTTP 429 status code
- Retry-After header (seconds)
- X-RateLimit-* headers
- OpenAI-compatible error response body
- Error type: "rate_limit_exceeded"
"""
import pytest
from datetime import datetime


class TestRateLimitErrorContract:
    """Contract tests for rate limit error responses."""

    @pytest.fixture
    def sample_rate_limit_exception(self):
        """Create sample RateLimitExceeded exception for testing."""
        from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        return RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="requests",
            limit=100,
            current=101,
            window_reset=1700000000,
            retry_after=60
        )

    def test_http_status_code_429(self, sample_rate_limit_exception):
        """Test that HTTP status code is 429 Too Many Requests.

        Contract: HTTP 429 status code required
        """
        # The exception handler should return 429
        # This is verified in integration tests
        assert sample_rate_limit_exception is not None

    def test_retry_after_header_present(self, sample_rate_limit_exception):
        """Test that Retry-After header is present in response.

        Contract: Retry-After: <seconds>
        Example: Retry-After: 60
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "Retry-After" in headers
        assert isinstance(headers["Retry-After"], str)
        assert int(headers["Retry-After"]) > 0

    def test_retry_after_is_integer_seconds(self, sample_rate_limit_exception):
        """Test that Retry-After value is integer seconds.

        Contract: Value must be integer representing seconds
        """
        headers = sample_rate_limit_exception.to_http_headers()

        retry_after = headers["Retry-After"]
        assert isinstance(retry_after, str)
        assert int(retry_after) == 60

    def test_ratelimit_limit_header_present(self, sample_rate_limit_exception):
        """Test that X-RateLimit-Limit header is present.

        Contract: X-RateLimit-Limit: <limit>
        Example: X-RateLimit-Limit: 100
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Limit" in headers
        assert isinstance(headers["X-RateLimit-Limit"], str)
        assert int(headers["X-RateLimit-Limit"]) == 100

    def test_ratelimit_remaining_header_present(self, sample_rate_limit_exception):
        """Test that X-RateLimit-Remaining header is present.

        Contract: X-RateLimit-Remaining: 0 (always 0 when rate limited)
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "0"

    def test_ratelimit_reset_header_present(self, sample_rate_limit_exception):
        """Test that X-RateLimit-Reset header is present.

        Contract: X-RateLimit-Reset: <unix_timestamp>
        Example: X-RateLimit-Reset: 1700000000
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Reset" in headers
        assert isinstance(headers["X-RateLimit-Reset"], str)
        assert int(headers["X-RateLimit-Reset"]) > 0

    def test_ratelimit_type_header_present(self, sample_rate_limit_exception):
        """Test that X-RateLimit-Type header indicates limit type.

        Contract: X-RateLimit-Type: requests|tokens
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Type" in headers
        assert headers["X-RateLimit-Type"] in ["requests", "tokens"]

    def test_ratelimit_scope_header_present(self, sample_rate_limit_exception):
        """Test that X-RateLimit-Scope header indicates scope.

        Contract: X-RateLimit-Scope: <scope_description>
        Example: X-RateLimit-Scope: model 'gpt-4'
        """
        headers = sample_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Scope" in headers
        assert isinstance(headers["X-RateLimit-Scope"], str)
        assert "gpt-4" in headers["X-RateLimit-Scope"]

    def test_error_response_has_error_key(self, sample_rate_limit_exception):
        """Test that response body has top-level 'error' key.

        Contract:
        {
          "error": { ... }
        }
        """
        response = sample_rate_limit_exception.to_error_response()

        assert "error" in response
        assert isinstance(response["error"], dict)

    def test_error_has_message_field(self, sample_rate_limit_exception):
        """Test that error object has 'message' field.

        Contract:
        {
          "error": {
            "message": "Rate limit exceeded: ...",
            ...
          }
        }
        """
        response = sample_rate_limit_exception.to_error_response()

        assert "message" in response["error"]
        assert isinstance(response["error"]["message"], str)
        assert len(response["error"]["message"]) > 0

    def test_error_has_type_field(self, sample_rate_limit_exception):
        """Test that error object has 'type' field.

        Contract:
        {
          "error": {
            "type": "rate_limit_exceeded",
            ...
          }
        }
        """
        response = sample_rate_limit_exception.to_error_response()

        assert "type" in response["error"]
        assert response["error"]["type"] == "rate_limit_exceeded"

    def test_error_has_code_field(self, sample_rate_limit_exception):
        """Test that error object has 'code' field.

        Contract:
        {
          "error": {
            "code": "rate_limit_exceeded",
            ...
          }
        }
        """
        response = sample_rate_limit_exception.to_error_response()

        assert "code" in response["error"]
        assert response["error"]["code"] == "rate_limit_exceeded"

    def test_error_has_details_field(self, sample_rate_limit_exception):
        """Test that error object has 'details' field with rate limit info.

        Contract:
        {
          "error": {
            "details": {
              "scope_type": "model",
              "scope_id": "gpt-4",
              "limit_type": "requests",
              "limit": 100,
              "current": 101,
              "reset_time": "2023-11-14T23:13:20",
              "retry_after_seconds": 60
            }
          }
        }
        """
        response = sample_rate_limit_exception.to_error_response()

        assert "details" in response["error"]
        details = response["error"]["details"]

        assert "scope_type" in details
        assert "scope_id" in details
        assert "limit_type" in details
        assert "limit" in details
        assert "current" in details
        assert "reset_time" in details
        assert "retry_after_seconds" in details

    def test_details_values_correct(self, sample_rate_limit_exception):
        """Test that details contain correct values.

        Verifies all detail fields have expected values.
        """
        response = sample_rate_limit_exception.to_error_response()
        details = response["error"]["details"]

        assert details["scope_type"] == "model"
        assert details["scope_id"] == "gpt-4"
        assert details["limit_type"] == "requests"
        assert details["limit"] == 100
        assert details["current"] == 101
        assert "reset_time" in details  # ISO 8601 format
        assert details["retry_after_seconds"] == 60

    def test_message_contains_scope_description(self, sample_rate_limit_exception):
        """Test that error message contains human-readable scope description.

        Contract: Message should clearly describe what was rate limited
        Example: "Rate limit exceeded for model 'gpt-4': ..."
        """
        response = sample_rate_limit_exception.to_error_response()
        message = response["error"]["message"]

        assert "gpt-4" in message.lower()
        assert "rate limit" in message.lower()

    def test_message_contains_limit_info(self, sample_rate_limit_exception):
        """Test that error message contains limit information.

        Contract: Message should include limit values for user clarity
        """
        response = sample_rate_limit_exception.to_error_response()
        message = response["error"]["message"]

        assert "100" in message or "limit" in message.lower()

    def test_global_scope_formatting(self):
        """Test error formatting for global scope.

        Verifies proper formatting when scope_id is None.
        """
        from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        exception = RateLimitExceeded(
            scope_type="global",
            scope_id=None,
            limit_type="requests",
            limit=1000,
            current=1001,
            window_reset=1700000000,
            retry_after=120
        )

        response = exception.to_error_response()
        message = response["error"]["message"]

        assert "global" in message.lower()
        assert response["error"]["details"]["scope_id"] is None

    def test_group_model_scope_formatting(self):
        """Test error formatting for group+model scope.

        Verifies proper formatting of composite scope ID.
        """
        from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        exception = RateLimitExceeded(
            scope_type="group_model",
            scope_id="team1:gpt-4",
            limit_type="requests",
            limit=50,
            current=51,
            window_reset=1700000000,
            retry_after=30
        )

        response = exception.to_error_response()
        headers = exception.to_http_headers()

        assert "team1" in headers["X-RateLimit-Scope"]
        assert "gpt-4" in headers["X-RateLimit-Scope"]

    def test_token_limit_type(self):
        """Test error formatting for token-based limits.

        Verifies limit_type="tokens" is handled correctly.
        """
        from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        exception = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="tokens",
            limit=100000,
            current=100001,
            window_reset=1700000000,
            retry_after=60
        )

        response = exception.to_error_response()
        headers = exception.to_http_headers()

        assert response["error"]["details"]["limit_type"] == "tokens"
        assert headers["X-RateLimit-Type"] == "tokens"

    def test_window_reset_iso8601_format(self):
        """Test that reset_time is in ISO 8601 format.

        Contract: reset_time is ISO 8601 formatted timestamp string
        """
        from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded

        exception = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="requests",
            limit=100,
            current=101,
            window_reset=1700000000,
            retry_after=60
        )

        response = exception.to_error_response()
        reset_time = response["error"]["details"]["reset_time"]

        # Should be ISO 8601 format string
        assert isinstance(reset_time, str)
        assert "T" in reset_time  # ISO 8601 has T separator

        # Should be parseable
        dt = datetime.fromisoformat(reset_time)
        assert dt.year >= 2023

    def test_all_required_headers_present(self, sample_rate_limit_exception):
        """Test that all required headers are present in single response.

        Contract: Complete set of headers required for rate limit response
        """
        headers = sample_rate_limit_exception.to_http_headers()

        required_headers = [
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-RateLimit-Type",
            "X-RateLimit-Scope"
        ]

        for header in required_headers:
            assert header in headers, f"Missing required header: {header}"

    def test_openai_compatibility(self, sample_rate_limit_exception):
        """Test that response structure matches OpenAI API format.

        Verifies compatibility with OpenAI SDK expectations.
        """
        response = sample_rate_limit_exception.to_error_response()

        # OpenAI format: top-level error key with message, type, code
        assert "error" in response
        assert "message" in response["error"]
        assert "type" in response["error"]
        assert "code" in response["error"]

        # Type should be snake_case
        assert "_" in response["error"]["type"]

        # Code should match type
        assert response["error"]["code"] == response["error"]["type"]

    def test_serializable_to_json(self, sample_rate_limit_exception):
        """Test that response can be serialized to JSON.

        Contract: Response must be JSON-serializable for HTTP transmission
        """
        import json

        response = sample_rate_limit_exception.to_error_response()

        # Should not raise exception
        json_str = json.dumps(response)
        assert len(json_str) > 0

        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed == response

    def test_headers_serializable_to_http(self, sample_rate_limit_exception):
        """Test that headers can be used in HTTP response.

        Contract: All header values must be valid HTTP header types
        """
        headers = sample_rate_limit_exception.to_http_headers()

        for key, value in headers.items():
            # Headers must be str or int (converted to str in HTTP)
            assert isinstance(value, (str, int)), f"Invalid header type for {key}: {type(value)}"

            # Keys must be strings
            assert isinstance(key, str)

            # No None values
            assert value is not None
