"""OpenTelemetry observability service for the FastAPI application."""
import logging
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
    """Service for managing OpenTelemetry instrumentation."""

    def __init__(self, settings: ObservabilitySettings):
        """Initialize telemetry service with configuration.

        Args:
            settings: Observability configuration settings
        """
        self.settings = settings
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize OpenTelemetry components."""
        if not self.settings.enabled:
            logger.info("Observability is disabled")
            return

        if self._initialized:
            logger.warning("Telemetry service already initialized")
            return

        logger.info(f"Initializing OpenTelemetry for service: {self.settings.service_name}")

        # Create resource
        resource = Resource.create({
            "service.name": self.settings.service_name,
            "service.version": self.settings.service_version,
        })

        # Initialize tracing
        if self.settings.tracing_enabled:
            self._setup_tracing(resource)

        # Initialize metrics
        if self.settings.metrics_enabled:
            self._setup_metrics(resource)

        # Initialize logging instrumentation
        if self.settings.logging_enabled:
            self._setup_logging()

        # Instrument common libraries
        self._instrument_libraries()

        self._initialized = True
        logger.info("OpenTelemetry initialization completed")

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

    def _setup_logging(self) -> None:
        """Setup logging instrumentation."""
        try:
            LoggingInstrumentor().instrument(
                set_logging_format=True,
                log_level=getattr(logging, self.settings.log_level.upper(), logging.INFO)
            )
            logger.info("Logging instrumentation setup completed")
        except Exception as e:
            logger.error(f"Failed to setup logging instrumentation: {e}")

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
