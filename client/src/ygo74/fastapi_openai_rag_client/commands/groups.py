"""Groups command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader, CLICommand
from knack.arguments import ArgumentsContext
from knack.help_files import helps

from ..core.utils import get_api_client

logger = logging.getLogger(__name__)

# Fonctions de commande au niveau du module
def list_groups(cmd: CLICommand, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """List all groups."""
    api_client = get_api_client(cmd)
    return api_client.list_groups(skip=skip, limit=limit)

def get_group(cmd: CLICommand, group_id: int) -> Dict[str, Any]:
    """Get group by ID."""
    api_client = get_api_client(cmd)
    return api_client.get_group(group_id=group_id)

def create_group(cmd: CLICommand, name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """Create a new group."""
    api_client = get_api_client(cmd)
    return api_client.create_group(name=name, description=description)

def update_group(cmd: CLICommand, group_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """Update an existing group."""
    api_client = get_api_client(cmd)
    return api_client.update_group(group_id=group_id, name=name, description=description)

def delete_group(cmd: CLICommand, group_id: int) -> Dict[str, Any]:
    """Delete a group."""
    api_client = get_api_client(cmd)
    return api_client.delete_group(group_id=group_id)

def get_group_statistics(cmd: CLICommand) -> Dict[str, Any]:
    """Get group statistics."""
    api_client = get_api_client(cmd)
    return api_client._make_request("GET", "/v1/admin/groups/statistics")

class GroupCommandsLoader:
    """Command loader for group commands."""

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load group commands into command table."""
        try:

            # Use the module path, not the class path
            with CommandGroup(command_loader, 'group', 'ygo74.fastapi_openai_rag_client.commands.groups#{}') as g:
                g.command('list', 'list_groups')
                g.command('show', 'get_group')
                g.command('create', 'create_group')
                g.command('update', 'update_group')
                g.command('delete', 'delete_group')
                g.command('stats', 'get_group_statistics')
        except Exception as e:
            logger.error(f"Error loading group commands: {str(e)}")
            raise

        return {}

    def load_arguments(self, command_loader: CLICommandsLoader, command):
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
