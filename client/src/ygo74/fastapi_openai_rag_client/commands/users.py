"""Users command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.commands import CommandGroup, CLICommandsLoader
from knack.arguments import ArgumentsContext

from ..core.client import ApiClient
from ..core.auth import AuthContext

logger = logging.getLogger(__name__)

class UserCommandsLoader(CLICommandsLoader):
    """Command loader for user commands."""

    def __init__(self, cli_ctx=None, api_client=None):
        """Initialize command loader.

        Args:
            cli_ctx: CLI context
            api_client: API client instance
        """
        self.cli_ctx = cli_ctx
        self.api_client = api_client

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load user commands into command table."""
        with CommandGroup(command_loader, 'user', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.users.UserCommandsLoader#{}') as g:
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
        with CommandGroup(command_loader, 'auth', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.users.UserCommandsLoader#{}') as g:
            g.command('login', "login")
            g.command('logout', "logout")
            g.command('set-key', "set_api_key")

        return {}

    def load_arguments(self, command_loader: CLICommandsLoader, command):
        """Load command arguments."""
        if command.name.startswith('user'):
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

        elif command.name.startswith('auth'):
            with ArgumentsContext(command_loader, 'auth login') as arg_context:
                arg_context.argument('username', type=str, help='Keycloak username')
                arg_context.argument('password', type=str, help='Keycloak password')

            with ArgumentsContext(command_loader, 'auth set-key') as arg_context:
                arg_context.argument('api_key', type=str, help='API key')

    def list_users(self, cmd, skip=0, limit=100, active_only=True):
        """List all users."""
        return self.api_client.list_users(skip=skip, limit=limit, active_only=active_only)

    def get_user(self, cmd, user_id):
        """Get user by ID."""
        return self.api_client.get_user(user_id=user_id)

    def get_user_by_username(self, cmd, username):
        """Get user by username."""
        return self.api_client.get_user_by_username(username=username)

    def create_user(self, cmd, username, email=None, groups=None):
        """Create a new user."""
        return self.api_client.create_user(username=username, email=email, groups=groups)

    def update_user(self, cmd, user_id, username=None, email=None, groups=None):
        """Update an existing user."""
        return self.api_client.update_user(
            user_id=user_id,
            username=username,
            email=email,
            groups=groups
        )

    def delete_user(self, cmd, user_id):
        """Delete a user."""
        return self.api_client.delete_user(user_id=user_id)

    def deactivate_user(self, cmd, user_id):
        """Deactivate a user."""
        return self.api_client.deactivate_user(user_id=user_id)

    def create_api_key(self, cmd, user_id, name=None, expires_at=None):
        """Create a new API key for a user."""
        result = self.api_client.create_api_key(user_id=user_id, name=name, expires_at=expires_at)

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

    def get_user_statistics(self, cmd):
        """Get user statistics."""
        return self.api_client._make_request("GET", "/v1/users/statistics")

    def login(self, cmd, username, password):
        """Login with username and password."""
        # Get auth context from CLI context
        auth_ctx = AuthContext(cmd.cli_ctx)
        success = auth_ctx.login_interactive(username, password)

        if success:
            return {"status": "success", "message": f"Successfully logged in as {username}"}
        else:
            return {"status": "error", "message": "Login failed. Check your credentials."}

    def logout(self, cmd):
        """Logout and clear authentication data."""
        auth_ctx = AuthContext(cmd.cli_ctx)
        auth_ctx.logout()
        return {"status": "success", "message": "Successfully logged out"}

    def set_api_key(self, cmd, api_key):
        """Set API key for authentication."""
        auth_ctx = AuthContext(cmd.cli_ctx)
        auth_ctx.set_api_key(api_key)
        return {"status": "success", "message": "API key saved successfully"}
