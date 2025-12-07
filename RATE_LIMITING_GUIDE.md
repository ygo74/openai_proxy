# Rate Limiting Implementation Guide

## Overview

This document describes the complete rate limiting implementation for the FastAPI OpenAI RAG proxy. The system provides hierarchical rate limiting with three levels of control: group/model-specific, global fallback, and model-level aggregate protection.

## Architecture

### Core Components

1. **RateLimitService** (`application/services/rate_limit_service.py`)
   - Database-backed service for rate limit configuration and enforcement
   - Three-tier fallback: Cache → Database → config.json
   - Supports hierarchical rate limit checks and recording

2. **RateLimitCache** (`infrastructure/cache/rate_limit_cache.py`)
   - Redis-backed caching with pub/sub for configuration updates
   - In-memory fallback when Redis unavailable
   - Thread-safe class-level persistence

3. **RateLimitCounter** (`infrastructure/cache/rate_limit_counter.py`)
   - Atomic counter operations for requests and tokens
   - Redis-backed with in-memory fallback
   - Thread-safe class-level persistence

4. **ChatCompletionService** (`application/services/chat_completion_service.py`)
   - Integrates rate limit checks before LLM requests
   - Hierarchical checking logic

5. **TokenTrackingService** (`application/services/token_tracking_service.py`)
   - Records token consumption in rate limit counters
   - Mirrors hierarchical check logic

### Database Schema

**rate_limits** table:
```sql
CREATE TABLE rate_limits (
    id SERIAL PRIMARY KEY,
    scope_type VARCHAR(20) NOT NULL,  -- 'global', 'model', 'group_model'
    scope_id VARCHAR(255),             -- NULL for global, model_id for model, group:model_id for group_model
    time_windows JSONB NOT NULL,       -- Array of time window configurations
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(scope_type, scope_id)
);
```

**Time Window Format:**
```json
[
  {
    "from_time": "00:00:00",
    "to_time": "23:59:59",
    "max_requests": 1000,
    "max_tokens": 100000
  }
]
```

## Rate Limit Hierarchy

The system uses a three-tier hierarchical rate limiting approach:

### 1. Group/Model Rate Limits (Highest Priority)

**Scope:** Applies to specific user groups for specific models
**Trigger:** User must be in an authorized group for the model
**Configuration:**
- `scope_type`: "group_model"
- `scope_id`: "{group_name}:{model_id}"

**Example:**
```bash
rag-client rate-limit create-group-model \
  --group-name key_users \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":100,"max_tokens":10000}]'
```

**Logic:**
```python
# In ChatCompletionService._check_rate_limits()
authorized_groups = user.groups ∩ model.groups
for group in authorized_groups:
    if rate_limit exists for (group.name, model.id):
        check_and_raise_if_exceeded(rate_limit)
        return  # Stop checking - group/model rate limit applied
```

### 2. Global Rate Limits (Fallback)

**Scope:** Default rate limit for all models
**Trigger:** No group/model rate limit found
**Configuration:**
- `scope_type`: "global"
- `scope_id`: NULL

**Example:**
```bash
rag-client rate-limit create-global \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]'
```

**Logic:**
```python
# In ChatCompletionService._check_rate_limits()
if no group/model rate limit checked:
    if global_rate_limit exists:
        check_and_raise_if_exceeded(global_rate_limit)
```

### 3. Model Rate Limits (Aggregate Protection)

**Scope:** Protects individual models from overload
**Trigger:** Always checked (independent of group/model and global)
**Configuration:**
- `scope_type`: "model"
- `scope_id`: "{model_id}"

**Example:**
```bash
rag-client rate-limit create-model \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'
```

**Logic:**
```python
# In ChatCompletionService._check_rate_limits()
# Always checked regardless of group/model or global rate limits
if model_rate_limit exists:
    check_and_raise_if_exceeded(model_rate_limit)
```

## Usage Flow

### 1. Request Arrival

```
User Request → FastAPI Endpoint → ChatCompletionService
```

### 2. Rate Limit Checking

```python
# In ChatCompletionService.create_completion()
await self._check_rate_limits(user, model)
```

**Check Sequence:**
1. **Find authorized groups**: `authorized_groups = user.groups ∩ model.groups`
2. **Check group/model limits**: For each authorized group, check if rate limit exists and is exceeded
3. **Check global limit**: If no group/model limit applied, check global rate limit
4. **Check model limit**: Always check model aggregate limit (independent)

### 3. LLM Request Execution

```python
response = await llm_client.chat_completion(request)
```

### 4. Token Consumption Recording

```python
# In TokenTrackingService.record_usage()
await self._record_rate_limit_usage(user, model, prompt_tokens, completion_tokens)
```

**Recording Sequence:**
1. **Record group/model usage**: For each authorized group with a rate limit
2. **Record global usage**: If global rate limit exists
3. **Record model usage**: If model rate limit exists

## Response Codes

### 429 Too Many Requests

Returned when rate limit is exceeded:

```json
{
  "detail": "Rate limit exceeded for scope group_model:key_users:5. Try again in 3600 seconds.",
  "error": {
    "message": "Rate limit exceeded for scope group_model:key_users:5. Try again in 3600 seconds.",
    "type": "rate_limit_exceeded",
    "code": 429
  }
}
```

## CLI Management

### List Rate Limits

```bash
rag-client rate-limit list [--skip 0] [--limit 100]
```

### Show Rate Limit

```bash
rag-client rate-limit show --scope-type <type> [--scope-id <id>]
```

Examples:
```bash
# Global rate limit
rag-client rate-limit show --scope-type global

# Model rate limit
rag-client rate-limit show --scope-type model --scope-id 5

# Group/model rate limit
rag-client rate-limit show --scope-type group_model --scope-id "key_users:5"
```

### Create Rate Limits

**Global:**
```bash
rag-client rate-limit create-global \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]'
```

**Model:**
```bash
rag-client rate-limit create-model \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'
```

**Group/Model:**
```bash
rag-client rate-limit create-group-model \
  --group-name key_users \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":100,"max_tokens":10000}]'
```

### Update Rate Limit

```bash
rag-client rate-limit update \
  --scope-type model \
  --scope-id 5 \
  --enabled false
```

### Delete Rate Limit

```bash
rag-client rate-limit delete \
  --scope-type model \
  --scope-id 5
```

## Advanced Scenarios

### Business Hours Rate Limiting

Different limits for business hours vs off-hours:

```bash
rag-client rate-limit create-model \
  --model-id 5 \
  --windows '[
    {"from_time":"09:00:00","to_time":"17:00:00","max_requests":1000,"max_tokens":100000},
    {"from_time":"17:00:00","to_time":"09:00:00","max_requests":100,"max_tokens":10000}
  ]'
```

### Priority Users

Give specific groups higher limits:

```bash
# Premium users: 500 requests/day
rag-client rate-limit create-group-model \
  --group-name premium_users \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'

# Regular users: 100 requests/day
rag-client rate-limit create-group-model \
  --group-name regular_users \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":100,"max_tokens":10000}]'

# Global fallback: 50 requests/day
rag-client rate-limit create-global \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":50,"max_tokens":5000}]'
```

### Model Protection

Prevent any single model from being overwhelmed:

```bash
# Model aggregate limit (applies to all users)
rag-client rate-limit create-model \
  --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":10000,"max_tokens":1000000}]'
```

## Fallback Mechanisms

### Redis Unavailable

When Redis is unavailable:
1. **InMemoryRateLimitCache** stores configurations in class-level dictionary
2. **InMemoryRateLimitCounter** stores counters in class-level dictionary
3. Persistence within FastAPI process (resets on restart)
4. Thread-safe operations with locks

### No Rate Limits Configured

When no rate limits are configured:
1. Database query returns empty result
2. Cache returns `None`
3. Fallback to `config.json` (if configured)
4. If no configuration found, requests proceed without rate limiting

## Monitoring

### Token Tracking

All token usage is recorded in the `token_logs` table:

```sql
SELECT
    user_id,
    model_id,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(completion_tokens) as total_completion_tokens,
    COUNT(*) as total_requests
FROM token_logs
WHERE created_at >= NOW() - INTERVAL '1 day'
GROUP BY user_id, model_id;
```

### Rate Limit Counters

Current counter values are stored in Redis (or in-memory):

**Key Format:**
- Requests: `rate_limit:{scope_type}:{scope_id}:requests:{date}`
- Tokens: `rate_limit:{scope_type}:{scope_id}:tokens:{date}`

**Example:**
```
rate_limit:group_model:key_users:5:requests:2024-01-15
rate_limit:group_model:key_users:5:tokens:2024-01-15
```

## Testing

### Unit Tests

```bash
pytest tests/application/test_chat_completion_service.py -v
pytest tests/application/test_token_tracking_service.py -v
pytest tests/infrastructure/test_rate_limit*.py -v
```

### Integration Tests

1. **Create rate limits:**
```bash
rag-client rate-limit create-model --model-id 5 --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":10,"max_tokens":1000}]'
```

2. **Send requests until limit exceeded:**
```bash
for i in {1..15}; do
  python tools/openai/openai_call_chat_completions.py --model gpt-4o
done
```

3. **Verify 429 response:**
Expected after 10 requests with proper error message.

## Configuration Examples

### Development Environment

```bash
# High limits for development
rag-client rate-limit create-global \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":10000,"max_tokens":1000000}]'
```

### Production Environment

```bash
# Conservative global limits
rag-client rate-limit create-global \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":1000,"max_tokens":100000}]'

# Per-model protection
rag-client rate-limit create-model --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":5000,"max_tokens":500000}]'

# Premium user group
rag-client rate-limit create-group-model --group-name premium --model-id 5 \
  --windows '[{"from_time":"00:00:00","to_time":"23:59:59","max_requests":500,"max_tokens":50000}]'
```

## Troubleshooting

### Rate Limit Not Applied

1. **Check configuration exists:**
```bash
rag-client rate-limit list
```

2. **Verify enabled status:**
```bash
rag-client rate-limit show --scope-type model --scope-id 5
```

3. **Check user group membership:**
```bash
rag-client user show --user-id <id>
```

4. **Check model group associations:**
```bash
rag-client model show --model-id <id>
```

### Counters Not Incrementing

1. **Check Redis connection:**
```bash
docker ps | grep redis
```

2. **Check logs for fallback to in-memory:**
```bash
grep "InMemoryRateLimitCounter" logs/fastapi.log
```

3. **Verify token tracking service:**
```bash
grep "TokenTrackingService" logs/fastapi.log
```

### Unexpected 429 Errors

1. **Check current counter values in Redis:**
```bash
docker exec -it <redis-container> redis-cli
> KEYS rate_limit:*
> GET rate_limit:model:5:requests:2024-01-15
```

2. **Check rate limit configuration:**
```bash
rag-client rate-limit show --scope-type model --scope-id 5
```

3. **Verify time window matches current time:**
Time windows use server time zone. Ensure `from_time` and `to_time` are correct.

## Future Enhancements

### Potential Improvements

1. **Dynamic window adjustments:** Automatically adjust limits based on load
2. **User-specific overrides:** Per-user rate limits
3. **Soft limits with warnings:** Warn users before hitting hard limits
4. **Rate limit analytics dashboard:** Grafana integration
5. **Token pooling:** Share tokens across users in a group
6. **Burst allowance:** Allow temporary bursts above steady-state limits

### API Enhancements

1. **Rate limit headers:** Add `X-RateLimit-*` headers to responses
2. **Rate limit endpoint:** GET `/v1/rate-limits/me` to check current status
3. **Webhook notifications:** Alert on approaching limits
4. **Audit logging:** Track all rate limit changes

## References

- **API Endpoints:** `src/ygo74/fastapi_openai_rag/interfaces/api/v1/rate_limits.py`
- **Service Layer:** `src/ygo74/fastapi_openai_rag/application/services/rate_limit_service.py`
- **CLI Commands:** `client/src/ygo74/fastapi_openai_rag_client/commands/rate_limits.py`
- **Database Models:** `src/ygo74/fastapi_openai_rag/infrastructure/db/models/rate_limit_orm.py`
- **Usage Guide:** `client/USAGE.md`
