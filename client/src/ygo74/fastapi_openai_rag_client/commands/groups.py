"""Groups command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader
from knack.arguments import ArgumentsContext
from knack.help_files import helps


from ..core.client import ApiClient

logger = logging.getLogger(__name__)




class GroupCommandsLoader:
    """Command loader for group commands."""

    def __init__(self, api_client=None):
        """Initialize command loader.

        Args:
            api_client: API client instance
        """
        self.api_client = api_client

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load group commands into command table."""
        try:
            with CommandGroup(command_loader, 'group', 'ygo74.fastapi_openai_rag_client.commands.groups.GroupCommandsLoader#{}') as g:
                g.command('list', "list_groups")
                g.command('show', "get_group")
                g.command('create', "create_group")
                g.command('update', "update_group")
                g.command('delete', "delete_group")
                g.command('stats', "get_group_statistics")
        except Exception as e:
            print(f"Error loading group commands: {str(e)}")
            raise

        return {}

    def load_arguments(self,command_loader: CLICommandsLoader, command):
        """Load command arguments."""
        with ArgumentsContext(command_loader, 'group list') as arg_context:
            arg_context.argument('skip', type=int, help='Number of records to skip')
            arg_context.argument('limit', type=int, help='Maximum number of records to return')

        with ArgumentsContext(command_loader, 'group show') as arg_context:
            arg_context.argument('group_id', type=int, help='Group ID')

        with ArgumentsContext(command_loader, 'group create') as arg_context:
            arg_context.argument('name', type=str, help='Group name')
            arg_context.argument('description', type=str, help='Group description')

        with ArgumentsContext(command_loader, 'group update') as arg_context:
            arg_context.argument('group_id', type=int, help='Group ID')
            arg_context.argument('name', type=str, help='New group name')
            arg_context.argument('description', type=str, help='New group description')

        with ArgumentsContext(command_loader, 'group delete') as arg_context:
            arg_context.argument('group_id', type=int, help='Group ID')

    def list_groups(self, cmd, skip=0, limit=100):
        """List all groups."""
        return self.api_client.list_groups(skip=skip, limit=limit)

    def get_group(self, cmd, group_id):
        """Get group by ID."""
        return self.api_client.get_group(group_id=group_id)

    def create_group(self, cmd, name, description=None):
        """Create a new group."""
        return self.api_client.create_group(name=name, description=description)

    def update_group(self, cmd, group_id, name=None, description=None):
        """Update an existing group."""
        return self.api_client.update_group(group_id=group_id, name=name, description=description)

    def delete_group(self, cmd, group_id):
        """Delete a group."""
        return self.api_client.delete_group(group_id=group_id)

    def get_group_statistics(self, cmd):
        """Get group statistics."""
        # Use the groups endpoint with statistics
        return self.api_client._make_request("GET", "/v1/groups/statistics")
