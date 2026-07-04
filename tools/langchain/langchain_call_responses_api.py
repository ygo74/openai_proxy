"""Responses API tester via LangChain ChatOpenAI.

Features:
- Invoke proxy /v1/responses transparently through LangChain (output_version="responses/v1")
- Optional streaming (token.text())
- Optional built-in tools (web_search_preview, image_generation)
- Optional reasoning effort + summary generation
- Optional follow-up question using previous_response_id (stateful conversation)
- Multimodal input (image/PDF) assembled as content blocks

Usage examples:
python langchain_call_responses_api.py --question "What is 3^3?" --model gpt-4o
python langchain_call_responses_api.py --question "Positive tech news today" --web-search --stream
python langchain_call_responses_api.py --question "Describe this" --file-path ./diagram.png --stream
python langchain_call_responses_api.py --question "Generate a cute cat" --image-generation
python langchain_call_responses_api.py --question "Hi, I'm Bob." --follow-up "What is my name?" --use-previous

Proxy compatibility:
The proxy must expose /v1/responses and support capability fallback (chat -> responses) for models without native responses.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
from pyexpat.errors import messages
import sys
from datetime import datetime
from mimetypes import guess_type
from typing import Any, Dict, List, Optional, cast
from datetime import datetime as dt

try:  # LangChain imports
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage  # type: ignore
    from langchain_core.tools import tool  # type: ignore
    langchain_available = True
except ImportError:  # pragma: no cover
    ChatOpenAI = object  # type: ignore
    HumanMessage = SystemMessage = AIMessage = object  # type: ignore
    tool = lambda *a, **k: (lambda f: f)  # type: ignore
    langchain_available = False

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("responses_api_tester")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}

SYSTEM_PROMPT = "You are a helpful assistant. Provide concise, correct answers."

TIMEZONE_DATA: Dict[str, str] = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris",
    "london": "Europe/London",
}

@tool
def get_current_time(location: str) -> str:  # type: ignore[valid-type]
    """Return current local time for a given location (city name)."""
    loc = location.lower().strip()
    for key, tz in TIMEZONE_DATA.items():
        if key in loc:
            try:
                from zoneinfo import ZoneInfo  # local import
                current = dt.now(ZoneInfo(tz)).strftime("%H:%M")
                return json.dumps({"location": location, "current_time": current})
            except Exception:
                break
    return json.dumps({"location": location, "current_time": "unknown"})

# ---------------- Utility: file -> data URL ---------------- #

def _file_to_data_url(path: str) -> str:
    """Convert file to data URL (image/PDF)."""
    mime, _ = guess_type(path)
    if mime is None:
        mime = "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _build_content_blocks(question: str, file_path: Optional[str]) -> List[Dict[str, Any]]:
    """Build content blocks for the Responses API format."""
    blocks: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": question
        }
    ]
    if not file_path:
        return blocks
    if not os.path.isfile(file_path):  # Defensive check
        raise FileNotFoundError(file_path)
    _, ext = os.path.splitext(file_path.lower())
    data_url = _file_to_data_url(file_path)
    if ext in IMAGE_EXTENSIONS:
        blocks.append({"type": "input_image", "image_url": data_url})
    elif ext in PDF_EXTENSIONS:
        # OpenAI native PDF block (treated as file). Some versions use {type: 'input_image'} for pages; we supply as file reference
        # blocks.append({"type": "input_file", "file_data": data_url, "mime_type": "application/pdf"}) => openai ?
        blocks.append({"type": "input_file", "file_data": data_url, "filename": os.path.basename(file_path)})
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
    return blocks

# ---------------- Tool Helpers ---------------- #

def _build_tool_definitions(web_search: bool, image_generation: bool, time_tool: bool) -> List[Any]:  # type: ignore[valid-type]
    """Return list of tool definitions for LangChain binding.

    For Responses API, we use LangChain's bind_tools which handles the correct format conversion.
    The raw Responses API tool format is different from Chat Completions format.
    """
    tools: List[Any] = []
    if web_search:
        # Built-in tools can be passed as dicts
        tools.append({"type": "web_search_preview"})
    if image_generation:
        tools.append({"type": "image_generation", "quality": "low"})
    if time_tool:
        # Python tools work with bind_tools() for proper Responses API format
        tools.append(get_current_time)
    return tools

# ---------------- Reasoning Config ---------------- #

def _build_reasoning(effort: Optional[str], summary: Optional[str]) -> Optional[Dict[str, Any]]:
    """Build reasoning dict if requested (routes to responses API)."""
    if not effort and not summary:
        return None
    reasoning: Dict[str, Any] = {}
    if effort:
        reasoning["effort"] = effort
    if summary and summary != "none":
        reasoning["generate_summary"] = summary
    return reasoning

# ---------------- Streaming ---------------- #

def _stream_invoke(llm: Any, content_blocks: List[Dict[str, Any]], reasoning: Optional[Dict[str, Any]]) -> AIMessage:  # type: ignore[valid-type]
    """Stream invocation printing token.text() where available.

    Returns the final AIMessage (last chunk with content)."""
    final_message: Optional[AIMessage] = None  # type: ignore
    for token in llm.stream([{"role": "user", "content": content_blocks}], reasoning=reasoning):  # type: ignore[attr-defined]
        try:
            text_piece = token.text()  # type: ignore[attr-defined]
        except Exception:
            text_piece = None
        if text_piece:
            print(text_piece, end="|", flush=True)
        if isinstance(token, AIMessage):  # capture evolving message objects
            final_message = token
    print()  # newline
    return final_message or AIMessage(content="", additional_kwargs={}, response_metadata={})  # type: ignore

# ---------------- Response Parsing ---------------- #

def _extract_text(ai_msg: AIMessage) -> str:  # type: ignore[valid-type]
    """Extract aggregated text from AIMessage content blocks."""
    content = getattr(ai_msg, "content", [])
    if isinstance(content, str):  # older formats
        return content
    if not isinstance(content, list):
        return str(content)
    texts: List[str] = []
    for block in content:  # type: ignore[assignment]
        b = cast(Any, block)
        if isinstance(b, dict):
            if b.get("type") == "text" and isinstance(b.get("text"), str):  # type: ignore[union-attr]
                texts.append(cast(str, b.get("text")))
        if isinstance(b, dict) and b.get("type") == "reasoning":  # type: ignore[union-attr]
            for summary in (b.get("summary", []) or []):  # type: ignore[union-attr]
                s = cast(Any, summary)
                if isinstance(s, dict) and s.get("text"):
                    texts.append(str(s.get("text")))
    return "\n".join(t for t in texts if t)


def _print_reasoning(ai_msg: AIMessage) -> None:  # type: ignore[valid-type]
    """Print reasoning summary blocks if present."""
    content = getattr(ai_msg, "content", [])
    if not isinstance(content, list):
        return
    for block in content:  # type: ignore[assignment]
        b = cast(Any, block)
        if isinstance(b, dict) and b.get("type") == "reasoning":
            summaries = b.get("summary", []) or []
            for summary in summaries:
                s = cast(Any, summary)
                if isinstance(s, dict) and s.get("text"):
                    logger.info(f"Reasoning: {s['text']}")

# ---------------- Argument Parsing ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(description="LangChain Responses API tester")

    # Environment file
    p.add_argument("--env-file", type=str, default=None,
                   help="Path to .env file to load (e.g. ../.env or ../.env_azure)")

    # Basic parameters
    p.add_argument("--model", default="gpt-4o", help="Model name")
    p.add_argument("--question", default="What is 3^3?", help="Primary question/prompt")
    p.add_argument("--proxy-url", default=None,
                   help="Proxy base (without /v1). Falls back to OPENAI_API_BASE env var")
    p.add_argument("--api-key", default=None,
                   help="API key. Falls back to OPENAI_API_KEY env var")

    # Generation parameters
    p.add_argument("--max-tokens", type=int, default=1000, help="Maximum output tokens")
    p.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")

    # Multimodal
    p.add_argument("--file-path", help="Optional image/PDF file path")

    # Tools
    p.add_argument("--function-tool", "--time-tool", action="store_true", dest="time_tool",
                   help="Enable time retrieval tool (get_current_time)")
    p.add_argument("--auto-execute", action="store_true", help="Auto-execute function calls")
    p.add_argument("--web-search", action="store_true", help="Enable web search tool")
    p.add_argument("--image-generation", action="store_true", help="Enable image generation tool")

    # Reasoning
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="Reasoning effort level")
    p.add_argument("--reasoning-summary", choices=["concise", "detailed", "auto", "none"], default="none",
                   help="Reasoning summary")

    # Streaming and conversation
    p.add_argument("--stream", action="store_true", help="Stream output tokens")
    p.add_argument("--follow-up", help="Follow-up question")
    p.add_argument("--use-previous", action="store_true", help="Use previous_response_id for follow-up")

    # Debug
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")

    return p.parse_args()

# ---------------- Main Logic ---------------- #

def _instantiate_llm(args: argparse.Namespace) -> Any:  # type: ignore[valid-type]
    """Instantiate ChatOpenAI with responses API routing enabled."""
    base_url = f"{args.proxy_url.rstrip('/')}/v1"

    # Configure LLM with params matching OpenAI script
    llm_kwargs = {
        "model": args.model,
        "api_key": args.api_key,
        "base_url": base_url,
        "temperature": args.temperature,
        "output_version": "responses/v1",
        "use_responses_api": True,
        "max_retries": 2,
    }

    # Add max tokens if specified
    if hasattr(args, "max_tokens") and args.max_tokens:
        llm_kwargs["max_tokens"] = args.max_tokens

    # Initialize LLM
    llm = ChatOpenAI(**llm_kwargs)  # type: ignore
    return llm


def _invoke_once(llm: Any, messages: List[Any], tools: List[Any], reasoning: Optional[Dict[str, Any]], stream: bool) -> AIMessage:  # type: ignore[valid-type]
    """Invoke model once (stream or non-stream) using bind_tools for proper Responses API format."""
    if tools:
        llm = llm.bind_tools(tools)  # type: ignore[attr-defined]
    if stream:
        logger.info("Streaming invocation (Responses API)")
        return _stream_invoke(llm, messages, reasoning)
    invoke_kwargs: Dict[str, Any] = {}
    if reasoning:
        invoke_kwargs["reasoning"] = reasoning
    return llm.invoke(messages, **invoke_kwargs)  # type: ignore[attr-defined]


def _stream_invoke(llm: Any, messages: List[Any], reasoning: Optional[Dict[str, Any]]) -> AIMessage:  # type: ignore[valid-type]
    """Stream invocation printing token.text() where available.

    Returns the final AIMessage (last chunk with content)."""
    final_message: Optional[AIMessage] = None  # type: ignore
    stream_kwargs: Dict[str, Any] = {}
    if reasoning:
        stream_kwargs["reasoning"] = reasoning
    for token in llm.stream(messages, **stream_kwargs):  # type: ignore[attr-defined]
        try:
            text_piece = token.text()  # type: ignore[attr-defined]
        except Exception:
            text_piece = None
        if text_piece:
            print(text_piece, end="|", flush=True)
        if isinstance(token, AIMessage):
            final_message = token
    print()
    return final_message or AIMessage(content="", additional_kwargs={}, response_metadata={})  # type: ignore



def _follow_up(llm: Any, first_ai: AIMessage, follow_up: str, use_previous: bool, reasoning: Optional[Dict[str, Any]]) -> AIMessage:  # type: ignore[valid-type]
    """Perform follow-up question optionally using previous_response_id."""
    if use_previous:
        prev_id = first_ai.response_metadata.get("id") if hasattr(first_ai, "response_metadata") else None  # type: ignore[attr-defined]
        logger.info(f"Follow-up using previous_response_id={prev_id}")
        return llm.invoke([{"role": "user", "content": follow_up}], previous_response_id=prev_id, reasoning=reasoning)  # type: ignore[attr-defined]
    # Manual message history (less efficient)
    content = getattr(first_ai, "content", "")
    return llm.invoke([
        {"role": "user", "content": content},  # prior answer as context
        {"role": "user", "content": follow_up},
    ], reasoning=reasoning)  # type: ignore[attr-defined]


# ---------------- Test Functions ---------------- #

def test_basic_response(llm: Any, args: argparse.Namespace) -> Optional[AIMessage]:  # type: ignore[valid-type]
    """Test basic text response functionality."""
    logger.info("=== Testing Basic Response ===")

    content_blocks = _build_content_blocks(args.question, args.file_path)
    messages = [{"role": "user", "content": content_blocks}]
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)

    try:
        if args.stream:
            # Handle streaming
            print(f"\n=== Basic Response (Streaming) ===")
            response = _stream_invoke(llm, messages, reasoning)
            return response
        else:
            # Handle non-streaming
            response = llm.invoke(messages, reasoning=reasoning)  # type: ignore[attr-defined]
            print(f"\n=== Basic Response (Non-Streaming) ===")
            text_out = _extract_text(response)
            print("\n=== Response Text ===\n" + (text_out or str(getattr(response, "content", ""))))
            _print_reasoning(response)

            # Print token usage if available
            usage = getattr(response, "response_metadata", {}).get("token_usage") if hasattr(response, "response_metadata") else None  # type: ignore[attr-defined]
            if usage:
                logger.info(f"Token usage: {json.dumps(usage)}")

            return response

    except Exception as e:
        logger.error(f"Basic response test failed: {e}")
        return None


def test_function_calling(llm: Any, args: argparse.Namespace) -> Optional[AIMessage]:  # type: ignore[valid-type]
    """Test function calling with time tool."""
    logger.info("=== Testing Function Calling ===")

    content_blocks = _build_content_blocks(args.question, args.file_path)
    messages = [{"role": "user", "content": content_blocks}]
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)
    tools = [get_current_time]

    try:
        # Bind tools to the LLM
        llm_with_tools = llm.bind_tools(tools)  # type: ignore[attr-defined]

        # Invoke with tools
        response = llm_with_tools.invoke(messages, reasoning=reasoning)  # type: ignore[attr-defined]
        print(f"\n=== Function Calling Response ===")
        text_out = _extract_text(response)
        print("\n=== Response Text ===\n" + (text_out or str(getattr(response, "content", ""))))

        # Check for tool calls in the response
        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            logger.info(f"-- Tool calls found ---")

            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                logger.info(f"Found tool call: {tool_name}")

                if tool_call.get("type") == "function":
                    arguments = tool_call.get("args", {})
                    logger.info(f"\n--- Executing tool: {tool_name} with arguments: {arguments} ---")

                    # Execute the tool
                    if tool_name == "get_current_time":
                        result = get_current_time.invoke(arguments)  # type: ignore[attr-defined]
                        print(f"Tool result: {result}")

                        # Create new conversation with tool outputs
                        tool_messages = []
                        tool_messages.extend(messages)
                        tool_messages.append({"role": "assistant", "content": text_out, "tool_calls": tool_calls})
                        tool_messages.append({"role": "tool", "tool_call_id": tool_call.get("id", ""), "name": tool_name, "content": result})

                        # Get final response with tool outputs
                        final_response = llm.invoke(tool_messages, reasoning=reasoning)  # type: ignore[attr-defined]
                        print(f"\n=== Final Response After Tool Execution ===")
                        final_text = _extract_text(final_response)
                        print(final_text)

                        return final_response

            return response
        else:
            logger.info("No tool calls found in response")

            # Print token usage if available
            usage = getattr(response, "response_metadata", {}).get("token_usage") if hasattr(response, "response_metadata") else None  # type: ignore[attr-defined]
            if usage:
                logger.info(f"Token usage: {json.dumps(usage)}")

            return response

    except Exception as e:
        logger.error(f"Function calling test failed: {e}")
        return None


def test_builtin_tools(llm: Any, args: argparse.Namespace) -> None:  # type: ignore[valid-type]
    """Test built-in tools (web search, image generation)."""
    logger.info("=== Testing Built-in Tools ===")

    content_blocks = _build_content_blocks(args.question, args.file_path)
    messages = [{"role": "user", "content": content_blocks}]
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)

    built_in_tools = []
    if args.web_search:
        built_in_tools.append({"type": "web_search_preview"})
    if args.image_generation:
        built_in_tools.append({"type": "image_generation", "quality": "low"})

    if not built_in_tools:
        logger.info("No built-in tools specified, skipping test")
        return

    try:
        # Bind built-in tools
        llm_with_tools = llm.bind_tools(built_in_tools)  # type: ignore[attr-defined]

        if args.stream:
            # Handle streaming
            print(f"\n=== Built-in Tools Response (Streaming) ===")
            _stream_invoke(llm_with_tools, messages, reasoning)
        else:
            # Handle non-streaming
            response = llm_with_tools.invoke(messages, reasoning=reasoning)  # type: ignore[attr-defined]
            print(f"\n=== Built-in Tools Response ===")
            text_out = _extract_text(response)
            print("\n=== Response Text ===\n" + (text_out or str(getattr(response, "content", ""))))

            # Print token usage if available
            usage = getattr(response, "response_metadata", {}).get("token_usage") if hasattr(response, "response_metadata") else None  # type: ignore[attr-defined]
            if usage:
                logger.info(f"Token usage: {json.dumps(usage)}")

    except Exception as e:
        logger.error(f"Built-in tools test failed: {e}")


def test_follow_up(llm: Any, args: argparse.Namespace, previous_response: Optional[AIMessage]) -> None:  # type: ignore[valid-type]
    """Test follow-up conversation functionality."""
    if not args.follow_up or not previous_response:
        return

    logger.info("=== Testing Follow-up Conversation ===")
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)

    try:
        response = _follow_up(llm, previous_response, args.follow_up, args.use_previous, reasoning)

        print(f"\n=== Follow-up Response ===")
        text_out = _extract_text(response)
        print("\n=== Response Text ===\n" + (text_out or str(getattr(response, "content", ""))))
        _print_reasoning(response)

        # Print token usage if available
        usage = getattr(response, "response_metadata", {}).get("token_usage") if hasattr(response, "response_metadata") else None  # type: ignore[attr-defined]
        if usage:
            logger.info(f"Token usage: {json.dumps(usage)}")

    except Exception as e:
        logger.error(f"Follow-up test failed: {e}")


def main() -> int:
    """Main entry point."""
    if not langchain_available:
        print("LangChain not installed. pip install langchain-openai")
        return 1

    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load .env file if specified
    if args.env_file:
        from pathlib import Path
        from dotenv import load_dotenv
        env_path = Path(args.env_file) if Path(args.env_file).is_absolute() else Path(__file__).parent / args.env_file
        if env_path.is_file():
            load_dotenv(dotenv_path=str(env_path), override=True)
        else:
            logger.error(f"Environment file not found: {env_path}")
            return 1

    # Resolve API key and proxy URL
    args.api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    args.proxy_url = args.proxy_url or os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")
    # Normalize: remove /v1 suffix for _instantiate_llm
    resolved = args.proxy_url.rstrip("/")
    if resolved.endswith("/v1"):
        args.proxy_url = resolved[:-3]

    if not args.api_key:
        logger.error("API key is required. Use --api-key or set OPENAI_API_KEY.")
        return 1

    # Initialize LLM client pointing to proxy
    base_url = f"{args.proxy_url.rstrip('/')}/v1"
    llm = _instantiate_llm(args)

    logger.info(f"Testing Responses API via proxy: {base_url}")
    logger.info(f"Model: {args.model}, Question: {args.question}")

    # Run tests based on arguments
    primary_response = None

    # Test basic response (always run unless other specific tests requested)
    if not (args.time_tool or args.web_search or args.image_generation):
        primary_response = test_basic_response(llm, args)

    # Test function calling if requested
    if args.time_tool:
        function_response = test_function_calling(llm, args)
        if function_response:
            primary_response = function_response

    # Test built-in tools if requested
    if args.web_search or args.image_generation:
        test_builtin_tools(llm, args)

    # Test follow-up if requested
    if args.follow_up and primary_response:
        test_follow_up(llm, args, primary_response)

    logger.info("All tests completed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
