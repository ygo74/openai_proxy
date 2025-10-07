"""Logging configuration module."""
import logging
import os
import sys
from typing import Dict, Any
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry._logs import set_logger_provider, get_logger

# Import OTLP exporters
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

def setup_logging() -> None:
    """Setup application logging configuration based on environment variables.

    Uses LOG_LEVEL environment variable to control log level.
    Defaults to INFO if not specified. Idempotent: calling multiple times just updates levels.
    """
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Resolve numeric level (fallback INFO)
    numeric_level: int = getattr(logging, log_level, logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]

    otlp_log_enabled = os.getenv("OTEL_LOGGING_ENABLED", "false").lower() == "true"
    if otlp_log_enabled:
        # Create resource info
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: "fastapi-openai-rag",
            ResourceAttributes.SERVICE_VERSION: "0.1.0",
        })

        # Create logger provider with resource
        provider = LoggerProvider(resource=resource)

        # Add console exporter for local development
        otlp_endpoint = os.getenv("OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs")
        otlp_processor = BatchLogRecordProcessor(OTLPLogExporter(endpoint=otlp_endpoint))
        provider.add_log_record_processor(otlp_processor)

        # Sets the global default logger provider
        set_logger_provider(provider)
        handler = LoggingHandler(level=numeric_level, logger_provider=provider)
        handlers.append(handler)


    root_logger = logging.getLogger()
    if not root_logger.handlers:

        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )
    else:
        # Update existing handlers' levels
        root_logger.setLevel(numeric_level)
        for h in root_logger.handlers:
            h.setLevel(numeric_level)

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
        # Do NOT disable propagate so root formatting/level apply; keep custom modules adjustable
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
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                "rename_fields": {
                    "levelname": "severity",
                    "asctime": "timestamp"
                }
            }
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "json": {
                "formatter": "json",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            }
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
            "uvicorn": {
                "level": log_level,
                "handlers": ["default"],
                "propagate": False,
            },
            "opentelemetry": {
                "level": "INFO",  # Keep OTEL logs at INFO to reduce noise
                "handlers": ["default"],
                "propagate": False,
            }
        },
    }
