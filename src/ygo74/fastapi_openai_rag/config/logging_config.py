"""Logging configuration module."""
import logging
import os
import sys

def setup_logging() -> None:
    """Setup application logging configuration based on environment variables.

    Uses LOG_LEVEL environment variable to control log level.
    Defaults to INFO if not specified. Idempotent: calling multiple times just updates levels.

    Note: OpenTelemetry logs forwarding is now handled by TelemetryService.
    """
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Resolve numeric level (fallback INFO)
    numeric_level: int = getattr(logging, log_level, logging.INFO)

    # Basic handlers - OpenTelemetry handler will be added by TelemetryService if enabled
    handlers = [logging.StreamHandler(sys.stdout)]

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
