"""Retry handler for cloud service resilience - similar to .NET Polly."""
import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union
from enum import Enum

import httpx
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    wait_random,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log,
    after_log,
    RetryCallState
)

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """Retry strategies similar to Polly."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"

class CloudRetryHandler:
    """Cloud service retry handler with configurable strategies."""

    # HTTP status codes that should trigger a retry (transient errors)
    RETRYABLE_HTTP_CODES = {
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
        507,  # Insufficient Storage
        509,  # Bandwidth Limit Exceeded
        520,  # Unknown Error (Cloudflare)
        521,  # Web Server Is Down (Cloudflare)
        522,  # Connection Timed Out (Cloudflare)
        523,  # Origin Is Unreachable (Cloudflare)
        524,  # A Timeout Occurred (Cloudflare)
    }

    # Exception types that should trigger a retry
    RETRYABLE_EXCEPTIONS = (
        httpx.TimeoutException,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.ConnectError,
        httpx.NetworkError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException,
        ConnectionError,
        OSError,
    )

    def __init__(self,
                 max_attempts: int = 3,
                 strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 jitter: bool = True,
                 backoff_multiplier: float = 2.0):
        """Initialize retry handler.

        Args:
            max_attempts (int): Maximum number of retry attempts
            strategy (RetryStrategy): Retry strategy to use
            base_delay (float): Base delay in seconds
            max_delay (float): Maximum delay in seconds
            jitter (bool): Add random jitter to delays
            backoff_multiplier (float): Multiplier for exponential backoff
        """
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.backoff_multiplier = backoff_multiplier

    def create_async_retry_decorator(self):
        """Create an async retry decorator with configured strategy.

        Returns:
            Configured async retry decorator
        """
        return retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=self._get_wait_strategy(),
            retry=self._should_retry_call_state,  # <-- Correction ici
            retry_error_callback=self._retry_error_callback,
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO)
        )

    def create_sync_retry_decorator(self):
        """Create a sync retry decorator with configured strategy.

        Returns:
            Configured sync retry decorator
        """
        return retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=self._get_wait_strategy(),
            retry=self._should_retry_call_state,
            retry_error_callback=self._retry_error_callback,
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO)
        )

    def _get_wait_strategy(self):
        """Get wait strategy based on configuration.

        Returns:
            Wait strategy for tenacity
        """
        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            wait_strategy = wait_exponential(
                multiplier=self.base_delay,
                max=self.max_delay,
                exp_base=self.backoff_multiplier
            )
        elif self.strategy == RetryStrategy.FIXED_DELAY:
            wait_strategy = wait_fixed(self.base_delay)
        elif self.strategy == RetryStrategy.RANDOM_JITTER:
            wait_strategy = wait_random(min=0, max=self.base_delay)
        else:
            wait_strategy = wait_exponential(multiplier=self.base_delay, max=self.max_delay)

        # Add jitter if enabled
        if self.jitter and self.strategy != RetryStrategy.RANDOM_JITTER:
            jitter_wait = wait_random(min=0, max=1)
            wait_strategy = wait_strategy + jitter_wait

        return wait_strategy

    def _should_retry_call_state(self, retry_state: RetryCallState) -> bool:
        """Check if the exception in RetryCallState should trigger retry.

        Args:
            retry_state (RetryCallState): Retry state from tenacity

        Returns:
            bool: True if should retry
        """
        exc = retry_state.outcome.exception() if retry_state.outcome and retry_state.outcome.failed else None
        if exc is None:
            return False
        return self._should_retry_exception(exc)

    def _should_retry_exception(self, exception: Exception) -> bool:
        """Check if exception should trigger retry.

        Args:
            exception (Exception): Exception to check

        Returns:
            bool: True if should retry
        """
        # Check HTTP status errors
        if isinstance(exception, httpx.HTTPStatusError):
            should_retry = exception.response.status_code in self.RETRYABLE_HTTP_CODES
            if should_retry:
                logger.warning(f"HTTP {exception.response.status_code} error, will retry: {exception}")
            return should_retry

        if isinstance(exception, requests.exceptions.HTTPError):
            status = getattr(getattr(exception, "response", None), "status_code", None)
            should_retry = status in self.RETRYABLE_HTTP_CODES if status is not None else False
            if should_retry:
                logger.warning(f"HTTP {status} error (requests), will retry: {exception}")
            return should_retry

        # Check other retryable exceptions
        should_retry = isinstance(exception, self.RETRYABLE_EXCEPTIONS)
        if should_retry:
            logger.warning(f"Retryable exception occurred, will retry: {exception}")

        return should_retry

    def _retry_error_callback(self, retry_state: RetryCallState) -> None:
        """Callback executed when all retries are exhausted.

        Args:
            retry_state (RetryCallState): Retry state information
        """
        logger.error(
            f"All {self.max_attempts} retry attempts exhausted for {retry_state.outcome.exception()}"
        )
        # Raise the last exception explicitly so that the caller/test sees the real error
        exc = retry_state.outcome.exception() if retry_state.outcome and retry_state.outcome.failed else None
        if exc:
            raise exc

class LLMRetryHandler(CloudRetryHandler):
    """Specialized retry handler for LLM API calls."""

    def __init__(self):
        """Initialize LLM retry handler with optimized settings."""
        super().__init__(
            max_attempts=4,  # More attempts for LLM calls
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=2.0,  # Longer base delay for LLM services
            max_delay=120.0,  # Longer max delay
            jitter=True,
            backoff_multiplier=2.0
        )

class KeycloakRetryHandler(CloudRetryHandler):
    """Retry handler tuned for Keycloak availability/latency patterns."""
    def __init__(self):
        """Initialize Keycloak retry handler with resilient defaults."""
        super().__init__(
            max_attempts=5,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=8.0,
            jitter=True,
            backoff_multiplier=2.0,
        )

def with_enterprise_retry(func: Callable) -> Callable:
    """Decorator that uses the client's enterprise configuration for retry.

    This decorator automatically detects if retry is enabled and uses the
    configured retry handler from the client instance, or creates one if needed.

    Args:
        func (Callable): Method to decorate (must be a method of a class with enterprise_config)

    Returns:
        Decorated function with intelligent retry
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        # Check if the instance has enterprise config and retry is enabled
        if (hasattr(self, 'enterprise_config') and
            self.enterprise_config.enable_retry):

            # Get or create retry handler and persist it in the config
            if not getattr(self.enterprise_config, "retry_handler", None):
                self.enterprise_config.retry_handler = LLMRetryHandler()
            retry_handler = self.enterprise_config.retry_handler

            logger.debug(f"with_enterprise_retry: Using retry handler {retry_handler} for {func.__name__}")

            # Apply retry using the handler
            retry_decorator = retry_handler.create_async_retry_decorator()
            return await retry_decorator(func)(self, *args, **kwargs)
        else:
            # No retry, execute directly
            return await func(self, *args, **kwargs)

    return wrapper

# Convenience decorator with default LLM settings (fallback)
def with_llm_retry(func: Callable) -> Callable:
    """Decorator with default LLM retry settings (fallback usage).

    Args:
        func (Callable): Function to decorate

    Returns:
        Decorated function with default LLM retry
    """
    handler = LLMRetryHandler()
    retry_decorator = handler.create_async_retry_decorator()
    return retry_decorator(func)
