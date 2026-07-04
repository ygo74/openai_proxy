# https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling

from openai import OpenAI
import logging
import argparse
import os
from typing import Dict, Any, Optional
import requests
import json
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from mimetypes import guess_type
# Setup logging
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

system_prompt= """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""

# Function to encode a local image into data URL
def local_image_to_data_url(image_path):
    # Guess the MIME type of the image based on the file extension
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default MIME type if none is found

    # Read and encode the image file
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode('utf-8')

    # Construct the data URL
    return f"data:{mime_type};base64,{base64_encoded_data}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=str, default=None,
                        help="Path to .env file to load (e.g. ../.env or ../.env_azure)")
    parser.add_argument("--model", help="Model's name", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="Can you describe this image?")
    parser.add_argument("--image_path", help="Path to the image file", required=True)
    parser.add_argument("--proxy-url", default=None,
                        help="Proxy base URL (without /v1). Falls back to OPENAI_API_BASE env var")
    parser.add_argument("--api-key", default=None,
                        help="API key. Falls back to OPENAI_API_KEY env var")
    args = parser.parse_args()

    # Load .env file if specified
    if args.env_file:
        from pathlib import Path
        env_path = Path(args.env_file) if Path(args.env_file).is_absolute() else Path(__file__).parent / args.env_file
        if env_path.is_file():
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=str(env_path), override=True)
        else:
            print(f"Environment file not found: {env_path}")
            return

    # Resolve API key and base URL: CLI args > env vars
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    proxy_url = args.proxy_url or os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")

    if not api_key:
        print("API key is required. Use --api-key or set OPENAI_API_KEY (via --env-file or shell).")
        return

    # Normalize base_url
    base_url = proxy_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    print(f"Script will use the model : {args.model}")
    print(f"Script will answer to the question: {args.question}")

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": args.question
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": local_image_to_data_url(args.image_path),
                        "detail": "high"
                    }
                }
            ]
        }
    ]


    # Initialize model
    print("Initialize llm")
    llm = OpenAI(
        base_url=base_url,
        api_key=api_key
    )


    print(f"API call: Ask the model on the image {args.image_path}")
    # First API call: Ask the model to use the function
    response = llm.chat.completions.create(
        model=args.model,
        messages=messages,
    )

    print("Model's response:")
    print(response)

if __name__ == "__main__":
    main()