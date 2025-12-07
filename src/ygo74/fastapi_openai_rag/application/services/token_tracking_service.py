"""Service for tracking token usage across LLM interactions."""

from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
import uuid
import time
import logging
from contextlib import contextmanager

# Import OpenAI typed objects
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion import Completion
from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.responses.response_completed_event import ResponseCompletedEvent
from openai.types.completion_usage import CompletionUsage

# from openai.types.create_embedding_response import CreateEmbeddingResponse
from ...domain.models.embedding import CreateEmbeddingResponse

from ...domain.unit_of_work import UnitOfWork
from ...domain.models.autenticated_user import AuthenticatedUser
from ...domain.models.llm_model import LlmModel

from ...infrastructure.observability.metrics_service import get_metrics_service, MetricsService
from .token_usage_service import TokenUsageService
from .rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)

# Type aliases for supported response types
SupportedResponseType = Union[
    ChatCompletion,
    ChatCompletionChunk,
    Completion,
    OpenAIResponse,
    ResponseStreamEvent,
    CreateEmbeddingResponse
]

class TokenTrackingService:
    """Service for tracking token usage and metrics in LLM requests."""

    def __init__(self, uow: UnitOfWork):
        """Initialize token tracking service with dependencies.

        Args:
            uow: Unit of work for database transactions
        """
        self._uow = uow
        self._token_service = TokenUsageService(uow)
        self._rate_limit_service = RateLimitService(uow)
        self._metrics_service = get_metrics_service()


    def _extract_usage_from_chat_completion(self, response: ChatCompletion) -> Optional[Dict[str, int]]:
        """Extract token usage from ChatCompletion response.

        Args:
            response: ChatCompletion response object

        Returns:
            Dictionary with prompt_tokens, completion_tokens, and total_tokens
        """
        if not response.usage:
            return None

        usage = response.usage
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }

    def _extract_usage_from_chat_completion_chunk(self, chunk: ChatCompletionChunk) -> Optional[Dict[str, int]]:
        """Extract token usage from ChatCompletionChunk (typically only in final chunk).

        Args:
            chunk: ChatCompletionChunk object

        Returns:
            Dictionary with prompt_tokens, completion_tokens, and total_tokens
        """
        if not chunk.usage:
            return None

        usage = chunk.usage
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }

    def _extract_usage_from_completion(self, response: Completion) -> Optional[Dict[str, int]]:
        """Extract token usage from Completion response.

        Args:
            response: Completion response object

        Returns:
            Dictionary with prompt_tokens, completion_tokens, and total_tokens
        """
        if not response.usage:
            return None

        usage = response.usage
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }

    def _extract_usage_from_openai_response(self, response: OpenAIResponse) -> Optional[Dict[str, int]]:
        """Extract token usage from OpenAI Response object (Responses API).

        Args:
            response: OpenAI Response object

        Returns:
            Dictionary with prompt_tokens, completion_tokens, and total_tokens
        """
        if not response.usage:
            return None

        usage = response.usage
        # Response API uses input_tokens/output_tokens naming
        return {
            "prompt_tokens": usage.input_tokens,
            "completion_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens
        }

    def _extract_usage_from_stream_event(self, event: ResponseStreamEvent) -> Optional[Dict[str, int]]:
        """Extract token usage from ResponseStreamEvent.

        Args:
            event: ResponseStreamEvent object

        Returns:
            Dictionary with prompt_tokens, completion_tokens, and total_tokens
        """
        # Only response.completed events contain usage data
        if event.type != "response.completed":
            return None

        if not hasattr(event, 'response') or not event.response:
            return None

        return self._extract_usage_from_openai_response(event.response)

    def _extract_usage_from_embedding_response(self, response: CreateEmbeddingResponse) -> Optional[Dict[str, int]]:
        """Extract token usage from CreateEmbeddingResponse.

        Args:
            response: CreateEmbeddingResponse object

        Returns:
            Dictionary with prompt_tokens, completion_tokens (0), and total_tokens
        """
        if not response.usage:
            return None

        usage = response.usage
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": 0,  # Embeddings don't have completion tokens
            "total_tokens": usage.total_tokens
        }

    def extract_token_usage(self, response: SupportedResponseType) -> Optional[Dict[str, int]]:
        """Extract token usage information from a typed response object.

        Args:
            response: Typed response object from OpenAI SDK

        Returns:
            Optional[Dict[str, int]]: Dictionary with prompt_tokens, completion_tokens, and total_tokens,
                or None if usage information cannot be extracted
        """
        try:
            # Use isinstance for type-safe extraction
            if isinstance(response, ChatCompletion):
                return self._extract_usage_from_chat_completion(response)
            elif isinstance(response, ChatCompletionChunk):
                return self._extract_usage_from_chat_completion_chunk(response)
            elif isinstance(response, Completion):
                return self._extract_usage_from_completion(response)
            elif isinstance(response, OpenAIResponse):
                return self._extract_usage_from_openai_response(response)
            elif isinstance(response, ResponseCompletedEvent):
                return self._extract_usage_from_stream_event(response)
            elif isinstance(response, CreateEmbeddingResponse):
                return self._extract_usage_from_embedding_response(response)
            else:
                # Fallback to generic extraction for unknown types
                logger.warning(f"Unsupported response type for token extraction: {type(response)}")
                return self._extract_usage_generic(response)

        except Exception as e:
            logger.error(f"Error extracting token usage: {e}", exc_info=True)
            return None

    def _extract_usage_generic(self, response: Any) -> Optional[Dict[str, int]]:
        """Fallback generic extraction for untyped or unknown response objects.

        This method preserves backward compatibility with the original implementation.
        """
        # Fallback to the original getattr-based approach for unknown types
        response_type = type(response).__name__
        logger.debug(f"Using generic extraction for response type: {response_type}")

        # Check for usage attribute with various naming conventions
        if hasattr(response, "usage"):
            usage_obj = getattr(response, "usage")
            if not usage_obj:
                return None

            # Try different naming conventions
            if hasattr(usage_obj, "prompt_tokens") and hasattr(usage_obj, "completion_tokens"):
                return {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                    "total_tokens": getattr(usage_obj, "total_tokens",
                                          getattr(usage_obj, "prompt_tokens", 0) +
                                          getattr(usage_obj, "completion_tokens", 0))
                }
            elif hasattr(usage_obj, "input_tokens") and hasattr(usage_obj, "output_tokens"):
                return {
                    "prompt_tokens": getattr(usage_obj, "input_tokens", 0),
                    "completion_tokens": getattr(usage_obj, "output_tokens", 0),
                    "total_tokens": getattr(usage_obj, "total_tokens",
                                          getattr(usage_obj, "input_tokens", 0) +
                                          getattr(usage_obj, "output_tokens", 0))
                }

        # Dictionary-based fallback
        if isinstance(response, dict):
            if "usage" in response:
                usage_dict = response["usage"]
                if isinstance(usage_dict, dict):
                    if "prompt_tokens" in usage_dict and "completion_tokens" in usage_dict:
                        return {
                            "prompt_tokens": usage_dict.get("prompt_tokens", 0),
                            "completion_tokens": usage_dict.get("completion_tokens", 0),
                            "total_tokens": usage_dict.get("total_tokens",
                                                         usage_dict.get("prompt_tokens", 0) +
                                                         usage_dict.get("completion_tokens", 0))
                        }

        logger.debug(f"Could not extract token usage from response type: {response_type}")
        return None

    def _extract_model_name(self, response: SupportedResponseType, fallback_model: Optional[str] = None) -> str:
        """Extract model name from typed response object.

        Args:
            response: Typed response object
            fallback_model: Fallback model name if not found in response

        Returns:
            Model name from response or fallback
        """
        try:
            if isinstance(response, (ChatCompletion, ChatCompletionChunk, Completion, OpenAIResponse, CreateEmbeddingResponse)):
                return response.model
            elif isinstance(response, ResponseStreamEvent):
                if hasattr(response, 'response') and response.response:
                    return response.response.model

            # Generic fallback
            if hasattr(response, 'model'):
                return str(getattr(response, 'model'))
            elif isinstance(response, dict) and 'model' in response:
                return str(response['model'])

        except Exception as e:
            logger.debug(f"Error extracting model name: {e}")

        return fallback_model or "unknown"

    def track_completion(self,
                        response: SupportedResponseType,
                        user: AuthenticatedUser,
                        endpoint: str,
                        model: LlmModel,
                        start_time: Optional[float] = None,
                        success: bool = True) -> None:
        """Track token usage for a completion response.

        Args:
            response: Typed LLM response object
            user: Authenticated user
            endpoint: API endpoint path
            model: Optional model name (will be extracted from response if not provided)
            start_time: Optional start time of request (for duration calculation)
            success: Whether the request was successful
        """
        try:
            # Extract model name from response if not provided
            model_name = model.name or self._extract_model_name(response, "unknown")

            # Calculate duration if start time was provided
            duration = 0.0
            if start_time is not None:
                duration = time.time() - start_time

            # Generate request ID
            request_id = str(uuid.uuid4())

            # Extract token usage information using typed methods
            token_usage = self.extract_token_usage(response)

            if token_usage is None:
                logger.debug(f"No token usage information could be extracted from response for model {model_name}")
                return

            # Get token counts
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)

            # Record token usage in database
            user_id = user.username or "anonymous"

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

            # Record token consumption in rate limit counters
            self._record_rate_limit_usage(user, model, total_tokens)

            logger.info(f"Recorded token usage for user {user_id}: {total_tokens} tokens on {endpoint}")

        except Exception as e:
            logger.error(f"Error recording token usage: {str(e)}", exc_info=True)

    def _record_rate_limit_usage(self, user: AuthenticatedUser, model: LlmModel, token_count: int) -> None:
        """Record token consumption in rate limit counters following the same hierarchy as checks.

        Records consumption for:
        1. Group/Model scopes (for authorized groups)
        2. Global scope (if no group/model limits exist)
        3. Model scope (aggregated across all users)

        Args:
            user: Authenticated user
            model: LLM model being used
            token_count: Number of tokens consumed
        """
        try:
            user_id = user.username

            # Get authorized groups for this model
            authorized_groups = []
            if model and model.groups:
                model_group_names = {g.name for g in model.groups}
                authorized_groups = [g for g in user.groups if g in model_group_names]

            # 1. Record for group/model scopes (user quota)
            group_model_recorded = False
            if model and model.id and authorized_groups:
                for group_id in authorized_groups:
                    scope_id = f"{group_id}:{model.id}"
                    rate_limit = self._rate_limit_service.get_rate_limit_config("group_model", scope_id)
                    if rate_limit and rate_limit.enabled:
                        try:
                            self._rate_limit_service.record_token_usage("group_model", scope_id, user_id, token_count)
                            logger.debug(f"Recorded {token_count} tokens for group/model {scope_id}, user {user_id}")
                            group_model_recorded = True
                        except Exception as e:
                            logger.debug(f"Failed to record tokens for group/model {scope_id}: {e}")

            # 2. Record for global scope (fallback if no group/model)
            if not group_model_recorded:
                global_limit = self._rate_limit_service.get_rate_limit_config("global", None)
                if global_limit and global_limit.enabled:
                    try:
                        self._rate_limit_service.record_token_usage("global", None, user_id, token_count)
                        logger.debug(f"Recorded {token_count} tokens for global scope, user {user_id}")
                    except Exception as e:
                        logger.debug(f"Failed to record tokens for global scope: {e}")

            # 3. Record for model scope (aggregate all users)
            if model and model.id:
                model_limit = self._rate_limit_service.get_rate_limit_config("model", str(model.id))
                if model_limit and model_limit.enabled:
                    try:
                        # Model-level uses empty user_id to aggregate ALL users
                        self._rate_limit_service.record_token_usage("model", str(model.id), "", token_count)
                        logger.debug(f"Recorded {token_count} tokens for model {model.name} (aggregate)")
                    except Exception as e:
                        logger.debug(f"Failed to record tokens for model scope: {e}")

        except Exception as e:
            logger.error(f"Error recording rate limit usage: {e}", exc_info=True)

    def track_stream_completion(self,
                               event: ResponseStreamEvent,
                               user: AuthenticatedUser,
                               endpoint: str,
                               model: LlmModel,
                               start_time: Optional[float] = None) -> bool:
        """Track token usage from a stream completion event.

        This method should be called for each event that might contain usage data.
        It will only record usage when appropriate usage information is found.

        Args:
            event: ResponseStreamEvent that may contain usage information
            user: Authenticated user
            endpoint: API endpoint path
            model: Model name
            start_time: Optional start time of request (for duration calculation)

        Returns:
            bool: True if token usage was successfully tracked, False otherwise
        """
        try:
            # Only process response.completed events
            if event.type != "response.completed":
                return False

            # Check if this event has usage data
            if not hasattr(event, 'response') or not event.response:
                return False

            # Track the completion with the response object
            self.track_completion(
                response=event,
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
                                   chunk: ChatCompletionChunk,
                                   user: AuthenticatedUser,
                                   endpoint: str,
                                   model: LlmModel,
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
            # Check if this chunk has usage information (typically only final chunk)
            if not chunk.usage:
                return False

            # Track the completion with the chunk object
            self.track_completion(
                response=chunk,
                user=user,
                endpoint=endpoint,
                model=model,
                start_time=start_time,
                success=True
            )

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