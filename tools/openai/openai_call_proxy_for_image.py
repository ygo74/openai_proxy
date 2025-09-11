# https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling

from openai import OpenAI
import logging
import argparse
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
    parser.add_argument("--model", help="Model's name as defined in Azure Deployment model", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="Can you describe this image?")
    parser.add_argument("--image_path", help="Path to the image file", required=True)
    args = parser.parse_args()

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
        base_url="http://localhost:8000/v1",
        api_key="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s"
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