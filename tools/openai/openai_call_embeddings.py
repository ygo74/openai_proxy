#!/usr/bin/env python3
"""Native OpenAI SDK test script for Embeddings API.

This script tests the /v1/embeddings endpoint using the native OpenAI SDK
to validate proxy functionality and embedding generation capabilities.

Features tested:
- Single text embedding generation
- Multiple text embeddings in a single request
- Different encoding formats (float vs base64)
- Dimension specification for compatible models
- Token array input format
- Various parameter configurations

Usage examples:
python openai_call_embeddings.py --input "Hello, world!"
python openai_call_embeddings.py --input "AI is transforming the world" --model text-embedding-3-large
python openai_call_embeddings.py --input-file texts.txt --encoding-format base64
python openai_call_embeddings.py --input "Test embedding" --dimensions 512 --model text-embedding-3-small
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI
from openai.types.create_embedding_response import CreateEmbeddingResponse
from openai.types.embedding import Embedding

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("embeddings_api_openai_test")


# ---------------- Utility Functions ---------------- #

def read_input_file(file_path: str) -> List[str]:
    """Read input texts from a file, one text per line."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]


def print_usage_info(response: CreateEmbeddingResponse) -> None:
    """Print token usage information."""
    if hasattr(response, 'usage') and response.usage:
        usage = response.usage
        logger.info(f"Token usage - Prompt: {usage.prompt_tokens}, "
                   f"Total: {usage.total_tokens}")


def print_embedding_info(response: CreateEmbeddingResponse, show_vectors: bool = False) -> None:
    """Print embedding information."""
    logger.info(f"Generated {len(response.data)} embedding(s)")

    for i, embedding in enumerate(response.data):
        logger.info(f"Embedding {i}: index={embedding.index}")

        # Check if embedding is base64 encoded or float array
        if isinstance(embedding.embedding, str):
            logger.info(f"  Format: base64 encoded string (length: {len(embedding.embedding)})")
            if show_vectors:
                try:
                    # Decode base64 to show actual vector
                    decoded = base64.b64decode(embedding.embedding)
                    import struct
                    floats = struct.unpack(f'{len(decoded)//4}f', decoded)
                    logger.info(f"  Vector (first 5 values): {floats[:5]}")
                    logger.info(f"  Vector dimensions: {len(floats)}")
                except Exception as e:
                    logger.warning(f"  Could not decode base64 embedding: {e}")
        elif isinstance(embedding.embedding, list):
            logger.info(f"  Format: float array")
            logger.info(f"  Vector dimensions: {len(embedding.embedding)}")
            if show_vectors and embedding.embedding:
                logger.info(f"  Vector (first 5 values): {embedding.embedding[:5]}")
        else:
            logger.info(f"  Format: unknown ({type(embedding.embedding)})")


def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have the same dimensions")

    # Dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    # Magnitudes
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(a * a for a in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


# ---------------- Test Functions ---------------- #

def test_single_embedding(client: OpenAI, args: argparse.Namespace) -> Optional[CreateEmbeddingResponse]:
    """Test single text embedding generation."""
    logger.info("=== Testing Single Embedding ===")

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": args.input,
        "encoding_format": args.encoding_format
    }

    # Add optional parameters if specified
    if args.dimensions:
        kwargs["dimensions"] = args.dimensions

    if args.user:
        kwargs["user"] = args.user

    try:
        logger.info(f"Generating embedding for: '{args.input[:50]}{'...' if len(args.input) > 50 else ''}'")
        response = client.embeddings.create(**kwargs)

        print(f"\n=== Single Embedding Response ===")
        print(f"Model: {response.model}")
        print_embedding_info(response, args.show_vectors)
        print_usage_info(response)

        return response

    except Exception as e:
        logger.error(f"Single embedding request failed: {e}")
        return None


def test_multiple_embeddings(client: OpenAI, args: argparse.Namespace) -> Optional[CreateEmbeddingResponse]:
    """Test multiple text embeddings in a single request."""
    logger.info("=== Testing Multiple Embeddings ===")

    # Get inputs (either from file or split the single input)
    inputs: List[str]
    if args.input_file:
        inputs = read_input_file(args.input_file)
        logger.info(f"Using {len(inputs)} inputs from file: {args.input_file}")
    else:
        # Split single input into sentences for demonstration
        inputs = [s.strip() + "." for s in args.input.split(".") if s.strip()]
        if len(inputs) < 2:
            # If no natural split, create variations
            inputs = [
                args.input,
                f"This is about: {args.input}",
                f"Related to: {args.input}"
            ]

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": inputs,
        "encoding_format": args.encoding_format
    }

    # Add optional parameters if specified
    if args.dimensions:
        kwargs["dimensions"] = args.dimensions

    if args.user:
        kwargs["user"] = args.user

    try:
        logger.info(f"Generating embeddings for {len(inputs)} texts")
        response = client.embeddings.create(**kwargs)

        print(f"\n=== Multiple Embeddings Response ===")
        print(f"Model: {response.model}")
        print_embedding_info(response, args.show_vectors)
        print_usage_info(response)

        # Calculate similarities if we have float vectors
        if (len(response.data) >= 2
            and isinstance(response.data[0].embedding, list)
            and isinstance(response.data[1].embedding, list)):

            similarity = calculate_similarity(
                response.data[0].embedding,
                response.data[1].embedding
            )
            logger.info(f"Similarity between first two embeddings: {similarity:.4f}")

        return response

    except Exception as e:
        logger.error(f"Multiple embeddings request failed: {e}")
        return None


def test_token_array_input(client: OpenAI, args: argparse.Namespace) -> Optional[CreateEmbeddingResponse]:
    """Test embedding generation with token array input."""
    logger.info("=== Testing Token Array Input ===")

    # Simple token array (this would normally come from a tokenizer)
    # For demonstration, we'll use some common token IDs
    token_array = [12092, 11, 1917, 0]  # Example token sequence

    kwargs: Dict[str, Any] = {
        "model": args.model,
        "input": token_array,
        "encoding_format": args.encoding_format
    }

    # Add optional parameters if specified
    if args.dimensions:
        kwargs["dimensions"] = args.dimensions

    if args.user:
        kwargs["user"] = args.user

    try:
        logger.info(f"Generating embedding for token array: {token_array}")
        response = client.embeddings.create(**kwargs)

        print(f"\n=== Token Array Embedding Response ===")
        print(f"Model: {response.model}")
        print_embedding_info(response, args.show_vectors)
        print_usage_info(response)

        return response

    except Exception as e:
        logger.error(f"Token array embedding request failed: {e}")
        logger.info("Note: Token array input may not be supported by all models/providers")
        return None


def test_encoding_formats(client: OpenAI, args: argparse.Namespace) -> None:
    """Test different encoding formats (float vs base64)."""
    logger.info("=== Testing Different Encoding Formats ===")

    test_input = "This is a test sentence for encoding format comparison."

    for encoding_format in ["float", "base64"]:
        logger.info(f"Testing encoding format: {encoding_format}")

        kwargs: Dict[str, Any] = {
            "model": args.model,
            "input": test_input,
            "encoding_format": encoding_format
        }

        if args.dimensions:
            kwargs["dimensions"] = args.dimensions

        try:
            response = client.embeddings.create(**kwargs)

            print(f"\n=== {encoding_format.upper()} Format Response ===")
            print(f"Model: {response.model}")
            print_embedding_info(response, False)  # Don't show vectors to avoid clutter

        except Exception as e:
            logger.error(f"Encoding format {encoding_format} test failed: {e}")


def test_dimension_variants(client: OpenAI, args: argparse.Namespace) -> None:
    """Test different dimension settings (for compatible models)."""
    logger.info("=== Testing Different Dimensions ===")

    if "text-embedding-3" not in args.model:
        logger.info("Dimension testing is only supported for text-embedding-3 models, skipping")
        return

    test_input = "Testing different embedding dimensions."
    dimensions_to_test = [512, 1024, 1536]  # Common dimension sizes

    for dim in dimensions_to_test:
        logger.info(f"Testing dimensions: {dim}")

        kwargs: Dict[str, Any] = {
            "model": args.model,
            "input": test_input,
            "dimensions": dim,
            "encoding_format": "float"  # Use float for easy dimension checking
        }

        try:
            response = client.embeddings.create(**kwargs)

            print(f"\n=== {dim} Dimensions Response ===")
            print(f"Model: {response.model}")

            if response.data and isinstance(response.data[0].embedding, list):
                actual_dim = len(response.data[0].embedding)
                print(f"Requested dimensions: {dim}, Actual dimensions: {actual_dim}")

                if actual_dim != dim:
                    logger.warning(f"Dimension mismatch! Requested {dim}, got {actual_dim}")

            print_usage_info(response)

        except Exception as e:
            logger.error(f"Dimension {dim} test failed: {e}")


# ---------------- CLI and Main ---------------- #

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Native OpenAI SDK Embeddings API tester")

    # Basic parameters
    parser.add_argument("--model", default="text-embedding-ada-002",
                        help="Embedding model name")
    parser.add_argument("--input", default="The quick brown fox jumps over the lazy dog.",
                        help="Text input for embedding")
    parser.add_argument("--input-file", help="File containing multiple texts (one per line)")
    parser.add_argument("--proxy-url", default="http://localhost:8000",
                        help="Proxy base URL (without /v1)")
    parser.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s",
                        help="API key")

    # Embedding parameters
    parser.add_argument("--encoding-format", choices=["float", "base64"], default="float",
                        help="The format to return the embeddings in")
    parser.add_argument("--dimensions", type=int,
                        help="Number of dimensions (only supported in text-embedding-3 models)")
    parser.add_argument("--user", help="User identifier for abuse monitoring")

    # Test options
    parser.add_argument("--test-multiple", action="store_true",
                        help="Test multiple embeddings in one request")
    parser.add_argument("--test-token-array", action="store_true",
                        help="Test embedding with token array input")
    parser.add_argument("--test-formats", action="store_true",
                        help="Test different encoding formats")
    parser.add_argument("--test-dimensions", action="store_true",
                        help="Test different dimension settings")
    parser.add_argument("--show-vectors", action="store_true",
                        help="Show actual embedding vectors (first 5 values)")

    # Debug
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Initialize OpenAI client pointing to proxy
    base_url = f"{args.proxy_url.rstrip('/')}/v1"
    client = OpenAI(
        api_key=args.api_key,
        base_url=base_url,
        max_retries=0
    )

    logger.info(f"Testing Embeddings API via proxy: {base_url}")
    logger.info(f"Model: {args.model}")

    if args.input_file:
        logger.info(f"Using inputs from file: {args.input_file}")
    else:
        logger.info(f"Input: {args.input[:50]}{'...' if len(args.input) > 50 else ''}")

    # Run tests based on arguments
    success_count = 0
    total_tests = 0

    # Test single embedding (always run unless only specific tests requested)
    if not any([args.test_multiple, args.test_token_array, args.test_formats, args.test_dimensions]):
        total_tests += 1
        if test_single_embedding(client, args):
            success_count += 1

    # Test multiple embeddings if requested
    if args.test_multiple:
        total_tests += 1
        if test_multiple_embeddings(client, args):
            success_count += 1

    # Test token array input if requested
    if args.test_token_array:
        total_tests += 1
        if test_token_array_input(client, args):
            success_count += 1

    # Test encoding formats if requested
    if args.test_formats:
        total_tests += 1
        try:
            test_encoding_formats(client, args)
            success_count += 1
        except Exception as e:
            logger.error(f"Encoding formats test failed: {e}")

    # Test dimensions if requested
    if args.test_dimensions:
        total_tests += 1
        try:
            test_dimension_variants(client, args)
            success_count += 1
        except Exception as e:
            logger.error(f"Dimensions test failed: {e}")

    logger.info(f"Tests completed: {success_count}/{total_tests} successful")
    return 0 if success_count == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
