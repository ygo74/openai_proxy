"""Domain models for rate limit configuration from config.json.

These models define the structure for global rate limits that are loaded
from the application configuration file. They support time-based windows
and can be used as fallback when no database-defined limits exist.
"""
from datetime import time
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TimeWindowConfig(BaseModel):
    """Time window configuration for rate limits in config.json.

    Defines a time range with associated request and token limits.
    Windows are specified using "HH:MM" or "HH:MM:SS" format.

    Attributes:
        from_time: Start time in "HH:MM" or "HH:MM:SS" format
        to_time: End time in "HH:MM" or "HH:MM:SS" format
        max_requests: Maximum requests allowed in this window (None = unlimited)
        max_tokens: Maximum tokens allowed in this window (None = unlimited)
    """

    from_time: str = Field(
        ...,
        description="Window start time in HH:MM or HH:MM:SS format"
    )
    to_time: str = Field(
        ...,
        description="Window end time in HH:MM or HH:MM:SS format"
    )
    max_requests: Optional[int] = Field(
        None,
        description="Maximum requests in this window (None = unlimited)",
        ge=1
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum tokens in this window (None = unlimited)",
        ge=1
    )

    @field_validator('from_time', 'to_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time string is in HH:MM or HH:MM:SS format.

        Args:
            v: Time string to validate

        Returns:
            Validated time string

        Raises:
            ValueError: If time format is invalid
        """
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Time must be in HH:MM or HH:MM:SS format, got: {v}"
            )
        return v

    @field_validator('max_tokens')
    @classmethod
    def validate_at_least_one_limit(cls, v: Optional[int], info) -> Optional[int]:
        """Validate that at least one limit (requests or tokens) is defined.

        Args:
            v: max_tokens value
            info: Validation context with other field values

        Returns:
            Validated max_tokens value

        Raises:
            ValueError: If both max_requests and max_tokens are None
        """
        max_requests = info.data.get('max_requests')
        if max_requests is None and v is None:
            raise ValueError(
                "At least one of max_requests or max_tokens must be specified"
            )
        return v

    def get_from_time(self) -> time:
        """Convert from_time string to datetime.time object.

        Returns:
            time: Parsed time object
        """
        parts = self.from_time.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return time(hour, minute, second)

    def get_to_time(self) -> time:
        """Convert to_time string to datetime.time object.

        Returns:
            time: Parsed time object
        """
        parts = self.to_time.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return time(hour, minute, second)


class GlobalRateLimitConfig(BaseModel):
    """Global rate limit configuration.

    Defines rate limits applied to all requests when no more specific
    (model-level or group/model-level) limits exist in the database.

    Attributes:
        enabled: Whether global rate limiting is active
        windows: List of time windows with limits
    """

    enabled: bool = Field(
        True,
        description="Whether global rate limiting is enabled"
    )
    windows: List[TimeWindowConfig] = Field(
        default_factory=list,
        description="Time windows with rate limits"
    )

    @field_validator('windows')
    @classmethod
    def validate_windows_when_enabled(cls, v: List[TimeWindowConfig], info) -> List[TimeWindowConfig]:
        """Validate that enabled limits have at least one window.

        Args:
            v: List of time windows
            info: Validation context with other field values

        Returns:
            Validated windows list

        Raises:
            ValueError: If enabled=True but no windows defined
        """
        enabled = info.data.get('enabled', True)
        if enabled and len(v) == 0:
            raise ValueError(
                "At least one time window must be defined when rate limiting is enabled"
            )
        return v


class RateLimitsConfig(BaseModel):
    """Rate limits configuration section from config.json.

    Root configuration object for all rate limiting settings.
    Currently only supports global limits, but can be extended
    for default model limits or other settings.

    Attributes:
        global_limits: Global rate limit configuration
    """

    global_limits: Optional[GlobalRateLimitConfig] = Field(
        None,
        alias="global",
        description="Global rate limit configuration"
    )

    class Config:
        """Pydantic configuration."""
        populate_by_name = True  # Allow both 'global' and 'global_limits'
