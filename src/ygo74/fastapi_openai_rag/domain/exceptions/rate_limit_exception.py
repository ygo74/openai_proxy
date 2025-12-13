"""Rate limit exception for enforcement violations.

This exception is raised when a rate limit is exceeded during request processing.
It contains structured information for generating HTTP 429 responses with proper
headers and error details.
"""
from datetime import datetime
from typing import Optional
from .domain_exception import DomainException


class RateLimitExceeded(DomainException):
    """Raised when a rate limit is exceeded.

    This exception contains all information needed to generate a properly structured
    HTTP 429 response with:
    - Retry-After header
    - X-RateLimit-* headers
    - OpenAI-compatible error response body

    Attributes:
        scope_type: Type of scope where limit was exceeded ('global', 'model', 'group_model')
        scope_id: Identifier for the scope (None for global)
        limit_type: Type of limit exceeded ('requests' or 'tokens')
        limit: The limit value that was exceeded
        current: Current usage value
        window_reset: Unix timestamp when the limit resets
        retry_after: Seconds until limit resets (for Retry-After header)
        message: Human-readable error message
    """

    def __init__(self,
                 scope_type: str,
                 scope_id: Optional[str],
                 limit_type: str,
                 limit: int,
                 current: int,
                 window_reset: int,
                 retry_after: int):
        """Initialize rate limit exceeded exception.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Scope identifier (None for global)
            limit_type: Type of limit ('requests' or 'tokens')
            limit: The limit value
            current: Current usage
            window_reset: Unix timestamp when limit resets
            retry_after: Seconds until reset
        """
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.limit_type = limit_type
        self.limit = limit
        self.current = current
        self.window_reset = window_reset
        self.retry_after = retry_after

        # Build human-readable message
        scope_desc = self._format_scope_description()
        self.message = (
            f"Rate limit exceeded for {scope_desc}: "
            f"{current}/{limit} {limit_type} used in current window. "
            f"Limit resets in {retry_after} seconds."
        )

        super().__init__(self.message)

    def _format_scope_description(self) -> str:
        """Format scope for human-readable message.

        Returns:
            str: Formatted scope description
        """
        if self.scope_type == "global":
            return "global scope"
        elif self.scope_type == "model":
            return f"model '{self.scope_id}'"
        elif self.scope_type == "group_model":
            if self.scope_id and ":" in self.scope_id:
                group_id, model_id = self.scope_id.split(":", 1)
                return f"group '{group_id}' with model '{model_id}'"
            return f"group/model scope '{self.scope_id}'"
        return f"{self.scope_type} scope"

    def to_http_headers(self) -> dict:
        """Generate HTTP headers for rate limit response.

        Returns:
            dict: Headers including Retry-After and X-RateLimit-* headers
        """
        return {
            "Retry-After": str(self.retry_after),
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.limit - self.current)),
            "X-RateLimit-Reset": str(self.window_reset),
            "X-RateLimit-Type": self.limit_type,
            "X-RateLimit-Scope": f"{self.scope_type}:{self.scope_id}" if self.scope_id else self.scope_type
        }

    def to_error_response(self) -> dict:
        """Generate OpenAI-compatible error response body.

        Returns:
            dict: Error response matching OpenAI format
        """
        return {
            "error": {
                "message": self.message,
                "type": "rate_limit_exceeded",
                "code": "rate_limit_exceeded",
                "param": None,
                "details": {
                    "scope_type": self.scope_type,
                    "scope_id": self.scope_id,
                    "limit_type": self.limit_type,
                    "limit": self.limit,
                    "current": self.current,
                    "reset_time": datetime.fromtimestamp(self.window_reset).isoformat(),
                    "retry_after_seconds": self.retry_after
                }
            }
        }
