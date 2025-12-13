"""Mapper for converting between rate limit API models and domain models.

This mapper belongs to the interfaces layer and handles conversions between:
- Pydantic API request/response models (interfaces layer)
- Domain entities (domain layer)

It does NOT handle ORM conversions - those are in infrastructure/db/mappers/.
"""
from typing import TYPE_CHECKING, Literal, cast
from datetime import time

from ....domain.models.rate_limit import RateLimit, RateLimitWindow

if TYPE_CHECKING:
    from ..models.rate_limit_api import (
        CreateRateLimitRequest,
        RateLimitWindowRequest,
        RateLimitResponse,
        RateLimitWindowResponse
    )


def time_to_str(t: time) -> str:
    """Convert datetime.time to string format HH:MM:SS.

    Args:
        t: Time object

    Returns:
        String in HH:MM:SS format
    """
    return t.strftime("%H:%M:%S")


def str_to_time(time_str: str) -> time:
    """Convert string HH:MM or HH:MM:SS to datetime.time.

    Args:
        time_str: Time string in HH:MM or HH:MM:SS format

    Returns:
        datetime.time object

    Raises:
        ValueError: If time format is invalid
    """
    parts = time_str.split(':')
    if len(parts) == 2:
        return time(int(parts[0]), int(parts[1]), 0)
    elif len(parts) == 3:
        return time(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM or HH:MM:SS")


class RateLimitApiMapper:
    """Mapper for converting between API models and domain models.

    Handles conversions between Pydantic API request/response models
    and domain entities, including time string formatting.

    This mapper is part of the interfaces layer and should NOT be used
    by infrastructure or domain layers.
    """

    @staticmethod
    def window_request_to_domain(api_window: "RateLimitWindowRequest") -> RateLimitWindow:
        """Convert API window request to domain RateLimitWindow.

        Args:
            api_window: RateLimitWindowRequest from API layer

        Returns:
            RateLimitWindow domain entity
        """
        return RateLimitWindow(
            from_time=str_to_time(api_window.from_time),
            to_time=str_to_time(api_window.to_time),
            max_requests=api_window.max_requests if api_window.max_requests is not None else -1,
            max_tokens=api_window.max_tokens if api_window.max_tokens is not None else -1
        )

    @staticmethod
    def window_domain_to_response(domain_window: RateLimitWindow) -> "RateLimitWindowResponse":
        """Convert domain RateLimitWindow to API response.

        Args:
            domain_window: RateLimitWindow domain entity

        Returns:
            RateLimitWindowResponse for API layer
        """
        from ..models.rate_limit_api import RateLimitWindowResponse

        return RateLimitWindowResponse(
            id=domain_window.id,
            from_time=time_to_str(domain_window.from_time),
            to_time=time_to_str(domain_window.to_time),
            max_requests=domain_window.max_requests,
            max_tokens=domain_window.max_tokens
        )

    @staticmethod
    def create_request_to_domain(
        api_request: "CreateRateLimitRequest",
        scope_type: str,
        scope_id: str
    ) -> RateLimit:
        """Convert CreateRateLimitRequest to domain RateLimit.

        Args:
            api_request: CreateRateLimitRequest from API layer
            scope_type: Scope type ("model" or "group_model")
            scope_id: Scope identifier

        Returns:
            RateLimit domain entity
        """
        windows = [
            RateLimitApiMapper.window_request_to_domain(w)
            for w in api_request.windows
        ]

        # Cast scope_type to Literal for type safety
        valid_scope_type = cast(Literal["global", "model", "group_model"], scope_type)

        return RateLimit(
            scope_type=valid_scope_type,
            scope_id=scope_id,
            enabled=api_request.enabled,
            windows=windows
        )

    @staticmethod
    def domain_to_response(domain_limit: RateLimit) -> "RateLimitResponse":
        """Convert domain RateLimit to API response.

        Args:
            domain_limit: RateLimit domain entity

        Returns:
            RateLimitResponse for API layer
        """
        from ..models.rate_limit_api import RateLimitResponse

        return RateLimitResponse(
            id=domain_limit.id,
            scope_type=domain_limit.scope_type,
            scope_id=domain_limit.scope_id,
            enabled=domain_limit.enabled,
            windows=[
                RateLimitApiMapper.window_domain_to_response(w)
                for w in domain_limit.windows
            ]
        )
