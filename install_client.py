#!/usr/bin/env python

"""Installation script for FastAPI OpenAI RAG client."""

import os
import sys
from pathlib import Path
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("install")

def main():
    """Install the client package."""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    client_dir = script_dir / "client"

    if not client_dir.exists():
        logger.error("Client directory not found: %s", client_dir)
        sys.exit(1)

    # Change to the client directory
    logger.info("Installing FastAPI OpenAI RAG client from %s", client_dir)
    os.chdir(client_dir)

    # Install the package in development mode
    try:
        logger.info("Running pip install -e .")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
    except subprocess.CalledProcessError as e:
        logger.error("Installation failed: %s", e)
        sys.exit(1)

    logger.info("Installation successful!")
    logger.info("You can now use the client by running 'rag-client' in your terminal.")
    logger.info("")
    logger.info("Configure the client by setting environment variables:")
    logger.info("  - RAG_API_URL: Base URL for the API (default: http://localhost:8000)")
    logger.info("  - RAG_API_KEY: API key for authentication")
    logger.info("  - RAG_KEYCLOAK_URL: Keycloak server URL")
    logger.info("")
    logger.info("Or authenticate using the CLI:")
    logger.info("  - rag-client auth set-key YOUR_API_KEY")
    logger.info("  - rag-client auth login --username USER --password PASS")

if __name__ == "__main__":
    main()
