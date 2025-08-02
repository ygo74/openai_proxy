"""Tests for retry handler infrastructure."""
import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
from tenacity import RetryError

from src.ygo74.fastapi_openai_rag.infrastructure.llm.retry_handler import (
    CloudRetryHandler, LLMRetryHandler, RetryStrategy, with_enterprise_retry, with_llm_retry
)
from src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory import EnterpriseConfig


class TestCloudRetryHandler:
    """Test CloudRetryHandler class."""

    def test_retry_handler_init_default_values(self):
        """Test retry handler initialization with default values."""
        # arrange & act
        handler = CloudRetryHandler()

        # assert
        assert handler.max_attempts == 3
        assert handler.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert handler.base_delay == 1.0
        assert handler.max_delay == 60.0
        assert handler.jitter is True
        assert handler.backoff_multiplier == 2.0

    def test_retry_handler_init_custom_values(self):
        """Test retry handler initialization with custom values."""
        # arrange & act
        handler = CloudRetryHandler(
            max_attempts=5,
            strategy=RetryStrategy.FIXED_DELAY,
            base_delay=2.0,
            max_delay=120.0,
            jitter=False,
            backoff_multiplier=3.0
        )

        # assert
        assert handler.max_attempts == 5
        assert handler.strategy == RetryStrategy.FIXED_DELAY
        assert handler.base_delay == 2.0
        assert handler.max_delay == 120.0
        assert handler.jitter is False
        assert handler.backoff_multiplier == 3.0

    def test_retry_handler_should_retry_http_status_error_retryable(self):
        """Test should retry for retryable HTTP status codes."""
        # arrange
        handler = CloudRetryHandler()
        mock_response = Mock()
        mock_response.status_code = 503
        exception = httpx.HTTPStatusError("Service unavailable", request=Mock(), response=mock_response)

        # act
        result = handler._should_retry_exception(exception)

        # assert
        assert result is True

    def test_retry_handler_should_retry_http_status_error_not_retryable(self):
        """Test should not retry for non-retryable HTTP status codes."""
        # arrange
        handler = CloudRetryHandler()
        mock_response = Mock()
        mock_response.status_code = 404
        exception = httpx.HTTPStatusError("Not found", request=Mock(), response=mock_response)

        # act
        result = handler._should_retry_exception(exception)

        # assert
        assert result is False

    def test_retry_handler_should_retry_network_exception(self):
        """Test should retry for network exceptions."""
        # arrange
        handler = CloudRetryHandler()
        exception = httpx.ConnectTimeout("Connection timeout")

        # act
        result = handler._should_retry_exception(exception)

        # assert
        assert result is True

    def test_retry_handler_should_not_retry_other_exception(self):
        """Test should not retry for other exceptions."""
        # arrange
        handler = CloudRetryHandler()
        exception = ValueError("Invalid value")

        # act
        result = handler._should_retry_exception(exception)

        # assert
        assert result is False

    def test_retry_handler_create_async_retry_decorator(self):
        """Test creating async retry decorator."""
        # arrange
        handler = CloudRetryHandler()

        # act
        decorator = handler.create_async_retry_decorator()

        # assert
        assert decorator is not None
        assert callable(decorator)


class TestLLMRetryHandler:
    """Test LLMRetryHandler class."""

    def test_llm_retry_handler_init_optimized_settings(self):
        """Test LLM retry handler has optimized settings."""
        # arrange & act
        handler = LLMRetryHandler()

        # assert
        assert handler.max_attempts == 4
        assert handler.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert handler.base_delay == 2.0
        assert handler.max_delay == 120.0
        assert handler.jitter is True
        assert handler.backoff_multiplier == 2.0


class TestWithEnterpriseRetry:
    """Test with_enterprise_retry decorator."""

    @pytest.mark.asyncio
    async def test_with_enterprise_retry_enabled_success(self):
        """Test enterprise retry decorator when retry is enabled and succeeds."""
        # arrange
        enterprise_config = EnterpriseConfig(enable_retry=True)

        class MockClient:
            def __init__(self):
                self.enterprise_config = enterprise_config
                self.call_count = 0

            @with_enterprise_retry
            async def test_method(self):
                self.call_count += 1
                return "success"

        client = MockClient()

        # act
        result = await client.test_method()

        # assert
        assert result == "success"
        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_with_enterprise_retry_disabled(self):
        """Test enterprise retry decorator when retry is disabled."""
        # arrange
        enterprise_config = EnterpriseConfig(enable_retry=False)

        class MockClient:
            def __init__(self):
                self.enterprise_config = enterprise_config
                self.call_count = 0

            @with_enterprise_retry
            async def test_method(self):
                self.call_count += 1
                return "success"

        client = MockClient()

        # act
        result = await client.test_method()

        # assert
        assert result == "success"
        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_with_enterprise_retry_no_config(self):
        """Test enterprise retry decorator when no enterprise config."""
        # arrange
        class MockClient:
            def __init__(self):
                self.call_count = 0

            @with_enterprise_retry
            async def test_method(self):
                self.call_count += 1
                return "success"

        client = MockClient()

        # act
        result = await client.test_method()

        # assert
        assert result == "success"
        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_with_enterprise_retry_with_exception(self):
        """Test enterprise retry decorator with retryable exception."""
        # arrange
        enterprise_config = EnterpriseConfig(enable_retry=True)

        class MockClient:
            def __init__(self):
                self.enterprise_config = enterprise_config
                self.call_count = 0

            @with_enterprise_retry
            async def test_method(self):
                self.call_count += 1
                if self.call_count < 3:
                    raise httpx.ConnectTimeout("Connection timeout")
                return "success"

        client = MockClient()

        # act
        result = await client.test_method()

        # assert
        assert result == "success"
        assert client.call_count == 3


class TestWithLlmRetry:
    """Test with_llm_retry decorator."""

    @pytest.mark.asyncio
    async def test_with_llm_retry_success(self):
        """Test LLM retry decorator success case."""
        # arrange
        call_count = 0

        @with_llm_retry
        async def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        # act
        result = await test_function()

        # assert
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_with_llm_retry_with_retryable_exception(self):
        """Test LLM retry decorator with retryable exception."""
        # arrange
        call_count = 0

        @with_llm_retry
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectTimeout("Connection timeout")
            return "success"

        # act
        result = await test_function()

        # assert
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_llm_retry_with_non_retryable_exception(self):
        """Test LLM retry decorator with non-retryable exception."""
        # arrange
        @with_llm_retry
        async def test_function():
            raise ValueError("Invalid value")

        # act & assert
        with pytest.raises(ValueError, match="Invalid value"):
            await test_function()
