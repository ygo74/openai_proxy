"""Rate limiting service."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any
import logging

from ...domain.models.rate_limit import (
    RateLimit,
    RateLimitWindow
)
from ...domain.models.rate_limit_config import GlobalRateLimitConfig
from ...domain.unit_of_work import UnitOfWork
from .config_service import ConfigService

logger = logging.getLogger(__name__)


class RateLimitService:
    """Service for managing new database-backed rate limiting system.

    This service handles rate limit enforcement for the new multi-level rate limiting
    system introduced in specs/1-rate-limit. It supports:
    - Global, model-level, and group/model-level rate limits
    - Request-based and token-based limiting
    - Multiple time windows per limit
    - Hierarchical limit priority (group/model > model > global)
    - Dynamic configuration via admin API

    The service uses the RateLimit domain models and IRateLimitRepository for
    persistence, following the onion architecture pattern.
    """

    def __init__(self,
                 uow: UnitOfWork,
                 repository_factory: Optional[callable] = None,
                 counter: Optional[Any] = None,
                 cache: Optional[Any] = None,
                 config_service: Optional[ConfigService] = None):
        """Initialize service with Unit of Work and optional repository factory.

        Args:
            uow: Unit of Work for transaction management
            repository_factory: Optional factory for creating repository instances (for testing)
            counter: Optional RateLimitCounter instance (for testing, creates default if None)
            cache: Optional RateLimitCache instance (for testing, creates default if None)
            config_service: Optional ConfigService instance (for testing, creates default if None)
        """
        from ...infrastructure.db.repositories.rate_limit_repository import SQLRateLimitRepository
        from ...infrastructure.cache.rate_limit_counter import RateLimitCounter
        from ...infrastructure.cache.rate_limit_cache import get_rate_limit_cache

        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: SQLRateLimitRepository(session))
        self._counter = counter if counter is not None else RateLimitCounter()
        self._cache = cache if cache is not None else get_rate_limit_cache()
        self._config_service = config_service if config_service is not None else ConfigService()
        logger.debug("RateLimitService initialized with Unit of Work, counter, cache, and config_service")

    def check_request_limit(self,
                           scope_type: str,
                           scope_id: Optional[str] = None,
                           user_id: Optional[str] = None) -> bool:
        """Check if a request is allowed under the current rate limits.

        Implements request-based rate limiting with:
        1. Retrieve rate limit configuration from database
        2. Find active time window for current time
        3. Calculate window start timestamp
        4. Atomically increment request counter in Redis
        5. Compare count against limit and raise exception if exceeded

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope (None for global, model_id for model,
                     'group_id:model_id' for group_model)
            user_id: Optional user identifier for user-specific tracking

        Returns:
            bool: True if request is allowed

        Raises:
            RateLimitExceeded: When the rate limit is exceeded
        """
        from datetime import datetime, time as dt_time
        from ...domain.exceptions.rate_limit_exception import RateLimitExceeded

        # Step 1: Get rate limit configuration
        rate_limit = self.get_rate_limit_config(scope_type, scope_id)

        if not rate_limit or not rate_limit.enabled:
            logger.debug(f"No rate limit configured or disabled for scope={scope_type}, id={scope_id}")
            return True  # No limit configured, allow request

        # Step 2: Find active window for current time
        current_time = datetime.now().time()
        active_window = rate_limit.get_active_window(current_time)

        if not active_window:
            logger.debug(f"No active window at {current_time} for scope={scope_type}, id={scope_id}")
            return True  # No active window, allow request

        # Check if window has request limit set
        if active_window.max_requests is None or active_window.max_requests < 0:
            logger.debug(f"No request limit in active window for scope={scope_type}, id={scope_id}")
            return True  # Unlimited requests (-1 or None)

        # Step 3: Calculate window start and duration
        window_start, window_duration = self.get_current_window_key(
            scope_type,
            scope_id,
            active_window.from_time,
            active_window.to_time
        )

        # Step 4: Atomically increment counter
        current_count = self._counter.increment_request_count(
            scope_type,
            scope_id,
            window_start,
            window_duration
        )

        # Handle Redis failure (fail-open)
        if current_count is None:
            logger.warning(f"Counter returned None (Redis unavailable), allowing request (fail-open)")
            return True

        # Step 5: Check if limit exceeded
        if current_count > active_window.max_requests:
            # Calculate retry_after
            import time
            current_timestamp = int(time.time())
            window_end = window_start + window_duration
            retry_after = max(1, window_end - current_timestamp)

            logger.warning(
                f"Rate limit exceeded: scope={scope_type}, id={scope_id}, "
                f"count={current_count}, limit={active_window.max_requests}"
            )

            raise RateLimitExceeded(
                scope_type=scope_type,
                scope_id=scope_id,
                limit_type="requests",
                limit=active_window.max_requests,
                current=current_count,
                window_reset=window_end,
                retry_after=retry_after
            )

        logger.debug(
            f"Request allowed: scope={scope_type}, id={scope_id}, "
            f"count={current_count}/{active_window.max_requests}"
        )
        return True

    def check_token_limit(self,
                         scope_type: str,
                         scope_id: Optional[str] = None,
                         user_id: Optional[str] = None,
                         estimated_tokens: Optional[int] = None) -> bool:
        """Check if a request is allowed under token-based rate limits.

        Implements token-based rate limiting with:
        1. Retrieve rate limit configuration from database
        2. Find active time window for current time
        3. Get current token usage from Redis
        4. Optionally check if estimated tokens would exceed limit (pre-flight check)
        5. Raise RateLimitExceeded exception if limit would be exceeded

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope
            user_id: Optional user identifier for user-specific tracking
            estimated_tokens: Optional estimated token count for pre-flight check

        Returns:
            bool: True if request is allowed under token limits

        Raises:
            RateLimitExceeded: When the token limit would be exceeded
        """
        from datetime import datetime, time as dt_time
        from ...domain.exceptions.rate_limit_exception import RateLimitExceeded

        # Step 1: Get rate limit configuration
        rate_limit = self.get_rate_limit_config(scope_type, scope_id)

        if not rate_limit or not rate_limit.enabled:
            logger.debug(f"No token rate limit configured or disabled for scope={scope_type}, id={scope_id}")
            return True  # No limit configured, allow request

        # Step 2: Find active window for current time
        current_time = datetime.now().time()
        active_window = rate_limit.get_active_window(current_time)

        if not active_window:
            logger.debug(f"No active window at {current_time} for token limit scope={scope_type}, id={scope_id}")
            return True  # No active window, allow request

        # Check if window has token limit set
        if active_window.max_tokens is None or active_window.max_tokens < 0:
            logger.debug(f"No token limit in active window for scope={scope_type}, id={scope_id}")
            return True  # Unlimited tokens (-1 or None)

        # Step 3: Calculate window start and duration
        window_start, window_duration = self.get_current_window_key(
            scope_type,
            scope_id,
            active_window.from_time,
            active_window.to_time
        )

        # Step 4: Get current token usage (not incrementing, just checking)
        current_token_count = self._counter.get_current_count(
            scope_type,
            scope_id,
            "tokens",
            window_start
        )

        # Handle Redis failure (fail-open)
        if current_token_count is None:
            logger.warning(f"Token counter returned None (Redis unavailable), allowing request (fail-open)")
            return True

        # Step 5: Optional pre-flight check with estimated tokens
        if estimated_tokens is not None:
            projected_count = current_token_count + estimated_tokens
            if projected_count > active_window.max_tokens:
                # Calculate retry_after
                import time
                current_timestamp = int(time.time())
                window_end = window_start + window_duration
                retry_after = max(1, window_end - current_timestamp)

                logger.warning(
                    f"Token limit would be exceeded with estimated tokens: scope={scope_type}, id={scope_id}, "
                    f"current={current_token_count}, estimated={estimated_tokens}, "
                    f"projected={projected_count}, limit={active_window.max_tokens}"
                )

                raise RateLimitExceeded(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    limit_type="tokens",
                    limit=active_window.max_tokens,
                    current=projected_count,
                    window_reset=window_end,
                    retry_after=retry_after
                )
        else:
            # No estimated tokens, just check current usage
            if current_token_count > active_window.max_tokens:
                # Calculate retry_after
                import time
                current_timestamp = int(time.time())
                window_end = window_start + window_duration
                retry_after = max(1, window_end - current_timestamp)

                logger.warning(
                    f"Token limit exceeded: scope={scope_type}, id={scope_id}, "
                    f"count={current_token_count}, limit={active_window.max_tokens}"
                )

                raise RateLimitExceeded(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    limit_type="tokens",
                    limit=active_window.max_tokens,
                    current=current_token_count,
                    window_reset=window_end,
                    retry_after=retry_after
                )

        logger.debug(
            f"Token limit check passed: scope={scope_type}, id={scope_id}, "
            f"current={current_token_count}/{active_window.max_tokens}"
        )
        return True

    def record_token_usage(self,
                          scope_type: str,
                          scope_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          prompt_tokens: int = 0,
                          completion_tokens: int = 0) -> None:
        """Record actual token usage after a request completes.

        This method records token consumption asynchronously after an LLM response
        is generated. It:
        1. Calculates total tokens (prompt + completion)
        2. Retrieves rate limit configuration to find active window
        3. Atomically increments the token counter in Redis (INCRBY operation)
        4. Should be called as a background task to avoid blocking response

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope
            user_id: Optional user identifier for user-specific tracking
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
        """
        from datetime import datetime

        # Calculate total tokens
        total_tokens = prompt_tokens + completion_tokens

        if total_tokens <= 0:
            logger.debug(f"No tokens to record for scope={scope_type}, id={scope_id}")
            return

        logger.debug(
            f"Recording token usage: scope={scope_type}, id={scope_id}, "
            f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        )

        try:
            # Get rate limit configuration
            rate_limit = self.get_rate_limit_config(scope_type, scope_id)

            if not rate_limit or not rate_limit.enabled:
                logger.debug(f"No rate limit configured for token recording, skipping")
                return

            # Find active window
            current_time = datetime.now().time()
            active_window = rate_limit.get_active_window(current_time)

            if not active_window:
                logger.debug(f"No active window for token recording, skipping")
                return

            # Check if window has token limit (only record if tracking tokens)
            if active_window.max_tokens is None or active_window.max_tokens < 0:
                logger.debug(f"No token limit configured in window, skipping recording")
                return

            # Calculate window start and duration
            window_start, window_duration = self.get_current_window_key(
                scope_type,
                scope_id,
                active_window.from_time,
                active_window.to_time
            )

            # Atomically increment token counter
            updated_count = self._counter.increment_token_count(
                scope_type,
                scope_id,
                window_start,
                window_duration,
                total_tokens
            )

            if updated_count is not None:
                logger.info(
                    f"Token usage recorded: scope={scope_type}, id={scope_id}, "
                    f"tokens_added={total_tokens}, new_total={updated_count}/{active_window.max_tokens}"
                )
            else:
                logger.warning(
                    f"Token counter returned None (Redis unavailable), token usage not recorded"
                )

        except Exception as e:
            # Don't fail the request if token recording fails (background task)
            logger.error(f"Error recording token usage: {e}", exc_info=True)

    def get_current_window_key(self,
                               scope_type: str,
                               scope_id: Optional[str],
                               from_time: Any,
                               to_time: Any) -> tuple[int, int]:
        """Calculate current time window start and duration.

        Implements lazy window evaluation: calculates window start based on current time
        and window boundaries. The window_start is aligned to the beginning of the day
        plus the from_time offset.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope
            from_time: Window start time (datetime.time object)
            to_time: Window end time (datetime.time object)

        Returns:
            tuple: (window_start_timestamp, window_duration_seconds)
        """
        import time
        from datetime import datetime, timedelta

        # Get current time
        now = datetime.now()
        current_timestamp = int(time.time())

        # Calculate window duration in seconds
        # Convert time objects to seconds since midnight
        from_seconds = from_time.hour * 3600 + from_time.minute * 60 + from_time.second
        to_seconds = to_time.hour * 3600 + to_time.minute * 60 + to_time.second
        window_duration = to_seconds - from_seconds

        # Calculate today's window start (midnight + from_time)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start_datetime = today_midnight + timedelta(seconds=from_seconds)
        window_start = int(window_start_datetime.timestamp())

        logger.debug(
            f"Window calculation: from={from_time}, to={to_time}, "
            f"duration={window_duration}s, start={window_start}"
        )

        return window_start, window_duration

    def get_rate_limit_config(self,
                             scope_type: str,
                             scope_id: Optional[str] = None) -> Optional[Any]:
        """Get the rate limit configuration for a specific scope with caching.

        This method first checks the local cache, then retrieves from the database
        if not cached. If no database configuration exists and scope is 'global',
        falls back to global rate limits from config.json.

        Priority: Cache → Database → config.json (global only) → None

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope

        Returns:
            Optional[RateLimit]: The rate limit configuration if found, None otherwise
        """
        # Try cache first
        cached = self._cache.get(scope_type, scope_id)
        if cached is not None:
            return cached

        # Cache miss - retrieve from database
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            rate_limit = repository.get_by_scope(scope_type, scope_id)

            # Store in cache if found in database
            if rate_limit is not None:
                self._cache.set(scope_type, scope_id, rate_limit)
                logger.debug(f"Retrieved rate limit config from DB for scope={scope_type}, id={scope_id}")
                return rate_limit

        # Database returned None - try global config fallback for 'global' scope
        if scope_type == "global" and scope_id is None:
            global_config = self._config_service.get_global_rate_limits()
            if global_config and global_config.enabled:
                # Convert GlobalRateLimitConfig to RateLimit domain model
                rate_limit = self._convert_global_config_to_rate_limit(global_config)
                # Cache the converted config
                self._cache.set(scope_type, scope_id, rate_limit)
                logger.debug(f"Using global rate limits from config.json as fallback")
                return rate_limit

        logger.debug(f"No rate limit config found for scope={scope_type}, id={scope_id}")
        return None

    def _convert_global_config_to_rate_limit(self, global_config: GlobalRateLimitConfig) -> RateLimit:
        """Convert GlobalRateLimitConfig from config.json to RateLimit domain model.

        Args:
            global_config: GlobalRateLimitConfig from configuration

        Returns:
            RateLimit: Converted domain model
        """
        from datetime import time as dt_time

        # Convert TimeWindowConfig to RateLimitWindow
        windows = []
        for window_config in global_config.windows:
            window = RateLimitWindow(
                from_time=window_config.get_from_time(),
                to_time=window_config.get_to_time(),
                max_requests=window_config.max_requests,
                max_tokens=window_config.max_tokens
            )
            windows.append(window)

        # Create RateLimit domain model
        rate_limit = RateLimit(
            id=None,  # Config-based limits have no DB ID
            scope_type="global",
            scope_id=None,
            enabled=global_config.enabled,
            windows=windows,
            created_at=None,  # Config-based limits have no timestamps
            updated_at=None
        )

        return rate_limit

    def get_rate_limit(self, scope_type: str, scope_id: Optional[str] = None) -> Optional[Any]:
        """Get rate limit configuration by scope (alias for get_rate_limit_config).

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope

        Returns:
            Optional[RateLimit]: The rate limit configuration if found, None otherwise
        """
        return self.get_rate_limit_config(scope_type, scope_id)

    def _validate_time_windows(self, windows: List[RateLimitWindow]) -> None:
        """Validate that time windows do not overlap.

        Args:
            windows: List of time windows to validate

        Raises:
            ValueError: If windows overlap or are invalid
        """
        if not windows:
            raise ValueError("At least one time window is required")

        # Convert time windows to sortable tuples (start_seconds, end_seconds, index)
        window_intervals = []
        for i, window in enumerate(windows):
            # Convert times to seconds since midnight
            start_seconds = window.from_time.hour * 3600 + window.from_time.minute * 60 + window.from_time.second
            end_seconds = window.to_time.hour * 3600 + window.to_time.minute * 60 + window.to_time.second

            # Validate that from_time < to_time (windows must stay within same day)
            if start_seconds >= end_seconds:
                raise ValueError(
                    f"Window {i+1}: from_time must be before to_time within the same day "
                    f"(from={window.from_time}, to={window.to_time}). "
                    f"Time windows cannot cross midnight. "
                    f"To define limits across midnight, split into separate windows:\n"
                    f"  Example: For night limits (20:00-08:00), use:\n"
                    f"  - Window 1: 00:00:00 to 07:59:59 (night end)\n"
                    f"  - Window 2: 20:00:00 to 23:59:59 (night start)"
                )

            window_intervals.append((start_seconds, end_seconds, i))

        # Sort by start time
        window_intervals.sort(key=lambda x: x[0])

        # Check for overlaps
        for i in range(len(window_intervals) - 1):
            current_start, current_end, current_idx = window_intervals[i]
            next_start, next_end, next_idx = window_intervals[i + 1]

            # Check if windows overlap (next starts before current ends)
            if next_start < current_end:
                current_window = windows[current_idx]
                next_window = windows[next_idx]
                raise ValueError(
                    f"Time windows overlap: "
                    f"Window {current_idx+1} ({current_window.from_time}-{current_window.to_time}) "
                    f"overlaps with Window {next_idx+1} ({next_window.from_time}-{next_window.to_time})"
                )

        logger.debug(f"Validated {len(windows)} time windows - no overlaps detected")

    def create_or_update_rate_limit(self, rate_limit: Any) -> Any:
        """Create or update a rate limit configuration with cache invalidation.

        This method will be used by the admin API (Phase 5) to create or update
        rate limit configurations. It uses the repository's upsert method and
        publishes cache invalidation messages.

        Args:
            rate_limit: The RateLimit domain model to create or update

        Returns:
            RateLimit: The created or updated rate limit configuration

        Raises:
            ValueError: If time windows overlap or are invalid
        """
        # Validate time windows before saving
        if rate_limit.windows:
            self._validate_time_windows(rate_limit.windows)

        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            result = repository.upsert(rate_limit)
            logger.info(f"Created/updated rate limit for scope={rate_limit.scope_type}, id={rate_limit.scope_id}")

            # Invalidate cache across all instances via Redis pub/sub
            self._cache.publish_change(
                operation="update",
                scope_type=rate_limit.scope_type,
                scope_id=rate_limit.scope_id
            )

            return result

    def delete_rate_limit(self,
                         scope_type: str,
                         scope_id: Optional[str] = None) -> bool:
        """Delete a rate limit configuration with cache invalidation.

        This method will be used by the admin API (Phase 5) to delete
        rate limit configurations. Publishes cache invalidation messages.

        Args:
            scope_type: Type of scope ('global', 'model', 'group_model')
            scope_id: Identifier for the scope

        Returns:
            bool: True if deleted, False if not found
        """
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            result = repository.delete_by_scope(scope_type, scope_id)
            if result:
                logger.info(f"Deleted rate limit for scope={scope_type}, id={scope_id}")

                # Invalidate cache across all instances via Redis pub/sub
                self._cache.publish_change(
                    operation="delete",
                    scope_type=scope_type,
                    scope_id=scope_id
                )
            else:
                logger.warning(f"Rate limit not found for deletion: scope={scope_type}, id={scope_id}")
            return result

    def get_all_rate_limits(self) -> List[Any]:
        """Get all rate limit configurations.

        This method will be used by the admin API (Phase 5) to list all
        configured rate limits.

        Returns:
            List[RateLimit]: List of all rate limit configurations
        """
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            rate_limits = repository.get_all()
            logger.debug(f"Retrieved {len(rate_limits)} rate limit configurations")
            return rate_limits

    def get_enabled_rate_limits(self) -> List[Any]:
        """Get all enabled rate limit configurations.

        Returns only rate limits where enabled=True.

        Returns:
            List[RateLimit]: List of enabled rate limit configurations
        """
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            rate_limits = repository.get_enabled_only()
            logger.debug(f"Retrieved {len(rate_limits)} enabled rate limit configurations")
            return rate_limits
