# Usage Guide for FastAPI OpenAI RAG Client

This guide provides step-by-step instructions for installing and using the FastAPI OpenAI RAG client.

## Installation

### Option 1: Regular Installation

```bash
# From the project root directory
cd client
pip install -e .
```

### Option 2: Installation with Dependencies Fix

If you encounter any issues with dependencies, use the fix script:

```bash
# From the project root directory
python fix_client.py
```

## Authentication

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

## Configuration

You can configure the client using environment variables:

```bash
# Windows PowerShell
$env:RAG_API_URL = "http://localhost:8000"  # Base URL for the API
$env:RAG_API_KEY = "your-api-key"           # API key (if not using login)
$env:RAG_KEYCLOAK_URL = "http://keycloak-server/realm/token"  # Keycloak token URL
```

## Examples

### Managing Users

```bash
# List all users
rag-client user list

# Get user details
rag-client user show --user-id 123

# Create a new user
rag-client user create --username jdoe --email john.doe@example.com

# Create API key for a user
rag-client user create-key --user-id 123 --name "dev-key" --expires-at "2024-12-31T23:59:59Z"
```

### Managing Groups

```bash
# List all groups
rag-client group list

# Create a new group
rag-client group create --name "data-science" --description "Data Science Team"

# Get group details
rag-client group show --group-id 456
```

### Managing Models

```bash
# List all models
rag-client model list

# Add a model to a group
rag-client model add-to-group --model-id 789 --group-id 456

# List models in a group
rag-client model list-in-group --group-id 456
```

### Managing Rate Limits

```bash
# List all rate limit configurations
rag-client rate-limit list

# Show specific rate limit
rag-client rate-limit show --scope-type model --scope-id 5

# Create global rate limit (applies to all models as fallback)
rag-client rate-limit create-global --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]'

# Create model-specific rate limit
rag-client rate-limit create-model --model-id 5 --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'

# Create group/model rate limit (highest priority)
rag-client rate-limit create-group-model --group-name key_users --model-id 5 --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":100,"max_tokens":10000}]'

# Update rate limit (disable temporarily)
rag-client rate-limit update --scope-type model --scope-id 5 --enabled false

# Delete rate limit
rag-client rate-limit delete --scope-type model --scope-id 5
```

**Rate Limit Hierarchy:**

1. **Group/Model** (highest priority) - Applies when user is in authorized group for that model
2. **Global** (fallback) - Applies when no group/model rate limit exists
3. **Model** (aggregate protection) - Always checked to prevent model overload

**Time Windows Format:**

- `from_time`: Start time in HH:MM:SS format (e.g., "09:00:00")
- `to_time`: End time in HH:MM:SS format (e.g., "17:00:00")
- `max_requests`: Maximum number of requests in the window
- `max_tokens`: Maximum number of tokens (input + output) in the window

#### Example: Business Hours Rate Limit

```bash
rag-client rate-limit create-model --model-id 5 --windows '[
  {"from_time":"09:00:00","to_time":"17:00:00","max_requests":1000,"max_tokens":100000},
  {"from_time":"17:00:00","to_time":"09:00:00","max_requests":100,"max_tokens":10000}
]'
```

## Troubleshooting

### Authentication Issues

If you encounter authentication issues:

1. Check if your API key is valid
2. Ensure your Keycloak credentials are correct
3. Try re-authenticating with `rag-client auth login`

### Connection Issues

If you encounter connection issues:

1. Verify that the API server is running
2. Check if the API URL is correct
3. Ensure network connectivity to the API server

## Getting Help

For more information about available commands:

```bash
# Show general help
rag-client -h

# Show help for a specific command group
rag-client user -h
rag-client model -h
rag-client group -h

# Show help for a specific command
rag-client user create -h
```
