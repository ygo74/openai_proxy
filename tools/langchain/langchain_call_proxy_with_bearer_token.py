from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
import logging
import argparse
from typing import Dict, Any, Optional
import requests
import json
from pydantic import BaseModel


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

system_prompt= """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "fastapi-openai-rag"
CLIENT_ID = "fastapi-app"
CLIENT_SECRET = "fastapi-secret-key"

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

@tool
def get_weather(location: str) -> str:
    """Get weather at a location."""
    print("=" * 60)
    print(f"Getting weather for location: {location}")
    return f"It's sunny at {location}."


class OutputSchema(BaseModel):
    """Schema for response."""

    answer: str
    justification: str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model's name as defined in Azure Deployment model", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="Who are you and what is your cutoff date?")
    parser.add_argument("--stream", help="Use streaming mode instead of normal invoke", action="store_true")
    args = parser.parse_args()

    print(f"Script will use the model: {args.model}")
    print(f"Script will answer to the question: {args.question}")
    print(f"Streaming mode: {'enabled' if args.stream else 'disabled'}")


    # Get access token
    token_data = get_access_token("admin_user", "admin123")
    if token_data is None:
        print("Failed to get access token. Exiting.")
        return

    access_token = token_data["access_token"]

    # Initialize model
    print("Initialize llm")

    # Pour plus de transparence, activons le débogage HTTP de Langchain
    import os
    import httpx
    import json

    # Activer le débogage Langchain - Update to use V2 tracing
    os.environ["LANGCHAIN_VERBOSE"] = "false"
    # Remove deprecated handler
    # os.environ["LANGCHAIN_HANDLER"] = "langchain"
    # Set the V2 tracing environment variable
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    # Créer un client HTTP standard avec le token d'authentification
    debug_client = httpx.Client(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=httpx.Timeout(timeout=None)
    )

    # Fonction de rappel pour enregistrer les requêtes et réponses
    def log_request(request):
        print(f"\n[DEBUG] Sending request to: {request.method} {request.url}")
        print(f"[DEBUG] Headers: {request.headers}")
        if request.content:
            try:
                body = request.content.decode('utf-8')
                body_json = json.loads(body)
                print(f"[DEBUG] Request body: {json.dumps(body_json, indent=2)[:1000]}")
            except:
                print(f"[DEBUG] Request body: (could not decode)")

    # Ajouter des hooks d'événements au client
    # debug_client.event_hooks["request"] = [log_request]

    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key=access_token,  # Non utilisé car on a déjà le bearer token dans les en-têtes
        model=args.model,
        temperature=0,
        max_retries=2,
        streaming=True if args.stream else False,
        http_client=debug_client,  # Utiliser notre client HTTP personnalisé
        verbose=True  # Activer la verbosité pour plus d'information
    )

    print(f"Configured LLM with streaming={args.stream}")

    structured_llm = llm.bind_tools(
        [get_weather],
        # response_format=OutputSchema,
        strict=True,
    )


    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            ("human", "{input}"),
        ]
    )

    chain = prompt | structured_llm

    print("Invoke llm")
    messages = {
        "input": args.question,
    }

    if args.stream:
        print("Using streaming mode")
        for chunk in chain.stream(messages):
            print(chunk.text(), end="")
        print("")  # Add a newline at the end
    else:
        print("Using normal invoke mode")
        result = chain.invoke(messages)
        print(result)

if __name__ == "__main__":
    main()