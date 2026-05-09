#!/usr/bin/env python3
"""List available models using OpenAI SDK.

This script uses the native OpenAI SDK to query the /v1/models endpoint
of the FastAPI proxy gateway and display available models.

Features:
- List all available models
- Filter by model name pattern
- Display detailed model information
- Show model capabilities and status
- Export results to JSON

Usage examples:
python openai_list_models.py
python openai_list_models.py --filter gpt-4
python openai_list_models.py --detailed
python openai_list_models.py --output models.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai.types import Model

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("openai_list_models")


def list_models(client: OpenAI) -> List[Model]:
    """Retrieve all available models from the gateway.

    Args:
        client (OpenAI): Configured OpenAI client

    Returns:
        List[Model]: List of available models
    """
    try:
        response = client.models.list()
        return list(response.data)
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return []


def filter_models(models: List[Model], pattern: Optional[str] = None) -> List[Model]:
    """Filter models by name pattern.

    Args:
        models (List[Model]): List of models to filter
        pattern (Optional[str]): Pattern to match in model ID (case-insensitive)

    Returns:
        List[Model]: Filtered list of models
    """
    if not pattern:
        return models

    pattern_lower = pattern.lower()
    return [m for m in models if pattern_lower in m.id.lower()]


def print_model_summary(models: List[Model]) -> None:
    """Print a summary table of models.

    Args:
        models (List[Model]): List of models to display
    """
    if not models:
        print("No models found.")
        return

    print(f"\n{'='*80}")
    print(f"{'ID':<40} {'Owner':<25} {'Created':<15}")
    print(f"{'='*80}")

    for model in models:
        created = model.created if hasattr(model, 'created') else 'N/A'
        owner = model.owned_by if hasattr(model, 'owned_by') else 'N/A'
        print(f"{model.id:<40} {owner:<25} {created:<15}")

    print(f"{'='*80}")
    print(f"Total models: {len(models)}\n")


def print_model_details(models: List[Model]) -> None:
    """Print detailed information for each model.

    Args:
        models (List[Model]): List of models to display
    """
    if not models:
        print("No models found.")
        return

    for idx, model in enumerate(models, 1):
        print(f"\n{'='*80}")
        print(f"Model {idx}/{len(models)}")
        print(f"{'='*80}")
        print(f"ID:      {model.id}")
        print(f"Owner:   {getattr(model, 'owned_by', 'N/A')}")
        print(f"Created: {getattr(model, 'created', 'N/A')}")
        print(f"Object:  {getattr(model, 'object', 'N/A')}")

        # Print any additional attributes
        model_dict = model.model_dump() if hasattr(model, 'model_dump') else {}
        extra_keys = set(model_dict.keys()) - {'id', 'owned_by', 'created', 'object'}

        if extra_keys:
            print("\nAdditional attributes:")
            for key in sorted(extra_keys):
                value = model_dict[key]
                if isinstance(value, (dict, list)):
                    print(f"  {key}: {json.dumps(value, indent=4)}")
                else:
                    print(f"  {key}: {value}")

    print(f"\n{'='*80}")
    print(f"Total models: {len(models)}\n")


def export_models_json(models: List[Model], output_path: str) -> bool:
    """Export models list to JSON file.

    Args:
        models (List[Model]): List of models to export
        output_path (str): Output file path

    Returns:
        bool: True if export successful, False otherwise
    """
    try:
        models_data = [
            model.model_dump() if hasattr(model, 'model_dump') else dict(model)
            for model in models
        ]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(models_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(models)} models to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export models: {e}")
        return False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="List available models using OpenAI SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Environment file
    parser.add_argument(
        "--env-file", type=str, default=None,
        help="Path to .env file to load (e.g. ../.env or ../.env_azure)"
    )

    # Connection parameters
    parser.add_argument(
        "--proxy-url", default=None,
        help="Proxy base URL (without /v1). Falls back to OPENAI_API_BASE env var"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key. Falls back to OPENAI_API_KEY env var"
    )

    # Filtering and display
    parser.add_argument(
        "--filter",
        help="Filter models by name pattern (case-insensitive)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed information for each model"
    )

    # Export options
    parser.add_argument(
        "--output",
        help="Export models to JSON file"
    )

    # Debug options
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
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

    logger.info(f"Connecting to gateway: {base_url}")

    # List all models
    models = list_models(client)

    if not models:
        logger.error("No models retrieved from gateway")
        return 1

    logger.info(f"Retrieved {len(models)} models from gateway")

    # Apply filter if specified
    if args.filter:
        models = filter_models(models, args.filter)
        logger.info(f"Filtered to {len(models)} models matching '{args.filter}'")

    # Display results
    if args.detailed:
        print_model_details(models)
    else:
        print_model_summary(models)

    # Export if requested
    if args.output:
        if export_models_json(models, args.output):
            print(f"Models exported to: {args.output}")
        else:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
