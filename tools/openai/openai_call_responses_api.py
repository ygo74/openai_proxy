#!/usr/bin/env python3
"""Native OpenAI SDK test script for Responses API.

This script tests the /v1/responses endpoint using the native OpenAI SDK
to validate proxy functionality and compare with LangChain implementation.

Features tested:
- Basic text responses
- Multimodal input (images, files)
- Function calling with tool execution
- Reasoning with different effort levels
- Streaming responses
- Follow-up conversations with previous_response_id
- Built-in tools (web_search_preview, image_generation)

Usage examples:
python test_responses_openai_sdk.py --question "What is 2+2?"
python test_responses_openai_sdk.py --question "What time is it in Paris?" --function-tools --auto-execute
python test_responses_openai_sdk.py --question "Latest tech news" --web-search --stream
python test_responses_openai_sdk.py --question "Hi, I'm Alice" --follow-up "What's my name?" --use-previous
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from mimetypes import guess_type
from typing import Any, Dict, List, Optional, Union
from datetime import datetime as dt

import openai
from openai import OpenAI
from openai.types.responses import Response
from openai.types.responses.response_stream_event import ResponseStreamEvent

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("responses_api_openai_test")

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

    logger.info(f"called get_current_time_tool with location: {location}")
    loc = location.lower().strip()
    for key, tz in TIMEZONE_DATA.items():
        if key in loc:
            try:
                from zoneinfo import ZoneInfo
                current = dt.now(ZoneInfo(tz)).strftime("%H:%M")
                return json.dumps({"location": location, "current_time": current})
            except Exception:
                break
    return json.dumps({"location": location, "current_time": "unknown"})


# ---------------- Utility Functions ---------------- #

def _handle_stream(stream: Any, args: argparse.Namespace) -> Optional[Response]:
    """Handle streaming response events consistently."""
    full_content = ""
    response: Optional[Response] = None
    for event in stream:
        if args.verbose:
            logger.debug(f"Stream event: {event}")

        if hasattr(event, 'type'):
            event_type = event.type

            # Handle text delta events
            if event_type == "response.output_text.delta":
                if hasattr(event, 'delta') and event.delta:
                    print(event.delta, end="|", flush=True)
                    full_content += event.delta

            # Handle text done events
            elif event_type == "response.output_text.done":
                if hasattr(event, 'text'):
                    # Sometimes the final text is in the done event
                    final_text = event.text
                    if final_text and final_text != full_content:
                        logger.debug(f"Final text from done event: {len(final_text)} chars")

            # Handle response completion
            elif event_type == "response.completed":
                print("\n[Stream completed]")
                if hasattr(event, 'response'):
                    print_usage_info(event.response)
                    print_reasoning_info(event.response)
                    response = event.response

            # Handle other event types for debugging
            elif args.verbose:
                logger.debug(f"Event type: {event_type}")

        elif hasattr(event, 'status'):
            logger.debug(f"Event with status: {event.status}")

    print()  # Ensure we end with a newline
    return response


def file_to_data_url(path: str) -> str:
    """Convert file to data URL for multimodal input."""
    mime, _ = guess_type(path)
    if mime is None:
        mime = "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_input_content(question: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build input content array for Responses API."""
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": question}]

    if file_path and os.path.isfile(file_path):
        _, ext = os.path.splitext(file_path.lower())
        data_url = file_to_data_url(file_path)

        if ext in IMAGE_EXTENSIONS:
            content.append({
                "type": "input_image",
                "image_url": data_url,
                "detail": "auto"
            })
        elif ext in PDF_EXTENSIONS:
            content.append({
                "type": "input_file",
                "file_data": data_url,
                "filename": os.path.basename(file_path)
            })
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    return [
        { "role": "user", "content": content }
    ]


def build_function_tools() -> List[Dict[str, Any]]:
    """Build function tool definitions for Responses API format."""
    return [{
        "type": "function",
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
            "required": ["location"],
            "additionalProperties": False,
        },
        "strict": True
    }]


def build_builtin_tools(web_search: bool = False, image_gen: bool = False) -> List[Dict[str, Any]]:
    """Build built-in tool definitions."""
    tools: List[Dict[str, Any]] = []
    if web_search:
        tools.append({"type": "web_search_preview"})
    if image_gen:
        tools.append({"type": "image_generation", "quality": "low"})
    return tools




def execute_function_calls(name: str, args: Dict[str, Any]) -> Optional[Union[str, Dict[str, Any]]]:
    """Execute function calls locally and return tool_outputs format."""
    if name == "get_current_time":
        return get_current_time_tool(**args)

    return None

def extract_text_content(response: Response) -> str:
    """Extract text content from Response object."""
    if not hasattr(response, 'output') or not response.output:
        logger.warning("not found")
        return ""

    texts: List[str] = []
    for item in response.output:
        logger.info(f"Processing output item: {item}")
        if hasattr(item, 'content'):
            for content in item.content:
                if hasattr(content, 'text'):
                    texts.append(str(content.text))

    return "\n".join(texts)


def print_reasoning_info(response: Response) -> None:
    """Print reasoning information if present."""
    if hasattr(response, 'reasoning') and response.reasoning:
        logger.info(f"Reasoning effort: {getattr(response.reasoning, 'effort', 'N/A')}")
        if hasattr(response.reasoning, 'summary') and response.reasoning.summary:
            for summary in response.reasoning.summary:
                if hasattr(summary, 'text'):
                    logger.info(f"Reasoning summary: {summary.text}")


def print_usage_info(response: Response) -> None:
    """Print token usage information."""
    if hasattr(response, 'usage') and response.usage:
        usage = response.usage
        logger.info(f"Token usage - Input: {getattr(usage, 'input_tokens', 0)}, "
                   f"Output: {getattr(usage, 'output_tokens', 0)}, "
                   f"Total: {getattr(usage, 'total_tokens', 0)}")


# ---------------- Test Functions ---------------- #

def test_basic_response(client: OpenAI, args: argparse.Namespace) -> Optional[Response]:
    """Test basic text response functionality."""
    logger.info("=== Testing Basic Response ===")

    if not args.file_path:
        input_content = args.question
    else:
        input_content = build_input_content(args.question, args.file_path)


    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": input_content,
        "max_output_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": args.stream  # Use stream flag from args
    }

    # Add reasoning if specified
    if args.reasoning_effort:
        kwargs["reasoning"] = {"effort": args.reasoning_effort}
        if args.reasoning_summary != "none":
            kwargs["reasoning"]["generate_summary"] = args.reasoning_summary

    try:
        if args.stream:
            # Handle streaming
            stream = client.responses.create(**kwargs)
            print(f"\n=== Handle Response (Streaming) ===")
            response = _handle_stream(stream, args)
            return response  # Can't return Response object from streaming
        else:
            # Handle non-streaming
            response = client.responses.create(**kwargs)
            print(f"\n=== Handle Response (Non-Streaming) ===")
            print(response.output_text)
            print_reasoning_info(response)
            print_usage_info(response)
            return response

    except Exception as e:
        logger.error(f"Basic response test failed: {e}")
        return None


def test_function_calling(client: OpenAI, args: argparse.Namespace) -> Optional[Response]:
    """Test function calling functionality."""
    logger.info("=== Testing Function Calling ===")

    input_content = build_input_content(args.question, args.file_path)
    function_tools = build_function_tools()

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": input_content,
        "tools": function_tools,
        "max_output_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": False  # args.stream  # Use stream flag from args
    }

    if args.reasoning_effort:
        kwargs["reasoning"] = {"effort": args.reasoning_effort}

    try:
        # Handle non-streaming function calling
        response = client.responses.create(**kwargs)
        print(f"\n=== Function Calling Response ===")
        print(extract_text_content(response))

        # Check for tool calls
        if response.tools:
            logger.info(f"-- tool calls found ---")

            input_content += response.output
            for item in response.output:
                logger.info(f"Found tool call: {item.name}")
                if item.type != "function_call":
                    continue

                name = item.name
                arguments = json.loads(item.arguments)  # Use loads() for string, not load() for file

                logger.info(f"\n--- Executing tool: {name} with arguments: {arguments} ---")
                result = execute_function_calls(name, arguments)
                input_content.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": str(result)
                })

            # print(input_content)
            final_response = client.responses.create(**kwargs)

            print(f"\n=== Final Response After Tool Execution ===")
            print(extract_text_content(final_response))
            print_usage_info(final_response)

            return final_response
        else:
            logger.info("No tool calls found in response")
            print_usage_info(response)
            return response

    except Exception as e:
        logger.error(f"Function calling test failed: {e}")
        return None


def test_builtin_tools(client: OpenAI, args: argparse.Namespace) -> None:
    """Test built-in tools (web search, image generation)."""
    logger.info("=== Testing Built-in Tools ===")

    input_content = build_input_content(args.question, args.file_path)
    builtin_tools = build_builtin_tools(args.web_search, args.image_generation)

    if not builtin_tools:
        logger.info("No built-in tools specified, skipping test")
        return

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": input_content,
        "tools": builtin_tools,
        "max_output_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": args.stream  # Use stream flag from args
    }

    try:
        if args.stream:
            # Handle streaming for built-in tools
            stream = client.responses.create(**kwargs)
            print(f"\n=== Built-in Tools Response (Streaming) ===")
            _handle_stream(stream, args)
        else:
            # Handle non-streaming
            response = client.responses.create(**kwargs)
            print(f"\n=== Built-in Tools Response ===")
            print(extract_text_content(response))
            print_usage_info(response)

    except Exception as e:
        logger.error(f"Built-in tools test failed: {e}")


def test_follow_up(client: OpenAI, args: argparse.Namespace, previous_response: Optional[Response]) -> None:
    """Test follow-up conversation functionality."""
    if not args.follow_up:
        return

    logger.info("=== Testing Follow-up Conversation ===")

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "max_output_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": False
    }

    # print("===previous response===")
    # print(previous_response)

    # Use previous_response_id if available and requested
    if args.use_previous and previous_response and hasattr(previous_response, 'id'):
        kwargs["previous_response_id"] = previous_response.id
        kwargs["input"] = build_input_content(args.follow_up)

        logger.info(f"Using previous_response_id: {previous_response.id}")
    else:
        logger.info("Not using previous_response_id")
        input_param = build_input_content(args.question, args.file_path)
        input_param += previous_response.output
        input_param.extend(build_input_content(args.follow_up))
        kwargs["input"] = input_param

    if args.reasoning_effort:
        kwargs["reasoning"] = {"effort": args.reasoning_effort}

    # print("=== follow-up kwargs ===")
    # print(kwargs["input"])

    try:
        response = client.responses.create(**kwargs)

        print(f"\n=== Follow-up Response ===")
        print(extract_text_content(response))
        print_usage_info(response)

    except Exception as e:
        logger.error(f"Follow-up test failed: {e}")


# ---------------- CLI and Main ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Native OpenAI SDK Responses API tester")

    # Basic parameters
    parser.add_argument("--model", default="gpt-4o", help="Model name")
    parser.add_argument("--question", default="What is 2+2?", help="Primary question/prompt")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="Proxy base URL (without /v1)")
    parser.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s", help="API key")

    # Generation parameters
    parser.add_argument("--max-tokens", type=int, default=1000, help="Maximum output tokens")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")

    # Multimodal
    parser.add_argument("--file-path", help="Optional image/PDF file path")

    # Tools
    parser.add_argument("--function-tools", action="store_true", help="Enable function calling tools")
    parser.add_argument("--auto-execute", action="store_true", help="Auto-execute function calls")
    parser.add_argument("--web-search", action="store_true", help="Enable web search tool")
    parser.add_argument("--image-generation", action="store_true", help="Enable image generation tool")

    # Reasoning
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="Reasoning effort level")
    parser.add_argument("--reasoning-summary", choices=["concise", "detailed", "auto", "none"], default="none", help="Reasoning summary")

    # Streaming and conversation
    parser.add_argument("--stream", action="store_true", help="Test streaming responses")
    parser.add_argument("--follow-up", help="Follow-up question")
    parser.add_argument("--use-previous", action="store_true", help="Use previous_response_id for follow-up")

    # Debug
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    return parser.parse_args()


def test_multiturn_conversation(client: OpenAI, args: argparse.Namespace) -> None:
    context = [
        { "role": "user", "content": "What is the capital of France?" }
    ]
    res1 = client.responses.create(
        model=args.model,
        input=context,
    )
    print("=== res1 ===")
    print(res1)

    # from openai.types.responses.response_output_message_param import ResponseOutputMessageParam
    # from openai.types.responses.response_output_text_param import ResponseOutputTextParam

    # output_content = ResponseOutputTextParam(
    #         annotations=[],
    #         text='The capital of France is **Paris**.',
    #         type='output_text',
    #         logprobs=None
    # )

    # print("=== output_content ===")
    # print(output_content)


    # input_content: ResponseOutputMessageParam = ResponseOutputMessageParam(
    #     id='msg_68cf9c0280dc81908eb018ce3932d391000ddd2d54aa3276',
    #     content=[output_content],
    #     role='assistant',
    #     status='completed',
    #     type='message'
    # )

    # print("=== input_content ===")
    # print(input_content)

    # Append the first response’s output to context
    # context += [input_content]
    context += res1.output

    # Add the next user message
    context += [
        { "role": "user", "content": "And it's population?" }
    ]

    print("=== context ===")
    print(context)

    res2 = client.responses.create(
        model=args.model,
        input=context,
    )

    print("=== res2 ===")
    print(res2)

def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Initialize OpenAI client pointing to proxy
    base_url = f"{args.proxy_url.rstrip('/')}/v1"
    client = OpenAI(
        api_key=args.api_key,
        base_url=base_url
    )

    logger.info(f"Testing Responses API via proxy: {base_url}")
    logger.info(f"Model: {args.model}, Question: {args.question}")

    # return test_multiturn_conversation(client=client, args=args)

    # Run tests based on arguments
    primary_response: Optional[Response] = None

    # Test basic response (always run unless other specific tests requested)
    if not (args.function_tools or args.web_search or args.image_generation):
        primary_response = test_basic_response(client, args)

    # Test function calling if requested
    if args.function_tools:
        function_response = test_function_calling(client, args)
        if function_response:
            primary_response = function_response

    # Test built-in tools if requested
    if args.web_search or args.image_generation:
        test_builtin_tools(client, args)

    # Test follow-up if requested
    if args.follow_up:
        test_follow_up(client, args, primary_response)

    logger.info("All tests completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())