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
    p.add_argument("--model", default="gpt-4o", help="Model name")
    p.add_argument("--question", default="What is 3^3?", help="User question / prompt")
    p.add_argument("--proxy-url", default="http://localhost:8000", help="Proxy base (without /v1)")
    p.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s", help="API key for proxy")
    p.add_argument("--file-path", dest="file_path", help="Optional image/PDF file path")
    p.add_argument("--stream", action="store_true", help="Stream output tokens")
    p.add_argument("--web-search", action="store_true", help="Enable web_search_preview tool")
    p.add_argument("--image-generation", action="store_true", help="Enable image_generation tool")
    p.add_argument("--time-tool", action="store_true", help="Enable time retrieval tool (get_current_time)")
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="Reasoning effort level")
    p.add_argument("--reasoning-summary", choices=["concise", "detailed", "auto", "none"], default="none", help="Reasoning summary preference")
    p.add_argument("--follow-up", help="Optional second user question (continuation)")
    p.add_argument("--use-previous", action="store_true", help="Use previous_response_id for follow-up")
    p.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return p.parse_args()

# ---------------- Main Logic ---------------- #

def _instantiate_llm(args: argparse.Namespace) -> Any:
    """Instantiate ChatOpenAI with responses API routing enabled."""
    base_url = f"{args.proxy_url.rstrip('/')}/v1"
    llm = ChatOpenAI(  # type: ignore
        model=args.model,
        api_key=args.api_key,
        base_url=base_url,
        temperature=args.temperature,
        output_version="responses/v1",
        use_responses_api=True,
        max_retries=2,
    )
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
    """Stream invocation printing token.text() where available."""
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
    return llm.invoke([
        {"role": "user", "content": first_ai.content},  # prior answer as context
        {"role": "user", "content": follow_up},
    ], reasoning=reasoning)  # type: ignore[attr-defined]


def main() -> int:
    """Entry point."""
    if not langchain_available:
        print("LangChain not installed. pip install langchain-openai")
        return 1
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info(
        "Model=%s Stream=%s WebSearch=%s ImageGen=%s ReasoningEffort=%s FollowUp=%s",  # noqa: E501
        args.model, args.stream, args.web_search, args.image_generation, args.reasoning_effort, bool(args.follow_up)
    )

    llm = _instantiate_llm(args)

    tools = _build_tool_definitions(args.web_search, args.image_generation, args.time_tool)
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)
    content_blocks = _build_content_blocks(args.question, args.file_path)
    messages = [HumanMessage(content=content_blocks)]
    ai_msg = _invoke_once(llm, messages, tools, reasoning, args.stream)
    print("\n--- Full Response ---")
    print(ai_msg)

    # Automatic tool execution cycle (only if requested and first response had calls)
    if ai_msg.tool_calls:
        print("\n--- Detected Tool Calls ---")
        executed_tools = False
        if isinstance(ai_msg.content, list):
            for item in ai_msg.tool_calls:
                print(f"Tool call: {item['name']} with args: {item['args']}")
                if item.get("type") == "tool_call" and item.get("name") == "get_current_time":
                    messages.append(ai_msg)
                    selected_tool = {"get_current_time": get_current_time}[item.get("name", "").lower()]
                    tool_msg = selected_tool.invoke(item)
                    print("Tool message:")
                    print(tool_msg)
                    messages.append(tool_msg)
                    executed_tools = True

        if executed_tools:
            print("\n--- Re-invoking with Tool Outputs ---")
            print("Updated content blocks:")
            print(messages)
            ai_msg = _invoke_once(llm, messages, tools, reasoning, args.stream)

    else:
        logger.info("No tool calls found in the response")
        # Print debug info about the response structure
        logger.debug(f"Response content type: {type(getattr(ai_msg, 'content', None))}")
        logger.debug(f"Response tool_calls: {getattr(ai_msg, 'tool_calls', None)}")
        logger.debug(f"Response additional_kwargs: {getattr(ai_msg, 'additional_kwargs', {})}")

    text_out = _extract_text(ai_msg)
    print("\n=== Response Text ===\n" + (text_out or str(getattr(ai_msg, "content", ""))))
    _print_reasoning(ai_msg)

    if args.follow_up:
        ai_msg2 = _follow_up(llm, ai_msg, args.follow_up, args.use_previous, reasoning)
        print("\n=== Follow-Up Text ===\n" + _extract_text(ai_msg2))
        _print_reasoning(ai_msg2)


    # Token usage metadata
    usage = getattr(ai_msg, "response_metadata", {}).get("token_usage") if hasattr(ai_msg, "response_metadata") else None  # type: ignore[attr-defined]
    if usage:
        logger.info(f"Token usage: {json.dumps(usage)}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
