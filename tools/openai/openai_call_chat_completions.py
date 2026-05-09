#!/usr/bin/env python3
"""Native OpenAI SDK test script for Chat Completions API.

This script tests the /v1/chat/completions endpoint using the native OpenAI SDK
to validate proxy functionality and compare with the Responses API implementation.

Features tested:
- Basic text chat completions
- Multimodal input (images)
- Function calling with tool execution
- Streaming responses
- Multi-turn conversations
- Response format control (JSON)

Usage examples:
python openai_call_chat_completions.py --env-file ../.env --question "What is 2+2?"
python openai_call_chat_completions.py --env-file ../.env_azure --question "What time is it in Paris?" --function-tools --auto-execute
python openai_call_chat_completions.py --question "Latest tech news" --stream
python openai_call_chat_completions.py --question "Hi, I'm Alice" --follow-up "What's my name?"
python openai_call_chat_completions.py --question "Describe this image" --file-path ./image.jpg

Environment variables (loaded from .env file or shell):
  OPENAI_API_BASE   - Base URL for the API (e.g. http://localhost:8000/v1)
  OPENAI_API_KEY    - API key for authentication
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from mimetypes import guess_type
from typing import Any, Dict, List, Optional, Union, cast

from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("chat_completions_api_openai_test")

# File type constants
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}

# Time zone mapping for function calling
TIMEZONE_DATA: Dict[str, str] = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris",
    "london": "Europe/London",
    "new york": "America/New_York",
}


def get_current_time_tool(location: str) -> str:
    """Get current time for a given location (for function calling)."""
    logger.info(f"Called get_current_time_tool with location: {location}")
    loc = location.lower().strip()
    for key, tz in TIMEZONE_DATA.items():
        if key in loc:
            try:
                from zoneinfo import ZoneInfo
                from datetime import datetime as dt
                current = dt.now(ZoneInfo(tz)).strftime("%H:%M")
                return json.dumps({"location": location, "current_time": current})
            except Exception:
                break
    return json.dumps({"location": location, "current_time": "unknown"})


# ---------------- Utility Functions ---------------- #

def _handle_stream(stream: Any, args: argparse.Namespace) -> Optional[ChatCompletionMessage]:
    """Handle streaming chat completion chunks consistently."""
    full_content = ""
    final_message: Optional[ChatCompletionMessage] = None

    for chunk in stream:
        if args.verbose:
            logger.debug(f"Stream chunk: {chunk}")

        if len(chunk.choices) == 0:
            continue

        delta = chunk.choices[0].delta

        # Handle content delta
        if delta.content:
            print(delta.content, end="|", flush=True)
            full_content += delta.content

        # Save final message with complete content
        if chunk.choices[0].finish_reason:
            # Create a complete message object from accumulated content
            final_message = ChatCompletionMessage(
                role="assistant",
                content=full_content,
                function_call=None,
                tool_calls=None
            )

    print()  # Ensure we end with a newline
    return final_message


def file_to_data_url(path: str) -> str:
    """Convert file to data URL for multimodal input."""
    mime, _ = guess_type(path)
    if mime is None:
        mime = "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_messages(question: str, file_path: Optional[str] = None,
                  system_message: Optional[str] = None,
                  previous_messages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Build messages array for Chat Completions API.

    Args:
        question (str): User question/prompt
        file_path (Optional[str]): Path to image or PDF file
        system_message (Optional[str]): System message
        previous_messages (Optional[List[Dict[str, Any]]]): Previous conversation messages

    Returns:
        List[Dict[str, Any]]: Messages array for Chat Completions API
    """
    messages = []

    # Add system message if provided
    if system_message:
        messages.append({"role": "system", "content": system_message})

    # Add previous conversation messages if provided
    if previous_messages:
        messages.extend(previous_messages)

    # Create user message with text content
    if not file_path:
        messages.append({"role": "user", "content": question})
    else:
        # Create multimodal content with image or PDF
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(file_path.lower())

            if ext in IMAGE_EXTENSIONS:
                # Handle image files
                data_url = file_to_data_url(file_path)
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                                "detail": "auto"
                            }
                        }
                    ]
                })
            elif ext in PDF_EXTENSIONS:
                # Handle PDF files
                data_url = file_to_data_url(file_path)
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "file",  # Some models use image_url for PDFs
                            "file": {
                                "filename": os.path.basename(file_path),
                                "file_data": data_url
                            }
                        }
                    ]
                })
            else:
                raise ValueError(f"Unsupported file extension: {ext}. Supported: {IMAGE_EXTENSIONS | PDF_EXTENSIONS}")
        else:
            raise FileNotFoundError(f"File not found: {file_path}")

    return messages


def build_function_tools() -> List[Dict[str, Any]]:
    """Build function tool definitions for Chat Completions API format."""
    return [{
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get current local time for a given location (city name).",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or location name (e.g., Paris, Tokyo, New York)"
                    },
                },
                "required": ["location"]
            }
        }
    }]


def execute_function_calls(name: str, args_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """Execute function calls locally based on name and argument string."""
    try:
        args = json.loads(args_str)
        if name == "get_current_time":
            return get_current_time_tool(**args)
    except Exception as e:
        logger.error(f"Error executing function {name}: {e}")

    return None


def print_usage_info(completion: ChatCompletion) -> None:
    """Print token usage information."""
    if hasattr(completion, 'usage') and completion.usage:
        usage = completion.usage
        logger.info(f"Token usage - Prompt: {usage.prompt_tokens}, "
                   f"Completion: {usage.completion_tokens}, "
                   f"Total: {usage.total_tokens}")


# ---------------- Test Functions ---------------- #

def test_basic_chat(client: OpenAI, args: argparse.Namespace) -> Optional[ChatCompletion]:
    """Test basic chat completion functionality."""
    logger.info("=== Testing Basic Chat Completion ===")

    messages = build_messages(
        args.question,
        args.file_path,
        args.system_message
    )

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": args.stream,
        "extra_body": {"timeout": 120}
    }

    # Add response format if JSON is requested
    if args.json_response:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        if args.stream:
            # Handle streaming
            stream = client.chat.completions.create(**kwargs)
            print(f"\n=== Chat Completion (Streaming) ===")
            _handle_stream(stream, args)
            # We can't easily return the complete ChatCompletion object from streaming
            return None
        else:
            # Handle non-streaming
            start_time = time.time()
            completion = client.chat.completions.create(**kwargs)
            end_time = time.time()
            process_time = (end_time - start_time) * 1000  # Convert to
            print(f"API call completed in {process_time:.2f} ms")
            print(f"\n=== Chat Completion (Non-Streaming) ===")
            print(completion.choices[0].message.content)
            print_usage_info(completion)
            return completion

    except Exception as e:
        logger.error(f"Basic chat completion failed: {e}")
        return None


def test_function_calling(client: OpenAI, args: argparse.Namespace) -> Optional[ChatCompletion]:
    """Test function calling functionality."""
    logger.info("=== Testing Function Calling ===")

    messages = build_messages(args.question, args.file_path, args.system_message)
    function_tools = build_function_tools()

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "tools": function_tools,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": False  # Disable streaming for function calling
    }

    # Configure tool choice
    if args.force_tools:
        kwargs["tool_choice"] = "required"
    else:
        kwargs["tool_choice"] = "auto"

    try:
        # Make initial request
        completion = client.chat.completions.create(**kwargs)
        print(f"\n=== Function Calling Response ===")
        message = completion.choices[0].message

        # Print message content if any
        if message.content:
            print(message.content)

        # Check for tool calls
        if message.tool_calls:
            logger.info(f"-- Tool calls found ---")

            for tool_call in message.tool_calls:
                logger.info(f"Found tool call: {tool_call.function.name}")

                name = tool_call.function.name
                arguments = tool_call.function.arguments

                logger.info(f"\n--- Executing tool: {name} with arguments: {arguments} ---")
                result = execute_function_calls(name, arguments)

                # Create new messages for follow-up
                if result:
                    # Add assistant message with tool call
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments
                            }
                        }]
                    })

                    # Add tool response message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })

                    # Get final response with tool outputs
                    kwargs["messages"] = messages
                    kwargs["tools"] = []  # Remove tools for follow-up
                    final_completion = client.chat.completions.create(**kwargs)

                    print(f"\n=== Final Response After Tool Execution ===")
                    final_message = final_completion.choices[0].message
                    print(final_message.content)
                    print_usage_info(final_completion)

                    return final_completion

            print_usage_info(completion)
            return completion
        else:
            logger.info("No tool calls found in response")
            print_usage_info(completion)
            return completion

    except Exception as e:
        logger.error(f"Function calling test failed: {e}")
        return None


def test_follow_up(client: OpenAI, args: argparse.Namespace, previous_completion: Optional[ChatCompletion]) -> None:
    """Test follow-up conversation with previous response."""
    if not args.follow_up or not previous_completion:
        return

    logger.info("=== Testing Follow-up Conversation ===")

    # First response message and content
    first_message = previous_completion.choices[0].message
    first_content = first_message.content

    # Create messages array with previous interaction
    messages = build_messages(
        args.question,
        args.file_path,
        args.system_message
    )

    # Add assistant response to conversation
    messages.append({
        "role": "assistant",
        "content": first_content
    })

    # Add follow-up user message
    messages.append({
        "role": "user",
        "content": args.follow_up
    })

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": False  # Disable streaming for follow-up
    }

    # Add response format if JSON is requested
    if args.json_response:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        # Send follow-up request
        follow_up_completion = client.chat.completions.create(**kwargs)

        print(f"\n=== Follow-up Response ===")
        print(follow_up_completion.choices[0].message.content)
        print_usage_info(follow_up_completion)

    except Exception as e:
        logger.error(f"Follow-up test failed: {e}")


# ---------------- CLI and Main ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Native OpenAI SDK Chat Completions API tester")

    # Environment file
    parser.add_argument("--env-file", type=str, default=None,
                        help="Path to .env file to load (e.g. ../.env or ../.env_azure)")

    # Basic parameters
    parser.add_argument("--model", default="gpt-4o", help="Model name")
    parser.add_argument("--question", default="What is 2+2?", help="Primary question/prompt")
    parser.add_argument("--proxy-url", default=None,
                        help="Proxy base URL (without /v1). Falls back to OPENAI_API_BASE env var")
    parser.add_argument("--api-key", default=None,
                        help="API key. Falls back to OPENAI_API_KEY env var")
    parser.add_argument("--system-message", default="You are a helpful assistant.", help="System message")

    # Generation parameters
    parser.add_argument("--max-tokens", type=int, default=1000, help="Maximum output tokens")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")

    # Multimodal
    parser.add_argument("--file-path", help="Path to image or PDF file for multimodal input")

    # Tools and function calling
    parser.add_argument("--function-tools", action="store_true", help="Enable function calling tools")
    parser.add_argument("--force-tools", action="store_true", help="Force tool usage (tool_choice=required)")
    parser.add_argument("--auto-execute", action="store_true", help="Auto-execute function calls")

    # Response format
    parser.add_argument("--json-response", action="store_true", help="Request JSON response format")

    # Streaming and conversation
    parser.add_argument("--stream", action="store_true", help="Test streaming responses")
    parser.add_argument("--follow-up", help="Follow-up question for multi-turn conversation")

    # Debug
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load .env file if specified
    if args.env_file:
        env_path = Path(args.env_file)
        if not env_path.is_absolute():
            env_path = Path(__file__).parent / env_path
        if env_path.is_file():
            logger.info(f"Loading environment from: {env_path}")
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=str(env_path), override=True)
        else:
            logger.error(f"Environment file not found: {env_path}")
            return 1

    # Resolve API key and base URL: CLI args > env vars
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    proxy_url = args.proxy_url or os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")

    if not api_key:
        logger.error("API key is required. Use --api-key or set OPENAI_API_KEY (via --env-file or shell).")
        return 1

    # Normalize base_url to end with /v1
    base_url = proxy_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    # Initialize OpenAI client pointing to proxy
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=0
    )

    logger.info(f"Testing Chat Completions API via proxy: {base_url}")
    logger.info(f"Model: {args.model}, Question: {args.question}")

    # Run tests based on arguments
    primary_completion: Optional[ChatCompletion] = None

    # Test basic chat completion (always run unless function tools requested)
    if not args.function_tools:
        primary_completion = test_basic_chat(client, args)

    # Test function calling if requested
    if args.function_tools:
        function_completion = test_function_calling(client, args)
        if function_completion:
            primary_completion = function_completion

    # Test follow-up if requested
    if args.follow_up:
        test_follow_up(client, args, primary_completion)

    logger.info("All tests completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
