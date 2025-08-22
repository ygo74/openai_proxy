"""CLI client for FastAPI OpenAI RAG."""
import os
import sys
import logging
from knack.commands import CLICommandsLoader, CommandGroup
from knack.help_files import helps
from knack.cli import CLI

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

    def __init__(self, cli_ctx=None ):
        """Initialize the command loader with auth and client contexts."""
        super().__init__(cli_ctx)
        self.auth_ctx = None
        self.api_client = None

    def _init_client_and_auth(self):
        """Initialize auth and client once CLI context is available."""
        if not self.auth_ctx and self.cli_ctx:
            self.auth_ctx = AuthContext(self.cli_ctx)
            self.api_client = ApiClient(self.auth_ctx)

    def load_command_table(self, args):
        """Load all command tables from command groups."""
        self._init_client_and_auth()  # Initialize client and auth

        # Register command groups
        with CommandGroup(self, '', 'ygo74.fastapi_openai_rag_client.__main__#{}') as g:
            g.command('version', 'show_version')  # Use function reference instead of string

        if self.cli_ctx and self.api_client:
            # Only load module commands if we have initialized client and auth
            try:
                GroupCommandsLoader(self.api_client).load_command_table(self)
                ModelCommandsLoader(self.api_client).load_command_table(self)
                UserCommandsLoader(self.api_client).load_command_table(self)
            except Exception as e:
                logger.error(f"Error loading command modules: {str(e)}")

        return super().load_command_table(args)

    def load_arguments(self, command):
        """Load arguments for commands."""
        self._init_client_and_auth()  # Initialize client and auth

        # This method is called for each command registered
        # Load sub-command arguments from each command module
        if self.cli_ctx and self.api_client:
            try:
                GroupCommandsLoader(self.api_client).load_arguments(self, command)
                ModelCommandsLoader(self.api_client).load_arguments(self, command)
                UserCommandsLoader(self.api_client).load_arguments(self, command)
            except Exception as e:
                logger.error(f"Error loading command arguments: {str(e)}")

        super().load_arguments(command)


def show_version(cmd):
    """Show the CLI version."""
    from . import __version__ as cli_version
    return {'version': cli_version}


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
