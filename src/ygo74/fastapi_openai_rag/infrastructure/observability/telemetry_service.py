"""OpenTelemetry observability service for the FastAPI application."""
import logging
import os
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from fastapi import FastAPI

# OpenTelemetry Logs imports
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.semconv.resource import ResourceAttributes

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    OTLP_AVAILABLE = True
except ImportError:
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter as OTLPSpanExporter
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter as OTLPMetricExporter
    OTLP_AVAILABLE = False

from ...config.settings import ObservabilitySettings

logger = logging.getLogger(__name__)


class TelemetryService:
    """Service for managing OpenTelemetry instrumentation including logs, traces, and metrics."""

    def __init__(self, settings: ObservabilitySettings):
        """Initialize telemetry service with configuration.

        Args:
            settings: Observability configuration settings
        """
        self.settings = settings
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.logger_provider: Optional[LoggerProvider] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize OpenTelemetry components including logs, traces, and metrics."""
        # Add detailed logging for debugging
        logger.info(f"ObservabilitySettings.enabled = {self.settings.enabled}")
        logger.info(f"ObservabilitySettings.service_name = {self.settings.service_name}")
        logger.info(f"ObservabilitySettings.otlp_endpoint = {self.settings.otlp_endpoint}")
        logger.info(f"ObservabilitySettings.tracing_enabled = {self.settings.tracing_enabled}")
        logger.info(f"ObservabilitySettings.metrics_enabled = {self.settings.metrics_enabled}")

        if not self.settings.enabled:
            logger.info("Observability is disabled - telemetry will not be initialized")
            return

        if self._initialized:
            logger.warning("Telemetry service already initialized")
            return

        logger.info(f"Initializing OpenTelemetry for service: {self.settings.service_name}")

        # Create common resource
        resource = self._create_resource()

        # Initialize logs first (as it affects logging for other components)
        if self.settings.logging_enabled:
            self._setup_logging(resource)

        # Initialize tracing
        if self.settings.tracing_enabled:
            self._setup_tracing(resource)

        # Initialize metrics
        if self.settings.metrics_enabled:
            self._setup_metrics(resource)

        # Instrument common libraries
        self._instrument_libraries()

        self._initialized = True
        logger.info("OpenTelemetry initialization completed")

    def _create_resource(self) -> Resource:
        """Create OpenTelemetry resource with service information.

        Returns:
            Resource: Configured OpenTelemetry resource
        """
        return Resource.create({
            ResourceAttributes.SERVICE_NAME: self.settings.service_name,
            ResourceAttributes.SERVICE_VERSION: self.settings.service_version,
            "deployment.environment": getattr(self.settings, 'environment', 'development'),
        })

    def _setup_logging(self, resource: Resource) -> None:
        """Setup logs forwarding to OpenTelemetry.

        Args:
            resource: OpenTelemetry resource
        """
        try:
            # Check if logs forwarding is enabled
            logs_enabled = os.getenv("OTEL_LOGGING_ENABLED", "false").lower() == "true"

            if not logs_enabled:
                logger.info("OpenTelemetry logs forwarding is disabled (OTEL_LOGGING_ENABLED=false)")
                return

            # Create logger provider with resource
            self.logger_provider = LoggerProvider(resource=resource)

            # Add console exporter for development
            # TODO: Use environment variable to control console exporter
            console_logs_enabled = os.getenv("OTEL_LOGGING_CONSOLE_ENABLED", "true").lower() == "true"
            if console_logs_enabled:
                console_processor = BatchLogRecordProcessor(ConsoleLogExporter())
                self.logger_provider.add_log_record_processor(console_processor)

            # Add OTLP HTTP exporter if endpoint is configured
            otlp_logs_endpoint = os.getenv("OTLP_LOGS_ENDPOINT", "http://localhost:4318/v1/logs")

            try:
                # Test connectivity before setting up exporter
                self._test_http_endpoint_connectivity(otlp_logs_endpoint)

                otlp_exporter = OTLPLogExporter(endpoint=otlp_logs_endpoint)
                otlp_processor = BatchLogRecordProcessor(otlp_exporter)
                self.logger_provider.add_log_record_processor(otlp_processor)

                logger.info(f"OTLP logs exporter configured with endpoint: {otlp_logs_endpoint}")

            except Exception as e:
                logger.warning(f"Failed to configure OTLP logs exporter: {e}")
                logger.info("Continuing with console-only log export")

            # Set global logger provider
            set_logger_provider(self.logger_provider)

            # Add OpenTelemetry handler to root logger
            root_logger = logging.getLogger()
            otel_handler = LoggingHandler(logger_provider=self.logger_provider)

            # Set appropriate log level for OTEL handler
            log_level = os.getenv("LOG_LEVEL", "INFO").upper()
            numeric_level = getattr(logging, log_level, logging.INFO)
            otel_handler.setLevel(numeric_level)

            root_logger.addHandler(otel_handler)

            logger.info("OpenTelemetry logs forwarding setup completed")

        except Exception as e:
            logger.error(f"Failed to setup OpenTelemetry logs: {e}")

    def _test_http_endpoint_connectivity(self, endpoint: str) -> None:
        """Test HTTP endpoint connectivity for logs.

        Args:
            endpoint: HTTP endpoint to test

        Raises:
            Exception: If connectivity test fails
        """
        import urllib.parse
        import socket

        try:
            parsed = urllib.parse.urlparse(endpoint)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            # For common OTLP ports, use those defaults
            if not parsed.port:
                if "4318" in endpoint:
                    port = 4318
                elif "4317" in endpoint:
                    port = 4317

            logger.debug(f"Testing HTTP connectivity to {host}:{port}")

            # Test TCP connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # Short timeout for HTTP
            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                raise ConnectionError(f"Cannot connect to {host}:{port}")

            logger.debug(f"HTTP endpoint {endpoint} is reachable")

        except Exception as e:
            logger.warning(f"HTTP endpoint connectivity test failed for {endpoint}: {e}")
            # In development mode, just warn but continue
            if "dev" in self.settings.service_name.lower():
                logger.warning("Continuing without OTLP connectivity in development mode")
            else:
                raise

    def _setup_tracing(self, resource: Resource) -> None:
        """Setup tracing configuration.

        Args:
            resource: OpenTelemetry resource
        """
        try:
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)

            # Create exporter with error handling
            span_exporter = self._create_span_exporter()

            # Add span processor
            span_processor = BatchSpanProcessor(span_exporter)
            self.tracer_provider.add_span_processor(span_processor)

            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)

            logger.info("Tracing setup completed")

        except Exception as e:
            logger.error(f"Failed to setup tracing: {e}")

    def _create_span_exporter(self):
        """Create span exporter with fallback logic."""
        if OTLP_AVAILABLE and self.settings.otlp_endpoint:
            try:
                exporter_kwargs = {
                    "endpoint": self.settings.otlp_endpoint,
                    "insecure": self.settings.otlp_insecure,
                    "timeout": 10  # Add timeout to avoid hanging
                }

                if self.settings.otlp_headers:
                    # Parse headers from string format "key1=value1,key2=value2"
                    headers = {}
                    for header in self.settings.otlp_headers.split(","):
                        if "=" in header:
                            key, value = header.strip().split("=", 1)
                            headers[key] = value
                    exporter_kwargs["headers"] = headers

                # Test connectivity before creating exporter
                self._test_otlp_connectivity(self.settings.otlp_endpoint)

                span_exporter = OTLPSpanExporter(**exporter_kwargs)
                logger.info(f"Using OTLP span exporter with endpoint: {self.settings.otlp_endpoint}")
                return span_exporter

            except Exception as e:
                logger.warning(f"Failed to create OTLP span exporter: {e}, falling back to console")

        # Fallback to console exporter
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        span_exporter = ConsoleSpanExporter()
        logger.info("Using console span exporter (OTLP failed or not configured)")
        return span_exporter

    def _setup_metrics(self, resource: Resource) -> None:
        """Setup metrics configuration.

        Args:
            resource: OpenTelemetry resource
        """
        try:
            # Create metric exporter with error handling
            metric_exporter = self._create_metric_exporter()

            # Create metric reader
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=10000  # Export every 10 seconds
            )

            # Create meter provider
            self.meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )

            # Set global meter provider
            metrics.set_meter_provider(self.meter_provider)

            logger.info("Metrics setup completed")

        except Exception as e:
            logger.error(f"Failed to setup metrics: {e}")

    def _create_metric_exporter(self):
        """Create metric exporter with fallback logic."""
        if OTLP_AVAILABLE and (self.settings.metrics_endpoint or self.settings.otlp_endpoint):
            try:
                endpoint = self.settings.metrics_endpoint or self.settings.otlp_endpoint
                exporter_kwargs = {
                    "endpoint": endpoint,
                    "insecure": self.settings.otlp_insecure,
                    "timeout": 10  # Add timeout
                }

                if self.settings.otlp_headers:
                    headers = {}
                    for header in self.settings.otlp_headers.split(","):
                        if "=" in header:
                            key, value = header.strip().split("=", 1)
                            headers[key] = value
                    exporter_kwargs["headers"] = headers

                # Test connectivity before creating exporter
                self._test_otlp_connectivity(endpoint)

                metric_exporter = OTLPMetricExporter(**exporter_kwargs)
                logger.info(f"Using OTLP metric exporter with endpoint: {endpoint}")
                return metric_exporter

            except Exception as e:
                logger.warning(f"Failed to create OTLP metric exporter: {e}, falling back to console")

        # Fallback to console exporter
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        metric_exporter = ConsoleMetricExporter()
        logger.info("Using console metric exporter (OTLP failed or not configured)")
        return metric_exporter

    def _test_otlp_connectivity(self, endpoint: str) -> None:
        """Test OTLP endpoint connectivity.

        Args:
            endpoint: OTLP endpoint to test

        Raises:
            Exception: If connectivity test fails
        """
        import socket
        import urllib.parse

        try:
            parsed = urllib.parse.urlparse(endpoint)
            host = parsed.hostname or "localhost"

            # Fix port detection for OTLP endpoints
            if parsed.port:
                port = parsed.port
            elif "4317" in endpoint:
                port = 4317  # gRPC
            elif "4318" in endpoint:
                port = 4318  # HTTP
            else:
                port = 4317  # Default to gRPC

            logger.debug(f"Testing connectivity to {host}:{port}")

            # Test TCP connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # Increase timeout for Docker containers
            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                raise ConnectionError(f"Cannot connect to {host}:{port}")

            logger.debug(f"OTLP endpoint {endpoint} is reachable")

        except Exception as e:
            logger.warning(f"OTLP connectivity test failed for {endpoint}: {e}")
            # Don't raise in development mode, just warn
            if "dev" in self.settings.service_name.lower():
                logger.warning("Continuing without OTLP connectivity in development mode")
            else:
                raise

    def _instrument_libraries(self) -> None:
        """Instrument common libraries."""
        try:
            # Instrument requests library for HTTP client calls
            RequestsInstrumentor().instrument()
            logger.info("Requests instrumentation enabled")

            # Instrument SQLAlchemy for database calls
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumentation enabled")

        except Exception as e:
            logger.error(f"Failed to instrument libraries: {e}")

    def instrument_fastapi(self, app: FastAPI) -> None:
        """Instrument FastAPI application.

        Args:
            app: FastAPI application instance
        """
        if not self.settings.enabled or not self.settings.tracing_enabled:
            logger.info("FastAPI instrumentation skipped (disabled)")
            return

        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=self.tracer_provider,
                excluded_urls="/health,/metrics"  # Exclude health check and metrics endpoints
            )
            logger.info("FastAPI instrumentation completed")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")

    def shutdown(self) -> None:
        """Shutdown telemetry service and cleanup resources."""
        if not self._initialized:
            return

        logger.info("Shutting down telemetry service")

        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()

            if self.meter_provider:
                self.meter_provider.shutdown()

            if self.logger_provider:
                self.logger_provider.shutdown()

            logger.info("Telemetry service shutdown completed")
        except Exception as e:
            logger.error(f"Error during telemetry shutdown: {e}")

    def get_tracer(self, name: str) -> trace.Tracer:
        """Get a tracer instance.

        Args:
            name: Tracer name

        Returns:
            Tracer instance
        """
        return trace.get_tracer(name)

    def get_meter(self, name: str) -> metrics.Meter:
        """Get a meter instance.

        Args:
            name: Meter name

        Returns:
            Meter instance
        """
        return metrics.get_meter(name)


# Global telemetry service instance
telemetry_service: Optional[TelemetryService] = None


def get_telemetry_service() -> Optional[TelemetryService]:
    """Get the global telemetry service instance.

    Returns:
        TelemetryService instance or None if not initialized
    """
    return telemetry_service


def initialize_telemetry(settings: ObservabilitySettings) -> TelemetryService:
    """Initialize global telemetry service.

    Args:
        settings: Observability configuration settings

    Returns:
        Initialized TelemetryService instance
    """
    global telemetry_service
    telemetry_service = TelemetryService(settings)
    telemetry_service.initialize()
    return telemetry_service
