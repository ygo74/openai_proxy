#!/usr/bin/env python3
"""Native OpenAI SDK test script for Completions API.

This script tests the /v1/completions endpoint using the native OpenAI SDK
to validate proxy functionality and compare with other endpoints.

Features tested:
- Basic text completions with single prompt
- Multiple prompts in a single request
- Streaming completions
- Various parameter configurations (temperature, max_tokens, etc.)

Usage examples:
python openai_call_completions.py --prompt "Write a haiku about AI."
python openai_call_completions.py --prompt "Complete this: Once upon a time" --temperature 0.8
python openai_call_completions.py --prompt-file prompts.txt --stream
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI
from openai.types.completion import Completion, CompletionChoice
from openai.types.completion_choice import CompletionChoice
from openai.types.completion_usage import CompletionUsage
from openai._streaming import Stream

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("completions_api_openai_test")


# ---------------- Utility Functions ---------------- #

def _handle_stream(stream: Stream[Completion], args: argparse.Namespace) -> Optional[Completion]:
    """Handle streaming completion chunks consistently."""
    choice_texts = [""] * args.n  # Initialize array for each choice's text
    response: Optional[Completion] = None
    for chunk in stream:
        response = chunk  # Keep updating to the latest chunk
        if args.verbose:
            logger.debug(f"Stream chunk: {chunk}")

        # Handle content for each choice
        for choice in chunk.choices:
            index = choice.index
            if choice.text:
                if index < len(choice_texts):
                    choice_texts[index] += choice.text
                    print(f"{choice.text}", end="|", flush=True)

    print()  # Ensure we end with a newline

    # Print the final assembled texts
    for i, text in enumerate(choice_texts):
        if text:
            print(f"\n=== Final text for choice {i} ===")
            print(text)

    return response

def read_prompt_file(file_path: str) -> List[str]:
    """Read prompts from a file, one prompt per line."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]


def print_usage_info(completion: Optional[Completion]) -> None:
    """Print token usage information."""
    if completion and hasattr(completion, 'usage') and completion.usage:
        usage = completion.usage
        logger.info(f"Token usage - Prompt: {usage.prompt_tokens}, "
                   f"Completion: {usage.completion_tokens}, "
                   f"Total: {usage.total_tokens}")


# ---------------- Test Functions ---------------- #

def test_basic_completion(client: OpenAI, args: argparse.Namespace) -> Optional[Completion]:
    """Test basic text completion functionality."""
    logger.info("=== Testing Basic Completion ===")

    # Get prompts (either single or multiple)
    prompts: Union[str, List[str]]
    if args.prompt_file:
        prompts = read_prompt_file(args.prompt_file)
        logger.info(f"Using {len(prompts)} prompts from file: {args.prompt_file}")
    else:
        prompts = args.prompt

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "prompt": prompts,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "n": args.n,
        "stream": args.stream,
        "echo": args.echo
    }

    # Add optional parameters if specified
    if args.stop:
        kwargs["stop"] = args.stop

    if args.presence_penalty is not None:
        kwargs["presence_penalty"] = args.presence_penalty

    if args.frequency_penalty is not None:
        kwargs["frequency_penalty"] = args.frequency_penalty

    try:
        if args.stream:
            # Handle streaming
            logger.info("Starting streaming request...")
            stream: Stream[Completion] = client.completions.create(**kwargs)  # type: ignore
            print(f"\n=== Completion (Streaming) ===")
            streamed_completion: Optional[Completion] = _handle_stream(stream, args)  # type: ignore
            print_usage_info(streamed_completion)
            return streamed_completion
        else:
            # Handle non-streaming
            logger.info("Starting non-streaming request...")
            completion: Optional[Completion] = client.completions.create(**kwargs)  # type: ignore
            print(f"\n=== Completion (Non-Streaming) ===")


            # Print each choice with its index
            for i, choice in enumerate(completion.choices):
                print(f"\n--- Choice {i} ---")
                print(choice.text)
                print(f"Finish reason: {choice.finish_reason}")

            print_usage_info(completion)
            return completion

    except Exception as e:
        logger.error(f"Completion request failed: {e}")
        return None


# ---------------- CLI and Main ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Native OpenAI SDK Completions API tester")

    # Environment file
    parser.add_argument("--env-file", type=str, default=None,
                        help="Path to .env file to load (e.g. ../.env or ../.env_azure)")

    # Basic parameters
    parser.add_argument("--model", default="gpt-3.5-turbo-instruct",
                        help="Model name (must support completions API)")
    parser.add_argument("--prompt", default="Complete this sentence: The future of AI is",
                        help="Text prompt for completion")
    parser.add_argument("--prompt-file", help="File containing multiple prompts (one per line)")
    parser.add_argument("--proxy-url", default=None,
                        help="Proxy base URL (without /v1). Falls back to OPENAI_API_BASE env var")
    parser.add_argument("--api-key", default=None,
                        help="API key. Falls back to OPENAI_API_KEY env var")

    # Generation parameters
    parser.add_argument("--max-tokens", type=int, default=100, help="Maximum output tokens")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature (0-2)")
    parser.add_argument("--top-p", type=float, default=1.0, help="Nucleus sampling parameter (0-1)")
    parser.add_argument("--n", type=int, default=1, help="Number of completions to generate")
    parser.add_argument("--stop", help="Stop sequences (comma separated)")
    parser.add_argument("--presence-penalty", type=float, help="Presence penalty (-2.0 to 2.0)")
    parser.add_argument("--frequency-penalty", type=float, help="Frequency penalty (-2.0 to 2.0)")
    parser.add_argument("--echo", action="store_true", help="Echo prompt in output")

    # Streaming
    parser.add_argument("--stream", action="store_true", help="Stream output tokens")

    # Debug
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Convert stop sequences from comma-separated string to list if provided
    if args.stop:
        args.stop = [s.strip() for s in args.stop.split(',')]

    return args


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load .env file if specified
    if args.env_file:
        from pathlib import Path
        env_path = Path(args.env_file) if Path(args.env_file).is_absolute() else Path(__file__).parent / args.env_file
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

    # Normalize base_url
    base_url = proxy_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    # Initialize OpenAI client pointing to proxy
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=2
    )

    logger.info(f"Testing Completions API via proxy: {base_url}")
    logger.info(f"Model: {args.model}")

    if isinstance(args.prompt, str):
        logger.info(f"Prompt: {args.prompt[:50]}...")
    elif args.prompt_file:
        logger.info(f"Using prompts from file: {args.prompt_file}")

    # Run completion test
    test_basic_completion(client, args)

    logger.info("Test completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
