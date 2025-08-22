"""Models command module."""
import logging
from typing import Optional, Dict, Any, List
from knack.commands import CommandGroup, CLICommandsLoader
from knack.arguments import ArgumentsContext

from ..core.client import ApiClient

logger = logging.getLogger(__name__)

class ModelCommandsLoader(CLICommandsLoader):
    """Command loader for model commands."""

    def __init__(self, cli_ctx=None, api_client=None):
        """Initialize command loader.

        Args:
            cli_ctx: CLI context
            api_client: API client instance
        """
        super().__init__(cli_ctx)
        self.cli_ctx = cli_ctx
        self.api_client = api_client

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load model commands into command table."""
        with CommandGroup(command_loader, 'model', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.models.ModelCommandsLoader#{}') as g:
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
        if command.name.startswith('model'):
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

    def list_models(self, cmd, skip=0, limit=100, status_filter=None):
        """List all models."""
        return self.api_client.list_models(skip=skip, limit=limit, status_filter=status_filter)

    def get_model(self, cmd, model_id):
        """Get model by ID."""
        return self.api_client.get_model(model_id=model_id)

    def create_model(self, cmd, url, name, technical_name, provider, capabilities=None):
        """Create a new model."""
        import json
        capabilities_dict = {}
        if capabilities:
            try:
                capabilities_dict = json.loads(capabilities)
            except json.JSONDecodeError:
                raise ValueError("Capabilities must be a valid JSON string")

        return self.api_client.create_model(
            url=url,
            name=name,
            technical_name=technical_name,
            provider=provider,
            capabilities=capabilities_dict
        )

    def update_model(self, cmd, model_id, url=None, name=None, technical_name=None, provider=None, capabilities=None):
        """Update an existing model."""
        import json
        capabilities_dict = None
        if capabilities:
            try:
                capabilities_dict = json.loads(capabilities)
            except json.JSONDecodeError:
                raise ValueError("Capabilities must be a valid JSON string")

        return self.api_client.update_model(
            model_id=model_id,
            url=url,
            name=name,
            technical_name=technical_name,
            provider=provider,
            capabilities=capabilities_dict
        )

    def delete_model(self, cmd, model_id):
        """Delete a model."""
        return self.api_client.delete_model(model_id=model_id)

    def update_model_status(self, cmd, model_id, status):
        """Update model status."""
        return self.api_client.update_model_status(model_id=model_id, status=status)

    def add_model_to_group(self, cmd, model_id, group_id):
        """Add model to group."""
        return self.api_client.add_model_to_group(model_id=model_id, group_id=group_id)

    def remove_model_from_group(self, cmd, model_id, group_id):
        """Remove model from group."""
        return self.api_client.remove_model_from_group(model_id=model_id, group_id=group_id)
