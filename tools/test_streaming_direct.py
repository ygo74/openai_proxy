#!/usr/bin/env python
"""
Script pour tester directement le streaming de l'API OpenAI Proxy
sans passer par Langchain, en utilisant les requêtes HTTP directes.
"""

import argparse
import json
import logging
import requests
import sys
import time
from typing import Dict, Any, Optional, Generator, List

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "fastapi-openai-rag"
CLIENT_ID = "fastapi-app"
CLIENT_SECRET = "fastapi-secret-key"
API_BASE_URL = "http://localhost:8000/v1"

def get_access_token(username: str, password: str) -> Optional[str]:
    """Récupère un token d'accès depuis Keycloak.

    Args:
        username (str): Nom d'utilisateur
        password (str): Mot de passe

    Returns:
        Optional[str]: Token d'accès ou None si échec
    """
    try:
        logger.info(f"Récupération du token d'accès pour l'utilisateur: {username}")

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
            access_token = token_data.get("access_token")
            logger.info("✅ Token d'accès obtenu avec succès")
            return access_token
        else:
            logger.error(f"❌ Échec de récupération du token: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération du token: {e}")
        return None

def create_chat_completion_stream(model: str, messages: List[Dict[str, str]], access_token: str) -> Generator[Dict[str, Any], None, None]:
    """Crée une complétion de chat en mode streaming.

    Args:
        model (str): Nom du modèle
        messages (list): Liste des messages
        access_token (str): Token d'authentification

    Yields:
        Generator[Dict[str, Any], None, None]: Générateur des chunks de réponse
    """
    url = f"{API_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }

    logger.debug(f"Envoi de la requête à {url}")
    logger.debug(f"Payload: {json.dumps(payload)}")

    try:
        # Utiliser la bibliothèque requests pour le streaming
        response = requests.post(url, json=payload, headers=headers, stream=True)
        response.raise_for_status()  # Lever une exception pour les erreurs HTTP

        logger.debug(f"Connexion établie. Status code: {response.status_code}")
        logger.debug(f"Headers: {response.headers}")

        # Variables pour suivre les chunks reçus
        chunk_count = 0
        start_time = time.time()
        content_received = ""

        # Traiter chaque ligne de la réponse
        for line in response.iter_lines():
            if not line:
                continue

            line = line.decode('utf-8')
            chunk_count += 1

            logger.debug(f"Chunk {chunk_count} reçu: {line[:100]}...")

            # Traiter les chunks SSE
            if line.startswith("data: "):
                data = line[6:]  # Enlever le préfixe "data: "

                # Détecter la fin du flux
                if data == "[DONE]":
                    logger.info("Fin du flux de données ([DONE] reçu)")
                    break

                try:
                    json_data = json.loads(data)

                    # Extraire le contenu du chunk (pour l'affichage progressif)
                    if "choices" in json_data and json_data["choices"]:
                        if "content" in json_data["choices"][0].get("delta", {}):
                            content = json_data["choices"][0]["delta"]["content"]
                            content_received += content
                            print(content, end="", flush=True)
                        elif "content" in json_data["choices"][0].get("message", {}):
                            content = json_data["choices"][0]["message"]["content"] or ""
                            content_received += content
                            print(content, end="", flush=True)

                    yield json_data
                except json.JSONDecodeError:
                    logger.warning(f"Impossible de décoder le JSON: {data}")

        # Afficher le résumé
        elapsed = time.time() - start_time
        logger.info(f"\n\nRésumé: {chunk_count} chunks reçus en {elapsed:.2f} secondes")
        logger.info(f"Contenu total reçu: {len(content_received)} caractères")

    except requests.RequestException as e:
        logger.error(f"Erreur lors de la requête: {e}")
        raise

def create_chat_completion_normal(model: str, messages: List[Dict[str, str]], access_token: str) -> Dict[str, Any]:
    """Crée une complétion de chat en mode normal (non-streaming).

    Args:
        model (str): Nom du modèle
        messages (list): Liste des messages
        access_token (str): Token d'authentification

    Returns:
        Dict[str, Any]: Réponse complète
    """
    url = f"{API_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0.7,
    }

    logger.debug(f"Envoi de la requête à {url}")
    logger.debug(f"Payload: {json.dumps(payload)}")

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        logger.debug(f"Réponse reçue. Status code: {response.status_code}")

        json_response = response.json()

        # Afficher le contenu de la réponse
        if "choices" in json_response and json_response["choices"]:
            content = json_response["choices"][0]["message"]["content"]
            print(f"\nRéponse: {content}")

        return json_response

    except requests.RequestException as e:
        logger.error(f"Erreur lors de la requête: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Test direct du streaming de l'API OpenAI Proxy")
    parser.add_argument("--model", help="Nom du modèle à utiliser", default="gpt-4o")
    parser.add_argument("--question", help="Question à poser au modèle",
                      default="Who are you and what is your cutoff date?")
    parser.add_argument("--stream", help="Utiliser le mode streaming", action="store_true")
    parser.add_argument("--username", help="Nom d'utilisateur pour l'authentification", default="admin_user")
    parser.add_argument("--password", help="Mot de passe pour l'authentification", default="admin123")
    parser.add_argument("--verbose", help="Afficher les logs détaillés", action="store_true")
    args = parser.parse_args()

    # Configurer le niveau de log
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    print(f"Test de l'API OpenAI Proxy")
    print(f"Modèle: {args.model}")
    print(f"Question: {args.question}")
    print(f"Mode streaming: {'activé' if args.stream else 'désactivé'}")
    print("-" * 50)

    # Obtenir le token d'accès
    access_token = get_access_token(args.username, args.password)
    if not access_token:
        logger.error("Impossible de continuer sans token d'accès")
        return 1

    # Préparer les messages
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "You are an expert in AI solution and you help your colleague to implement AI solutions"},
        {"role": "user", "content": args.question}
    ]

    try:
        if args.stream:
            print("Mode streaming activé, réponse en temps réel:\n")
            # Collecter les réponses du flux (mais l'affichage se fait dans la fonction)
            chunks = list(create_chat_completion_stream(args.model, messages, access_token))
            print(f"\n\nNombre de chunks reçus: {len(chunks)}")
        else:
            print("Mode normal (non-streaming):\n")
            response = create_chat_completion_normal(args.model, messages, access_token)
            print(f"\nRéponse complète reçue")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
