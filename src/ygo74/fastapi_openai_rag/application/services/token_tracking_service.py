"""Service for tracking token usage across LLM interactions."""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import time
import logging
from contextlib import contextmanager

from ...domain.unit_of_work import UnitOfWork
from ...domain.models.autenticated_user import AuthenticatedUser
from ...infrastructure.observability.metrics_service import get_metrics_service, MetricsService
from .token_usage_service import TokenUsageService

logger = logging.getLogger(__name__)

class TokenTrackingService:
    """Service for tracking token usage and metrics in LLM requests."""

    def __init__(self, uow: UnitOfWork):
        """Initialize token tracking service with dependencies.

        Args:
            uow: Unit of work for database transactions
        """
        self._uow = uow
        self._token_service = TokenUsageService(uow)
        self._metrics_service = get_metrics_service()

    def extract_token_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """Extract token usage information from a response object or dictionary.

        Handles different response types with their specific token usage property names:
        - Response: input_tokens, output_tokens, total_tokens
        - ChatCompletionResponse/CompletionResponse: prompt_tokens, completion_tokens, total_tokens
        - Dictionary variants of both

        Args:
            response: Response object or dictionary from LLM API

        Returns:
            Optional[Dict[str, int]]: Dictionary with prompt_tokens, completion_tokens, and total_tokens,
                or None if usage information cannot be extracted
        """
        # Check the type of response
        response_type = type(response).__name__
        logger.debug(f"Extracting token usage from response type: {response_type}")

        # Case 1: Response object from OpenAI responses API
        if response_type == "Response" or response_type.startswith("Response"):
            # OpenAI responses API uses input_tokens and output_tokens
            if hasattr(response, "usage"):
                usage_obj = getattr(response, "usage")
                if usage_obj:
                    input_tokens = getattr(usage_obj, "input_tokens", 0)
                    output_tokens = getattr(usage_obj, "output_tokens", 0)
                    total_tokens = getattr(usage_obj, "total_tokens", input_tokens + output_tokens)
                    return {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": total_tokens
                    }

        # Case 2: ChatCompletionResponse or CompletionResponse
        if response_type in ["ChatCompletionResponse", "CompletionResponse"]:
            if hasattr(response, "usage"):
                usage_obj = getattr(response, "usage")
                if usage_obj:
                    prompt_tokens = getattr(usage_obj, "prompt_tokens", 0)
                    completion_tokens = getattr(usage_obj, "completion_tokens", 0)
                    total_tokens = getattr(usage_obj, "total_tokens", prompt_tokens + completion_tokens)
                    return {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }

        # Case 3: Direct object with usage attribute but non-standard type
        if hasattr(response, "usage"):
            usage_obj = getattr(response, "usage")
            if usage_obj:
                # Try both naming conventions
                # First prompt/completion naming
                if hasattr(usage_obj, "prompt_tokens") and hasattr(usage_obj, "completion_tokens"):
                    return {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                        "total_tokens": getattr(usage_obj, "total_tokens",
                                              getattr(usage_obj, "prompt_tokens", 0) +
                                              getattr(usage_obj, "completion_tokens", 0))
                    }
                # Then input/output naming
                elif hasattr(usage_obj, "input_tokens") and hasattr(usage_obj, "output_tokens"):
                    return {
                        "prompt_tokens": getattr(usage_obj, "input_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "output_tokens", 0),
                        "total_tokens": getattr(usage_obj, "total_tokens",
                                              getattr(usage_obj, "input_tokens", 0) +
                                              getattr(usage_obj, "output_tokens", 0))
                    }

        # Case 4: Dictionary-based response
        if isinstance(response, dict):
            # Direct usage in dictionary format
            if "usage" in response:
                usage_dict = response["usage"]
                if isinstance(usage_dict, dict):
                    # Try both naming conventions for dictionary
                    if "prompt_tokens" in usage_dict and "completion_tokens" in usage_dict:
                        return {
                            "prompt_tokens": usage_dict.get("prompt_tokens", 0),
                            "completion_tokens": usage_dict.get("completion_tokens", 0),
                            "total_tokens": usage_dict.get("total_tokens",
                                                         usage_dict.get("prompt_tokens", 0) +
                                                         usage_dict.get("completion_tokens", 0))
                        }
                    elif "input_tokens" in usage_dict and "output_tokens" in usage_dict:
                        return {
                            "prompt_tokens": usage_dict.get("input_tokens", 0),
                            "completion_tokens": usage_dict.get("output_tokens", 0),
                            "total_tokens": usage_dict.get("total_tokens",
                                                         usage_dict.get("input_tokens", 0) +
                                                         usage_dict.get("output_tokens", 0))
                        }

            # Direct top-level token properties in Response
            if "input_tokens" in response and "output_tokens" in response:
                return {
                    "prompt_tokens": response.get("input_tokens", 0),
                    "completion_tokens": response.get("output_tokens", 0),
                    "total_tokens": response.get("total_tokens",
                                               response.get("input_tokens", 0) +
                                               response.get("output_tokens", 0))
                }

        logger.debug(f"Could not extract token usage from response type: {response_type}")
        return None

    def track_completion(self,
                        response: Any,
                        user: AuthenticatedUser,
                        endpoint: str,
                        model: Optional[str] = None,
                        start_time: Optional[float] = None,
                        success: bool = True) -> None:
        """Track token usage for a completion response.

        Args:
            response: LLM response object
            user: Authenticated user
            endpoint: API endpoint path
            model: Optional model name (will be extracted from response if not provided)
            start_time: Optional start time of request (for duration calculation)
            success: Whether the request was successful
        """
        try:
            # Extract model name from response if not provided
            model_name = model or "unknown"
            if not model and hasattr(response, "model"):
                model_name = str(getattr(response, "model", model_name))
            elif not model and isinstance(response, dict) and "model" in response:
                model_name = str(response.get("model", model_name))

            # Calculate duration if start time was provided
            duration = 0.0
            if start_time is not None:
                duration = time.time() - start_time

            # Generate request ID
            request_id = str(uuid.uuid4())

            # Extract token usage information
            token_usage = self.extract_token_usage(response)

            if token_usage is None:
                logger.debug(f"No token usage information could be extracted from response for model {model_name}")
                return

            # Get token counts
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)

            # Record token usage in database
            user_id = getattr(user, "username", "anonymous")
            if user_id is None:
                user_id = "anonymous"

            # Record in database
            self._token_service.record_token_usage(
                user_id=user_id,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                endpoint=endpoint,
                request_id=request_id
            )

            # Record metrics if available
            if self._metrics_service:
                self._metrics_service.record_llm_request(
                    model=model_name,
                    tokens_in=prompt_tokens,
                    tokens_out=completion_tokens,
                    duration=duration,
                    success=success
                )

            logger.info(f"Recorded token usage for user {user_id}: {total_tokens} tokens on {endpoint}")

        except Exception as e:
            logger.error(f"Error recording token usage: {str(e)}", exc_info=True)

    def track_stream_completion(self,
                               event: Any,
                               user: AuthenticatedUser,
                               endpoint: str,
                               model: str,
                               start_time: Optional[float] = None) -> bool:
        """Track token usage from a stream completion event.

        This method should be called for each event that might contain usage data.
        It will only record usage when appropriate usage information is found.

        Args:
            event: Stream event that may contain usage information
            user: Authenticated user
            endpoint: API endpoint path
            model: Model name
            start_time: Optional start time of request (for duration calculation)

        Returns:
            bool: True if token usage was successfully tracked, False otherwise
        """
        try:
            # For response.completed events, check for usage data
            event_type = getattr(event, "type", None)

            # Skip events that don't contain token usage
            if event_type != "response.completed":
                return False

            # Check if this event has usage data
            response_obj = getattr(event, "response", None)
            if not response_obj:
                return False

            # Calculate duration if start time was provided
            duration = 0.0
            if start_time is not None:
                duration = time.time() - start_time

            # Track the completion with the response object
            self.track_completion(
                response=response_obj,
                user=user,
                endpoint=endpoint,
                model=model,
                start_time=start_time,
                success=True
            )

            return True

        except Exception as e:
            logger.error(f"Error tracking stream token usage: {str(e)}", exc_info=True)
            return False

    def track_chat_completion_chunk(self,
                                   chunk: Any,
                                   user: AuthenticatedUser,
                                   endpoint: str,
                                   model: str,
                                   start_time: Optional[float] = None) -> bool:
        """Track token usage from a chat completion stream chunk.

        Specifically handles chunks of type ChatCompletionChunk, which have
        a different structure than response stream events.

        Args:
            chunk: ChatCompletionChunk that may contain usage information
            user: Authenticated user
            endpoint: API endpoint path
            model: Model name
            start_time: Optional start time of request (for duration calculation)

        Returns:
            bool: True if token usage was successfully tracked, False otherwise
        """
        try:
            # Check if this is the final chunk with usage information
            # In chat completion chunks, usage is typically included in the final chunk
            if not hasattr(chunk, "usage") or not chunk.usage:
                return False

            # Extract usage data
            usage = chunk.usage

            # Calculate duration if start time was provided
            duration = 0.0
            if start_time is not None:
                duration = time.time() - start_time

            # Generate request ID
            request_id = str(uuid.uuid4())

            # Get token counts from ChatCompletionChunk usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
            total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens)

            # Record token usage in database
            user_id = getattr(user, "username", "anonymous")
            if user_id is None:
                user_id = "anonymous"

            # Record in database
            self._token_service.record_token_usage(
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                endpoint=endpoint,
                request_id=request_id
            )

            # Record metrics if available
            if self._metrics_service:
                self._metrics_service.record_llm_request(
                    model=model,
                    tokens_in=prompt_tokens,
                    tokens_out=completion_tokens,
                    duration=duration,
                    success=True
                )

            logger.info(f"Recorded chat completion chunk token usage for user {user_id}: {total_tokens} tokens on {endpoint}")
            return True

        except Exception as e:
            logger.error(f"Error tracking chat completion chunk token usage: {str(e)}", exc_info=True)
            return False

    @contextmanager
    def track_request_in_progress(self, model: str):
        """Context manager for tracking in-progress requests.

        Args:
            model: Name of the model being used

        Yields:
            None
        """
        if self._metrics_service:
            with self._metrics_service.track_llm_request_in_progress(model):
                yield
        else:
            yield