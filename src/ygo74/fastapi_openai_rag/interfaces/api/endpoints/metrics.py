"""Metrics inspection endpoint for debugging."""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
import requests
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    """Get Prometheus metrics from the collector.

    Returns:
        PlainTextResponse: Prometheus metrics in text format
    """
    try:
        # Try to get metrics from the OTEL collector's Prometheus endpoint
        response = requests.get("http://localhost:8889/metrics", timeout=5)
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
            "total_metrics": len(metric_names),
            "metric_names": sorted(list(metric_names)),
            "http_metrics": [m for m in metric_names if 'http' in m.lower()],
            "fastapi_metrics": [m for m in metric_names if 'fastapi' in m.lower()]
        }

    except Exception as e:
        logger.error(f"Failed to debug metrics: {e}")
        return {"error": str(e)}

@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """Get Prometheus metrics directly from Prometheus/LGTM.

    Returns:
        PlainTextResponse: Prometheus metrics in text format
    """
    try:
        # Try to get metrics directly from Prometheus in LGTM stack
        response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=5)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch Prometheus metrics: {e}")
        return f"# Error fetching Prometheus metrics: {e}\n"

@router.get("/metrics/compare")
async def compare_metrics():
    """Compare metrics between OTEL collector and Prometheus.

    Returns:
        dict: Comparison of metrics
    """
    try:
        # Get metrics from OTEL collector
        otel_response = requests.get("http://localhost:8889/metrics", timeout=5)
        otel_response.raise_for_status()

        # Parse OTEL metrics
        otel_lines = otel_response.text.split('\n')
        otel_metrics = set()
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

        # Get metrics from Prometheus
        try:
            prom_response = requests.get("http://localhost:9090/api/v1/label/__name__/values", timeout=5)
            prom_response.raise_for_status()
            prom_data = prom_response.json()
            prom_metrics = set(prom_data.get("data", []))
        except Exception as e:
            logger.warning(f"Could not fetch Prometheus metrics: {e}")
            prom_metrics = set()

        # Find FastAPI-specific metrics
        fastapi_otel = {m for m in otel_metrics if 'http' in m.lower() or 'fastapi' in m.lower()}
        fastapi_prom = {m for m in prom_metrics if 'http' in m.lower() or 'fastapi' in m.lower()}

        return {
            "otel_collector": {
                "total_metrics": len(otel_metrics),
                "fastapi_metrics": sorted(list(fastapi_otel)),
                "sample_metrics": sorted(list(otel_metrics))[:10]
            },
            "prometheus": {
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
