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
import sys
from datetime import datetime
from mimetypes import guess_type
from typing import Any, Dict, List, Optional

try:  # LangChain imports
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage  # type: ignore
    langchain_available = True
except ImportError:  # pragma: no cover
    ChatOpenAI = object  # type: ignore
    HumanMessage = SystemMessage = AIMessage = object  # type: ignore
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
    blocks: List[Dict[str, Any]] = [{"type": "text", "text": question}]
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

def _build_tool_definitions(web_search: bool, image_generation: bool) -> List[Dict[str, Any]]:
    """Return list of built-in tool definitions based on flags."""
    tools: List[Dict[str, Any]] = []
    if web_search:
        tools.append({"type": "web_search_preview"})
    if image_generation:
        # quality optional; can pass a dict per OpenAI docs
        tools.append({"type": "image_generation", "quality": "low"})
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

def _stream_invoke(llm: Any, content_blocks: List[Dict[str, Any]], reasoning: Optional[Dict[str, Any]]) -> AIMessage:
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
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])  # type: ignore[index]
        # reasoning summaries
        if isinstance(block, dict) and block.get("type") == "reasoning":
            for summary in block.get("summary", []) or []:
                if isinstance(summary, dict) and summary.get("text"):
                    texts.append(str(summary.get("text")))
    return "\n".join(t for t in texts if t)


def _print_reasoning(ai_msg: AIMessage) -> None:  # type: ignore[valid-type]
    """Print reasoning summary blocks if present."""
    content = getattr(ai_msg, "content", [])
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "reasoning":
            summaries = block.get("summary", []) or []
            for summary in summaries:
                if isinstance(summary, dict) and summary.get("text"):
                    logger.info(f"Reasoning: {summary['text']}")

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
        openai_api_key=args.api_key,
        openai_api_base=base_url,
        temperature=args.temperature,
        output_version="responses/v1",  # ensures new format & routing
        use_responses_api=True,
        max_retries=2,
    )
    return llm


def _invoke_once(llm: Any, content_blocks: List[Dict[str, Any]], tools: List[Dict[str, Any]], reasoning: Optional[Dict[str, Any]], stream: bool) -> AIMessage:  # type: ignore[valid-type]
    """Invoke model once (stream or non-stream)."""
    if tools:
        llm = llm.bind_tools(tools)  # type: ignore[attr-defined]
    if stream:
        logger.info("Streaming invocation (Responses API)")
        ai_msg = _stream_invoke(llm, content_blocks, reasoning)
    else:
        ai_msg = llm.invoke([{"role": "user", "content": content_blocks}], reasoning=reasoning)  # type: ignore[attr-defined]
    return ai_msg


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

    tools = _build_tool_definitions(args.web_search, args.image_generation)
    reasoning = _build_reasoning(args.reasoning_effort, args.reasoning_summary)
    content_blocks = _build_content_blocks(args.question, args.file_path)

    ai_msg = _invoke_once(llm, content_blocks, tools, reasoning, args.stream)

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
