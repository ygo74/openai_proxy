"""Domain models for token rate limiting."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum

class RateLimitWindow(str, Enum):
    """Rate limit time windows."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"

class TokenRateLimit(BaseModel):
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

    def get_limit_for_window(self, window: RateLimitWindow) -> Optional[int]:
        """Get limit for specific time window."""
        if not self.enabled:
            return None

        if window == RateLimitWindow.MINUTE:
            return self.tokens_per_minute
        elif window == RateLimitWindow.HOUR:
            return self.tokens_per_hour
        elif window == RateLimitWindow.DAY:
            return self.tokens_per_day
        return None

class RateLimitUsage(BaseModel):
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

class RateLimitViolation(Exception):
    """Exception raised when rate limit is exceeded.

    Attributes:
        window: Time window that was exceeded
        limit: The rate limit that was exceeded
        current_usage: Current usage count
        reset_time: When the limit resets
        message: Error message
    """

    def __init__(self,
                 window: RateLimitWindow,
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
