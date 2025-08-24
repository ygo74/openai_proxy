from knack.commands import CLICommand
from .client import ApiClient

def get_api_client(cmd: CLICommand) -> ApiClient:
    """Retrieve the ApiClient instance from the CLI context."""

    cli_ctx = getattr(cmd, "cli_ctx", None)
    if cli_ctx is None or not hasattr(cli_ctx, "data"):
        raise ValueError("CLI context is not properly initialized.")

    data = getattr(cli_ctx, "data", None)
    if data is None or not hasattr(data, "get"):
        raise ValueError("CLI context data is not available.")

    api_client = data.get("api_client", None)
    if not isinstance(api_client, ApiClient):
        raise ValueError("Not authenticated. Please log in first.")
    return api_client

def get_auth_ctx(cmd: CLICommand):
    """Retrieve the AuthContext instance from the CLI context."""

    cli_ctx = getattr(cmd, "cli_ctx", None)
    if cli_ctx is None or not hasattr(cli_ctx, "data"):
        raise ValueError("CLI context is not properly initialized.")

    data = getattr(cli_ctx, "data", None)
    if data is None or not hasattr(data, "get"):
        raise ValueError("CLI context data is not available.")

    auth_ctx = data.get("auth_ctx", None)
    if auth_ctx is None:
        raise ValueError("Authentication context is not available.")
    return auth_ctx