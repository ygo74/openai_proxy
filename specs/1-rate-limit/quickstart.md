# Rate Limiting Quickstart Guide

This guide will help you get started with the multi-level rate limiting system in the FastAPI OpenAI RAG gateway.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Admin API Usage](#admin-api-usage)
- [Testing Rate Limits](#testing-rate-limits)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

The rate limiting system provides:

- **Multi-level limits**: Global, model-specific, and group+model combinations
- **Dual limiting**: Both request-based and token-based limits
- **Time windows**: Different limits for different hours (e.g., off-peak vs peak)
- **Hierarchical priority**: Most specific limit wins (group+model > model > global)
- **Dynamic configuration**: Update limits via REST API without restart
- **Fail-open resilience**: System continues working if Redis fails

### Limit Hierarchy

When a request is evaluated, limits are checked in this order:

1. **Group+Model** (most specific) - e.g., "engineering-team" using "gpt-4"
2. **Model** (medium priority) - e.g., all groups using "gpt-4"
3. **Global** (fallback) - configured in `config.json`

The first enabled, non-unlimited limit found is enforced.

## Prerequisites

### Required

- Python 3.10+
- PostgreSQL or SQLite database
- Keycloak for authentication (admin role required)

### Optional (Recommended)

- Redis for distributed rate limiting (falls back to in-memory if unavailable)
- Prometheus/Grafana for metrics visualization

### Installation

```bash
# Install dependencies
poetry install

# Or with pip
pip install -r requirements.txt

# Run database migrations
alembic upgrade head
```

## Configuration

### 1. Basic Config (`config.json`)

Create `config.json` from `config.json.example`:

```json
{
  "model_configs": [...],
  "db_type": "postgres",
  "db_url": "postgresql://user:password@localhost:5432/fastapi_proxy",

  "rate_limits": {
    "global": {
      "enabled": true,
      "windows": [
        {
          "from_time": "00:00",
          "to_time": "23:59",
          "max_requests": 10000,
          "max_tokens": 1000000
        }
      ]
    }
  },

  "redis_cache": {
    "enabled": true,
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": null,
    "max_cache_size": 64,
    "ttl_seconds": 30
  }
}
```

### 2. Time Window Configuration

Configure different limits for different hours:

```json
{
  "rate_limits": {
    "global": {
      "enabled": true,
      "windows": [
        {
          "from_time": "00:00",
          "to_time": "08:00",
          "max_requests": 100,
          "max_tokens": 10000,
          "comment": "Off-peak hours: Lower limits"
        },
        {
          "from_time": "08:00",
          "to_time": "23:59",
          "max_requests": 1000,
          "max_tokens": 100000,
          "comment": "Business hours: Higher limits"
        }
      ]
    }
  }
}
```

### 3. Unlimited Limits

Set limits to `-1` or `null` to make them unlimited:

```json
{
  "from_time": "00:00",
  "to_time": "23:59",
  "max_requests": 1000,
  "max_tokens": -1  // Unlimited tokens, but request limit still applies
}
```

## Admin API Usage

All admin endpoints require authentication with admin role.

### Authentication

```bash
# Get JWT token from Keycloak
TOKEN=$(curl -X POST "http://localhost:8080/realms/fastapi-rag/protocol/openid-connect/token" \
  -d "client_id=fastapi-client" \
  -d "username=admin" \
  -d "password=admin123" \
  -d "grant_type=password" | jq -r '.access_token')
```

### List All Rate Limits

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/rate-limits
```

Response:
```json
{
  "rate_limits": [
    {
      "id": 1,
      "scope_type": "model",
      "scope_id": "gpt-4",
      "enabled": true,
      "windows": [
        {
          "id": 1,
          "from_time": "00:00:00",
          "to_time": "23:59:59",
          "max_requests": 1000,
          "max_tokens": 100000
        }
      ]
    }
  ],
  "total": 1
}
```

### Create Model-Level Rate Limit

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/v1/admin/rate-limits/models/gpt-4 \
  -d '{
    "enabled": true,
    "windows": [
      {
        "from_time": "00:00",
        "to_time": "23:59",
        "max_requests": 1000,
        "max_tokens": 100000
      }
    ]
  }'
```

**Important**: Model-level limits aggregate usage across **all groups** using that model.

### Create Group+Model Rate Limit

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/v1/admin/rate-limits/groups/engineering-team/models/gpt-4 \
  -d '{
    "enabled": true,
    "windows": [
      {
        "from_time": "00:00",
        "to_time": "23:59",
        "max_requests": 500,
        "max_tokens": 50000
      }
    ]
  }'
```

This limit applies only to "engineering-team" group's usage of "gpt-4".

### Update Rate Limit (Partial)

```bash
# Disable a limit
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/v1/admin/rate-limits/model/gpt-4 \
  -d '{"enabled": false}'

# Update windows only
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/v1/admin/rate-limits/model/gpt-4 \
  -d '{
    "windows": [
      {
        "from_time": "00:00",
        "to_time": "23:59",
        "max_requests": 2000,
        "max_tokens": 200000
      }
    ]
  }'
```

### Delete Rate Limit

```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/admin/rate-limits/model/gpt-4
```

After deletion, requests fall back to the next level in hierarchy (e.g., global limits).

### Query Applicable Limits (Debugging)

```bash
# Check which limits apply for a specific group+model
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v1/admin/rate-limits/applicable?group_id=engineering-team&model_id=gpt-4"
```

Response shows hierarchy:
```json
{
  "group_model": {
    "id": 3,
    "scope_type": "group_model",
    "scope_id": "engineering-team:gpt-4",
    "enabled": true,
    "windows": [...]
  },
  "model": {
    "id": 1,
    "scope_type": "model",
    "scope_id": "gpt-4",
    "enabled": true,
    "windows": [...]
  },
  "global": {
    "enabled": true,
    "windows": [...]
  }
}
```

The **first non-null, enabled limit** will be enforced.

## Testing Rate Limits

### Manual Testing with curl

```bash
# Test chat completions endpoint
for i in {1..10}; do
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "gpt-4",
      "messages": [{"role": "user", "content": "Hello"}]
    }'
done
```

Expected behavior:
- First N requests succeed (where N = limit)
- Request N+1 returns HTTP 429 with retry-after header

### Check Rate Limit Headers

```bash
curl -i -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Test"}]}'
```

Response headers:
```http
HTTP/1.1 200 OK
X-RateLimit-Limit-Requests: 1000
X-RateLimit-Remaining-Requests: 995
X-RateLimit-Reset: 1733683200
```

### Rate Limit Exceeded Response

When limit is exceeded:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
Content-Type: application/json

{
  "error": {
    "type": "rate_limit_exceeded",
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded for scope model:gpt-4",
    "details": {
      "scope_type": "model",
      "scope_id": "gpt-4",
      "limit_type": "requests",
      "limit": 1000,
      "current": 1001,
      "window_reset": 1733683200,
      "retry_after": 3600
    }
  }
}
```

### Automated Testing with Python

```python
import requests

# Setup
API_URL = "http://localhost:8000/v1/chat/completions"
headers = {"Authorization": f"Bearer {token}"}

# Send requests until rate limit hit
for i in range(1, 1100):
    response = requests.post(
        API_URL,
        headers=headers,
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": f"Request {i}"}]
        }
    )

    if response.status_code == 429:
        print(f"Rate limit hit at request {i}")
        retry_after = response.headers.get("Retry-After")
        print(f"Retry after {retry_after} seconds")
        break
    elif response.status_code == 200:
        remaining = response.headers.get("X-RateLimit-Remaining-Requests")
        print(f"Request {i} succeeded, {remaining} remaining")
```

### Integration Tests

```bash
# Run all rate limiting tests
pytest tests/interfaces/test_rate_limiting_integration.py -v

# Run specific test
pytest tests/interfaces/test_rate_limiting_integration.py::test_model_limit_aggregates_across_groups -v

# Run with coverage
pytest tests/ --cov=src.ygo74.fastapi_openai_rag.application.services.rate_limit_service
```

## Monitoring

### Prometheus Metrics

Available metrics:

```promql
# Rate limit evaluations per second
rate(rate_limit_evaluations_total[1m])

# Rate limit exceeded events
rate(rate_limit_exceeded_total[1m])

# Evaluation latency (p50, p95, p99)
histogram_quantile(0.99, rate(rate_limit_evaluation_duration_ms_bucket[5m]))

# Cache hit rate
rate(rate_limit_cache_hits_total[5m]) / (rate(rate_limit_cache_hits_total[5m]) + rate(rate_limit_cache_misses_total[5m]))
```

### Grafana Dashboard

Example queries for dashboard panels:

**Rate Limit Evaluations by Scope**
```promql
sum by (scope_type) (rate(rate_limit_evaluations_total[5m]))
```

**Rate Limit Exceeded by Model**
```promql
sum by (scope_id) (rate(rate_limit_exceeded_total{scope_type="model"}[5m]))
```

**P99 Evaluation Latency**
```promql
histogram_quantile(0.99, sum by (le) (rate(rate_limit_evaluation_duration_ms_bucket[5m])))
```

### Health Check

```bash
# Check rate limiting system health
curl http://localhost:8000/v1/health/detailed
```

Response includes Redis status:
```json
{
  "status": "healthy",
  "checks": [
    {
      "name": "database",
      "status": "healthy",
      "response_time_ms": 2.5
    },
    {
      "name": "redis_rate_limiting",
      "status": "healthy",
      "response_time_ms": 1.2,
      "details": {
        "host": "localhost",
        "port": 6379,
        "db": 0
      }
    }
  ]
}
```

### Logs

Rate limit events are logged with structured data:

```json
{
  "timestamp": "2025-12-08T10:30:45.123Z",
  "level": "WARNING",
  "message": "Rate limit exceeded",
  "scope_type": "model",
  "scope_id": "gpt-4",
  "limit_type": "requests",
  "current": 1001,
  "limit": 1000
}
```

Filter logs:
```bash
# Show rate limit exceeded events
grep "Rate limit exceeded" /var/log/fastapi-openai-rag.log

# Show cache misses
grep "cache miss" /var/log/fastapi-openai-rag.log
```

## Troubleshooting

### Issue: Rate limits not enforcing

**Symptoms**: Requests succeed beyond configured limit

**Checks**:
1. Verify limit is enabled:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/admin/rate-limits/model/gpt-4
   ```

2. Check if limit is set to `-1` (unlimited):
   ```json
   {"max_requests": -1}  // This means unlimited!
   ```

3. Verify Redis connection:
   ```bash
   curl http://localhost:8000/v1/health/detailed
   ```

4. Check logs for fail-open mode:
   ```bash
   grep "fail-open" /var/log/fastapi-openai-rag.log
   ```

**Solutions**:
- Set `enabled: true` in rate limit config
- Use positive integers for limits (not `-1` or `null`)
- Fix Redis connection if degraded
- Review hierarchy - more specific limit might be overriding

### Issue: Limits not updating after API call

**Symptoms**: Updated limits take >5 seconds to apply

**Checks**:
1. Verify Redis pub/sub is working:
   ```bash
   redis-cli
   > SUBSCRIBE rate_limit_changes
   # In another terminal, update a limit via API
   # You should see message published
   ```

2. Check cache TTL:
   ```json
   "redis_cache": {
     "ttl_seconds": 30  // Increase if updates too slow
   }
   ```

**Solutions**:
- Ensure Redis `enabled: true` in config
- Increase `max_cache_size` if many limits cached
- Reduce `ttl_seconds` for faster updates
- Restart all gateway instances if pub/sub broken

### Issue: Redis failures causing 500 errors

**Symptoms**: HTTP 500 when Redis is down

**Expected Behavior**: System should fail-open (allow requests)

**Checks**:
1. Verify fail-open logic:
   ```bash
   # Stop Redis
   sudo systemctl stop redis

   # Requests should still succeed
   curl -X POST http://localhost:8000/v1/chat/completions ...
   ```

2. Check logs for fail-open:
   ```bash
   grep "fail-open" /var/log/fastapi-openai-rag.log
   ```

**Solutions**:
- Ensure `RedisRateLimitCounter` returns `infinity` on errors
- Check exception handling in `rate_limit_counter.py`
- File bug report if requests are blocked

### Issue: Incorrect limit applied

**Symptoms**: Wrong limit enforced (e.g., global instead of group+model)

**Checks**:
1. Query applicable limits:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/v1/admin/rate-limits/applicable?group_id=team&model_id=gpt-4"
   ```

2. Verify hierarchy priority:
   - Group+model limit present and enabled?
   - Model limit present and enabled?
   - Global limit fallback enabled?

3. Check for disabled limits:
   ```json
   {"enabled": false}  // This limit is skipped!
   ```

**Solutions**:
- Enable the specific limit you want enforced
- Delete less specific limits to force hierarchy
- Set unwanted limits to `enabled: false` instead of deleting

### Issue: Token limits not working

**Symptoms**: Token-based limits not blocking requests

**Checks**:
1. Verify token recording:
   ```bash
   # Check logs after request completes
   grep "token usage" /var/log/fastapi-openai-rag.log
   ```

2. Check if `max_tokens` is unlimited:
   ```json
   {"max_tokens": -1}  // Unlimited!
   ```

3. Verify LLM response includes token usage:
   ```python
   # Response must include usage data
   {
     "usage": {
       "prompt_tokens": 10,
       "completion_tokens": 50,
       "total_tokens": 60
     }
   }
   ```

**Solutions**:
- Set positive `max_tokens` value
- Ensure LLM provider returns usage data
- Check `record_token_usage()` is called after completion

### Performance Tuning

If rate limiting is slow (>10ms p99):

1. **Enable Redis** (in-memory is slower for distributed systems):
   ```json
   "redis_cache": {"enabled": true}
   ```

2. **Increase cache size**:
   ```json
   "max_cache_size": 128  // More cached limits
   ```

3. **Optimize time windows**:
   - Use fewer windows per limit (1-2 is optimal)
   - Avoid overlapping windows

4. **Monitor cache hit rate**:
   ```promql
   rate(rate_limit_cache_hits_total[5m]) /
   (rate(rate_limit_cache_hits_total[5m]) + rate(rate_limit_cache_misses_total[5m]))
   ```
   Target: >95% hit rate

## Advanced Usage

### Custom Client SDK

Use the management client SDK for programmatic administration:

```python
from ygo74.fastapi_openai_rag_client import RateLimitsClient

client = RateLimitsClient(
    base_url="http://localhost:8000",
    api_key=admin_token
)

# Create model limit
client.create_model_limit(
    model_id="gpt-4",
    max_requests=1000,
    max_tokens=100000
)

# List all limits
limits = client.list_limits()
for limit in limits:
    print(f"{limit.scope_type}:{limit.scope_id} - {limit.enabled}")

# Get applicable limits
applicable = client.get_applicable_limits(
    group_id="engineering-team",
    model_id="gpt-4"
)
print(f"Enforced limit: {applicable.group_model or applicable.model or applicable.global_}")
```

### Automated Limit Management

Example: Adjust limits based on usage patterns

```python
import schedule
import time
from datetime import datetime

def adjust_peak_hours():
    """Increase limits during business hours"""
    hour = datetime.now().hour

    if 8 <= hour < 18:  # Business hours
        client.update_model_limit(
            model_id="gpt-4",
            windows=[{
                "from_time": "08:00",
                "to_time": "18:00",
                "max_requests": 2000,
                "max_tokens": 200000
            }]
        )
    else:  # Off-peak
        client.update_model_limit(
            model_id="gpt-4",
            windows=[{
                "from_time": "18:00",
                "to_time": "08:00",
                "max_requests": 500,
                "max_tokens": 50000
            }]
        )

# Run every hour
schedule.every().hour.do(adjust_peak_hours)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## References

- [OpenAPI Specification](./contracts/admin-rate-limits-api.yaml)
- [Config Schema](./contracts/config-schema.json)
- [Architecture Documentation](./plan.md)
- [Data Model](./data-model.md)
- [Implementation Tasks](./tasks.md)

## Support

For issues or questions:
- Check logs: `/var/log/fastapi-openai-rag.log`
- Review metrics: http://localhost:9090 (Prometheus)
- Health check: http://localhost:8000/v1/health/detailed
- GitHub Issues: https://github.com/ygo74/fastapi-openai-rag/issues
