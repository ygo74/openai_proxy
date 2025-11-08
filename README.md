# FastAPI OpenAI Proxy

This project is a FastAPI-based proxy for OpenAI. It provides a simple interface to interact with OpenAI's API.

## Features

- OpenAI-compatible API endpoints (`/v1/chat/completions`, `/v1/completions`, `/v1/models`)
- Streaming support for chat completions using Server-Sent Events (SSE)
- Authentication via OAuth2/Keycloak and API keys
- Authorization based on user groups and model permissions
- Support for multiple LLM providers (OpenAI, Azure OpenAI, Anthropic)

# sources

transparent proxy : https://github.com/fangwentong/openai-proxy
OpenAI:

- schema : https://github.com/openai/openai-openapi/blob/manual_spec/openapi.yaml
- migration to responses api: https://platform.openai.com/docs/guides/migrate-to-responses
- sdk : https://github.com/openai/openai-python/blob/main/src/openai/types/chat/chat_completion_chunk.py
- responses API: https://platform.openai.com/docs/api-reference/responses

Azure:

- https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure?tabs=global-standard-aoai%2Cstandard-chat-completions%2Cglobal-standard&pivots=azure-openai

# development

## Init environment

``` bash
python3.11 -m venv venv/openai_proxy
. venv/openai_proxy/bin/activate
pip install --upgrade pip
pip install poetry
pip install wheel setuptools Cython

poetry install

```

## Start backends

``` powershell
docker compose -f .\docker-compose-backend.yml up -d

```

## start the service

``` powershell
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

```

## Using streaming chat completions

Streaming is supported for chat completions by setting the `stream` parameter to `true`:

```json
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Tell me a story"}],
  "stream": true
}
```

The API will return a Server-Sent Events (SSE) stream that can be consumed by clients such as the official OpenAI SDK or compatible libraries.

## Using tools

Tools are supported if the underlying model supports function calls:
- https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling
- https://python.langchain.com/docs/how_to/tool_results_pass_to_model/

### Responses API vs Chat Completions API Tool Format

The Responses API uses a different tool format compared to Chat Completions:
- **Chat Completions**: Uses `tools` array with `{"type": "function", "function": {...}}` format
- **Responses API**: Uses different tool format - see [OpenAI migration guide](https://platform.openai.com/docs/guides/migrate-to-responses)

When using LangChain with `output_version="responses/v1"`, the library handles the format conversion automatically via `bind_tools()`.

## Testing Responses API

Two test scripts are provided to validate Responses API functionality:

### LangChain Test Script
```bash
# Basic test with LangChain
python tools/langchain/langchain_call_responses_api.py --question "What is 2+2?" --model gpt-4o

# Function calling with auto-execution
python tools/langchain/langchain_call_responses_api.py --question "What time is it in Paris?" --model gpt-4o --time-tool --auto-tools

# Streaming with reasoning
python tools/langchain/langchain_call_responses_api.py --question "Explain quantum computing" --model gpt-4o --stream --reasoning-effort medium
```

### Native OpenAI SDK Test Script
```bash
# Basic test with native SDK
python tools/test_responses_openai_sdk.py --question "What is 2+2?" --model gpt-4o

# Function calling with auto-execution
python tools/test_responses_openai_sdk.py --question "What time is it in Tokyo?" --model gpt-4o --function-tools --auto-execute

# Web search with streaming
python tools/test_responses_openai_sdk.py --question "Latest AI news" --model gpt-4o --web-search --stream

# Multimodal with reasoning
python tools/test_responses_openai_sdk.py --question "Describe this image" --file-path ./image.png --reasoning-effort high --reasoning-summary detailed

# Follow-up conversation
python tools/test_responses_openai_sdk.py --question "Hi, I'm Bob" --follow-up "What's my name?" --use-previous
```

The native SDK script tests all Responses API features directly without LangChain abstraction.

# Azure configuration

Pour pouvoir lister les modèles déployés sur Azure via l’API REST que tu mentionnes, il te faut une authentification OAuth 2.0 avec Azure Active Directory (AAD). Voici comment procéder étape par étape pour intégrer cela dans une API :

## 🔐 Étapes pour s'authentifier sur Azure via une API

1. Enregistrer ton application dans Azure AD
Va sur Azure Portal

Navigue vers Azure Active Directory > App registrations

Clique sur New registration

Note le Client ID (Application ID) et le Tenant ID

2. Créer un secret ou certificat pour l’application
Dans ton application enregistrée > Certificates & Secrets

Crée un secret client (Client Secret) et sauvegarde sa valeur

3. Attribuer les autorisations API
Dans ton application > API permissions

Ajoute l’autorisation Azure Service Management > user_impersonation (ou selon l’API utilisée)

Clique sur Grant admin consent si nécessaire

## 🔍 Étapes pour le retrouver dans le portail Azure
Connecte-toi au portail Azure

Dans le menu de gauche, clique sur Abonnements (ou cherche "Subscriptions" dans la barre de recherche)

Tu verras la liste de tes abonnements. L’ID d’abonnement est affiché dans la deuxième colonne

Tu peux aussi cliquer sur le nom de l’abonnement pour voir plus de détails et copier l’ID facilement

## 🔐 Étapes pour donner accès au service azure openai

1. Vérifie que ton application a bien le rôle requis
Tu dois attribuer à ton application Azure AD un rôle sur la ressource Azure OpenAI. Voici comment faire :

Va sur Azure Portal

Navigue vers la ressource Azure OpenAI

Clique sur Contrôle d’accès (IAM) dans le menu de gauche

Clique sur Ajouter un rôle

Sélectionne le rôle permettant de lire les déploiements:

- Use this Role : Cognitive Services OpenAI User

Dans la section Membre, choisis Identité managée ou application et sélectionne ton application

# Database initialisation

- install dependencies

  ``` powershell
  poetry add alembic sqlalchemy psycopg2-binary

  ```

- alembic.ini

  ``` ini
  sqlalchemy.url = postgresql+psycopg2://fastapi:fastapi@localhost:5432/fastapi_proxy
  ```

- Generate first migration

``` powershell
poetry run alembic revision --autogenerate -m "init schema"

```