"""Unique AI proxy client for Unique's API."""
import json
import time
import uuid
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List, Union
from datetime import datetime, timezone

import unique_sdk
from unique_sdk import ChatCompletion, Integrated

from ....domain.models.chat_completion import (
    ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatCompletionStreamChoice,
    ChatCompletionStreamResponse, ChatMessage
)
from ....domain.models.completion import (
    CompletionRequest, CompletionResponse, CompletionChoice
)
from ....domain.models.llm import LLMProvider, TokenUsage
from ....domain.protocols.llm_client import LLMClientProtocol
from ..http_client_factory import HttpClientFactory
from ..retry_handler import with_enterprise_retry, LLMRetryHandler
from ..enterprise_config import EnterpriseConfig
import logging

logger = logging.getLogger(__name__)

class UniqueProxyClient(LLMClientProtocol):
    """Unique AI proxy client with SDK integration for Unique's API."""

    def __init__(self, api_key: str, app_id: str,company_id: str,
                 user_id: str,
                 base_url: str,
                 enterprise_config: Optional[EnterpriseConfig] = None):
        """Initialize Unique proxy client with enterprise configuration.

        Args:
            api_key (str): API key for authentication
            company_id (str): Company ID for Unique API calls
            user_id (Optional[str]): Default user ID for API calls
            base_url (Optional[str]): Base URL for the Unique API (if different from default)
            provider (LLMProvider): Provider type (defaults to UNIQUE)
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration
        """
        self.api_key = api_key
        self.app_id = app_id
        self.company_id = company_id
        self.user_id = user_id
        self.base_url = base_url
        self.provider = LLMProvider.UNIQUE

        # Use default enterprise config if none provided
        if enterprise_config is None:
            enterprise_config = EnterpriseConfig()

        self.enterprise_config = enterprise_config

        # Initialize the Unique SDK
        self._initialize_sdk()

        logger.debug(f"UniqueProxyClient initialized for {self.provider}, company ID: {company_id}")

    def _initialize_sdk(self):
        """Initialize the Unique SDK with the provided configuration."""
        # Set API key for the SDK
        unique_sdk.api_key = self.api_key
        unique_sdk.app_id = self.app_id
        unique_sdk.api_base = self.base_url

        logger.debug("Unique SDK initialized with API key and configuration")

    @with_enterprise_retry
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Create chat completion via Unique API with retry resilience.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Returns:
            ChatCompletionResponse: Generated response

        Raises:
            Exception: If API request fails after all retries
        """
        start_time = time.time()

        # Convert domain model request to Unique SDK format
        unique_messages = self._convert_messages_for_unique(request.messages)
        model = request.model

        # Prepare options object with temperature and other parameters
        options = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature

        # Add other parameters if they're specified
        for param_name in ["top_p", "max_tokens", "frequency_penalty", "presence_penalty"]:
            param_value = getattr(request, param_name, None)
            if param_value is not None:
                options[param_name] = param_value

        logger.info(f"Making Unique chat completion request for model: {model}")
        logger.debug(f"Request options: {options}")

        try:
            # Call the Unique SDK
            response = await ChatCompletion.create_async(
                company_id=self.company_id,
                user_id=self.user_id,
                model=model,
                messages=unique_messages,
                timeout=int(request.timeout * 1000) if request.timeout else None,  # Convert seconds to ms
                **options
            )

            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"Chat completion request completed in {latency_ms:.2f} ms")

            # Convert SDK response to domain model
            return self._parse_chat_response(response, latency_ms)

        except Exception as e:
            logger.error(f"Error in Unique chat completion: {str(e)}")
            raise

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Stream chat completion via Unique API - simulated streaming since Unique doesn't support native streaming.

        Args:
            request (ChatCompletionRequest): Chat completion request

        Yields:
            ChatCompletionStreamResponse: Simulated streaming response chunks
        """
        start_time = time.time()
        logger.debug(f"Starting simulated streaming for Unique model: {request.model}")

        try:
            # Get the complete chat completion response first
            complete_response = await self.chat_completion(request)

            # Extract content from the response (usually from the first choice)
            if not complete_response.choices or not complete_response.choices[0].message.content:
                logger.warning("No content found in Unique response to stream")
                return

            full_content = complete_response.choices[0].message.content
            response_id = complete_response.id
            model = complete_response.model

            # Generate a unique ID if none in response
            if not response_id:
                response_id = str(uuid.uuid4())

            # Create chunks by character - could be adjusted to split by sentences/tokens
            # Different chunk sizes for better streaming simulation
            content_length = len(full_content)

            # Calculate a reasonable chunk size based on content length
            # Shorter content = smaller chunks for smoother appearance
            if content_length < 100:
                chunk_size = 4  # Very small chunks for short content
            elif content_length < 500:
                chunk_size = 10  # Small chunks for medium content
            else:
                chunk_size = 20  # Larger chunks for long content

            # Ensure at least 5 chunks for smooth appearance
            chunk_size = min(chunk_size, max(1, content_length // 5))

            logger.debug(f"Simulating stream with content length {content_length} using chunk size {chunk_size}")

            content_so_far = ""
            position = 0

            # Stream chunks with a small delay to simulate real-time generation
            while position < content_length:
                # Calculate end position for this chunk (don't exceed content length)
                end_pos = min(position + chunk_size, content_length)

                # Extract chunk content
                delta_content = full_content[position:end_pos]
                content_so_far += delta_content
                position = end_pos

                # Calculate finish reason - only set on last chunk
                finish_reason = "stop" if position == content_length else None

                # Calculate latency
                current_latency_ms = (time.time() - start_time) * 1000

                # Create and yield stream chunk
                stream_chunk = self._create_stream_chunk(
                    response_id,
                    model,
                    delta_content,
                    finish_reason,
                    current_latency_ms
                )

                yield stream_chunk


            logger.info(f"Simulated streaming finished in {(time.time() - start_time) * 1000:.2f}ms")

        except Exception as e:
            logger.error(f"Error in simulated streaming for Unique: {str(e)}")
            raise

    @with_enterprise_retry
    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """Create text completion by converting to chat completion.

        Args:
            request (CompletionRequest): Text completion request

        Returns:
            CompletionResponse: Generated response converted from chat completion
        """
        # Unique doesn't have a direct text completion endpoint, so convert to chat
        logger.info(f"Converting text completion to chat for Unique model: {request.model}")

        # Create a chat completion request from the text completion request
        messages = [ChatMessage(role="user", content=prompt) if isinstance(prompt, str)
                   else ChatMessage(role="user", content="\n".join(prompt))
                   for prompt in ([request.prompt] if isinstance(request.prompt, str)
                                  else request.prompt)]

        chat_request = ChatCompletionRequest(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
            stream=False,
            user=request.user
        )

        # Get the chat completion response
        chat_response = await self.chat_completion(chat_request)

        # Convert to a text completion response
        return self._convert_chat_to_completion_response(chat_response)

    def _convert_messages_for_unique(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert domain model messages to Unique SDK format.

        Args:
            messages (List[ChatMessage]): Domain model messages

        Returns:
            List[Dict[str, Any]]: Messages in Unique format
        """
        unique_messages = []
        for msg in messages:
            message_dict = msg.model_dump(exclude_none=True)

            # Add name if available
            if hasattr(msg, 'name') and msg.name:
                message_dict["name"] = msg.name

            # Add function call if available (may need adaptation for Unique's format)
            if msg.function_call:
                message_dict["function_call"] = msg.function_call

            # Add tool calls if available (may need adaptation for Unique's format)
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls

            unique_messages.append(message_dict)

        return unique_messages

    def _parse_chat_response(self, response_data: Any, latency_ms: float) -> ChatCompletionResponse:
        """Parse Unique chat completion response to domain model.

        Args:
            response_data (Any): SDK response object or dictionary
            latency_ms (float): Request latency

        Returns:
            ChatCompletionResponse: Domain response
        """
        # Convert response to dictionary if it's not already
        if not isinstance(response_data, dict):
            response_dict = response_data.__dict__ if hasattr(response_data, '__dict__') else {}
        else:
            response_dict = response_data

        print(response_dict)
        # Extract and format choices
        choices = []
        response_choices = response_dict.get('choices', [])
        for idx, choice_data in enumerate(response_choices):
            # Extract message content from the choice
            message_data = choice_data.get('message', {})

            # Create a message object
            message = ChatMessage(
                role=message_data.get('role', 'assistant'),
                content=message_data.get('content', ''),
                # Include other fields if present
                function_call=message_data.get('function_call'),
                tool_calls=message_data.get('tool_calls')
            )

            # Create a choice object
            choice = ChatCompletionChoice(
                index=choice_data.get('index', idx),
                message=message,
                finish_reason=choice_data.get('finish_reason', 'stop')
            )

            choices.append(choice)

        # Extract token usage from response if available
        usage_data = response_dict.get('usage', {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get('promptTokens', 0),  # Utilisation de promptTokens de l'API Unique
            completion_tokens=usage_data.get('completionTokens', 0),  # Utilisation de completionTokens de l'API Unique
            total_tokens=usage_data.get('totalTokens', 0)  # Utilisation de totalTokens de l'API Unique
        )

        # Create and return the response
        return ChatCompletionResponse(
            id=response_dict.get('id', str(uuid.uuid4())),
            object="chat.completion",
            created=int(time.time()),
            model=response_dict.get('model', ''),
            choices=choices,
            usage=usage,
            provider=self.provider,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc),
            raw_response=response_dict
        )

    def _create_stream_chunk(self, response_id: str, model: str, content: str,
                             finish_reason: Optional[str], latency_ms: float) -> ChatCompletionStreamResponse:
        """Create a streaming response chunk.

        Args:
            response_id (str): Response ID
            model (str): Model name
            content (str): Content delta
            finish_reason (Optional[str]): Finish reason if any
            latency_ms (float): Latency in milliseconds

        Returns:
            ChatCompletionStreamResponse: Stream chunk response
        """
        # Create a delta message with the content
        delta = ChatMessage(
            role="assistant",
            content=content,
        )

        # Create a choice with the delta
        choice = ChatCompletionStreamChoice(
            index=0,
            delta=delta,
            finish_reason=finish_reason
        )

        # Create and return the stream response
        return ChatCompletionStreamResponse(
            id=response_id,
            object="chat.completion.chunk",
            created=int(time.time()),
            model=model,
            choices=[choice],
            provider=self.provider,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc),
            raw_response={"delta": content, "finish_reason": finish_reason}
        )

    def _convert_chat_to_completion_response(self, chat_response: ChatCompletionResponse) -> CompletionResponse:
        """Convert chat completion response to text completion response.

        Args:
            chat_response (ChatCompletionResponse): Chat completion response

        Returns:
            CompletionResponse: Text completion response
        """
        # Extract text from the first choice's message content
        choices = []
        for idx, chat_choice in enumerate(chat_response.choices):
            choice = CompletionChoice(
                text=chat_choice.message.content or "",
                index=chat_choice.index,
                logprobs=None,  # Chat completions don't provide logprobs
                finish_reason=chat_choice.finish_reason
            )
            choices.append(choice)

        # Create and return the completion response
        return CompletionResponse(
            id=chat_response.id,
            object="text_completion",
            created=chat_response.created,
            model=chat_response.model,
            system_fingerprint=chat_response.system_fingerprint,
            choices=choices,
            usage=chat_response.usage,
            provider=chat_response.provider,
            latency_ms=chat_response.latency_ms,
            timestamp=chat_response.timestamp,
            raw_response=chat_response.raw_response
        )

    @with_enterprise_retry
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Azure OpenAI API with retry resilience.

        Returns:
            List[Dict[str, Any]]: List of available models

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        return []

    @with_enterprise_retry
    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployed models from Azure using Management API or fallback to models endpoint with retry.

        Returns:
            List[Dict[str, Any]]: List of deployed models with deployment info

        Raises:
            httpx.HTTPError: If API request fails after all retries
        """
        return []
