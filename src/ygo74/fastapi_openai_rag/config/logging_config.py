"""Logging configuration module."""
import logging
import os
import sys
from typing import Dict, Any

def setup_logging() -> None:
    """Setup application logging configuration based on environment variables.

    Uses LOG_LEVEL environment variable to control log level.
    Defaults to INFO if not specified.
    """
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Validate log level
    numeric_level: int = getattr(logging, log_level, logging.INFO)
    numeric_level = logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Configure specific loggers
    configure_application_loggers(numeric_level)


def configure_application_loggers(level: int) -> None:
    """Configure application-specific loggers.

    Args:
        level (int): Logging level to set
    """
    # Set level for your application modules
    app_loggers: list[str] = [
        "ygo74.fastapi_openai_rag",
        "ygo74.fastapi_openai_rag.application",
        "ygo74.fastapi_openai_rag.infrastructure",
        "ygo74.fastapi_openai_rag.interfaces",
        "ygo74.fastapi_openai_rag.domain"
    ]

    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = True

    # Optionally reduce noise from external libraries in debug mode
    if level == logging.DEBUG:
        # Keep httpx logs at INFO level to avoid too much noise
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("httpcore").setLevel(logging.INFO)

    logging.info(f"Logging configured with level: {logging.getLevelName(level)}")


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration dictionary for uvicorn.

    Returns:
        Dict[str, Any]: Logging configuration
    """
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["default"],
        },
        "loggers": {
            "ygo74.fastapi_openai_rag": {
                "level": log_level,
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }
