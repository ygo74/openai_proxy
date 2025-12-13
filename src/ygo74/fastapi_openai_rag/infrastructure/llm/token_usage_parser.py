"""Token usage parser for extracting token counts from LLM provider responses.

This module provides utilities for parsing token usage information from different
LLM provider response formats (OpenAI, Azure OpenAI, Anthropic, etc.). It follows
the infrastructure layer pattern as it deals with external provider formats.

Usage:
    from infrastructure.llm.token_usage_parser import TokenUsageParser

    parser = TokenUsageParser()
    prompt_tokens, completion_tokens, total_tokens = parser.parse_response(response)
"""
from typing import Tuple, Optional, Any, Union
import logging

# Import OpenAI typed objects
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion import Completion
from openai.types.completion_usage import CompletionUsage

logger = logging.getLogger(__name__)


class TokenUsageParser:
    """Parser for extracting token usage from LLM provider responses.

    Supports multiple response formats:
    - OpenAI ChatCompletion
    - OpenAI ChatCompletionChunk (streaming)
    - OpenAI Completion
    - Azure OpenAI responses (same format as OpenAI)
    - Raw dictionaries with 'usage' key

    All providers follow the standard format:
    {
        "usage": {
            "prompt_tokens": int,
            "completion_tokens": int,
            "total_tokens": int
        }
    }
    """

    def parse_response(self,
                      response: Any,
                      default_if_missing: bool = True) -> Tuple[int, int, int]:
        """Parse token usage from any supported response format.

        Args:
            response: LLM provider response object
            default_if_missing: If True, return (0, 0, 0) when usage not found,
                              if False, return None values

        Returns:
            Tuple[int, int, int]: (prompt_tokens, completion_tokens, total_tokens)
                                 Returns (0, 0, 0) or (None, None, None) if not found

        Examples:
            >>> parser = TokenUsageParser()
            >>> prompt, completion, total = parser.parse_response(chat_completion)
            >>> print(f"Used {total} tokens: {prompt} prompt + {completion} completion")
        """
        try:
            # Try ChatCompletion format
            if isinstance(response, ChatCompletion):
                return self._parse_chat_completion(response, default_if_missing)

            # Try ChatCompletionChunk format (streaming)
            if isinstance(response, ChatCompletionChunk):
                return self._parse_chat_completion_chunk(response, default_if_missing)

            # Try Completion format
            if isinstance(response, Completion):
                return self._parse_completion(response, default_if_missing)

            # Try dictionary with 'usage' key
            if isinstance(response, dict):
                return self._parse_dict_response(response, default_if_missing)

            # Unknown format
            logger.warning(f"Unknown response type: {type(response)}, cannot parse token usage")
            return (0, 0, 0) if default_if_missing else (None, None, None)

        except Exception as e:
            logger.error(f"Error parsing token usage: {e}", exc_info=True)
            return (0, 0, 0) if default_if_missing else (None, None, None)

    def _parse_chat_completion(self,
                               response: ChatCompletion,
                               default_if_missing: bool) -> Tuple[int, int, int]:
        """Parse token usage from ChatCompletion response.

        Args:
            response: ChatCompletion object
            default_if_missing: Return (0, 0, 0) or (None, None, None) if missing

        Returns:
            Tuple[int, int, int]: (prompt_tokens, completion_tokens, total_tokens)
        """
        if not response.usage:
            logger.debug("No usage information in ChatCompletion response")
            return (0, 0, 0) if default_if_missing else (None, None, None)

        usage = response.usage
        return (
            usage.prompt_tokens or 0,
            usage.completion_tokens or 0,
            usage.total_tokens or 0
        )

    def _parse_chat_completion_chunk(self,
                                    chunk: ChatCompletionChunk,
                                    default_if_missing: bool) -> Tuple[int, int, int]:
        """Parse token usage from ChatCompletionChunk (streaming response).

        Note: Usage information is typically only present in the final chunk
        of a streaming response.

        Args:
            chunk: ChatCompletionChunk object
            default_if_missing: Return (0, 0, 0) or (None, None, None) if missing

        Returns:
            Tuple[int, int, int]: (prompt_tokens, completion_tokens, total_tokens)
        """
        if not chunk.usage:
            # This is normal for non-final chunks
            return (0, 0, 0) if default_if_missing else (None, None, None)

        usage = chunk.usage
        return (
            usage.prompt_tokens or 0,
            usage.completion_tokens or 0,
            usage.total_tokens or 0
        )

    def _parse_completion(self,
                         response: Completion,
                         default_if_missing: bool) -> Tuple[int, int, int]:
        """Parse token usage from Completion response.

        Args:
            response: Completion object
            default_if_missing: Return (0, 0, 0) or (None, None, None) if missing

        Returns:
            Tuple[int, int, int]: (prompt_tokens, completion_tokens, total_tokens)
        """
        if not response.usage:
            logger.debug("No usage information in Completion response")
            return (0, 0, 0) if default_if_missing else (None, None, None)

        usage = response.usage
        return (
            usage.prompt_tokens or 0,
            usage.completion_tokens or 0,
            usage.total_tokens or 0
        )

    def _parse_dict_response(self,
                            response: dict,
                            default_if_missing: bool) -> Tuple[int, int, int]:
        """Parse token usage from dictionary response.

        Supports responses with 'usage' key containing token counts.

        Args:
            response: Dictionary with 'usage' key
            default_if_missing: Return (0, 0, 0) or (None, None, None) if missing

        Returns:
            Tuple[int, int, int]: (prompt_tokens, completion_tokens, total_tokens)
        """
        usage = response.get('usage')
        if not usage:
            logger.debug("No 'usage' key in dictionary response")
            return (0, 0, 0) if default_if_missing else (None, None, None)

        # Handle both dict and CompletionUsage object
        if isinstance(usage, CompletionUsage):
            return (
                usage.prompt_tokens or 0,
                usage.completion_tokens or 0,
                usage.total_tokens or 0
            )

        # Handle raw dictionary
        return (
            usage.get('prompt_tokens', 0),
            usage.get('completion_tokens', 0),
            usage.get('total_tokens', 0)
        )

    def has_usage_info(self, response: Any) -> bool:
        """Check if response contains token usage information.

        Args:
            response: LLM provider response object

        Returns:
            bool: True if response contains usage information

        Examples:
            >>> parser = TokenUsageParser()
            >>> if parser.has_usage_info(response):
            ...     tokens = parser.parse_response(response)
        """
        try:
            if isinstance(response, (ChatCompletion, Completion)):
                return response.usage is not None

            if isinstance(response, ChatCompletionChunk):
                return response.usage is not None

            if isinstance(response, dict):
                return 'usage' in response and response['usage'] is not None

            return False

        except Exception as e:
            logger.error(f"Error checking usage info: {e}")
            return False


# Singleton instance for convenient access
_parser_instance: Optional[TokenUsageParser] = None


def get_token_usage_parser() -> TokenUsageParser:
    """Get singleton TokenUsageParser instance.

    Returns:
        TokenUsageParser: Shared parser instance

    Examples:
        >>> from infrastructure.llm.token_usage_parser import get_token_usage_parser
        >>> parser = get_token_usage_parser()
        >>> tokens = parser.parse_response(response)
    """
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = TokenUsageParser()
    return _parser_instance
