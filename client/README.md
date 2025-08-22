# FastAPI OpenAI RAG Client

A command-line client for managing FastAPI OpenAI RAG proxy.

## Installation

Install the client package:

```bash
# From the client directory
pip install -e .
```

## Authentication

There are two ways to authenticate:

### Using API Key

```bash
# Set your API key
rag-client auth set-key YOUR_API_KEY
```

### Using Keycloak

```bash
# Login with Keycloak
rag-client auth login --username YOUR_USERNAME --password YOUR_PASSWORD
```

## Usage

### User Management

```bash
# List all users
rag-client user list

# Get user by ID
rag-client user show --user-id USER_ID

# Find user by username
rag-client user find --username USERNAME

# Create a new user
rag-client user create --username USERNAME --email EMAIL --groups GROUP1 GROUP2

# Update user
rag-client user update --user-id USER_ID --username NEW_USERNAME --email NEW_EMAIL

# Deactivate user
rag-client user deactivate --user-id USER_ID

# Create API key for user
rag-client user create-key --user-id USER_ID --name KEY_NAME --expires-at "2024-12-31T23:59:59Z"
```

### Group Management

```bash
# List all groups
rag-client group list

# Get group by ID
rag-client group show --group-id GROUP_ID

# Create a new group
rag-client group create --name GROUP_NAME --description "Group description"

# Update group
rag-client group update --group-id GROUP_ID --name NEW_NAME --description "New description"

# Delete group
rag-client group delete --group-id GROUP_ID
```

### Model Management

```bash
# List all models
rag-client model list

# Get model by ID
rag-client model show --model-id MODEL_ID

# Create a new model
rag-client model create --name MODEL_NAME --provider PROVIDER --base-url URL --description "Model description"

# Update model
rag-client model update --model-id MODEL_ID --name NEW_NAME --description "New description"

# Delete model
rag-client model delete --model-id MODEL_ID

# Associate model with group
rag-client model add-to-group --model-id MODEL_ID --group-id GROUP_ID

# Remove model from group
rag-client model remove-from-group --model-id MODEL_ID --group-id GROUP_ID

# List models in a group
rag-client model list-in-group --group-id GROUP_ID
```

## Environment Variables

You can configure the client using environment variables:

- `RAG_API_URL`: Base URL for the API
- `RAG_API_KEY`: API key for authentication
- `RAG_KEYCLOAK_URL`: Keycloak server URL
- `RAG_KEYCLOAK_REALM`: Keycloak realm
- `RAG_KEYCLOAK_CLIENT_ID`: Keycloak client ID
