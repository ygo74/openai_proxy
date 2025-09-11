"""Unified Langchain proxy capability tester.

Features:
- Basic chat or completion question
- Optional file (image or PDF) auto-detected and sent as multi-part content
- Optional tool invocation (model decides). If tool calls returned, execute and re-invoke
- Supports streaming and non-streaming modes
- Force completion or chat mode via --mode

Usage examples:
python langchain_call_proxy_unified.py --question "Who are you?" --model gpt-4o
python langchain_call_proxy_unified.py --file-path ./image.jpg --question "Describe this image" --stream
python langchain_call_proxy_unified.py --file-path ./doc.pdf --question "Summarize this document" --mode chat
python langchain_call_proxy_unified.py --question "What's the current time in Paris?" --enable-tools
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from datetime import datetime
from mimetypes import guess_type
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI, OpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
    langchain_available = True
except ImportError:  # pragma: no cover - dependency missing scenario
    ChatOpenAI = OpenAI = object  # type: ignore
    langchain_available = False

# ---------------- Configuration & Logging ---------------- #
log_level_env: str = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level_env, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("unified_proxy_tester")

SYSTEM_PROMPT = (
    "You are an expert AI assistant. Be concise and helpful."
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}

# ---------------- File Handling Helpers ---------------- #

def _to_data_url(path: str) -> str:
    """Return a data: URL for a file (image or PDF)."""
    mime_type, _ = guess_type(path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    with open(path, "rb") as f:
        encoded: str = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _build_file_content_parts(file_path: str, question: str) -> List[Dict[str, Any]]:
    """Build content parts list including text + file/image part."""
    lower = file_path.lower()
    _, ext = os.path.splitext(lower)
    data_url = _to_data_url(file_path)
    parts: List[Dict[str, Any]] = [
        {"type": "text", "text": question}
    ]
    if ext in IMAGE_EXTENSIONS:
        parts.append({
            "type": "image_url",
            "image_url": {"url": data_url, "detail": "high"}
        })
    elif ext in PDF_EXTENSIONS:
        parts.append({
            "type": "file",
            "file": {
                "filename": os.path.basename(file_path),
                "file_data": data_url
            }
        })
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
    return parts

# ---------------- Tools (Example) ---------------- #
try:
    from langchain_core.tools import tool  # type: ignore
except ImportError:  # pragma: no cover
    def tool(func):  # type: ignore
        return func

TIMEZONE_DATA = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris",
    "new york": "America/New_York",
}

@tool
def get_current_time(location: str) -> str:
    """Return current time (HH:MM) for a location if known."""
    loc = location.lower()
    for key, tz in TIMEZONE_DATA.items():
        if key in loc:
            from zoneinfo import ZoneInfo  # local import for performance
            current_time = datetime.now(ZoneInfo(tz)).strftime("%H:%M")
            return json.dumps({"location": location, "current_time": current_time})
    return json.dumps({"location": location, "current_time": "unknown"})

TOOLS = {"get_current_time": get_current_time}

# ---------------- Invocation Logic ---------------- #

def _create_clients(api_base: str, api_key: str, model: str, mode: str, temperature: float = 0.0) -> Dict[str, Any]:
    """Create chat and/or completion clients based on mode."""
    openai_api_base = f"{api_base.rstrip('/')}/v1"
    clients: Dict[str, Any] = {}
    if mode in ("chat", "auto"):
        clients["chat"] = ChatOpenAI(  # type: ignore
            openai_api_base=openai_api_base,
            openai_api_key=api_key,
            model=model,
            streaming=False,
            temperature=temperature,
        )
    if mode in ("completion", "auto"):
        clients["completion"] = OpenAI(  # type: ignore
            openai_api_base=openai_api_base,
            openai_api_key=api_key,
            model=model,
            temperature=temperature,
        )
    return clients


def _maybe_bind_tools(chat_client: Any, enable_tools: bool) -> Any:
    """Bind tools if enabled; return original otherwise."""
    if enable_tools:
        try:
            return chat_client.bind_tools(list(TOOLS.values()))
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to bind tools: {e}")
    return chat_client


def _stream_chat(chat_client: Any, messages: List[Any]) -> str:
    """Stream chat response; return concatenated content."""
    full = []
    for chunk in chat_client.stream(messages):  # type: ignore[attr-defined]
        content = getattr(chunk, "content", "")
        if isinstance(content, list):
            content = "".join(str(p) for p in content)
        if content:
            full.append(str(content))
            print(content, end="|", flush=True)
    print()  # newline
    return "".join(full)


def _invoke_with_optional_tools(chat_client: Any, messages: List[Any], stream: bool) -> str:
    """Invoke chat, handle tool calls if any, then final answer."""
    # First call
    if stream:
        logger.info("Streaming initial chat response (tools may not trigger with streaming).")
        return _stream_chat(chat_client, messages)

    ai_msg = chat_client.invoke(messages)
    messages.append(ai_msg)

    tool_calls = getattr(ai_msg, "tool_calls", []) or []
    if not tool_calls:
        return getattr(ai_msg, "content", "")

    logger.info(f"Executing {len(tool_calls)} tool call(s)")
    for call in tool_calls:
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        if not name:
            continue
        tool_fn = TOOLS.get(name.lower())
        if not tool_fn:
            logger.warning(f"No tool found for {name}")
            continue
        try:
            tool_result = tool_fn.invoke(call) if hasattr(tool_fn, "invoke") else tool_fn(**(args or {}))  # type: ignore
            messages.append(tool_result)
        except TypeError:
            # Fallback if tool signature mismatch
            try:
                tool_result = tool_fn(args)  # type: ignore
                messages.append(tool_result)
            except Exception as e:  # pragma: no cover
                logger.error(f"Tool execution failed for {name}: {e}")

    logger.info("Calling model with tool results")
    final_msg = chat_client.invoke(messages)
    messages.append(final_msg)
    return getattr(final_msg, "content", "")

# ---------------- Main ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Unified proxy capability tester")
    parser.add_argument("--model", default="gpt-4o", help="Model name")
    parser.add_argument("--question", default="Who are you?", help="Question to send")
    parser.add_argument("--file-path", dest="file_path", help="Optional image or PDF path")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="Proxy base URL (without /v1)")
    parser.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s", help="Proxy API key")
    parser.add_argument("--mode", choices=["chat", "completion", "auto"], default="chat", help="Force chat, completion or auto")
    parser.add_argument("--stream", action="store_true", help="Use streaming for chat mode")
    parser.add_argument("--enable-tools", action="store_true", help="Enable tool binding")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    if not langchain_available:
        print("Langchain dependencies missing. Install with: pip install langchain-openai")
        return 1

    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info(f"Mode={args.mode} Model={args.model} Stream={args.stream} Tools={args.enable_tools} File={args.file_path}")

    # Create clients
    clients = _create_clients(api_base=args.proxy_url, api_key=args.api_key, model=args.model, mode=args.mode, temperature=args.temperature)

    # Build messages
    messages: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]  # type: ignore

    if args.file_path:
        if not os.path.isfile(args.file_path):
            logger.error(f"File not found: {args.file_path}")
            return 2
        parts = _build_file_content_parts(args.file_path, args.question)
        messages.append(HumanMessage(content=parts))  # type: ignore
    else:
        messages.append(HumanMessage(content=args.question))  # type: ignore

    # Completion mode forced
    if args.mode == "completion":
        llm = clients.get("completion")
        if not llm:
            logger.error("Completion client not available")
            return 3
        if args.stream and hasattr(llm, "stream"):
            logger.info("Streaming completion response")
            full = []
            for chunk in llm.stream(args.question):  # type: ignore[attr-defined]
                if chunk:
                    full.append(str(chunk))
                    print(chunk, end="", flush=True)
            print()
            logger.info("Done")
        else:
            response = llm.invoke(args.question)  # type: ignore[attr-defined]
            print(response)
        return 0

    # Chat (or auto) mode
    chat_client = clients.get("chat")
    if not chat_client:
        logger.error("Chat client not available")
        return 4

    chat_client = _maybe_bind_tools(chat_client, args.enable_tools)

    if args.stream:
        logger.info("Streaming chat response")
        _stream_chat(chat_client, messages)
        return 0

    result = _invoke_with_optional_tools(chat_client, messages, stream=False)
    print(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
