"""
Script pour appeler le proxy FastAPI directement avec la bibliothèque OpenAI et un Bearer token.
Cette version n'utilise pas Langchain mais directement le client OpenAI.
"""

import argparse
import logging
import json
import time
import sys
from typing import Dict, Any, Optional
import requests
from openai import OpenAI

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "fastapi-openai-rag"
CLIENT_ID = "fastapi-app"
CLIENT_SECRET = "fastapi-secret-key"

# Prompt système par défaut
DEFAULT_SYSTEM_PROMPT = """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""

def get_access_token(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Get access token from Keycloak.

    Args:
        username (str): Username
        password (str): Password

    Returns:
        Optional[Dict[str, Any]]: Token data if successful, None otherwise
    """
    try:
        logger.info(f"Getting access token for user: {username}")

        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password
        }

        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token",
            data=data
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info("✅ Access token obtained successfully")
            logger.info(f"   Token type: {token_data.get('token_type')}")
            logger.info(f"   Expires in: {token_data.get('expires_in')} seconds")
            return token_data
        else:
            logger.error(f"❌ Failed to get token: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ Error getting token: {e}")
        raise

def create_openai_client(base_url: str, bearer_token: str) -> OpenAI:
    """Create an OpenAI client with custom base URL and bearer token.

    Args:
        base_url (str): Base URL for the API
        bearer_token (str): Bearer token for authentication

    Returns:
        OpenAI: Configured OpenAI client
    """
    return OpenAI(
        api_key=bearer_token,  # La clé API est utilisée comme token
        base_url=base_url
    )

def invoke_chat_completion(client: OpenAI, model: str, messages: list, stream: bool = False, temperature: float = 0):
    """Invoke chat completion with OpenAI client.

    Args:
        client (OpenAI): OpenAI client
        model (str): Model name
        messages (list): List of messages
        stream (bool, optional): Whether to stream the response. Defaults to False.
        temperature (float, optional): Temperature for generation. Defaults to 0.

    Returns:
        Union[str, Generator]: Response text or stream
    """
    logger.info(f"Invoking chat completion with model: {model}")
    logger.debug(f"Messages: {json.dumps(messages)}")

    start_time = time.time()

    try:
        if stream:
            logger.info("Using streaming mode")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True
            )

            # Return the stream directly for the caller to process
            return response
        else:
            logger.info("Using regular completion mode")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )

            execution_time = time.time() - start_time
            logger.info(f"Completion received in {execution_time:.2f}s")

            return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Error during chat completion: {e}", exc_info=True)
        raise

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Direct OpenAI client for FastAPI proxy with Bearer token")
    parser.add_argument("--model", default="gpt-4o", help="Model name to use")
    parser.add_argument("--question", default="Who are you and what is your cutoff date?",
                        help="Question to ask the model")
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT,
                       help="System prompt to use")
    parser.add_argument("--stream", action="store_true", help="Use streaming mode")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    print(f"Script will use the model: {args.model}")
    print(f"Script will answer to the question: {args.question}")
    print(f"Streaming mode: {'enabled' if args.stream else 'disabled'}")

    # Get access token
    token_data = get_access_token("admin_user", "admin123")
    if token_data is None:
        print("Failed to get access token. Exiting.")
        return 1

    access_token = token_data["access_token"]

    # Initialize OpenAI client with our proxy
    base_url = "http://localhost:8000/v1"
    client = create_openai_client(base_url, access_token)

    # Prepare messages
    messages = [
        {"role": "system", "content": args.system_prompt},
        {"role": "user", "content": args.question}
    ]

    try:
        if args.stream:
            # Process streaming response
            print("\nStreaming response:\n" + "-" * 50)
            stream = invoke_chat_completion(client, args.model, messages, stream=True, temperature=0)

            # Track streaming statistics
            chunk_count = 0
            start_time = time.time()
            full_response = ""

            # Print each chunk as it arrives
            for chunk in stream:
                chunk_count += 1
                # print(chunk)
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    print(content, end="", flush=True)

                    # Print statistics every 20 chunks
                    if chunk_count % 20 == 0 and args.verbose:
                        elapsed = time.time() - start_time
                        print(f"\n[INFO] Received {chunk_count} chunks in {elapsed:.2f}s", end="", flush=True)

            # Final statistics
            total_time = time.time() - start_time
            print("\n" + "-" * 50)
            print(f"\nTotal chunks: {chunk_count}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Response length: {len(full_response)} characters")

        else:
            # Process regular response
            response = invoke_chat_completion(client, args.model, messages, stream=False, temperature=0)
            print("\nResponse:\n" + "-" * 50)
            print(response)
            print("-" * 50)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
