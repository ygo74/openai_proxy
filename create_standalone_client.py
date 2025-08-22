#!/usr/bin/env python

"""Create a standalone client package for FastAPI OpenAI RAG CLI."""

import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("setup-client")

# Constants
CLIENT_DIR = Path("client")
STANDALONE_DIR = Path("standalone_client")
SIMPLE_CLIENT = "simple-rag-client.py"

def create_standalone_client():
    """Create a standalone client package."""
    logger.info("Creating standalone client package...")

    # Create directory structure
    os.makedirs(STANDALONE_DIR / "src", exist_ok=True)

    # Create setup.py
    with open(STANDALONE_DIR / "setup.py", "w") as f:
        f.write("""
from setuptools import setup, find_packages

setup(
    name="rag-client",
    version="0.1.0",
    description="Command-line client for FastAPI OpenAI RAG proxy",
    author="ygo74",
    author_email="yannickgobert@yahoo.fr",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.25.0",
        "keyring>=23.0.0",
    ],
    entry_points={
        "console_scripts": [
            "rag-client=rag_client.cli:main",
        ],
    },
)
""")

    # Create README.md
    with open(STANDALONE_DIR / "README.md", "w") as f:
        f.write("""# FastAPI OpenAI RAG Client

A command-line client for managing FastAPI OpenAI RAG proxy.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Set API key
rag-client auth set-key YOUR_API_KEY

# Or login with Keycloak
rag-client auth login --username USER --password PASS

# List users
rag-client user list

# Create a new model
rag-client model create --name gpt-4 --provider azure
```

For more information, run `rag-client --help`
""")

    # Create package directory
    package_dir = STANDALONE_DIR / "src" / "rag_client"
    os.makedirs(package_dir, exist_ok=True)

    # Create __init__.py
    with open(package_dir / "__init__.py", "w") as f:
        f.write('''"""FastAPI OpenAI RAG Client package."""

__version__ = "0.1.0"
''')

    # Copy the simple client as cli.py
    with open(SIMPLE_CLIENT, "r") as src:
        with open(package_dir / "cli.py", "w") as dest:
            content = src.read()
            # Update version import
            content = content.replace('VERSION = "0.1.0"', 'from . import __version__ as VERSION')
            dest.write(content)

    logger.info("Standalone client package created successfully!")
    logger.info("To install:")
    logger.info("  cd %s", STANDALONE_DIR)
    logger.info("  pip install -e .")
    logger.info("")
    logger.info("To use:")
    logger.info("  rag-client --help")


if __name__ == "__main__":
    create_standalone_client()
