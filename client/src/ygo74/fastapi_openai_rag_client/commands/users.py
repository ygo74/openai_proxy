"""Users command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader, CLICommand
from knack.arguments import ArgumentsContext

from ..core.client import ApiClient
from ..core.utils import get_api_client, get_auth_ctx
from knack.log import get_logger
logger = get_logger(__name__)

class UserCommandsLoader:
    """Command loader for user commands."""

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load user commands into command table."""

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

        if command.startswith('user'):
            with ArgumentsContext(command_loader, 'user list') as arg_context:
                arg_context.argument('skip', type=int, help='Number of records to skip')
                arg_context.argument('limit', type=int, help='Maximum number of records to return')
                arg_context.argument('active_only', help='Show only active users')

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

def list_users(cmd: CLICommand, skip: int =0, limit: int=100, active_only=False)-> List[Dict[str, Any]]:
    """List all users."""
    api_client = get_api_client(cmd)
    return api_client.list_users(skip=skip, limit=limit, active_only=active_only)

def get_user(cmd: CLICommand, user_id: str) -> Dict[str, Any]:
    """Get user by ID."""
    api_client = get_api_client(cmd)
    return api_client.get_user(user_id=user_id)

def get_user_by_username(cmd: CLICommand, username: str) -> Dict[str, Any]:
    """Get user by username."""
    api_client = get_api_client(cmd)
    return api_client.get_user_by_username(username=username)

def create_user(cmd: CLICommand, username: str, email: Optional[str] = None, groups: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create a new user."""
    api_client = get_api_client(cmd)
    return api_client.create_user(username=username, email=email, groups=groups)

def update_user(cmd: CLICommand, user_id: str, username: Optional[str] = None, email: Optional[str] = None, groups: Optional[List[str]] = None) -> Dict[str, Any]:
    """Update an existing user."""
    api_client = get_api_client(cmd)
    return api_client.update_user(
        user_id=user_id,
        username=username,
        email=email,
        groups=groups
    )

def delete_user(cmd: CLICommand, user_id: str) -> Dict[str, Any]:
    """Delete a user."""
    api_client = get_api_client(cmd)
    return api_client.delete_user(user_id=user_id)

def deactivate_user(cmd: CLICommand, user_id: str) -> Dict[str, Any]:
    """Deactivate a user."""
    api_client = get_api_client(cmd)
    return api_client.deactivate_user(user_id=user_id)

def create_api_key(cmd: CLICommand, user_id: str, name: Optional[str] = None, expires_at: Optional[str] = None) -> Dict[str, Any]:
    """Create a new API key for a user."""
    api_client = get_api_client(cmd)
    result = api_client.create_api_key(user_id=user_id, name=name, expires_at=expires_at)

    # Format the output to make the API key more visible
    if 'api_key' in result:
        # Format the output in a user-friendly way
        formatted = {
            'API_KEY': result['api_key'],
            'key_info': result['key_info']
        }
        # Ensure the API key is prominently displayed
        logger.warning("\nAPI KEY: %s\n", result['api_key'])
        logger.warning("KEEP THIS KEY SAFE! It won't be shown again.")
        return formatted

    return result

def get_user_statistics(cmd: CLICommand) -> Dict[str, Any]:
    """Get user statistics."""
    api_client = get_api_client(cmd)
    return api_client._make_request("GET", "/v1/users/statistics")

def login(cmd: CLICommand, username: str, password: str) -> Dict[str, Any]:
    """Login with username and password."""
    # Get auth context from CLI context
    auth_ctx = get_auth_ctx(cmd)
    success = auth_ctx.login_interactive(username, password)

    if success:
        return {"status": "success", "message": f"Successfully logged in as {username}"}
    else:
        return {"status": "error", "message": "Login failed. Check your credentials."}

def logout(cmd: CLICommand) -> Dict[str, Any]:
    """Logout and clear authentication data."""
    auth_ctx = get_auth_ctx(cmd)
    auth_ctx.logout()
    return {"status": "success", "message": "Successfully logged out"}

def set_api_key(cmd: CLICommand, api_key: str) -> Dict[str, Any]:
    """Set API key for authentication."""
    auth_ctx = get_auth_ctx(cmd)
    auth_ctx.set_api_key(api_key)
    return {"status": "success", "message": "API key saved successfully"}
