"""Models command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader, CLICommand
from knack.arguments import ArgumentsContext

from ..core.utils import get_api_client


logger = logging.getLogger(__name__)


class ModelCommandsLoader:
    """Command loader for model commands."""

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load model commands into command table."""

        with CommandGroup(command_loader, 'model', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.models#{}') as g:
            g.command('list', "list_models")
            g.command('show', "get_model")
            g.command('create', "create_model")
            g.command('update', "update_model")
            g.command('delete', "delete_model")
            g.command('set-status', "update_model_status")
            g.command('add-to-group', "add_model_to_group")
            g.command('remove-from-group', "remove_model_from_group")

        return {}

    def load_arguments(self, command_loader: CLICommandsLoader, command):
        """Load command arguments."""

        with ArgumentsContext(command_loader, 'model list') as arg_context:
            arg_context.argument('skip', type=int, help='Number of records to skip')
            arg_context.argument('limit', type=int, help='Maximum number of records to return')
            arg_context.argument('status_filter', type=str, help='Filter by model status')

        with ArgumentsContext(command_loader, 'model show') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')

        with ArgumentsContext(command_loader, 'model create') as arg_context:
            arg_context.argument('url', type=str, help='Model URL')
            arg_context.argument('name', type=str, help='Model display name')
            arg_context.argument('technical_name', type=str, help='Model technical name')
            arg_context.argument('provider', type=str, help='LLM provider')
            arg_context.argument('capabilities', type=str, help='JSON string of model capabilities')

        with ArgumentsContext(command_loader, 'model update') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('url', type=str, help='Model URL')
            arg_context.argument('name', type=str, help='Model display name')
            arg_context.argument('technical_name', type=str, help='Model technical name')
            arg_context.argument('provider', type=str, help='LLM provider')
            arg_context.argument('capabilities', type=str, help='JSON string of model capabilities')

        with ArgumentsContext(command_loader, 'model delete') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')

        with ArgumentsContext(command_loader, 'model set-status') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('status', type=str, help='New model status')

        with ArgumentsContext(command_loader, 'model add-to-group') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('group_id', type=int, help='Group ID')

        with ArgumentsContext(command_loader, 'model remove-from-group') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('group_id', type=int, help='Group ID')

def list_models(cmd: CLICommand, skip: int = 0, limit: int = 100, status_filter=None) -> List[Dict[str, Any]]:
    """List all models."""
    api_client = get_api_client(cmd)
    return api_client.list_models(skip=skip, limit=limit, status_filter=status_filter)

def get_model(cmd: CLICommand, model_id: int) -> Dict[str, Any]:
    """Get model by ID."""
    api_client = get_api_client(cmd)
    return api_client.get_model(model_id=model_id)

def create_model(cmd: CLICommand, url: str, name: str, technical_name: str, provider:str, capabilities: Optional[str]=None):
    """Create a new model."""
    api_client = get_api_client(cmd)
    import json
    capabilities_dict = {}
    if capabilities:
        try:
            capabilities_dict = json.loads(capabilities)
        except json.JSONDecodeError:
            raise ValueError("Capabilities must be a valid JSON string")

    return api_client.create_model(
        url=url,
        name=name,
        technical_name=technical_name,
        provider=provider,
        capabilities=capabilities_dict
    )

def update_model(cmd: CLICommand, model_id: int, url: Optional[str] = None, name: Optional[str] = None, technical_name: Optional[str] = None, provider: Optional[str] = None, capabilities: Optional[str] = None) -> Dict[str, Any]:
    """Update an existing model."""
    api_client = get_api_client(cmd)
    import json
    capabilities_dict = None
    if capabilities:
        try:
            capabilities_dict = json.loads(capabilities)
        except json.JSONDecodeError:
            raise ValueError("Capabilities must be a valid JSON string")

    return api_client.update_model(
        model_id=model_id,
        url=url,
        name=name,
        technical_name=technical_name,
        provider=provider,
        capabilities=capabilities_dict
    )

def delete_model(cmd: CLICommand, model_id: int) -> Dict[str, Any]:
    """Delete a model."""
    api_client = get_api_client(cmd)
    return api_client.delete_model(model_id=model_id)

def update_model_status(cmd: CLICommand, model_id: int, status: str) -> Dict[str, Any]:
    """Update model status."""
    api_client = get_api_client(cmd)
    return api_client.update_model_status(model_id=model_id, status=status)

def add_model_to_group(cmd: CLICommand, model_id: int, group_id: int) -> Dict[str, Any]:
    """Add model to group."""
    api_client = get_api_client(cmd)
    return api_client.add_model_to_group(model_id=model_id, group_id=group_id)

def remove_model_from_group(cmd: CLICommand, model_id: int, group_id: int) -> Dict[str, Any]:
    """Remove model from group."""
    api_client = get_api_client(cmd)
    return api_client.remove_model_from_group(model_id=model_id, group_id=group_id)
