"""CLI client for FastAPI OpenAI RAG."""
import os
import sys
import logging
from knack.commands import CLICommandsLoader, CommandGroup
from knack.help_files import helps
from knack.cli import CLI
from knack.arguments import ArgumentsContext

from typing import Optional, Dict, Any
from .core.auth import AuthContext
from .core.client import ApiClient
from .commands.groups import GroupCommandsLoader
from .commands.models import ModelCommandsLoader
from .commands.users import UserCommandsLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# Setup knack help content
helps[''] = """
    type: group
    short-summary: FastAPI OpenAI RAG Management CLI.
    long-summary: Command-line tools for managing FastAPI OpenAI RAG proxy.
"""

helps['group list'] = """
type: command
short-summary: List openai proxy groups.
examples:
    - name: list all groups.
      text: {cli_name} group list
""".format(cli_name="rag_client")

# Setup knack help for top-level groups
helps['group'] = """
    type: group
    short-summary: Manage group resources.
"""

helps['model'] = """
    type: group
    short-summary: Manage LLM model resources.
"""

helps['user'] = """
    type: group
    short-summary: Manage user resources.
"""

helps['version'] = """
    type: commannd
    short-summary: display the CLI version.
"""

class RagProxyCommandsLoader(CLICommandsLoader):
    """Command loader for the FastAPI OpenAI RAG CLI."""

    def __init__(self, cli_ctx=None):
        """Initialize the command loader with auth and client contexts."""
        super().__init__(cli_ctx)
        self.auth_ctx = None
        self.api_client = None

    def _init_client_and_auth(self):
        """Initialize auth and client once CLI context is available."""
        if not self.auth_ctx and self.cli_ctx:
            self.auth_ctx = AuthContext(self.cli_ctx)
            self.api_client = ApiClient(self.auth_ctx)

            # Store in CLI context data for commands to access
            if not hasattr(self.cli_ctx, 'data'):
                self.cli_ctx.data = {}
            self.cli_ctx.data['auth_ctx'] = self.auth_ctx
            self.cli_ctx.data['api_client'] = self.api_client

    def load_command_table(self, args):
        """Load all command tables from command groups."""
        self._init_client_and_auth()  # Initialize client and auth

        # Register command groups
        with CommandGroup(self, '', 'ygo74.fastapi_openai_rag_client.__main__#{}') as g:
            g.command('version', 'show_version')  # Use function reference instead of string
            g.command('whoami', 'whoami')

        # Only load module commands if we have initialized client and auth
        try:
            GroupCommandsLoader().load_command_table(self)
            ModelCommandsLoader().load_command_table(self)
            UserCommandsLoader().load_command_table(self)
        except Exception as e:
            logger.error(f"Error loading command modules: {str(e)}")

        return super().load_command_table(args)

    def load_arguments(self, command):
        """Load arguments for commands."""
        self._init_client_and_auth()  # Initialize client and auth

        # This method is called for each command registered
        # Load sub-command arguments from each command module

        # with ArgumentsContext(command, 'whoami') as arg_context:
        #     arg_context.argument('force-cache-clear', help="clear the cached authenticated user")

        try:
            GroupCommandsLoader().load_arguments(self, command)
            ModelCommandsLoader().load_arguments(self, command)
            UserCommandsLoader().load_arguments(self, command)
        except Exception as e:
            logger.error(f"Error loading command arguments: {str(e)}")

        super().load_arguments(command)

def show_version() -> Dict[str, str]:
    """Show the CLI version."""
    from . import __version__ as cli_version
    return {'version': cli_version}

def whoami(cmd, force_cache_clear = True) -> Dict[str, Any]:
    """Get the current authenticated user."""
    api_client = cmd.cli_ctx.data.get('api_client')
    if not api_client:
        return {'error': 'Not authenticated'}

    if force_cache_clear:
        logger.info("Forcing cache clear for authenticated user")
        return api_client._make_request("GET", "/v1/whoami?force_cache_clear=true")
    else:
        logger.info("Fetching authenticated user info")
        return api_client._make_request("GET", "/v1/whoami")

def main():
    """Run the CLI."""
    # Setup Knack CLI with correct parameters for version 0.10.1
    cli_args = {
        'config_dir': os.path.expanduser('~/.rag-client'),
        'config_env_var_prefix': 'RAG',
    }

    rag_cli = CLI(cli_name="rag_client", commands_loader_cls=RagProxyCommandsLoader, **cli_args)

    exit_code = rag_cli.invoke(sys.argv[1:])
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
