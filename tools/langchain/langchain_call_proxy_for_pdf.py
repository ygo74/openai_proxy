from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import logging
import argparse
import os
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import json
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from mimetypes import guess_type


# # Setup logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

system_prompt= """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""

# Function to encode a local PDF document into data URL
def pdf_document_to_data_url(pdf_path: str):
    # Guess the MIME type of the PDF based on the file extension
    mime_type, _ = guess_type(pdf_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default MIME type if none is found

    # Read and encode the PDF file
    with open(pdf_path, "rb") as pdf_file:
        base64_encoded_data = base64.b64encode(pdf_file.read()).decode('utf-8')

    # Construct the data URL
    return f"data:{mime_type};base64,{base64_encoded_data}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=str, default=None,
                        help="Path to .env file to load (e.g. ../.env or ../.env_azure)")
    parser.add_argument("--model", help="Model's name", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="Can you describe this PDF document?")
    parser.add_argument("--pdf_path", help="Path to the PDF file", required=True)
    parser.add_argument("--proxy-url", default=None,
                        help="Proxy base URL. Falls back to OPENAI_API_BASE env var")
    parser.add_argument("--api-key", default=None,
                        help="API key. Falls back to OPENAI_API_KEY env var")
    args = parser.parse_args()

    # Load .env file if specified
    if args.env_file:
        env_path = Path(args.env_file) if Path(args.env_file).is_absolute() else Path(__file__).parent / args.env_file
        if env_path.is_file():
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=str(env_path), override=True)
        else:
            print(f"Environment file not found: {env_path}")
            return

    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    proxy_url = args.proxy_url or os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")
    base_url = proxy_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    if not api_key:
        print("API key is required. Use --api-key or set OPENAI_API_KEY.")
        return

    print(f"Script will use the model: {args.model}")
    print(f"Script will answer to the question: {args.question}")

    messages=[
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
                {
                    "type": "text",
                    "text": args.question
                },
                {
                    "type": "file",
                    "file": {
                        "filename": args.pdf_path.split("/")[-1],
                        "file_data": pdf_document_to_data_url(args.pdf_path),
                    }
                }
            ])
    ]


    # Initialize model
    print("Initialize llm")

    llm = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=args.model,
        temperature=0,
        max_retries=2
    )

    print("Ask the model about the document")
    ai_msg = llm.invoke(messages)

    print(ai_msg.content)


if __name__ == "__main__":
    main()