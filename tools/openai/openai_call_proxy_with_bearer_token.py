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
from openai import OpenAI
import os
from dotenv import load_dotenv
import urllib.parse
import requests
from requests_kerberos import HTTPKerberosAuth, OPTIONAL
import jwt
import base64
import hashlib



# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
# Load environment variables from .env file if present
load_dotenv()

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "fastapi-openai-rag")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "fastapi-app")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", None)

# Optionnel: chemin CA si nécessaire pour la vérification TLS (sinon mettre verify=False à vos risques)
verify = True  # ou un chemin de fichier PEM, ex: "/etc/ssl/certs/your-ca.pem"

redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

# Prompt système par défaut
DEFAULT_SYSTEM_PROMPT = """
You are an expert in AI solution and you help your colleague to implement AI solutions
"""

def urlsafe_b64encode_no_padding(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def generate_code_verifier() -> str:
    # 32 octets aléatoires -> base64 urlsafe sans padding
    random_bytes = os.urandom(32)
    return urlsafe_b64encode_no_padding(random_bytes)

def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return urlsafe_b64encode_no_padding(digest)

def decode_jwt_no_verify(token: str) -> dict:
    # Décoder payload sans vérifier la signature (équivalent de votre fonction PowerShell)
    # Pour vérifier la signature, il faudrait récupérer la clé publique (JWKS).
    return jwt.decode(token, options={"verify_signature": False, "verify_exp": False})

def get_auth_code_with_spnego(auth_url: str) -> str:
    # On lance une requête GET avec Kerberos. Keycloak redirige vers l’URL de redirection avec ?code=...
    # On n'autorise pas la redirection automatique pour capturer l’en-tête Location.
    session = requests.Session()
    # requests-kerberos: OPTIONAL permet de continuer même si le serveur ne supporte pas Negotiate,
    # mettez REQUIRED si vous voulez forcer.
    auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)
    # auth = requests_gssapi.HTTPSPNEGOAuth()
    # auth = HttpNegotiateAuth()
    resp = session.get(auth_url, auth=auth, allow_redirects=False, verify=verify)
    # Si Keycloak renvoie une redirection (302/303), récupérer Location
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location")
        if not location:
            raise RuntimeError("Redirection sans en-tête Location, impossible d'extraire le code.")
        # Extraire le paramètre "code" de l’URL
        parsed = urllib.parse.urlparse(location)
        qs = urllib.parse.parse_qs(parsed.query)
        code_values = qs.get("code")
        if not code_values:
            raise RuntimeError(f"Paramètre 'code' introuvable dans Location: {location}")
        return code_values
    else:
        # Certains environnements peuvent renvoyer directement une page contenant le code pour l’OOB.
        # Essayer de trouver le code dans le corps si nécessaire.
        # Si votre setup exige strictement une redirection, c’est une erreur.
        raise RuntimeError(f"Réponse inattendue {resp.status_code}, corps: {resp.text[:500]}")

def exchange_code_for_token(token_url: str, code: str, code_verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "client_id": KEYCLOAK_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    # if KEYCLOAK_CLIENT_SECRET:
    #     data["KEYCLOAK_CLIENT_SECRET"] = KEYCLOAK_CLIENT_SECRET

    resp = requests.post(token_url, data=data, verify=verify)
    if resp.status_code != 200:
        raise RuntimeError(f"Echec token request: {resp.status_code} {resp.text}")
    return resp.json()


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
            "KEYCLOAK_CLIENT_ID": KEYCLOAK_CLIENT_ID,
            "KEYCLOAK_CLIENT_SECRET": KEYCLOAK_CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password
        }

        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
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

def get_access_token_from_kerberos() -> Optional[Dict[str, Any]]:

    # 1) Generate PKCE
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # 2) Build auth url
    auth_params = {
        "client_id": KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth?{urllib.parse.urlencode(auth_params)}"

    # 3) Get code via SPNEGO/Kerberos
    code = get_auth_code_with_spnego(auth_url)
    logger.info(f"Authorization code: {code}")

    # 4) Exchange code for token
    token_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    token_response = exchange_code_for_token(token_url, code, code_verifier)

    return token_response

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
    parser.add_argument("--model_url", default="http://localhost:8000/v1", help="Model url to connect")
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
    # token_data = get_access_token("admin_user", "admin123")
    token_data = get_access_token_from_kerberos()

    if token_data is None:
        print("Failed to get access token. Exiting.")
        return 1

    access_token = token_data["access_token"]

    # Initialize OpenAI client with our proxy
    base_url = args.model_url
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
