"""Configuration settings for the FastAPI OpenAI RAG application."""
import os
import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AuthSettings(BaseModel):
    """Authentication configuration settings."""

    # JWT Configuration
    jwt_secret: str
    jwt_algorithm: str

    # Keycloak Configuration
    keycloak_url: str
    keycloak_realm: str

    # OAuth Configuration
    oauth_issuer: Optional[str]
    oauth_audience: Optional[str]

    @classmethod
    def from_env(cls) -> "AuthSettings":
        """Create AuthSettings instance from environment variables."""
        return cls(
            jwt_secret=os.getenv("JWT_SECRET", "fastapi-secret-key"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            keycloak_url=os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
            keycloak_realm=os.getenv("KEYCLOAK_REALM", "fastapi-openai-rag"),
            oauth_issuer=os.getenv("OAUTH_ISSUER"),
            oauth_audience=os.getenv("OAUTH_AUDIENCE"),
        )


class ObservabilitySettings(BaseModel):
    """Observability configuration settings."""

    # OpenTelemetry Configuration
    enabled: bool
    service_name: str
    service_version: str

    # OTLP Exporter Configuration
    otlp_endpoint: Optional[str]
    otlp_insecure: bool
    otlp_headers: Optional[str]

    # Tracing Configuration
    tracing_enabled: bool
    sampling_rate: float

    # Metrics Configuration
    metrics_enabled: bool
    metrics_endpoint: Optional[str]

    # Logging Configuration
    logging_enabled: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "ObservabilitySettings":
        """Create ObservabilitySettings instance from environment variables."""
        # Debug environment variables
        observability_enabled_raw = os.getenv("OBSERVABILITY_ENABLED", "false")
        observability_enabled = observability_enabled_raw.lower() == "true"

        logger.info(f"Environment OBSERVABILITY_ENABLED raw value: '{observability_enabled_raw}'")
        logger.info(f"Environment OBSERVABILITY_ENABLED parsed: {observability_enabled}")

        settings = cls(
            enabled=observability_enabled,
            service_name=os.getenv("OTEL_SERVICE_NAME", "fastapi-openai-rag"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            otlp_insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
            otlp_headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS"),
            tracing_enabled=os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true",
            sampling_rate=float(os.getenv("OTEL_SAMPLING_RATE", "1.0")),
            metrics_enabled=os.getenv("OTEL_METRICS_ENABLED", "true").lower() == "true",
            metrics_endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"),
            logging_enabled=os.getenv("OTEL_LOGGING_ENABLED", "true").lower() == "true",
            log_level=os.getenv("OTEL_LOG_LEVEL", "INFO"),
        )

        logger.info(f"Created ObservabilitySettings: enabled={settings.enabled}, service_name={settings.service_name}")
        return settings


class Settings(BaseModel):
    """Main application settings."""

    # Authentication settings
    auth: AuthSettings

    # Observability settings
    observability: ObservabilitySettings

    @classmethod
    def from_env(cls) -> "Settings":
        """Create Settings instance from environment variables."""
        return cls(
            auth=AuthSettings.from_env(),
            observability=ObservabilitySettings.from_env(),
        )


# Global settings instance
settings = Settings.from_env()
