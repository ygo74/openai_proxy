# Implementation Plan: Rate Limiting System

**Branch**: `1-rate-limit` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1-rate-limit/spec.md`

## Summary

Implement hierarchical, time-window-aware rate limiting system for the AI Gateway with three scope levels (global, model, group/model). System enforces limits on request count and token consumption with <10ms overhead. Global limits configured in `config.json`, model/group-model limits stored in database for dynamic updates via admin API. Cache-based enforcement with atomic counters ensures consistency under 1000+ concurrent requests. HTTP 429 responses with structured errors and standard rate limit headers provide client feedback.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy, Redis (or local memory), Alembic
**Storage**: PostgreSQL (existing) for model/group-model limits; config.json for global limits
**Testing**: pytest with layer-based organization (domain, application, infrastructure, interfaces)
**Target Platform**: Linux server (existing gateway deployment)
**Project Type**: Single project (FastAPI backend with onion architecture)
**Performance Goals**: <10ms rate limit evaluation overhead, 1000+ concurrent requests, <5s config propagation
**Constraints**: <200ms p95 API response (including rate limiting), <50ms p95 DB queries, atomic counter operations
**Scale/Scope**: 4 new domain models, 6 admin API endpoints, 3 database tables, 1 middleware/dependency

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Onion Architecture Integrity ✅ PASS

- **Domain layer isolation**: RateLimit, RateLimitWindow, RateLimitUsage, RateLimitErrorResponse models in `domain/models/` with zero external dependencies
- **Protocol abstraction**: `IRateLimitRepository` protocol in `domain/repositories/`, `IRateLimitEvaluator` protocol for evaluation logic
- **Infrastructure implements protocols**: SQLAlchemy repositories in `infrastructure/db/repositories/`, Redis/memory counter storage in `infrastructure/cache/`
- **Interfaces expose endpoints**: Admin API in `interfaces/api/admin/rate_limits.py`, rate limiting middleware/dependency in `interfaces/api/dependencies/`
- **No dependency violations**: Domain never imports SQLAlchemy, Redis, FastAPI; Infrastructure implements domain protocols

**Justification**: Feature naturally aligns with onion architecture. Rate limiting logic is pure business rules (domain), database/cache are infrastructure concerns, REST API is interface layer.

### Principle II: Test-First Development (NON-NEGOTIABLE) ✅ PASS

- **Test organization**: Tests mirror onion layers (`tests/domain/test_rate_limit_models.py`, `tests/application/test_rate_limit_service.py`, `tests/infrastructure/test_rate_limit_repository.py`, `tests/interfaces/test_rate_limits_endpoints.py`)
- **Contract tests**: HTTP 429 response structure, rate limit headers, error response schema validation
- **Integration tests**: Time window transitions, cache invalidation, database failover scenarios, concurrent request handling
- **Mocking strategy**: DB mocked in application tests, external APIs mocked in infrastructure tests, services mocked in interface tests
- **Test naming**: Follows `test_<module>_<function>_<case>()` pattern with Arrange-Act-Assert structure

**Test Examples**:
- `test_rate_limit_service_evaluate_limit_exceeded_returns_error()`
- `test_rate_limit_repository_get_model_limit_aggregates_windows()`
- `test_rate_limits_endpoint_create_model_limit_validates_payload()`

### Principle III: Type Safety & Documentation ✅ PASS

- **Full typing**: All models use Pydantic with explicit types, all functions typed (args, return, Optional where needed)
- **Docstrings**: English documentation for all public classes/functions explaining purpose, parameters, return values, exceptions
- **Domain/ORM separation**: `RateLimit` (domain) vs `RateLimitORM` (infrastructure/db/models/), explicit `RateLimitMapper` for conversions
- **Protocol classes**: `IRateLimitRepository`, `IRateLimitEvaluator`, `IRateLimitCache` protocols in domain layer
- **Pydantic validation**: Admin API request/response models, config.json schema validation

**Example**:
```python
class RateLimit(BaseModel):
    """Domain model for rate limit configuration.

    Attributes:
        id: Unique identifier
        scope_type: Type of scope (global/model/group_model)
        scope_id: Identifier for model or group+model combination
        windows: List of time-based limit windows
    """
    id: Optional[int]
    scope_type: Literal["global", "model", "group_model"]
    scope_id: Optional[str]
    windows: List[RateLimitWindow]
```

### Principle IV: Performance & Observability ✅ PASS

- **Performance targets met**: <10ms evaluation (in-memory cache lookup + counter increment), <200ms admin API (simple DB CRUD), <5s propagation (cache TTL/pub-sub)
- **Observability**: Structured logging for rate limit hits/misses, metrics for enforcement latency, counter usage tracking, audit logs for admin changes
- **Atomic operations**: Redis INCR/INCRBY or Python threading.Lock for local memory counters
- **Graceful degradation**: Continue with cached limits if DB unavailable (FR-032), alerting on database failures
- **Monitoring**: Track rate limit hit rate per scope, window transition timing, cache hit ratio, admin API latency

**Metrics to emit**:
- `rate_limit.evaluation.duration_ms` (histogram)
- `rate_limit.exceeded.count` (counter, by scope)
- `rate_limit.cache.hit_ratio` (gauge)
- `rate_limit.admin_api.latency_ms` (histogram)

## Project Structure

### Documentation (this feature)

```text
specs/1-rate-limit/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── admin-rate-limits-api.yaml (OpenAPI)
│   └── config-schema.json (JSON Schema for config.json)
└── checklists/
    └── requirements.md  # Requirements validation (completed)
```

### Source Code (repository root)

```text
src/ygo74/fastapi_openai_rag/
├── domain/
│   ├── models/
│   │   ├── rate_limit.py            # NEW: RateLimit, RateLimitWindow domain models
│   │   └── rate_limit_usage.py      # NEW: RateLimitUsage, RateLimitErrorResponse models
│   ├── protocols/
│   │   └── rate_limit_protocol.py   # NEW: IRateLimitEvaluator, IRateLimitCache protocols
│   └── repositories/
│       └── rate_limit_repository.py # NEW: IRateLimitRepository protocol
│
├── application/
│   └── services/
│       └── rate_limit_service.py    # NEW: RateLimitService (evaluation logic, cache coordination)
│
├── infrastructure/
│   ├── db/
│   │   ├── models/
│   │   │   ├── rate_limit_orm.py    # NEW: RateLimitORM, RateLimitWindowORM SQLAlchemy models
│   │   │   └── __init__.py          # UPDATED: Import new ORM models
│   │   ├── mappers/
│   │   │   └── rate_limit_mapper.py # NEW: RateLimitMapper (ORM ↔ domain conversion)
│   │   └── repositories/
│   │       └── rate_limit_repository.py # NEW: SQLRateLimitRepository implementation
│   │
│   └── cache/
│       ├── rate_limit_cache.py      # NEW: Redis or local memory cache for counters
│       └── cache_factory.py         # NEW: Factory to create Redis/Local cache based on config
│
├── interfaces/
│   └── api/
│       ├── admin/
│       │   └── rate_limits.py       # NEW: Admin endpoints for rate limit CRUD
│       └── dependencies/
│           └── rate_limiting.py     # NEW: FastAPI dependency for rate limit enforcement
│
└── config/
    └── settings.py                  # UPDATED: Add rate_limits section loading from config.json

tests/
├── domain/
│   ├── test_rate_limit_models.py    # NEW: Domain model validation tests
│   └── test_rate_limit_usage.py     # NEW: Usage counter and error response tests
│
├── application/
│   └── test_rate_limit_service.py   # NEW: Service layer with mocked repository/cache
│
├── infrastructure/
│   ├── test_rate_limit_repository.py # NEW: Repository with test database
│   └── test_rate_limit_cache.py      # NEW: Cache implementation tests
│
└── interfaces/
    ├── test_rate_limits_endpoints.py # NEW: Admin API endpoint tests
    └── test_rate_limiting_dependency.py # NEW: Middleware/dependency integration tests

alembic/versions/
└── YYYYMMDD_add_rate_limiting.py    # NEW: Migration for rate_limits, rate_limit_windows tables
```

## Complexity Tracking

**No constitutional violations** - All principles satisfied without justification needed.

**Complexity Considerations**:
- **Atomic counters**: Requires Redis INCR or threading.Lock for race-free increments (standard practice)
- **Time window transitions**: Requires background task or lazy evaluation on first request in new window (design decision in research phase)
- **Cache invalidation**: Redis pub/sub or polling with TTL (implementation detail, multiple proven patterns available)
- **Config.json schema**: Extends existing pattern used for LLM model configuration (low risk)

## Phase 0: Outline & Research

**Goal**: Resolve all NEEDS CLARIFICATION items and research best practices for implementation patterns.

### Research Tasks

1. **Rate Limiting Algorithms**: Research sliding window vs fixed window vs token bucket algorithms. Determine if simple fixed window with counter reset is sufficient or if sliding window needed for smoother enforcement.

2. **Atomic Counter Implementations**: Research Redis INCR/INCRBY patterns for distributed counters vs Python threading.Lock for local memory. Evaluate trade-offs (performance, consistency, deployment complexity).

3. **Time Window Transition Strategies**: Research background scheduler (APScheduler) vs lazy evaluation on first request. Determine reset timing precision requirements.

4. **Cache Invalidation Patterns**: Research Redis pub/sub vs polling with TTL vs webhook-based invalidation. Evaluate <5s propagation requirement feasibility.

5. **FastAPI Middleware vs Dependency**: Research FastAPI middleware pattern vs dependency injection for rate limiting. Evaluate request context access, error handling, and testability.

6. **Token Counting Approaches**: Research pre-request estimation (tiktoken library) vs post-response counting. Determine if pre-request blocking needed or post-request tracking sufficient.

7. **Config.json Schema Validation**: Review existing config.json loading mechanism. Determine Pydantic schema for rate_limits section.

8. **HTTP 429 Best Practices**: Research OpenAI, GitHub, Stripe rate limiting header standards. Confirm `Retry-After`, `X-RateLimit-*` header patterns.

### Research Output: `research.md`

Document decisions for:
- **Counter Storage**: Redis vs local memory (decision criteria: deployment model, consistency requirements)
- **Window Algorithm**: Fixed window with reset vs sliding window (decision criteria: precision vs implementation simplicity)
- **Middleware Pattern**: FastAPI dependency injection vs middleware (decision criteria: testability, error handling)
- **Cache Strategy**: Pub/sub vs polling vs TTL-only (decision criteria: <5s requirement, deployment complexity)
- **Token Estimation**: Pre-request blocking vs post-request tracking (decision criteria: accuracy vs performance)

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` complete with all algorithm/pattern decisions made

### Deliverable 1: Data Model (`data-model.md`)

Define complete entity model with attributes, relationships, validation rules:

#### Domain Models

**RateLimit**:
- Attributes: `id` (Optional[int]), `scope_type` (Literal["global", "model", "group_model"]), `scope_id` (Optional[str]), `windows` (List[RateLimitWindow]), `created_at` (datetime), `updated_at` (datetime)
- Validation: scope_id required if scope_type != "global", windows list non-empty, scope_id format validation (model_id for model, "group_id:model_id" for group_model)
- Relationships: One-to-many with RateLimitWindow

**RateLimitWindow**:
- Attributes: `id` (Optional[int]), `rate_limit_id` (int), `from_time` (str, format "HH:MM:SS"), `to_time` (str, format "HH:MM:SS"), `max_requests` (int, -1 for unlimited), `max_tokens` (int, -1 for unlimited)
- Validation: from_time < to_time (or handle day rollover), max_requests/max_tokens >= -1, time format regex
- Relationships: Many-to-one with RateLimit

**RateLimitUsage**:
- Attributes: `scope_identifier` (str), `window_start_timestamp` (datetime), `request_count` (int), `token_count` (int), `last_updated` (datetime)
- Validation: Counts >= 0, scope_identifier non-empty
- State transitions: Reset when window_start_timestamp changes

**RateLimitErrorResponse**:
- Attributes: `error` (ErrorDetails object)
- ErrorDetails: `type` ("rate_limit_exceeded"), `scope` (str), `message` (str), `details` (LimitDetails object)
- LimitDetails: `limit_type` ("requests"/"tokens"), `current_usage` (int), `limit` (int), `window_reset_at` (datetime ISO 8601)

#### ORM Models

**RateLimitORM** (table: `rate_limits`):
- Columns: `id` (PK), `scope_type` (String), `scope_id` (String, nullable), `created_at` (DateTime), `updated_at` (DateTime)
- Indexes: Unique index on (scope_type, scope_id), index on scope_type
- Relationships: One-to-many with RateLimitWindowORM

**RateLimitWindowORM** (table: `rate_limit_windows`):
- Columns: `id` (PK), `rate_limit_id` (FK to rate_limits), `from_time` (String), `to_time` (String), `max_requests` (Integer), `max_tokens` (Integer)
- Indexes: FK index on rate_limit_id
- Constraints: Check max_requests >= -1, max_tokens >= -1

#### Mapper Functions

**RateLimitMapper**:
- `to_domain(orm: RateLimitORM) -> RateLimit`: Convert ORM to domain model with windows
- `to_orm(domain: RateLimit, existing: Optional[RateLimitORM]) -> RateLimitORM`: Convert domain to ORM for persistence

### Deliverable 2: API Contracts (`contracts/`)

#### Admin API OpenAPI Spec (`admin-rate-limits-api.yaml`)

```yaml
openapi: 3.0.3
info:
  title: Rate Limits Admin API
  version: 1.0.0

paths:
  /admin/rate-limits/global:
    get:
      summary: Get global rate limits
      security:
        - OAuth2: [admin]
      responses:
        '200':
          description: Global rate limits from config.json
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RateLimitResponse'

  /admin/rate-limits/models/{model_id}:
    post:
      summary: Create/update model-level rate limit
      parameters:
        - name: model_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RateLimitRequest'
      responses:
        '200':
          description: Rate limit created/updated
        '400':
          description: Validation error
    delete:
      summary: Delete model-level rate limit
      # ... similar structure

  /admin/rate-limits/groups/{group_id}/models/{model_id}:
    post:
      summary: Create/update group/model rate limit
      # ... similar structure

  /admin/rate-limits:
    get:
      summary: List all rate limits
      parameters:
        - name: scope_type
          in: query
          schema:
            type: string
            enum: [global, model, group_model]
        - name: model_id
          in: query
          schema:
            type: string
      responses:
        '200':
          description: List of rate limits
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/RateLimitResponse'

components:
  schemas:
    RateLimitRequest:
      type: object
      properties:
        windows:
          type: array
          items:
            $ref: '#/components/schemas/WindowRequest'
      required: [windows]

    WindowRequest:
      type: object
      properties:
        from_time:
          type: string
          pattern: '^([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
        to_time:
          type: string
          pattern: '^([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
        max_requests:
          type: integer
          minimum: -1
        max_tokens:
          type: integer
          minimum: -1
      required: [from_time, to_time, max_requests, max_tokens]

    RateLimitResponse:
      # ... similar structure with id, scope details, usage stats
```

#### Config JSON Schema (`config-schema.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "rate_limits": {
      "type": "object",
      "properties": {
        "global": {
          "type": "object",
          "properties": {
            "windows": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "from": {"type": "string", "pattern": "^([0-1][0-9]|2[0-3]):[0-5][0-9]$"},
                  "to": {"type": "string", "pattern": "^([0-1][0-9]|2[0-3]):[0-5][0-9]$"},
                  "max_requests": {"type": "integer", "minimum": -1},
                  "max_tokens": {"type": "integer", "minimum": -1}
                },
                "required": ["from", "to", "max_requests", "max_tokens"]
              },
              "minItems": 1
            }
          },
          "required": ["windows"]
        }
      },
      "required": ["global"]
    }
  }
}
```

### Deliverable 3: Quickstart Guide (`quickstart.md`)

**Configuration Setup**:
```bash
# 1. Configure global limits in config.json
{
  "rate_limits": {
    "global": {
      "windows": [
        {"from": "00:00", "to": "23:59", "max_requests": 1000, "max_tokens": 500000}
      ]
    }
  }
}

# 2. Run database migration
poetry run alembic upgrade head

# 3. Restart gateway to load config
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --reload

# 4. Create model-level limit via API
curl -X POST http://localhost:8000/admin/rate-limits/models/gpt-4 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"windows": [{"from": "00:00", "to": "23:59", "max_requests": 100, "max_tokens": 50000}]}'

# 5. Test rate limiting
for i in {1..150}; do curl http://localhost:8000/v1/chat/completions ...; done
# Expect HTTP 429 after limit reached
```

**Testing**:
```bash
# Run all rate limiting tests
pytest tests/ -k rate_limit

# Run specific layer tests
pytest tests/domain/test_rate_limit_models.py -v
pytest tests/application/test_rate_limit_service.py -v
pytest tests/infrastructure/test_rate_limit_repository.py -v
pytest tests/interfaces/test_rate_limits_endpoints.py -v
```

### Deliverable 4: Agent Context Update

Run agent context update script to add rate limiting technologies to copilot instructions:

```powershell
.specify/scripts/powershell/update-agent-context.ps1 -AgentType copilot
```

Additions to `.github/copilot-instructions.md`:
- Rate limiting middleware pattern
- Redis counter patterns (INCR/EXPIRE)
- Time window selection algorithm
- FastAPI dependency injection for rate limiting
- HTTP 429 response structure

## Phase 1: Constitution Re-check

**Re-evaluate after design phase**:

### Principle I: Onion Architecture ✅ STILL PASS
- Data model confirms domain/ORM separation via explicit mapper
- Contracts show clear API boundary at interfaces layer
- No infrastructure leakage detected in entity definitions

### Principle II: Test-First Development ✅ STILL PASS
- Test file structure mirrors source code organization
- Contract tests defined via OpenAPI spec
- Integration test scenarios identified (time transitions, cache invalidation)

### Principle III: Type Safety ✅ STILL PASS
- All Pydantic models have explicit types in contracts
- OpenAPI schema provides type validation for API
- Config schema enforces type safety for configuration

### Principle IV: Performance & Observability ✅ STILL PASS
- <10ms overhead achievable with in-memory cache
- Atomic counter patterns ensure correctness under concurrency
- Metrics defined for observability requirements

## Notes

**Design Decisions Pending Research (Phase 0)**:
- Counter storage mechanism (Redis vs local memory)
- Window transition timing (background scheduler vs lazy evaluation)
- Cache invalidation strategy (pub/sub vs polling)
- Token estimation approach (pre-request vs post-request)

**Risk Mitigation**:
- **Race conditions**: Mitigated by atomic counter operations (Redis INCR or threading.Lock)
- **Cache inconsistency**: Mitigated by TTL + invalidation events, acceptable <5s eventual consistency
- **Database failure**: Mitigated by graceful degradation using cached configuration (FR-032)
- **Performance degradation**: Mitigated by in-memory cache, target <10ms overhead validated through load testing

**Integration Points**:
- **Existing authentication**: Admin endpoints reuse `require_admin_role` dependency (no changes needed)
- **Existing Group/Model management**: Rate limit repository queries existing tables (foreign key relationships)
- **Existing config.json loader**: Extend settings.py to parse rate_limits section (minimal changes)
- **Existing middleware stack**: Rate limiting dependency injected before LLM client call (middleware order matters)

**Next Steps**:
1. Execute Phase 0 research to resolve algorithm/pattern decisions
2. Generate `research.md` documenting all decisions with rationale
3. Execute Phase 1 to produce `data-model.md`, `contracts/`, `quickstart.md`
4. Review constitution compliance after Phase 1 design
5. Proceed to `/speckit.tasks` to generate implementation task list
