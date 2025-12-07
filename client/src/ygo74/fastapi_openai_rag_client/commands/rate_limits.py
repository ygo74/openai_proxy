"""Rate Limits command module."""
import logging
import json
from typing import Optional, Dict, Any, List, Union
from knack.cli import CLI
from knack.commands import CommandGroup, CLICommandsLoader, CLICommand
from knack.arguments import ArgumentsContext

from ..core.utils import get_api_client


logger = logging.getLogger(__name__)


def _parse_bool(value: Optional[Union[str, bool]]) -> Optional[bool]:
    """Parse string or bool value to bool.

    Args:
        value: String ('true', 'false', 'yes', 'no', '1', '0') or bool or None

    Returns:
        Boolean value or None
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower_value = value.lower()
        if lower_value in ('true', 'yes', '1'):
            return True
        elif lower_value in ('false', 'no', '0'):
            return False
    return None


class RateLimitCommandsLoader:
    """Command loader for rate limit commands."""

    def load_command_table(self, command_loader: CLICommandsLoader):
        """Load rate limit commands into command table."""

        with CommandGroup(command_loader, 'rate-limit', operations_tmpl='ygo74.fastapi_openai_rag_client.commands.rate_limits#{}') as g:
            g.command('list', "list_rate_limits")
            g.command('show', "get_rate_limit")
            g.command('create-global', "create_global_rate_limit")
            g.command('create-model', "create_model_rate_limit")
            g.command('create-group-model', "create_group_model_rate_limit")
            g.command('update', "update_rate_limit")
            g.command('delete', "delete_rate_limit")

        return {}

    def load_arguments(self, command_loader: CLICommandsLoader, command):
        """Load command arguments."""

        with ArgumentsContext(command_loader, 'rate-limit list') as arg_context:
            arg_context.argument('skip', type=int, help='Number of records to skip')
            arg_context.argument('limit', type=int, help='Maximum number of records to return')

        with ArgumentsContext(command_loader, 'rate-limit show') as arg_context:
            arg_context.argument('scope_type', type=str, help='Scope type (global, model, group_model)')
            arg_context.argument('scope_id', type=str, help='Scope identifier (optional for global)')

        with ArgumentsContext(command_loader, 'rate-limit create-global') as arg_context:
            arg_context.argument('windows', type=str, help='JSON string of time windows (e.g., \'[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]\'')
            arg_context.argument('enabled', help='Enable the rate limit: true or false (default: true)')

        with ArgumentsContext(command_loader, 'rate-limit create-model') as arg_context:
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('windows', type=str, help='JSON string of time windows')
            arg_context.argument('enabled', help='Enable the rate limit: true or false (default: true)')

        with ArgumentsContext(command_loader, 'rate-limit create-group-model') as arg_context:
            arg_context.argument('group_name', type=str, help='Group name')
            arg_context.argument('model_id', type=int, help='Model ID')
            arg_context.argument('windows', type=str, help='JSON string of time windows')
            arg_context.argument('enabled', help='Enable the rate limit: true or false (default: true)')

        with ArgumentsContext(command_loader, 'rate-limit update') as arg_context:
            arg_context.argument('scope_type', type=str, help='Scope type (global, model, group_model)')
            arg_context.argument('scope_id', type=str, help='Scope identifier (optional for global)')
            arg_context.argument('windows', type=str, help='JSON string of new time windows')
            arg_context.argument('enabled', help='New enabled status: true or false')

        with ArgumentsContext(command_loader, 'rate-limit delete') as arg_context:
            arg_context.argument('scope_type', type=str, help='Scope type (global, model, group_model)')
            arg_context.argument('scope_id', type=str, help='Scope identifier (optional for global)')


def list_rate_limits(cmd: CLICommand, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """List all rate limit configurations."""
    api_client = get_api_client(cmd)
    return api_client.list_rate_limits(skip=skip, limit=limit)


def get_rate_limit(cmd: CLICommand, scope_type: str, scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Get rate limit configuration by scope."""
    api_client = get_api_client(cmd)
    return api_client.get_rate_limit(scope_type=scope_type, scope_id=scope_id)


def create_global_rate_limit(cmd: CLICommand, windows: str, enabled: Optional[Union[str, bool]] = None) -> Dict[str, Any]:
    """Create or update global rate limit configuration.

    Example:
        rag-client rate-limit create-global --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]'
    """
    api_client = get_api_client(cmd)

    try:
        windows_list = json.loads(windows)
        if not isinstance(windows_list, list):
            raise ValueError("Windows must be a JSON array")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON for windows: {e}")

    # Parse enabled to bool (default True if not provided)
    enabled_bool = _parse_bool(enabled) if enabled is not None else True
    if enabled_bool is None:
        enabled_bool = True

    return api_client.create_global_rate_limit(windows=windows_list, enabled=enabled_bool)
def create_model_rate_limit(cmd: CLICommand, model_id: int, windows: str, enabled: Optional[Union[str, bool]] = None) -> Dict[str, Any]:
    """Create or update model-specific rate limit configuration.

    Example:
        rag-client rate-limit create-model --model-id 5 --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'
    """
    api_client = get_api_client(cmd)

    try:
        windows_list = json.loads(windows)
        if not isinstance(windows_list, list):
            raise ValueError("Windows must be a JSON array")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON for windows: {e}")

    # Parse enabled to bool (default True if not provided)
    enabled_bool = _parse_bool(enabled) if enabled is not None else True
    if enabled_bool is None:
        enabled_bool = True

    return api_client.create_model_rate_limit(model_id=model_id, windows=windows_list, enabled=enabled_bool)
def create_group_model_rate_limit(cmd: CLICommand, group_name: str, model_id: int, windows: str, enabled: Optional[Union[str, bool]] = None) -> Dict[str, Any]:
    """Create or update group/model-specific rate limit configuration.

    Example:
        rag-client rate-limit create-group-model --group-name key_users --model-id 5 --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":100,"max_tokens":10000}]'
    """
    api_client = get_api_client(cmd)

    try:
        windows_list = json.loads(windows)
        if not isinstance(windows_list, list):
            raise ValueError("Windows must be a JSON array")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON for windows: {e}")

    # Parse enabled to bool (default True if not provided)
    enabled_bool = _parse_bool(enabled) if enabled is not None else True
    if enabled_bool is None:
        enabled_bool = True

    return api_client.create_group_model_rate_limit(
        group_name=group_name,
        model_id=model_id,
        windows=windows_list,
        enabled=enabled_bool
    )
def update_rate_limit(
    cmd: CLICommand,
    scope_type: str,
    scope_id: Optional[str] = None,
    windows: Optional[str] = None,
    enabled: Optional[Union[str, bool]] = None
) -> Dict[str, Any]:
    """Update existing rate limit configuration.

    Example:
        rag-client rate-limit update --scope-type model --scope-id 5 --enabled false
    """
    api_client = get_api_client(cmd)

    windows_list = None
    if windows:
        try:
            windows_list = json.loads(windows)
            if not isinstance(windows_list, list):
                raise ValueError("Windows must be a JSON array")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON for windows: {e}")

    # Parse enabled to bool if provided
    enabled_bool = _parse_bool(enabled) if enabled is not None else None

    return api_client.update_rate_limit(
        scope_type=scope_type,
        scope_id=scope_id,
        windows=windows_list,
        enabled=enabled_bool
    )
def delete_rate_limit(cmd: CLICommand, scope_type: str, scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Delete rate limit configuration.

    Example:
        rag-client rate-limit delete --scope-type model --scope-id 5
    """
    api_client = get_api_client(cmd)
    return api_client.delete_rate_limit(scope_type=scope_type, scope_id=scope_id)
