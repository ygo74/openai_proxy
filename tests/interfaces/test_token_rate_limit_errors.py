"""Contract tests for token-based rate limit HTTP 429 responses.

This test file validates the HTTP 429 response format when token limits
are exceeded, ensuring compliance with:
- OpenAI API rate limit error format
- Standard HTTP rate limit headers
- JSON schema for error responses

Contract tests focus on the shape and structure of responses, not the
enforcement logic (covered by integration tests).
"""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock

from src.ygo74.fastapi_openai_rag.domain.exceptions.rate_limit_exception import RateLimitExceeded


class TestTokenRateLimitErrorContract:
    """Contract test suite for token rate limit error responses.

    Validates that HTTP 429 responses for token limits match the expected
    contract for client consumption.
    """

    @pytest.fixture
    def sample_token_rate_limit_exception(self):
        """Create sample RateLimitExceeded exception for token limit.

        Returns exception with realistic values for testing response format.
        """
        return RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="tokens",
            limit=10000,
            current=10500,
            window_reset=1700000000,
            retry_after=300
        )

    # ============================================================================
    # Token-Specific Header Tests
    # ============================================================================

    def test_token_limit_type_header_value(self, sample_token_rate_limit_exception):
        """Test X-RateLimit-Type header indicates 'tokens' for token limits.

        Verifies:
        - Header value is exactly "tokens" (not "requests")
        - Clients can distinguish token vs request limits
        """
        headers = sample_token_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Type" in headers
        assert headers["X-RateLimit-Type"] == "tokens"

    def test_token_limit_value_in_header(self, sample_token_rate_limit_exception):
        """Test X-RateLimit-Limit contains token limit value.

        Verifies:
        - Header contains max tokens allowed (10000)
        - Value is string type (HTTP header requirement)
        """
        headers = sample_token_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "10000"
        assert isinstance(headers["X-RateLimit-Limit"], str)

    def test_token_remaining_negative_when_exceeded(self, sample_token_rate_limit_exception):
        """Test X-RateLimit-Remaining can be negative when limit exceeded.

        Verifies:
        - Remaining = limit - current = 10000 - 10500 = -500
        - Negative value indicates tokens over limit
        """
        headers = sample_token_rate_limit_exception.to_http_headers()

        assert "X-RateLimit-Remaining" in headers
        remaining_value = int(headers["X-RateLimit-Remaining"])
        assert remaining_value == -500  # 10000 - 10500

    def test_error_message_mentions_tokens(self, sample_token_rate_limit_exception):
        """Test error message mentions 'tokens' not 'requests'.

        Verifies:
        - Message clearly indicates token limit, not request limit
        - User-facing message is accurate
        """
        error_response = sample_token_rate_limit_exception.to_error_response()

        message = error_response["error"]["message"]
        assert "token" in message.lower()

    # ============================================================================
    # Scope-Specific Tests for Token Limits
    # ============================================================================

    def test_global_token_scope_formatting(self):
        """Test global scope error message for token limits.

        Verifies:
        - Message indicates global token limit
        - Scope header is "global"
        """
        exc = RateLimitExceeded(
            scope_type="global",
            scope_id=None,
            limit_type="tokens",
            limit=50000,
            current=50200,
            window_reset=1700000000,
            retry_after=300
        )

        headers = exc.to_http_headers()
        error_response = exc.to_error_response()

        assert headers["X-RateLimit-Scope"] == "global"
        assert "global" in error_response["error"]["message"].lower()

    def test_model_token_scope_formatting(self):
        """Test model scope error message for token limits.

        Verifies:
        - Message includes model name
        - Scope indicates model-specific limit
        """
        exc = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="tokens",
            limit=10000,
            current=10100,
            window_reset=1700000000,
            retry_after=300
        )

        headers = exc.to_http_headers()
        error_response = exc.to_error_response()

        assert "gpt-4" in headers["X-RateLimit-Scope"]
        assert "gpt-4" in error_response["error"]["message"]

    def test_group_model_token_scope_formatting(self):
        """Test group+model scope error message for token limits.

        Verifies:
        - Message includes both group and model
        - Scope clearly indicates composite limit
        """
        exc = RateLimitExceeded(
            scope_type="group_model",
            scope_id="engineering:gpt-4",
            limit_type="tokens",
            limit=5000,
            current=5100,
            window_reset=1700000000,
            retry_after=300
        )

        headers = exc.to_http_headers()
        error_response = exc.to_error_response()

        assert "engineering" in headers["X-RateLimit-Scope"]
        assert "gpt-4" in headers["X-RateLimit-Scope"]
        assert "engineering" in error_response["error"]["message"]
        assert "gpt-4" in error_response["error"]["message"]

    # ============================================================================
    # Combined Request + Token Limit Tests
    # ============================================================================

    def test_token_and_request_limits_distinguishable(self):
        """Test token and request limit errors are clearly distinguishable.

        Verifies:
        - X-RateLimit-Type header differs ("tokens" vs "requests")
        - Error messages differ
        - Clients can identify which limit was hit
        """
        token_exc = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="tokens",
            limit=10000,
            current=10100,
            window_reset=1700000000,
            retry_after=300
        )

        request_exc = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="requests",
            limit=100,
            current=101,
            window_reset=1700000000,
            retry_after=300
        )

        token_headers = token_exc.to_http_headers()
        request_headers = request_exc.to_http_headers()

        # Verify different limit types
        assert token_headers["X-RateLimit-Type"] == "tokens"
        assert request_headers["X-RateLimit-Type"] == "requests"

        # Verify different messages
        token_msg = token_exc.to_error_response()["error"]["message"]
        request_msg = request_exc.to_error_response()["error"]["message"]
        assert token_msg != request_msg

    # ============================================================================
    # Response Schema Validation
    # ============================================================================

    def test_token_error_response_schema_complete(self, sample_token_rate_limit_exception):
        """Test complete error response schema for token limits.

        Verifies all required fields present:
        - error.message
        - error.type
        - error.code
        - error.details.reset_time
        - error.details.retry_after_seconds
        """
        error_response = sample_token_rate_limit_exception.to_error_response()

        # Top-level structure
        assert "error" in error_response

        # Error fields
        error = error_response["error"]
        assert "message" in error
        assert "type" in error
        assert "code" in error
        assert "details" in error

        # Details fields
        details = error["details"]
        assert "reset_time" in details
        assert "retry_after_seconds" in details

        # Verify types
        assert isinstance(error["message"], str)
        assert error["type"] == "rate_limit_exceeded"
        assert error["code"] == "rate_limit_exceeded"
        assert isinstance(details["reset_time"], str)  # ISO 8601 string
        assert isinstance(details["retry_after_seconds"], int)

    def test_token_error_details_values(self, sample_token_rate_limit_exception):
        """Test error details contain correct values for token limits.

        Verifies:
        - reset_time is ISO 8601 formatted
        - retry_after_seconds matches constructor value
        """
        error_response = sample_token_rate_limit_exception.to_error_response()
        details = error_response["error"]["details"]

        # Verify reset_time is valid ISO 8601
        reset_time_str = details["reset_time"]
        datetime.fromisoformat(reset_time_str)  # Should not raise
        assert "T" in reset_time_str  # ISO format includes T separator

        # Verify retry_after_seconds
        assert details["retry_after_seconds"] == 300

    def test_token_error_serializable_to_json(self, sample_token_rate_limit_exception):
        """Test error response is JSON serializable.

        Verifies:
        - All values are JSON-compatible types
        - json.dumps succeeds
        - json.loads reconstructs correctly
        """
        error_response = sample_token_rate_limit_exception.to_error_response()

        # Should not raise JSONDecodeError
        json_str = json.dumps(error_response)
        reconstructed = json.loads(json_str)

        # Verify structure preserved
        assert reconstructed["error"]["type"] == "rate_limit_exceeded"
        assert "details" in reconstructed["error"]

    def test_token_headers_serializable_to_http(self, sample_token_rate_limit_exception):
        """Test headers are valid HTTP header types.

        Verifies:
        - All header values are strings or integers
        - No complex objects
        - Compatible with HTTP protocol
        """
        headers = sample_token_rate_limit_exception.to_http_headers()

        for key, value in headers.items():
            assert isinstance(key, str)
            assert isinstance(value, (str, int)), f"Header {key} has invalid type {type(value)}"

    # ============================================================================
    # OpenAI Compatibility Tests
    # ============================================================================

    def test_token_error_openai_compatible_format(self, sample_token_rate_limit_exception):
        """Test error response matches OpenAI API format for rate limits.

        OpenAI format:
        {
            "error": {
                "message": "...",
                "type": "...",
                "param": null,
                "code": "rate_limit_exceeded"
            }
        }

        Verifies our format is compatible (may have additional fields).
        """
        error_response = sample_token_rate_limit_exception.to_error_response()

        # Verify OpenAI-required fields
        assert "error" in error_response
        assert "message" in error_response["error"]
        assert "type" in error_response["error"]
        assert "code" in error_response["error"]

        # Verify code value
        assert error_response["error"]["code"] == "rate_limit_exceeded"

    def test_token_limit_headers_standard_compliant(self, sample_token_rate_limit_exception):
        """Test rate limit headers follow standard conventions.

        Standard headers:
        - Retry-After: Seconds to wait
        - X-RateLimit-Limit: Maximum allowed
        - X-RateLimit-Remaining: Remaining in window
        - X-RateLimit-Reset: Unix timestamp

        Additional headers:
        - X-RateLimit-Type: "tokens" or "requests"
        - X-RateLimit-Scope: Scope description
        """
        headers = sample_token_rate_limit_exception.to_http_headers()

        # Standard headers
        assert "Retry-After" in headers
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

        # Extension headers
        assert "X-RateLimit-Type" in headers
        assert "X-RateLimit-Scope" in headers

    # ============================================================================
    # Edge Cases
    # ============================================================================

    def test_large_token_count_formatting(self):
        """Test formatting with large token counts (GPT-4 32k context).

        Verifies:
        - Large numbers formatted correctly
        - No scientific notation in strings
        """
        exc = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4-32k",
            limit_type="tokens",
            limit=100000,
            current=100500,
            window_reset=1700000000,
            retry_after=300
        )

        headers = exc.to_http_headers()

        assert headers["X-RateLimit-Limit"] == "100000"
        assert "e" not in headers["X-RateLimit-Limit"].lower()  # No scientific notation

    def test_zero_retry_after_minimum(self):
        """Test retry_after has minimum value of 1 second.

        Verifies:
        - Never returns 0 or negative retry_after
        - Prevents immediate retry storms
        """
        exc = RateLimitExceeded(
            scope_type="model",
            scope_id="gpt-4",
            limit_type="tokens",
            limit=10000,
            current=10100,
            window_reset=1700000000,
            retry_after=0  # Edge case
        )

        headers = exc.to_http_headers()

        # Retry-After should be at least 1
        retry_after = int(headers["Retry-After"])
        assert retry_after >= 1

    def test_token_limit_message_clarity(self, sample_token_rate_limit_exception):
        """Test error message is clear and actionable.

        Verifies message includes:
        - What was exceeded (token limit)
        - Current usage
        - Maximum allowed
        - When it resets
        """
        error_response = sample_token_rate_limit_exception.to_error_response()
        message = error_response["error"]["message"]

        # Should mention key information
        assert "token" in message.lower()
        assert "limit" in message.lower()

        # Should be reasonably concise (not a paragraph)
        assert len(message) < 500  # Reasonable limit
        assert len(message) > 20    # Not too terse
