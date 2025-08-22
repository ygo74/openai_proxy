"""Users command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader
from knack.arguments import ArgumentsContext

from ..core.client import ApiClient
from ..core.auth import AuthContext

logger = logging.getLogger(__name__)

def init_api_client(cli: CLI | None):
    global api_client
    if cli is not None and 'api_client' in cli.data:
        api_client = cli.data['api_client']

def init_auth_ctx(cli: CLI | None):
    global auth_ctx
    if cli is not None and 'auth_ctx' in cli.data:
        auth_ctx = cli.data['auth_ctx']

class UserCommandsLoader:
    """Command loader for user commands."""

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load user commands into command table."""

        init_api_client(command_loader.cli_ctx)
        init_auth_ctx(command_loader.cli_ctx)

        with CommandGroup(command_loader, 'user', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.users#{}') as g:
            g.command('list', "list_users")
            g.command('show', "get_user")
            g.command('find', "get_user_by_username")
            g.command('create', "create_user")
            g.command('update', "update_user")
            g.command('delete', "delete_user")
            g.command('deactivate', "deactivate_user")
            g.command('create-key', "create_api_key")
            g.command('stats', "get_user_statistics")

        # Add auth commands
        with CommandGroup(command_loader, 'auth', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.users#{}') as g:
            g.command('login', "login")
            g.command('logout', "logout")
            g.command('set-key', "set_api_key")

        return {}

    def load_arguments(self, command_loader: CLICommandsLoader, command):
        """Load command arguments."""

        init_api_client(command_loader.cli_ctx)
        init_auth_ctx(command_loader.cli_ctx)

        if command.startswith('user'):
            with ArgumentsContext(command_loader, 'user list') as arg_context:
                arg_context.argument('skip', type=int, help='Number of records to skip')
                arg_context.argument('limit', type=int, help='Maximum number of records to return')
                arg_context.argument('active_only', type=bool, help='Show only active users')

            with ArgumentsContext(command_loader, 'user show') as arg_context:
                arg_context.argument('user_id', type=str, help='User ID')

            with ArgumentsContext(command_loader, 'user find') as arg_context:
                arg_context.argument('username', type=str, help='Username to search for')

            with ArgumentsContext(command_loader, 'user create') as arg_context:
                arg_context.argument('username', type=str, help='Username')
                arg_context.argument('email', type=str, help='Email address')
                arg_context.argument('groups', type=str, nargs='+', help='List of group names')

            with ArgumentsContext(command_loader, 'user update') as arg_context:
                arg_context.argument('user_id', type=str, help='User ID')
                arg_context.argument('username', type=str, help='New username')
                arg_context.argument('email', type=str, help='New email address')
                arg_context.argument('groups', type=str, nargs='+', help='New list of group names')

            with ArgumentsContext(command_loader, 'user delete') as arg_context:
                arg_context.argument('user_id', type=str, help='User ID')

            with ArgumentsContext(command_loader, 'user deactivate') as arg_context:
                arg_context.argument('user_id', type=str, help='User ID')

            with ArgumentsContext(command_loader, 'user create-key') as arg_context:
                arg_context.argument('user_id', type=str, help='User ID')
                arg_context.argument('name', type=str, help='Key name')
                arg_context.argument('expires_at', type=str, help='Expiration date (ISO format)')

        elif command.startswith('auth'):
            with ArgumentsContext(command_loader, 'auth login') as arg_context:
                arg_context.argument('username', type=str, help='Keycloak username')
                arg_context.argument('password', type=str, help='Keycloak password')

            with ArgumentsContext(command_loader, 'auth set-key') as arg_context:
                arg_context.argument('api_key', type=str, help='API key')

def list_users(skip=0, limit=100, active_only=True):
    """List all users."""
    return api_client.list_users(skip=skip, limit=limit, active_only=active_only)

def get_user(user_id):
    """Get user by ID."""
    return api_client.get_user(user_id=user_id)

def get_user_by_username(username):
    """Get user by username."""
    return api_client.get_user_by_username(username=username)

def create_user(username, email=None, groups=None):
    """Create a new user."""
    return api_client.create_user(username=username, email=email, groups=groups)

def update_user(user_id, username=None, email=None, groups=None):
    """Update an existing user."""
    return api_client.update_user(
        user_id=user_id,
        username=username,
        email=email,
        groups=groups
    )

def delete_user(user_id):
    """Delete a user."""
    return api_client.delete_user(user_id=user_id)

def deactivate_user(user_id):
    """Deactivate a user."""
    return api_client.deactivate_user(user_id=user_id)

def create_api_key(user_id, name=None, expires_at=None):
    """Create a new API key for a user."""
    result = api_client.create_api_key(user_id=user_id, name=name, expires_at=expires_at)

    # Format the output to make the API key more visible
    if 'api_key' in result:
        # Format the output in a user-friendly way
        formatted = {
            'API_KEY': result['api_key'],
            'key_info': result['key_info']
        }
        # Ensure the API key is prominently displayed
        cmd.cli_ctx.get_log().warning("\nAPI KEY: %s\n", result['api_key'])
        cmd.cli_ctx.get_log().warning("KEEP THIS KEY SAFE! It won't be shown again.")
        return formatted

    return result

def get_user_statistics(self):
    """Get user statistics."""
    return api_client._make_request("GET", "/v1/users/statistics")

def login(self, username, password):
    """Login with username and password."""
    # Get auth context from CLI context
    success = auth_ctx.login_interactive(username, password)

    if success:
        return {"status": "success", "message": f"Successfully logged in as {username}"}
    else:
        return {"status": "error", "message": "Login failed. Check your credentials."}

def logout(self):
    """Logout and clear authentication data."""
    auth_ctx.logout()
    return {"status": "success", "message": "Successfully logged out"}

def set_api_key(api_key):
    """Set API key for authentication."""
    auth_ctx.set_api_key(api_key)
    return {"status": "success", "message": "API key saved successfully"}
