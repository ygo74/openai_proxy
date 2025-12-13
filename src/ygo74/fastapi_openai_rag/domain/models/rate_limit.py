"""Domain models for rate limiting.

This module contains two rate limiting systems:
1. FixedWindow* classes: Fixed-period rate limiting (minute/hour/day windows)
2. RateLimit* classes: Time-based window rate limiting (configurable HH:MM:SS ranges)
"""
from datetime import datetime, timedelta, timezone, time
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

class FixedWindowRateLimit(str, Enum):
    """Rate limit time windows."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"

class FixedWindowTokenRateLimit(BaseModel):
    """Token rate limit configuration.

    Attributes:
        tokens_per_minute: Maximum tokens allowed per minute (None = unlimited)
        tokens_per_hour: Maximum tokens allowed per hour (None = unlimited)
        tokens_per_day: Maximum tokens allowed per day (None = unlimited)
        enabled: Whether rate limiting is enabled
    """
    tokens_per_minute: Optional[int] = Field(None, ge=0)
    tokens_per_hour: Optional[int] = Field(None, ge=0)
    tokens_per_day: Optional[int] = Field(None, ge=0)
    enabled: bool = Field(True)

    @field_validator("tokens_per_minute", "tokens_per_hour", "tokens_per_day", mode="before")
    @classmethod
    def validate_token_limits(cls, v):
        """Validate that token limits are non-negative if specified."""
        if v is not None and v < 0:
            raise ValueError("Token limits must be non-negative")
        return v

    def is_unlimited(self) -> bool:
        """Check if rate limiting is effectively unlimited."""
        return (not self.enabled or
                (self.tokens_per_minute is None and
                 self.tokens_per_hour is None and
                 self.tokens_per_day is None))

    def get_limit_for_window(self, window: FixedWindowRateLimit) -> Optional[int]:
        """Get limit for specific time window."""
        if not self.enabled:
            return None

        if window == FixedWindowRateLimit.MINUTE:
            return self.tokens_per_minute
        elif window == FixedWindowRateLimit.HOUR:
            return self.tokens_per_hour
        elif window == FixedWindowRateLimit.DAY:
            return self.tokens_per_day
        return None

class FixedRateLimitUsage(BaseModel):
    """Current rate limit usage tracking.

    Attributes:
        user_id: User identifier
        group_name: Group name (optional)
        model_name: Model name (optional)
        tokens_used_minute: Tokens used in current minute window
        tokens_used_hour: Tokens used in current hour window
        tokens_used_day: Tokens used in current day window
        minute_window_start: Start of current minute window
        hour_window_start: Start of current hour window
        day_window_start: Start of current day window
        last_updated: Last update timestamp
    """
    user_id: str
    group_name: Optional[str] = None
    model_name: Optional[str] = None
    tokens_used_minute: int = 0
    tokens_used_hour: int = 0
    tokens_used_day: int = 0
    minute_window_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hour_window_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    day_window_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_usage_key(self) -> str:
        """Generate unique key for this usage tracking entry."""
        parts = [self.user_id]
        if self.group_name:
            parts.append(f"group:{self.group_name}")
        if self.model_name:
            parts.append(f"model:{self.model_name}")
        return ":".join(parts)

    def reset_if_needed(self, current_time: Optional[datetime] = None) -> bool:
        """Reset usage counters if windows have expired.

        Returns:
            bool: True if any counters were reset
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        reset_occurred = False

        # Reset minute window if needed
        if (current_time - self.minute_window_start) >= timedelta(minutes=1):
            self.tokens_used_minute = 0
            self.minute_window_start = current_time.replace(second=0, microsecond=0)
            reset_occurred = True

        # Reset hour window if needed
        if (current_time - self.hour_window_start) >= timedelta(hours=1):
            self.tokens_used_hour = 0
            self.hour_window_start = current_time.replace(minute=0, second=0, microsecond=0)
            reset_occurred = True

        # Reset day window if needed
        if (current_time - self.day_window_start) >= timedelta(days=1):
            self.tokens_used_day = 0
            self.day_window_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            reset_occurred = True

        if reset_occurred:
            self.last_updated = current_time

        return reset_occurred

    def add_tokens(self, token_count: int, current_time: Optional[datetime] = None) -> None:
        """Add tokens to all usage windows."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Reset windows if needed first
        self.reset_if_needed(current_time)

        # Add tokens to all windows
        self.tokens_used_minute += token_count
        self.tokens_used_hour += token_count
        self.tokens_used_day += token_count
        self.last_updated = current_time

class FixedRateLimitViolation(Exception):
    """Exception raised when rate limit is exceeded.

    Attributes:
        window: Time window that was exceeded
        limit: The rate limit that was exceeded
        current_usage: Current usage count
        reset_time: When the limit resets
        message: Error message
    """

    def __init__(self,
                 window: FixedWindowRateLimit,
                 limit: int,
                 current_usage: int,
                 reset_time: datetime,
                 user_id: str,
                 group_name: Optional[str] = None,
                 model_name: Optional[str] = None):
        self.window = window
        self.limit = limit
        self.current_usage = current_usage
        self.reset_time = reset_time
        self.user_id = user_id
        self.group_name = group_name
        self.model_name = model_name

        # Build descriptive message
        scope_parts = []
        if model_name:
            scope_parts.append(f"model '{model_name}'")
        if group_name:
            scope_parts.append(f"group '{group_name}'")
        if not scope_parts:
            scope_parts.append("global")

        scope_desc = " for " + " and ".join(scope_parts) if scope_parts != ["global"] else ""

        self.message = (f"Rate limit exceeded{scope_desc}: {current_usage}/{limit} tokens used "
                       f"in current {window.value}. Limit resets at {reset_time.isoformat()}")
        super().__init__(self.message)


# ============================================================================
# Time-Based Window Rate Limiting Models (US1-US6 Feature)
# ============================================================================


class RateLimitWindow(BaseModel):
    """Time-based window for rate limit enforcement.

    Represents a specific time range (e.g., 00:00:00-08:00:00) with associated
    request and token limits. Multiple windows can be defined for different
    time periods within a day.

    Attributes:
        id: Unique identifier (None for new windows)
        from_time: Window start time (HH:MM:SS format)
        to_time: Window end time (HH:MM:SS format)
        max_requests: Maximum requests allowed in this window (0 = unlimited)
        max_tokens: Maximum tokens allowed in this window (0 = unlimited)

    Validation:
        - At least one limit (requests or tokens) must be > 0
        - from_time must be before to_time
        - Both limits cannot be 0 simultaneously
    """

    id: Optional[int] = Field(default=None, description="Database primary key")
    from_time: time = Field(description="Window start time (00:00:00 to 23:59:59)")
    to_time: time = Field(description="Window end time (00:00:00 to 23:59:59)")
    max_requests: Optional[int] = Field(default=None, ge=-1, description="Max requests in window (-1 = unlimited, None = not set)")
    max_tokens: Optional[int] = Field(default=None, ge=-1, description="Max tokens in window (-1 = unlimited, None = not set)")

    @model_validator(mode='after')
    def validate_window(self):
        """Validate time range and ensure at least one limit is set."""
        # Validate time ordering
        if self.to_time <= self.from_time:
            raise ValueError(f"to_time ({self.to_time}) must be after from_time ({self.from_time})")

        # Ensure at least one limit is set (not None)
        if self.max_requests is None and self.max_tokens is None:
            raise ValueError("At least one of max_requests or max_tokens must be set (cannot both be None)")

        return self

    def is_active_at(self, check_time: time) -> bool:
        """Check if this window is active at the given time.

        Args:
            check_time: Time to check against window bounds

        Returns:
            True if check_time falls within [from_time, to_time)
        """
        return self.from_time <= check_time < self.to_time

    class Config:
        """Pydantic configuration."""
        frozen = False  # Allow field updates for admin API
        json_schema_extra = {
            "example": {
                "id": 1,
                "from_time": "00:00:00",
                "to_time": "08:00:00",
                "max_requests": 100,
                "max_tokens": 50000
            }
        }


class RateLimit(BaseModel):
    """Rate limit configuration for a specific scope.

    Defines rate limiting rules that apply to a particular scope (global,
    model, or group/model combination). Each rate limit contains one or more
    time windows with specific request/token thresholds.

    Attributes:
        id: Unique identifier (None for new limits)
        scope_type: Level of rate limit application
        scope_id: Identifier for model or group+model (None for global)
        windows: List of time windows with limits
        enabled: Whether this rate limit is active
        created_at: Timestamp when limit was created
        updated_at: Timestamp when limit was last modified

    Scope Types:
        - global: Applies to all requests (scope_id must be None)
        - model: Applies to all requests for a specific model (scope_id = model technical name)
        - group_model: Applies to specific group+model combo (scope_id = "group_name:model_name")

    Validation:
        - At least one window required when enabled=True
        - scope_id must be None for global scope
        - scope_id must be set for model/group_model scopes
        - group_model scope_id must follow "group:model" format
    """

    id: Optional[int] = Field(default=None, description="Database primary key")
    scope_type: Literal["global", "model", "group_model"] = Field(
        description="Type of scope for this rate limit"
    )
    scope_id: Optional[str] = Field(
        default=None,
        description="Identifier for model or group+model (None for global)"
    )
    windows: List[RateLimitWindow] = Field(
        default_factory=list,
        description="Time windows with rate limits"
    )
    enabled: bool = Field(default=True, description="Whether limit is active")
    created_at: Optional[str] = Field(default=None, description="ISO 8601 creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="ISO 8601 update timestamp")

    @field_validator('scope_id')
    @classmethod
    def validate_scope_id(cls, v: Optional[str], info) -> Optional[str]:
        """Validate scope_id based on scope_type."""
        scope_type = info.data.get('scope_type')

        if scope_type == 'global':
            if v is not None:
                raise ValueError("Global scope must have scope_id=None")
        elif scope_type in ('model', 'group_model'):
            if not v:
                raise ValueError(f"{scope_type} scope requires scope_id to be set")
            if scope_type == 'group_model' and ':' not in v:
                raise ValueError("group_model scope_id must follow 'group_name:model_name' format")

        return v

    @model_validator(mode='after')
    def validate_windows_when_enabled(self):
        """Ensure at least one window when enabled."""
        if self.enabled and len(self.windows) == 0:
            raise ValueError("At least one window required when rate limit is enabled")
        return self

    def get_active_window(self, current_time: time, use_default_fallback: bool = True) -> Optional[RateLimitWindow]:
        """Get the active window for the current time with optional 24-hour fallback.

        This method finds the time window matching the current time. If no window matches
        and use_default_fallback=True, returns a default 24-hour window (00:00:00-23:59:59)
        that uses the first window's limits as defaults.

        Args:
            current_time: Current time to check against windows
            use_default_fallback: If True, return default 24-hour window when no match (default: True)

        Returns:
            Active RateLimitWindow or None if no window matches and no fallback
        """
        # Try to find matching window
        for window in self.windows:
            if window.is_active_at(current_time):
                return window

        # No matching window - use default 24-hour fallback if enabled
        if use_default_fallback and len(self.windows) > 0:
            # Create default 24-hour window using first window's limits as template
            first_window = self.windows[0]
            default_window = RateLimitWindow(
                from_time=time(0, 0, 0),
                to_time=time(23, 59, 59),
                max_requests=first_window.max_requests,
                max_tokens=first_window.max_tokens
            )
            return default_window

        return None

    @property
    def scope_identifier(self) -> str:
        """Get canonical scope identifier for cache/counter keys.

        Returns:
            String in format "{scope_type}:{scope_id}" or "global" for global scope
        """
        if self.scope_type == 'global':
            return 'global'
        return f"{self.scope_type}:{self.scope_id}"

    class Config:
        """Pydantic configuration."""
        frozen = False
        json_schema_extra = {
            "example": {
                "id": 1,
                "scope_type": "model",
                "scope_id": "gpt-4",
                "windows": [
                    {
                        "from_time": "00:00:00",
                        "to_time": "23:59:59",
                        "max_requests": 1000,
                        "max_tokens": 500000
                    }
                ],
                "enabled": True,
                "created_at": "2025-12-06T10:30:00Z",
                "updated_at": "2025-12-06T10:30:00Z"
            }
        }


class RateLimitUsage(BaseModel):
    """Runtime tracking of rate limit consumption.

    Tracks current request and token usage for a specific scope within
    a time window. Used for enforcement decisions and remaining quota
    calculations.

    This is typically stored in Redis or in-memory cache, not in the database.
    It represents ephemeral state that resets with each window transition.

    Attributes:
        scope_identifier: Canonical scope ID (e.g., "model:gpt-4")
        metric: Type of metric being tracked (requests or tokens)
        window_start: UNIX timestamp when current window started
        window_duration: Window duration in seconds
        current_count: Current usage count (requests or tokens)
        limit: Maximum allowed in this window (0 = unlimited)

    Methods:
        is_exceeded: Check if limit has been exceeded
        remaining: Calculate remaining quota
        reset_at: Get UNIX timestamp when window resets
    """

    scope_identifier: str = Field(description="Scope ID (global, model:name, group_model:g:m)")
    metric: Literal["requests", "tokens"] = Field(description="Metric being tracked")
    window_start: int = Field(description="UNIX timestamp of window start")
    window_duration: int = Field(gt=0, description="Window duration in seconds")
    current_count: int = Field(ge=0, default=0, description="Current usage count")
    limit: int = Field(ge=0, description="Maximum allowed (0 = unlimited)")

    def is_exceeded(self) -> bool:
        """Check if the rate limit has been exceeded.

        Returns:
            True if current_count >= limit (and limit > 0), False otherwise
        """
        if self.limit == 0:  # 0 means unlimited
            return False
        return self.current_count >= self.limit

    def remaining(self) -> int:
        """Calculate remaining quota in this window.

        Returns:
            Number of requests/tokens remaining (0 if exceeded or unlimited)
        """
        if self.limit == 0:  # Unlimited
            return 0  # Convention: 0 indicates unlimited
        remaining = self.limit - self.current_count
        return max(0, remaining)

    def reset_at(self) -> int:
        """Get UNIX timestamp when this window resets.

        Returns:
            UNIX timestamp of window end
        """
        return self.window_start + self.window_duration

    def increment(self, amount: int = 1) -> int:
        """Increment usage counter.

        Args:
            amount: Amount to increment (default 1 for requests)

        Returns:
            New current_count value
        """
        self.current_count += amount
        return self.current_count

    class Config:
        """Pydantic configuration."""
        frozen = False  # Allow mutation for counter increments
        json_schema_extra = {
            "example": {
                "scope_identifier": "model:gpt-4",
                "metric": "requests",
                "window_start": 1701936000,
                "window_duration": 3600,
                "current_count": 87,
                "limit": 100
            }
        }


class RateLimitErrorDetails(BaseModel):
    """Detailed information about rate limit violation.

    Attributes:
        scope_type: Which scope was violated (global/model/group_model)
        scope_id: Specific scope identifier (None for global)
        limit_type: Which metric was exceeded (requests/tokens)
        limit: The configured limit value
        window_seconds: Window duration in seconds
        retry_after_seconds: Seconds until window resets
        current_usage: Current usage count (optional)
    """

    scope_type: Literal["global", "model", "group_model"] = Field(
        description="Type of scope that triggered rate limit"
    )
    scope_id: Optional[str] = Field(
        default=None,
        description="Specific model or group/model identifier"
    )
    limit_type: Literal["requests", "tokens"] = Field(
        description="Which metric exceeded the limit"
    )
    limit: int = Field(ge=0, description="The configured maximum value")
    window_seconds: int = Field(gt=0, description="Duration of rate limit window")
    retry_after_seconds: int = Field(ge=0, description="Seconds until limit resets")
    current_usage: Optional[int] = Field(
        default=None,
        description="Current usage count (optional for debugging)"
    )


class RateLimitErrorResponse(BaseModel):
    """OpenAI-compatible HTTP 429 error response body.

    Structured error response matching OpenAI API format for client
    compatibility. Used by exception handler to generate HTTP 429 responses.

    Attributes:
        error: Error object containing message, type, code, and details

    Response Headers (not in this model, set by exception handler):
        - Retry-After: Seconds until reset
        - X-RateLimit-Limit-Requests: Max requests allowed
        - X-RateLimit-Limit-Tokens: Max tokens allowed
        - X-RateLimit-Remaining-Requests: Requests remaining
        - X-RateLimit-Remaining-Tokens: Tokens remaining
        - X-RateLimit-Reset-Requests: UNIX timestamp of reset
        - X-RateLimit-Reset-Tokens: UNIX timestamp of reset
    """

    class ErrorObject(BaseModel):
        """Error details object."""
        message: str = Field(description="Human-readable error message")
        type: Literal["rate_limit_exceeded"] = Field(
            default="rate_limit_exceeded",
            description="Error type constant"
        )
        param: Optional[str] = Field(
            default=None,
            description="Parameter that caused error (always None for rate limits)"
        )
        code: str = Field(description="Machine-readable error code")
        details: RateLimitErrorDetails = Field(description="Rate limit violation details")

    error: ErrorObject = Field(description="Error information")

    @classmethod
    def from_usage(
        cls,
        usage: RateLimitUsage,
        scope_type: Literal["global", "model", "group_model"],
        scope_id: Optional[str] = None
    ) -> "RateLimitErrorResponse":
        """Create error response from RateLimitUsage.

        Args:
            usage: Usage object that exceeded limit
            scope_type: Type of scope (global/model/group_model)
            scope_id: Specific scope identifier

        Returns:
            Formatted RateLimitErrorResponse
        """
        scope_display = f"{scope_type}" if scope_type == "global" else f"{scope_type} '{scope_id}'"
        message = f"Rate limit exceeded for {scope_display}: {usage.metric} limit of {usage.limit} per {usage.window_duration}s"

        retry_after = usage.reset_at() - int(datetime.now().timestamp())

        return cls(
            error=cls.ErrorObject(
                message=message,
                code=f"{scope_type}_rate_limit_exceeded",
                details=RateLimitErrorDetails(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    limit_type=usage.metric,
                    limit=usage.limit,
                    window_seconds=usage.window_duration,
                    retry_after_seconds=max(0, retry_after),
                    current_usage=usage.current_count
                )
            )
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "error": {
                    "message": "Rate limit exceeded for model 'gpt-4': requests limit of 100 per 3600s",
                    "type": "rate_limit_exceeded",
                    "param": None,
                    "code": "model_rate_limit_exceeded",
                    "details": {
                        "scope_type": "model",
                        "scope_id": "gpt-4",
                        "limit_type": "requests",
                        "limit": 100,
                        "window_seconds": 3600,
                        "retry_after_seconds": 1234,
                        "current_usage": 102
                    }
                }
            }
        }
