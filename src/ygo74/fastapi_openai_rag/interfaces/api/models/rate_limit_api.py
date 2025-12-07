"""Pydantic models for Rate Limit Admin API request/response validation.

This module defines the API contracts for the admin endpoints that manage
rate limit configurations. It follows the interfaces layer pattern with
Pydantic models for validation and serialization.

Models:
- Request models: Validate incoming API payloads
- Response models: Structure API responses
- Window models: Time-based limit configurations
"""
from typing import Optional, List
from datetime import time
from pydantic import BaseModel, Field, field_validator


class RateLimitWindowRequest(BaseModel):
    """Request model for creating/updating a rate limit time window.

    Attributes:
        from_time: Window start time (format: "HH:MM" or "HH:MM:SS")
        to_time: Window end time (format: "HH:MM" or "HH:MM:SS")
        max_requests: Maximum requests in window (-1 for unlimited, None to not limit)
        max_tokens: Maximum tokens in window (-1 for unlimited, None to not limit)

    Examples:
        {"from_time": "00:00", "to_time": "23:59", "max_requests": 100}
        {"from_time": "09:00:00", "to_time": "17:00:00", "max_tokens": 50000}
    """
    from_time: str = Field(..., description="Window start time (HH:MM or HH:MM:SS)", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$")
    to_time: str = Field(..., description="Window end time (HH:MM or HH:MM:SS)", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$")
    max_requests: Optional[int] = Field(None, ge=-1, description="Max requests (-1=unlimited, None=not limited)")
    max_tokens: Optional[int] = Field(None, ge=-1, description="Max tokens (-1=unlimited, None=not limited)")

    @field_validator('to_time')
    @classmethod
    def validate_time_range(cls, to_time_str: str, info) -> str:
        """Ensure from_time is before to_time."""
        from_time_str = info.data.get('from_time')
        if from_time_str:
            # Parse times for comparison
            from_parts = from_time_str.split(':')
            to_parts = to_time_str.split(':')

            # Pad with seconds if not provided
            if len(from_parts) == 2:
                from_parts.append('00')
            if len(to_parts) == 2:
                to_parts.append('00')

            from_time = time(int(from_parts[0]), int(from_parts[1]), int(from_parts[2]))
            to_time = time(int(to_parts[0]), int(to_parts[1]), int(to_parts[2]))

            if to_time <= from_time:
                raise ValueError(f"to_time ({to_time_str}) must be after from_time ({from_time_str})")

        return to_time_str

    @field_validator('max_tokens')
    @classmethod
    def validate_at_least_one_limit(cls, v: Optional[int], info) -> Optional[int]:
        """Ensure at least one limit is set (not both None).

        This validator runs after all fields are set, checking max_tokens last.
        """
        max_requests = info.data.get('max_requests')

        # If both are None, that's invalid
        if max_requests is None and v is None:
            raise ValueError("At least one limit (requests or tokens) must be specified")

        return v


class CreateRateLimitRequest(BaseModel):
    """Request model for creating a new rate limit configuration.

    Used by POST endpoints to create model or group+model rate limits.

    Attributes:
        enabled: Whether the rate limit is active
        windows: List of time-based limit windows
    """
    enabled: bool = Field(True, description="Enable/disable rate limiting")
    windows: List[RateLimitWindowRequest] = Field(..., min_length=1, description="Time-based limit windows")

    @field_validator('windows')
    @classmethod
    def validate_windows(cls, windows: List[RateLimitWindowRequest]) -> List[RateLimitWindowRequest]:
        """Validate at least one window is configured."""
        if not windows:
            raise ValueError("At least one time window must be configured")
        return windows


class UpdateRateLimitRequest(BaseModel):
    """Request model for updating an existing rate limit configuration.

    All fields optional to support partial updates.

    Attributes:
        enabled: Whether the rate limit is active
        windows: List of time-based limit windows (replaces existing)
    """
    enabled: Optional[bool] = Field(None, description="Enable/disable rate limiting")
    windows: Optional[List[RateLimitWindowRequest]] = Field(None, min_length=1, description="Time-based limit windows")

    @field_validator('windows')
    @classmethod
    def validate_windows_if_provided(cls, windows: Optional[List[RateLimitWindowRequest]]) -> Optional[List[RateLimitWindowRequest]]:
        """Validate windows if provided."""
        if windows is not None and len(windows) == 0:
            raise ValueError("If windows are specified, at least one window must be configured")
        return windows


class RateLimitWindowResponse(BaseModel):
    """Response model for a rate limit time window.

    Includes database ID for client reference.

    Attributes:
        id: Database primary key
        from_time: Window start time (format: "HH:MM:SS")
        to_time: Window end time (format: "HH:MM:SS")
        max_requests: Maximum requests in window
        max_tokens: Maximum tokens in window
    """
    id: Optional[int] = Field(None, description="Window ID")
    from_time: str = Field(..., description="Window start time (HH:MM:SS)")
    to_time: str = Field(..., description="Window end time (HH:MM:SS)")
    max_requests: Optional[int] = Field(None, description="Max requests (-1=unlimited)")
    max_tokens: Optional[int] = Field(None, description="Max tokens (-1=unlimited)")

    class Config:
        """Pydantic configuration."""
        from_attributes = True  # Enable ORM mode for SQLAlchemy models


class RateLimitResponse(BaseModel):
    """Response model for a complete rate limit configuration.

    Returned by GET endpoints and after successful POST/PUT operations.

    Attributes:
        id: Database primary key
        scope_type: Type of scope (global, model, group_model)
        scope_id: Identifier for the scope
        enabled: Whether the rate limit is active
        windows: List of configured time windows
    """
    id: Optional[int] = Field(None, description="Rate limit ID")
    scope_type: str = Field(..., description="Scope type: global, model, group_model")
    scope_id: Optional[str] = Field(None, description="Scope identifier")
    enabled: bool = Field(..., description="Rate limit enabled status")
    windows: List[RateLimitWindowResponse] = Field(..., description="Configured time windows")

    class Config:
        """Pydantic configuration."""
        from_attributes = True  # Enable ORM mode for SQLAlchemy models


class RateLimitListResponse(BaseModel):
    """Response model for listing multiple rate limits.

    Returned by GET /admin/rate-limits endpoint.

    Attributes:
        rate_limits: List of all configured rate limits
        total: Total count of rate limits
    """
    rate_limits: List[RateLimitResponse] = Field(..., description="List of rate limit configurations")
    total: int = Field(..., description="Total number of rate limits")


class RateLimitDeleteResponse(BaseModel):
    """Response model for successful DELETE operations.

    Attributes:
        success: Whether deletion succeeded
        message: Human-readable message
        scope_type: Deleted scope type
        scope_id: Deleted scope identifier
    """
    success: bool = Field(..., description="Deletion success status")
    message: str = Field(..., description="Human-readable message")
    scope_type: str = Field(..., description="Deleted scope type")
    scope_id: Optional[str] = Field(None, description="Deleted scope identifier")


class GlobalRateLimitResponse(BaseModel):
    """Response model for global rate limits from config.json.

    Returned by GET /admin/rate-limits/global endpoint.

    Note: Global limits are read-only from config.json,
    cannot be modified via API (by design).

    Attributes:
        source: Source of the configuration (always "config.json")
        enabled: Whether global limits are active
        windows: Configured time windows from config
    """
    source: str = Field("config.json", description="Configuration source")
    enabled: bool = Field(..., description="Global rate limit enabled status")
    windows: List[RateLimitWindowResponse] = Field(..., description="Global time windows")


class RateLimitErrorResponse(BaseModel):
    """Error response model for validation failures.

    Returned when request validation fails (HTTP 400).

    Attributes:
        error: Error type
        message: Human-readable error message
        details: Additional error details (field-specific errors)
    """
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Field-specific validation errors")
