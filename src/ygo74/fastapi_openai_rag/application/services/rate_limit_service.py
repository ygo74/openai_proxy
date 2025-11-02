"""Token rate limiting service."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any
import logging

from ...domain.models.rate_limit import (
    TokenRateLimit,
    RateLimitUsage,
    RateLimitViolation,
    RateLimitWindow
)
from ...domain.models.autenticated_user import AuthenticatedUser
from ...domain.models.llm_model import LlmModel
from ...domain.unit_of_work import UnitOfWork
from .config_service import ConfigService

logger = logging.getLogger(__name__)

_GLOBAL_USAGE_CACHE: Dict[str, RateLimitUsage] = {}

class TokenRateLimitService:
    """Service for managing token-based rate limiting with hierarchical configuration."""

    _shared_instance: Optional["TokenRateLimitService"] = None

    def __new__(cls, uow: UnitOfWork, config_service: Optional[ConfigService] = None) -> "TokenRateLimitService":
        """Create or reuse the singleton TokenRateLimitService instance."""
        if cls._shared_instance is None:
            cls._shared_instance = super().__new__(cls)
        return cls._shared_instance

    def __init__(self, uow: UnitOfWork, config_service: Optional[ConfigService] = None):
        """Initialize the singleton instance only once."""
        if getattr(self, "_is_initialized", False):
            return
        self._initialize_shared_state(uow, config_service)

    def _initialize_shared_state(self, uow: UnitOfWork, config_service: Optional[ConfigService]) -> None:
        """Initialize shared state for the singleton service."""
        self._uow = uow
        self._config_service = config_service or ConfigService()
        self._usage_cache = _GLOBAL_USAGE_CACHE
        self._is_initialized = True

    def _get_effective_rate_limit(self,
                                 user: AuthenticatedUser,
                                 model: Optional[LlmModel] = None) -> Optional[TokenRateLimit]:
        """Get effective rate limit using hierarchical configuration.

        Priority order: Group-specific > Model-specific > Global

        Args:
            user: Authenticated user with group memberships
            model: Optional model (for model-specific limits)

        Returns:
            Effective token rate limit configuration or None if unlimited
        """
        try:
            config = self._config_service.get_config()

            # Start with global rate limit (lowest priority)
            effective_limit = config.global_token_rate_limit

            # Override with model-specific rate limit if available
            if model and model.technical_name:
                model_config = self._config_service.get_model_config(model.technical_name)
                if model_config and model_config.token_rate_limit:
                    effective_limit = model_config.token_rate_limit
                    logger.debug(f"Using model-specific rate limit for {model.technical_name}")

            # Override with group-specific rate limit if available (highest priority)
            for group_name in user.groups:
                if group_name in config.group_token_rate_limits:
                    effective_limit = config.group_token_rate_limits[group_name]
                    logger.debug(f"Using group-specific rate limit for group {group_name}")
                    break  # Use first matching group's limit

            return effective_limit

        except Exception as e:
            logger.error(f"Error determining effective rate limit: {e}")
            return None

    def _get_usage_key(self, user_id: str, group_name: Optional[str] = None, model_name: Optional[str] = None) -> str:
        """Generate usage tracking key."""
        parts = [user_id]
        if group_name:
            parts.append(f"group:{group_name}")
        if model_name:
            parts.append(f"model:{model_name}")
        return ":".join(parts)

    def _get_or_create_usage(self,
                           user: AuthenticatedUser,
                           model: Optional[LlmModel] = None) -> RateLimitUsage:
        """Get or create usage tracking entry."""
        # Determine which group to use for tracking (first group if multiple)
        group_name = user.groups[0] if user.groups else None
        model_name = model.technical_name if model else None

        usage_key = self._get_usage_key(user.username, group_name, model_name)

        if usage_key not in self._usage_cache:
            # Try to load from database (implementation depends on your storage choice)
            # For now, create new usage tracking
            self._usage_cache[usage_key] = RateLimitUsage(
                user_id=user.username,
                group_name=group_name,
                model_name=model_name
            )
            logger.debug(f"Created new usage tracking for key: {usage_key}")

        return self._usage_cache[usage_key]

    def check_rate_limit(self,
                        user: AuthenticatedUser,
                        model: Optional[LlmModel] = None) -> None:
        """Check if the requested token usage would exceed rate limits.

        Args:
            user: Authenticated user
            model: Optional model for model-specific limits

        Raises:
            RateLimitViolation: If rate limit would be exceeded
        """
        # Get effective rate limit configuration
        rate_limit = self._get_effective_rate_limit(user, model)

        if not rate_limit or rate_limit.is_unlimited():
            logger.debug("No rate limiting configured or unlimited")
            return

        # Get current usage
        usage = self._get_or_create_usage(user, model)
        current_time = datetime.now(timezone.utc)

        # Reset usage windows if needed
        usage.reset_if_needed(current_time)

        # Check each configured limit
        for window in RateLimitWindow:
            limit = rate_limit.get_limit_for_window(window)
            if limit is None:
                continue

            # Get current usage for this window
            if window == RateLimitWindow.MINUTE:
                current_usage = usage.tokens_used_minute
                reset_time = usage.minute_window_start + timedelta(minutes=1)
            elif window == RateLimitWindow.HOUR:
                current_usage = usage.tokens_used_hour
                reset_time = usage.hour_window_start + timedelta(hours=1)
            elif window == RateLimitWindow.DAY:
                current_usage = usage.tokens_used_day
                reset_time = usage.day_window_start + timedelta(days=1)
            else:
                continue

            # Check if adding requested tokens would exceed limit
            if current_usage > limit:
                raise RateLimitViolation(
                    window=window,
                    limit=limit,
                    current_usage=current_usage,
                    reset_time=reset_time,
                    user_id=user.username,
                    group_name=usage.group_name,
                    model_name=usage.model_name
                )

        logger.debug(f"Rate limit check passed for {model} and user {user.username}")

    def consume_tokens(self,
                      user: AuthenticatedUser,
                      token_count: int,
                      model: Optional[LlmModel] = None) -> None:
        """Record token consumption after successful API call.

        Args:
            user: Authenticated user
            token_count: Number of tokens consumed
            model: Optional model for model-specific tracking
        """
        if token_count <= 0:
            return

        # Get current usage and update it
        usage = self._get_or_create_usage(user, model)
        current_time = datetime.now(timezone.utc)

        usage.add_tokens(token_count, current_time)

        # Persist to database (implementation depends on your storage choice)
        self._persist_usage(usage)

        logger.debug(f"Consumed {token_count} tokens for user {user.username}")

    def get_current_usage(self,
                         user: AuthenticatedUser,
                         model: Optional[LlmModel] = None) -> Dict[str, Any]:
        """Get current usage statistics for a user.

        Args:
            user: Authenticated user
            model: Optional model for model-specific usage

        Returns:
            Dictionary with current usage for each time window
        """
        usage = self._get_or_create_usage(user, model)
        current_time = datetime.now(timezone.utc)

        # Reset usage windows if needed
        usage.reset_if_needed(current_time)

        return {
            "tokens_used_minute": usage.tokens_used_minute,
            "tokens_used_hour": usage.tokens_used_hour,
            "tokens_used_day": usage.tokens_used_day,
            "minute_window_start": usage.minute_window_start.isoformat(),
            "hour_window_start": usage.hour_window_start.isoformat(),
            "day_window_start": usage.day_window_start.isoformat()
        }

    def get_rate_limit_info(self,
                           user: AuthenticatedUser,
                           model: Optional[LlmModel] = None) -> Dict[str, Any]:
        """Get rate limit configuration and current usage for a user.

        Args:
            user: Authenticated user
            model: Optional model for model-specific info

        Returns:
            Dictionary with rate limit configuration and usage
        """
        rate_limit = self._get_effective_rate_limit(user, model)
        current_usage = self.get_current_usage(user, model)

        result: Dict[str, Any] = {
            "rate_limit_enabled": rate_limit is not None and rate_limit.enabled if rate_limit else False,
            "current_usage": current_usage
        }

        if rate_limit and rate_limit.enabled:
            result.update({
                "limits": {
                    "tokens_per_minute": rate_limit.tokens_per_minute,
                    "tokens_per_hour": rate_limit.tokens_per_hour,
                    "tokens_per_day": rate_limit.tokens_per_day
                }
            })

        return result

    def _persist_usage(self, usage: RateLimitUsage) -> None:
        """Persist usage data to storage.

        This is a placeholder for database persistence.
        In a real implementation, you'd store this in Redis or database.
        """
        # TODO: Implement persistence to database or Redis
        # For now, we just keep it in memory cache
        pass

    def cleanup_expired_usage(self) -> None:
        """Clean up expired usage entries from cache."""
        current_time = datetime.now(timezone.utc)
        expired_keys = []

        for key, usage in self._usage_cache.items():
            # Remove entries that haven't been updated in over a day
            if (current_time - usage.last_updated) > timedelta(days=1):
                expired_keys.append(key)

        for key in expired_keys:
            del self._usage_cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired usage entries")
