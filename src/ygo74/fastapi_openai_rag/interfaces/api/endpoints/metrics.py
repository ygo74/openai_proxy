"""Metrics inspection endpoint for debugging."""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
import requests
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    """Get Prometheus metrics from LGTM.

    Returns:
        PlainTextResponse: Prometheus metrics in text format
    """
    try:
        # Get metrics directly from LGTM Prometheus
        response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=5)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch metrics: {e}")
        return f"# Error fetching metrics: {e}\n"

@router.get("/metrics/debug")
async def debug_metrics():
    """Debug endpoint to show available metrics.

    Returns:
        dict: Information about available metrics
    """
    try:
        # Try to get metrics from OTEL collector first (if available)
        try:
            response = requests.get("http://localhost:8889/metrics", timeout=5)
            response.raise_for_status()

            # Parse metric names from Prometheus format
            lines = response.text.split('\n')
            metric_names = set()

            for line in lines:
                if line.startswith('#'):
                    continue
                if '{' in line:
                    metric_name = line.split('{')[0]
                elif ' ' in line:
                    metric_name = line.split(' ')[0]
                else:
                    continue

                if metric_name:
                    metric_names.add(metric_name)

            return {
                "source": "otel_collector",
                "total_metrics": len(metric_names),
                "metric_names": sorted(list(metric_names)),
                "http_metrics": [m for m in metric_names if 'http' in m.lower()],
                "fastapi_metrics": [m for m in metric_names if 'fastapi' in m.lower()]
            }
        except Exception:
            # Fallback to LGTM Prometheus
            prom_response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=5)
            prom_response.raise_for_status()
            prom_data = prom_response.json()
            prom_metrics = set(prom_data.get("data", []))

            return {
                "source": "lgtm_prometheus",
                "total_metrics": len(prom_metrics),
                "metric_names": sorted(list(prom_metrics)),
                "http_metrics": [m for m in prom_metrics if 'http' in m.lower()],
                "fastapi_metrics": [m for m in prom_metrics if 'fastapi' in m.lower()]
            }

    except Exception as e:
        logger.error(f"Failed to debug metrics: {e}")
        return {"error": str(e)}

@router.get("/metrics/compare")
async def compare_metrics():
    """Compare metrics between collector and LGTM Prometheus.

    Returns:
        dict: Comparison of metrics
    """
    try:
        # Get metrics from OTEL collector
        otel_metrics = set()
        try:
            otel_response = requests.get("http://localhost:8889/metrics", timeout=5)
            otel_response.raise_for_status()

            # Parse OTEL metrics
            otel_lines = otel_response.text.split('\n')
            for line in otel_lines:
                if line.startswith('#') or not line.strip():
                    continue
                if '{' in line:
                    metric_name = line.split('{')[0]
                elif ' ' in line:
                    metric_name = line.split(' ')[0]
                else:
                    continue
                if metric_name:
                    otel_metrics.add(metric_name)
        except Exception as e:
            logger.warning(f"Could not fetch OTEL collector metrics: {e}")

        # Get metrics from LGTM Prometheus
        prom_metrics = set()
        try:
            prom_response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=5)
            prom_response.raise_for_status()
            prom_data = prom_response.json()
            prom_metrics = set(prom_data.get("data", []))
        except Exception as e:
            logger.warning(f"Could not fetch LGTM Prometheus metrics: {e}")

        # Find FastAPI-specific metrics
        fastapi_otel = {m for m in otel_metrics if 'http' in m.lower() or 'fastapi' in m.lower()}
        fastapi_prom = {m for m in prom_metrics if 'http' in m.lower() or 'fastapi' in m.lower()}

        return {
            "otel_collector": {
                "total_metrics": len(otel_metrics),
                "fastapi_metrics": sorted(list(fastapi_otel)),
                "sample_metrics": sorted(list(otel_metrics))[:10]
            },
            "lgtm_prometheus": {
                "total_metrics": len(prom_metrics),
                "fastapi_metrics": sorted(list(fastapi_prom)),
                "sample_metrics": sorted(list(prom_metrics))[:10]
            },
            "missing_in_prometheus": sorted(list(otel_metrics - prom_metrics)),
            "fastapi_missing_in_prometheus": sorted(list(fastapi_otel - fastapi_prom))
        }

    except Exception as e:
        logger.error(f"Failed to compare metrics: {e}")
        return {"error": str(e)}

@router.get("/otel/status")
async def otel_status():
    """Check OpenTelemetry service status and configuration.

    Returns:
        dict: OpenTelemetry status information
    """
    from ....infrastructure.observability.telemetry_service import get_telemetry_service
    from ....config.settings import settings
    import socket
    import urllib.parse

    telemetry_service = get_telemetry_service()

    status = {
        "telemetry_service": {
            "initialized": telemetry_service is not None,
            "settings": {
                "enabled": settings.observability.enabled,
                "service_name": settings.observability.service_name,
                "otlp_endpoint": settings.observability.otlp_endpoint,
                "tracing_enabled": settings.observability.tracing_enabled,
                "metrics_enabled": settings.observability.metrics_enabled,
            }
        },
        "connectivity": {}
    }

    # Test OTLP endpoint connectivity
    if settings.observability.otlp_endpoint:
        try:
            parsed = urllib.parse.urlparse(settings.observability.otlp_endpoint)
            host = parsed.hostname or "localhost"
            port = parsed.port or (4317 if "4317" in settings.observability.otlp_endpoint else 4318)

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            status["connectivity"]["otlp_endpoint"] = {
                "reachable": result == 0,
                "host": host,
                "port": port,
                "error": None if result == 0 else f"Connection failed with code {result}"
            }
        except Exception as e:
            status["connectivity"]["otlp_endpoint"] = {
                "reachable": False,
                "error": str(e)
            }

    return status
