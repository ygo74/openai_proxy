# Feature Specification: Rate Limiting System

**Feature Branch**: `1-rate-limit`
**Created**: 2025-12-06
**Status**: Draft
**Input**: "Implement multi-level rate limiting system with database-backed configuration for OpenAI-compatible endpoints"

## Clarifications

### Session 2025-12-06

- Q: What should be the structure of the error response when rate limits are exceeded? → A: HTTP 429 with JSON structure including error type, scope, message, and retry guidance with standard rate limit headers
- Q: Should default global rate limits be stored in the database? → A: No, default global rate limits should be configured in the gateway configuration file (config.json), not in the database. Only model-level and group/model-level overrides are database-backed for dynamic management

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Request Rate Limiting Enforcement (Priority: P1) 🎯 MVP

When a user or application makes API requests to the gateway, the system enforces rate limits based on request count, preventing abuse and ensuring fair resource allocation.

**Why this priority**: Core protection mechanism - without this, the gateway has no throttling capability. This is the fundamental value proposition of the feature.

**Independent Test**: Configure a global limit of 50 requests per hour. Send 60 requests within one hour. Verify that requests 1-50 succeed with HTTP 200, and requests 51-60 fail with appropriate error indicating global limit exceeded.

**Acceptance Scenarios**:

1. **Given** a group has no specific rate limit configured, **When** the group makes 10 requests using a model, **Then** the global rate limit is applied and requests are counted against the global limit
2. **Given** a global rate limit of 100 requests per hour, **When** any group exceeds 100 requests in that hour, **Then** subsequent requests return HTTP 429 with error indicating "global" scope
3. **Given** a model-level rate limit of 50 requests per hour, **When** total requests across all groups for that model exceed 50, **Then** subsequent requests return HTTP 429 with error indicating "model" scope
4. **Given** a group/model rate limit of 20 requests per hour, **When** that specific group/model combination exceeds 20 requests, **Then** subsequent requests return HTTP 429 with error indicating "group/model" scope
5. **Given** an active rate limit is exceeded, **When** a request is blocked, **Then** the error response clearly indicates which scope triggered the rejection

---

### User Story 2 - Token-Based Rate Limiting (Priority: P1) 🎯 MVP

When processing requests, the system tracks token consumption (input + output tokens) and enforces limits based on cumulative token usage, protecting against expensive large-context requests.

**Why this priority**: Token limits are equally critical for cost control and resource protection as request limits. Both must work together for effective rate limiting.

**Independent Test**: Configure a token limit of 10,000 tokens per hour. Send requests consuming 2,000 tokens each. Verify first 5 requests succeed, 6th request fails with error indicating token limit exceeded.

**Acceptance Scenarios**:

1. **Given** a token limit of 50,000 per hour, **When** cumulative token usage reaches 50,000, **Then** subsequent requests are blocked regardless of request count
2. **Given** a request that would exceed the token limit, **When** the request is evaluated, **Then** it is rejected before forwarding to the LLM provider
3. **Given** both request and token limits exist, **When** either limit is exceeded, **Then** the request is blocked and the error indicates which metric was exceeded
4. **Given** token usage tracking, **When** a streaming response completes, **Then** the final token count is recorded and applied to the rate limit

---

### User Story 3 - Hierarchical Limit Priority (Priority: P2)

When multiple rate limits exist (global, model-level, group/model), the system applies the most specific limit first (group/model → model → global), providing fine-grained control while maintaining reasonable defaults.

**Why this priority**: Enables flexibility in rate limit configuration. Without hierarchy, administrators cannot create general rules with specific exceptions.

**Independent Test**: Configure global limit of 1000 req/hr, model limit of 500 req/hr, and group/model limit of 100 req/hr. Verify the group/model limit (100) is enforced, not the global or model limits.

**Acceptance Scenarios**:

1. **Given** a group/model limit exists, **When** evaluating a request for that group/model, **Then** the group/model limit takes precedence over model and global limits
2. **Given** no group/model limit but a model limit exists, **When** evaluating a request, **Then** the model limit takes precedence over the global limit
3. **Given** only a global limit exists, **When** evaluating any request, **Then** the global limit is applied
4. **Given** a limit set to `-1` or `None`, **When** that limit is evaluated, **Then** it is treated as "no limit" and the next priority level is checked

---

### User Story 4 - Time Window Management (Priority: P2)

Administrators can define time-based rate limit windows (e.g., day/night) with different thresholds, and the active limit automatically switches based on current time.

**Why this priority**: Enables business policies like "higher limits during business hours, lower at night" without manual intervention. Critical for dynamic load management.

**Independent Test**: Configure two windows: 00:00-08:00 with 100 req limit, 08:00-23:59 with 1000 req limit. At 07:55, use 90 requests. At 08:05, verify counter has reset and full 1000 request limit is available.

**Acceptance Scenarios**:

1. **Given** multiple time windows are configured, **When** the current time falls within a window, **Then** that window's limits are applied
2. **Given** a time window transition occurs, **When** the new window starts, **Then** request and token counters reset to zero
3. **Given** no time window matches current time, **When** evaluating a request, **Then** a default 24-hour window is used

---

### User Story 5 - Dynamic Limit Configuration via Admin API (Priority: P1) 🎯 MVP

Administrators can create, update, and delete rate limits through REST API endpoints without restarting the gateway, and changes take effect immediately or within seconds.

**Why this priority**: The core requirement distinguishing this from static configuration. Enables operational agility and incident response without downtime.

**Independent Test**: Configure a model-level rate limit via `POST /admin/rate-limits/models/{model_id}` with 100 req/hr. Immediately send requests and verify the new limit is enforced. Update to 200 req/hr, verify new limit applies within 5 seconds.

**Acceptance Scenarios**:

1. **Given** admin credentials, **When** calling `GET /admin/rate-limits/global`, **Then** the current global rate limits from configuration file are returned
2. **Given** admin credentials, **When** calling `POST /admin/rate-limits/models/{model_id}` with valid payload, **Then** the model-level rate limit is created/updated in the database
3. **Given** admin credentials, **When** calling `POST /admin/rate-limits/groups/{group_id}/models/{model_id}`, **Then** the group/model rate limit is created/updated
4. **Given** a rate limit exists, **When** admin calls `DELETE /admin/rate-limits/{id}`, **Then** the limit is removed and no longer enforced
5. **Given** admin calls `GET /admin/rate-limits`, **When** the request completes, **Then** all configured rate limits are returned
6. **Given** a rate limit is modified, **When** the change is persisted, **Then** the enforcement system picks up the change without restart
7. **Given** an invalid payload, **When** creating/updating a limit, **Then** the API returns HTTP 400 with validation errors

---

### User Story 6 - Model-Level Usage Aggregation (Priority: P2)

When a model-level rate limit is configured, the system aggregates usage across all groups using that model, enabling organization-wide model protection.

**Why this priority**: Prevents a single model from being overwhelmed by combined usage from multiple groups. Essential for protecting shared model resources.

**Independent Test**: Configure model-level limit of 100 req/hr for "gpt-4". Send 60 requests from Group A and 50 requests from Group B within one hour. Verify that after 100 total requests, both groups receive rate limit errors.

**Acceptance Scenarios**:

1. **Given** a model-level rate limit of 100 requests per hour, **When** Group A uses 60 requests and Group B uses 40 requests for the same model, **Then** the combined 100 requests are counted
2. **Given** a model-level rate limit is reached, **When** any group attempts to use that model, **Then** the request is blocked regardless of which group made prior requests
3. **Given** multiple models with separate limits, **When** a group uses different models, **Then** each model's usage is tracked independently

---

### Edge Cases

- **What happens when rate limit is exceeded mid-request?** The evaluation occurs before forwarding to the LLM. Once a request starts processing, it completes normally.
- **What happens when database is temporarily unavailable?** The system continues using cached rate limit configurations. New limits cannot be created, but enforcement continues. An alert is triggered.
- **What happens to counters during configuration updates?** Counters are separate from configuration. Updating limits does not reset current usage counters unless explicitly requested.
- **What happens when a model is deleted but has rate limits?** Cascading deletion removes associated model-level and group/model rate limits, or admin endpoint warns before deletion.
- **What happens with concurrent requests at the limit boundary?** The system uses atomic counter increments. One request succeeds (reaching the limit), others receive errors. No over-limit requests are allowed.
- **What happens when limits are disabled (`-1` or `None`) at all levels?** The system allows unlimited requests, effectively disabling rate limiting. Monitoring still occurs.
- **What happens to streaming requests?** Streaming requests count as 1 request when started. Token usage is updated as chunks arrive. If limit exceeded mid-stream, the stream continues but subsequent requests are blocked.

## Requirements *(mandatory)*

### Functional Requirements

**Rate Limit Enforcement:**

- **FR-001**: System MUST enforce rate limits on all OpenAI-compatible endpoints (`/v1/completions`, `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`)
- **FR-002**: System MUST track request counts and token consumption (input + output) per applicable scope
- **FR-003**: System MUST return HTTP 429 with structured JSON error response when rate limits are exceeded, including: error type ("rate_limit_exceeded"), scope (global/model/group_model), descriptive message, details object with limit_type (requests/tokens), current_usage, limit, and window_reset_at timestamp
- **FR-003a**: System MUST include standard rate limit HTTP headers in all responses: `Retry-After` (seconds until reset), `X-RateLimit-Limit` (maximum allowed), `X-RateLimit-Remaining` (requests/tokens remaining), `X-RateLimit-Reset` (Unix timestamp of window reset)
- **FR-004**: System MUST block requests before forwarding to LLM providers when limits are exceeded

**Rate Limit Levels:**

- **FR-005**: System MUST support three rate limit scopes: global, model-level, and group/model-level
- **FR-006**: Global rate limit MUST be defined in the gateway configuration file (config.json) and serve as default when no more specific limits exist
- **FR-007**: Model-level rate limit MUST aggregate usage across all groups using that model
- **FR-008**: Group/model rate limit MUST track usage for specific group/model combinations

**Rate Limit Metrics:**

- **FR-009**: Each rate limit MUST define maximum number of requests
- **FR-010**: Each rate limit MUST define maximum number of tokens
- **FR-011**: System MUST support `-1` or `None` values to indicate "no limit" for either metric

**Priority Rules:**

- **FR-012**: System MUST apply rate limits in priority order: group/model first, then model, then global
- **FR-013**: System MUST skip levels where limit is set to `-1` or `None` and check next priority level
- **FR-014**: System MUST use the first applicable non-null limit encountered in the priority chain

**Time-Based Windows:**

- **FR-015**: System MUST support multiple time windows per rate limit with configurable start/end times
- **FR-016**: System MUST select the active time window based on current system time
- **FR-017**: System MUST reset request and token counters when transitioning to a new time window
- **FR-018**: System MUST support time format HH:MM:SS for window boundaries (24-hour format, UTC)

**Database-Backed Configuration:**

- **FR-019**: System MUST store model-level and group/model-level rate limit configurations in the database (global defaults are in configuration file)
- **FR-020**: System MUST support creating, updating, deleting, and querying model-level and group/model-level rate limits via database operations
- **FR-021**: Database schema MUST support: limit scope (model/group-model), time windows, max_requests, max_tokens, and disabled flags

**Admin API Endpoints:**

- **FR-022**: System MUST expose `GET /admin/rate-limits/global` to view current global rate limits from configuration (global limits are read-only via API, modified via config file)
- **FR-023**: System MUST expose `POST /admin/rate-limits/models/{model_id}` to create/update model-level rate limits
- **FR-024**: System MUST expose `POST /admin/rate-limits/groups/{group_id}/models/{model_id}` to create/update group/model rate limits
- **FR-025**: System MUST expose `GET /admin/rate-limits` to list all configured rate limits
- **FR-026**: System MUST expose `DELETE /admin/rate-limits/{id}` to remove a rate limit
- **FR-027**: Admin endpoints MUST validate payloads and return HTTP 400 with detailed errors for invalid data
- **FR-028**: Admin endpoints MUST require admin authentication (consistent with existing `/admin/*` endpoints)

**Runtime Modification:**

- **FR-029**: System MUST apply model-level and group/model-level configuration changes without requiring gateway restart (global limits require restart per spec note)
- **FR-030**: Model-level and group/model-level configuration changes MUST take effect within a reasonable timeframe (target: <5 seconds)
- **FR-031**: System MUST use caching for performance while maintaining consistency
- **FR-032**: System MUST continue enforcing cached limits if database becomes temporarily unavailable

**Usage Tracking:**

- **FR-033**: System MUST use atomic operations for counter increments to prevent race conditions
- **FR-034**: System MUST update token counters after LLM response completes (including streaming)
- **FR-035**: System MUST maintain separate counters for each active scope (global, per-model, per-group/model)

### Key Entities

- **RateLimit**: Core configuration entity representing a rate limit at any scope level. Attributes: id, scope_type (global/model/group-model), scope_id (identifies model or group+model), created_at, updated_at

- **RateLimitWindow**: Time-based limit configuration associated with a RateLimit. Attributes: id, rate_limit_id (foreign key), from_time (HH:MM:SS), to_time (HH:MM:SS), max_requests (integer or -1), max_tokens (integer or -1)

- **RateLimitUsage**: Current usage counters for tracking consumption. Attributes: scope_identifier, window_start_timestamp, request_count, token_count, last_updated

- **RateLimitErrorResponse**: Error response structure returned when limits exceeded. Attributes: error object containing type ("rate_limit_exceeded"), scope (global/model/group_model), message (descriptive text), details object with limit_type (requests/tokens), current_usage (integer), limit (integer), window_reset_at (ISO 8601 timestamp)

- **Group**: Existing entity representing user groups. Relationship: associated with group/model rate limits

- **Model**: Existing entity representing LLM models. Relationship: associated with model-level and group/model rate limits

### Configuration File Structure for Global Rate Limits

Global rate limits are defined in `config.json`:

```json
{
  "rate_limits": {
    "global": {
      "windows": [
        {
          "from": "00:00:00",
          "to": "08:00:00",
          "max_requests": 100,
          "max_tokens": 50000
        },
        {
          "from": "08:00:00",
          "to": "23:59:00",
          "max_requests": 1000,
          "max_tokens": 500000
        }
      ]
    }
  }
}
```

**Note**: Changes to global rate limits in the configuration file require a gateway restart to take effect. For dynamic rate limit management without restarts, use model-level or group/model-level limits via the admin API.

### Error Response Example

When a rate limit is exceeded, the system returns:

**HTTP Status**: 429 Too Many Requests

**Response Headers**:
```
Retry-After: 3600
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1733486400
```

**Response Body**:
```json
{
  "error": {
    "type": "rate_limit_exceeded",
    "scope": "global",
    "message": "Rate limit exceeded for global scope",
    "details": {
      "limit_type": "requests",
      "current_usage": 100,
      "limit": 100,
      "window_reset_at": "2025-12-06T09:00:00Z"
    }
  }
}
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can create and modify rate limits via API without gateway downtime, with changes effective within 5 seconds
- **SC-002**: System successfully blocks 100% of requests exceeding configured limits with appropriate error responses
- **SC-003**: Rate limit enforcement adds <10ms overhead per request evaluation
- **SC-004**: System handles 1000+ concurrent requests without counter inconsistencies (verified through stress testing)
- **SC-005**: Time window transitions complete automatically with counter resets occurring in <100ms
- **SC-006**: Hierarchical limit priority correctly applied in 100% of test cases (verified through scenarios testing all three levels)
- **SC-007**: Model-level usage aggregation accurately combines usage from all groups (verified through multi-group tests)
- **SC-008**: System continues operating with cached limits when database is unavailable, degrading gracefully
- **SC-009**: Admin API endpoints respond in <200ms for CRUD operations on rate limit configurations
- **SC-010**: Token counting accuracy is within 5% of actual LLM provider token counts

## Assumptions

- **Configuration File**: Default global rate limits are defined in the gateway's configuration file (config.json). Changes to global limits require configuration file update and gateway restart
- **Database**: The gateway uses a relational database (PostgreSQL/MySQL/SQLite) with SQLAlchemy ORM. Model-level and group/model-level rate limit tables will be added via Alembic migrations
- **Caching**: Redis is available or local memory caching is acceptable for performance optimization. Configuration-based global limits are loaded at startup
- **Authentication**: Admin endpoints use the existing admin authentication mechanism (`require_admin_role` dependency)
- **Token Counting**: Token counts are available from LLM provider responses. For pre-request estimation, tokenizer libraries can be used
- **Time Zones**: All times are in UTC. Time windows use 24-hour format (HH:MM)
- **Default Window**: If no time windows are configured, a default 24-hour window (00:00-23:59) with specified limits is assumed
- **Deployment**: For multi-instance deployments, cache synchronization occurs via Redis pub/sub or polling (implementation detail)

## Dependencies

- **Existing Systems**: Requires integration with existing Group and Model management (database tables, services, repositories)
- **Configuration System**: Requires integration with existing config.json loading mechanism for global rate limits
- **Admin API Framework**: Extends existing admin API structure in `interfaces/api/admin/`
- **Middleware**: Rate limiting logic implemented as FastAPI middleware or dependency injection
- **Migration**: Requires Alembic migration for new database tables (model-level and group/model-level limits only)

## Out of Scope

- **Detailed Reporting Dashboards**: While usage statistics are tracked, comprehensive reporting UIs are not included
- **User-Facing Rate Limit Queries**: End users cannot query their rate limit status (only admins)
- **Per-User Rate Limits**: Rate limits apply to groups, not individual users within groups
- **Geographic Rate Limits**: Limits based on request origin (IP, region) are not supported
- **Custom Time Zones**: All time windows use UTC only
- **Rate Limit Predictions**: ML-based forecasting of limit exhaustion is not included
- **Soft Limits/Warnings**: Only hard limits enforced. Warning thresholds (e.g., "80% used") not implemented
- **Billing Integration**: Usage tracking exists but billing/cost allocation is separate concern
