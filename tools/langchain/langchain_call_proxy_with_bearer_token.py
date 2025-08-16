from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import logging
import argparse
from typing import Dict, Any, Optional
import requests
import json

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model's name as defined in Azure Deployment model", default="gpt-4o")
    parser.add_argument("--question", help="Question to ask the model", required=False, default="Who are you and what is your cutoff date?")
    args = parser.parse_args()

    print(f"Script will use the model : {args.model}")
    print(f"Script will answer to the question: {args.question}")


    # Get access token
    token_data = get_access_token("admin_user", "admin123")
    access_token = token_data["access_token"]

    # Initialize model
    print("Initialize llm")
    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key=access_token,
        model=args.model,
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2
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

    chain = prompt | llm

    print("Invoke llm")
    result = chain.invoke(
        {
            "input": args.question,
        }
    )
    print(result)

if __name__ == "__main__":
    main()