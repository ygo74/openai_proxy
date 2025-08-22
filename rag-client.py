#!/usr/bin/env python

"""Wrapper script for rag-client CLI."""

import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

def main():
    """Run the client in a safer way that handles Knack import errors."""
    try:
        # Import directly to test if the modules are available
        from knack.cli import CLI
        from knack.commands import CLICommandsLoader

        # If imports work, try to run the client directly
        from ygo74.fastapi_openai_rag_client.__main__ import main as client_main
        client_main()
    except (ImportError, AttributeError) as e:
        # If we get import errors, recommend using fix_client.py
        logging.error("Error: %s", str(e))
        logging.error("")
        logging.error("The FastAPI OpenAI RAG client encountered an error with dependencies.")
        logging.error("Please run the following command to fix the issue:")
        logging.error("")
        logging.error("    python fix_client.py")
        logging.error("")
        sys.exit(1)

if __name__ == "__main__":
    main()
