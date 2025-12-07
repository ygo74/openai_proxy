# Implementation Tasks: Rate Limiting System

**Feature**: Multi-level Rate Limiting
**Branch**: `feature/add_rate_limit`
**Generated**: 2025-12-06
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md), [research.md](./research.md)

---

## Task Organization

Tasks are organized by **user story** to enable independent, incremental delivery. Each user story phase can be implemented and tested independently, allowing for true MVP-first development.

**Legend**:
- `[P]` = Parallelizable (can run simultaneously with other [P] tasks in same phase)
- `[US#]` = User Story label (US1, US2, etc.)
- Task IDs: Sequential (T001, T002, etc.) in logical execution order

**MVP Scope (P1 stories)**: US1 (Request Limiting), US2 (Token Limiting), US5 (Admin API)

---

## Implementation Strategy

### Approach: User Story → Independent Testing → Incremental Delivery

Each user story phase is **self-contained** with:
1. **Story goal**: What user value this phase delivers
2. **Independent test**: How to verify this story works in isolation
3. **Implementation tasks**: Domain → Application → Infrastructure → Interfaces (onion architecture)
4. **Test tasks**: Unit → Integration → Contract tests

This enables:
- ✅ **Parallel development**: Multiple stories can progress simultaneously
- ✅ **Early feedback**: Each story can be demoed/tested independently
- ✅ **Risk mitigation**: MVP (US1+US2+US5) can ship without P2 features
- ✅ **Clear progress**: Each completed story = measurable user value

---

## Phase 1: Setup & Foundation

**Goal**: Initialize project structure, database schema, and base configuration

**Dependencies**: None (foundational work)

### Tasks

- [ ] T001 Create Alembic migration for rate_limits and rate_limit_windows tables in alembic/versions/YYYYMMDD_add_rate_limiting.py
- [ ] T002 [P] Create base domain model files: domain/models/rate_limit.py (empty initially)
- [ ] T003 [P] Create base ORM model files: infrastructure/db/models/rate_limit_orm.py (empty initially)
- [ ] T004 [P] Create repository protocol: domain/repositories/rate_limit_repository.py with IRateLimitRepository interface
- [ ] T005 [P] Update infrastructure/db/models/__init__.py to import new ORM models
- [ ] T006 Run Alembic migration to create database tables: `alembic upgrade head`
- [ ] T007 Create tests/domain/test_rate_limit_models.py for domain model validation tests
- [ ] T008 Create tests/infrastructure/test_rate_limit_repository.py for repository tests

**Validation**:
- Database tables exist with correct schema
- Import structure works (no circular dependencies)
- Test files created and discoverable by pytest

---

## Phase 2: Foundational Models & Services

**Goal**: Implement core domain models and service layer that all user stories depend on

**Dependencies**: Phase 1 complete

### Tasks

- [X] T009 [P] Implement RateLimitWindow domain model in domain/models/rate_limit.py with validation
- [X] T010 [P] Implement RateLimit domain model in domain/models/rate_limit.py with scope_type validation
- [X] T011 [P] Implement RateLimitUsage domain model for counter tracking in domain/models/rate_limit.py
- [X] T012 [P] Implement RateLimitErrorResponse domain model in domain/models/rate_limit.py
- [X] T013 [P] Write domain model tests in tests/domain/test_rate_limit_models.py (validation, is_active_at, scope_identifier)
- [X] T014 [P] Implement RateLimitWindowORM in infrastructure/db/models/rate_limit_orm.py
- [X] T015 [P] Implement RateLimitORM in infrastructure/db/models/rate_limit_orm.py with relationships
- [X] T016 [P] Implement RateLimitMapper in infrastructure/db/mappers/rate_limit_mapper.py (to_domain, to_orm)
- [X] T017 Implement SQLRateLimitRepository in infrastructure/db/repositories/rate_limit_repository.py (CRUD operations)
- [X] T018 Write repository tests in tests/infrastructure/test_rate_limit_repository.py (get, create, update, delete)
- [X] T019 [P] Create application/services/rate_limit_service.py with skeleton RateLimitService class
- [X] T020 [P] Create tests/application/test_rate_limit_service.py with test structure

**Validation**:
- All domain models validate correctly (Pydantic validation tests pass)
- Mapper converts between domain ↔ ORM without data loss
- Repository CRUD operations work against test database
- Service skeleton exists and importable

---

## Phase 3: User Story 1 - Request Rate Limiting Enforcement

**Story Goal**: Enforce request-based rate limits (global, model, group/model scopes) with HTTP 429 responses

**Independent Test**: Configure global limit of 50 req/hr. Send 60 requests. Verify 1-50 succeed, 51-60 return HTTP 429.

### Tasks

- [X] T021 [US1] Implement counter storage: Create infrastructure/cache/rate_limit_counter.py with Redis INCR operations
- [X] T022 [US1] Implement get_current_window_key() in RateLimitService for window start calculation
- [X] T023 [US1] Implement check_request_limit() in RateLimitService with counter increment and limit evaluation
- [X] T024 [US1] Create RateLimitExceeded exception in domain/exceptions/rate_limit_exception.py
- [X] T025 [US1] Implement rate limit exception handler in interfaces/api/exception_handlers.py (HTTP 429 response)
- [X] T026 [US1] Create FastAPI dependency: interfaces/api/dependencies/rate_limiting.py with check_rate_limit()
- [X] T027 [US1] Integrate rate limiting dependency into /v1/chat/completions endpoint
- [X] T028 [US1] Write counter storage tests in tests/infrastructure/test_rate_limit_counter.py (Redis operations)
- [X] T029 [US1] Write service tests in tests/application/test_rate_limit_service.py (check_request_limit scenarios)
- [X] T030 [US1] Write integration tests in tests/interfaces/test_rate_limiting_integration.py (end-to-end request limiting)
- [X] T031 [US1] Write HTTP 429 contract tests in tests/interfaces/test_rate_limit_errors.py (response structure)

**Validation Criteria**:
- ✅ Request counter increments atomically (concurrent test)
- ✅ HTTP 429 returned when limit exceeded with correct headers
- ✅ Error response matches OpenAI format (type, code, details)
- ✅ Global limits enforced across all requests
- ✅ Model limits enforced per model
- ✅ Group/model limits enforced per group+model combo

---

## Phase 4: User Story 2 - Token-Based Rate Limiting

**Story Goal**: Track and enforce token consumption limits (prompt + completion tokens)

**Independent Test**: Configure token limit of 10,000 tokens/hr. Send 5 requests @ 2,000 tokens each. Verify 6th fails.

### Tasks

- [X] T032 [US2] Add token counter support to infrastructure/cache/rate_limit_counter.py (INCRBY operations)
- [X] T033 [US2] Implement record_token_usage() in RateLimitService with async background task
- [X] T034 [US2] Implement check_token_limit() in RateLimitService with token usage evaluation
- [X] T035 [US2] Parse token usage from LLM provider responses in infrastructure/llm/token_usage_parser.py
- [X] T036 [US2] Integrate token recording into /v1/chat/completions endpoint (background task)
- [X] T037 [US2] Add token limit checks to rate limiting dependency in interfaces/api/dependencies/rate_limiting.py
- [X] T038 [US2] Write token counter tests in tests/infrastructure/test_rate_limit_counter.py (INCRBY, multi-window)
- [X] T039 [US2] Write service tests for token limiting in tests/application/test_rate_limit_service.py
- [X] T040 [US2] Write integration tests for token limits in tests/interfaces/test_token_rate_limiting_integration.py
- [X] T041 [US2] Write HTTP 429 tests for token limit exceeded in tests/interfaces/test_token_rate_limit_errors.py

**Validation Criteria**:
- ✅ Token usage recorded after response completion
- ✅ Token limits block requests when exceeded
- ✅ HTTP 429 indicates "tokens" as limit_type
- ✅ Both requests and tokens can coexist (check both limits)
- ✅ Token counts accurate from provider responses (OpenAI, Azure, Anthropic)

---

## Phase 5: User Story 5 - Dynamic Limit Configuration (Admin API)

**Story Goal**: Administrators can create/update/delete rate limits via REST API without restart

**Independent Test**: POST model limit via API. Immediately verify enforcement. Update limit, verify new limit within 5s.

### Tasks

- [X] T042 [US5] Create Pydantic request models in interfaces/api/models/rate_limit_api.py (CreateRateLimitRequest, UpdateRateLimitRequest)
- [X] T043 [US5] Create Pydantic response models in interfaces/api/models/rate_limit_api.py (RateLimitResponse)
- [X] T044 [US5] Implement GET /admin/rate-limits endpoint in interfaces/api/admin/rate_limits.py (list all)
- [X] T045 [US5] Implement GET /admin/rate-limits/global endpoint (return config.json global limits)
- [X] T046 [US5] Implement POST /admin/rate-limits/models/{model_id} endpoint (create/update model limit)
- [X] T047 [US5] Implement POST /admin/rate-limits/groups/{group_id}/models/{model_id} endpoint (create/update group/model limit)
- [X] T048 [US5] Implement DELETE /admin/rate-limits/{id} endpoint
- [X] T049 [US5] Implement cache invalidation via Redis pub/sub in infrastructure/cache/rate_limit_cache.py
- [X] T050 [US5] Add pub/sub listener to RateLimitService for config updates
- [X] T051 [US5] Add LRU in-memory cache (64 entries, 30s TTL) to RateLimitService
- [X] T052 [US5] Write admin API tests in tests/interfaces/test_admin_rate_limits.py (CRUD operations)
- [X] T053 [US5] Write cache invalidation tests in tests/infrastructure/test_rate_limit_cache.py (pub/sub propagation)
- [X] T054 [US5] Write integration tests for <5s propagation in tests/interfaces/test_rate_limit_propagation.py

**Validation Criteria**:
- ✅ Admin can create model-level rate limits via API (17 tests passing)
- ✅ Admin can create group/model-level rate limits via API (17 tests passing)
- ✅ Changes propagate to all instances within 5 seconds (8 propagation tests)
- ✅ Invalid payloads return HTTP 400 with validation errors (tested)
- ✅ Admin endpoints require admin role (auth check tested)
- ✅ GET /admin/rate-limits returns all configured limits (tested)
- ✅ Cache invalidation via Redis pub/sub works (14 cache tests passing)
- ✅ LRU cache with 30s TTL implemented and tested
- ✅ Time format: User-friendly "HH:MM" or "HH:MM:SS" strings

---

## Phase 6: User Story 3 - Hierarchical Limit Priority (P2)

**Story Goal**: Apply most specific limit (group/model → model → global) when multiple exist

**Independent Test**: Configure global=1000, model=500, group/model=100. Verify group/model limit (100) enforced.

### Tasks

- [ ] T055 [US3] Implement get_applicable_limits() in RateLimitService to query all hierarchy levels
- [ ] T056 [US3] Implement limit priority evaluation in check_limit() (group/model > model > global)
- [ ] T057 [US3] Add -1/None handling for unlimited limits in evaluation logic
- [ ] T058 [US3] Write hierarchy tests in tests/application/test_rate_limit_service.py (priority scenarios)
- [ ] T059 [US3] Write integration tests for hierarchical enforcement in tests/interfaces/test_rate_limiting_integration.py

**Validation Criteria**:
- ✅ Group/model limit takes precedence over model and global
- ✅ Model limit takes precedence over global when no group/model limit
- ✅ Global limit applied when no more specific limits exist
- ✅ Limit set to -1 or None treated as unlimited (skip to next level)

---

## Phase 7: User Story 4 - Time Window Management (P2)

**Story Goal**: Support multiple time windows per limit with automatic transitions

**Independent Test**: Configure 00:00-08:00 → 100 req, 08:00-23:59 → 1000 req. Verify counter resets at 08:00.

### Tasks

- [ ] T060 [US4] Implement get_active_window() in RateLimit domain model to find current time window
- [ ] T061 [US4] Update check_limit() in RateLimitService to use active window's limits
- [ ] T062 [US4] Implement window transition detection in get_current_window_key() (new window = new key)
- [ ] T063 [US4] Add default 24-hour window fallback when no time windows match
- [ ] T064 [US4] Write time window tests in tests/domain/test_rate_limit_models.py (is_active_at, window selection)
- [ ] T065 [US4] Write window transition tests in tests/application/test_rate_limit_service.py (counter reset)
- [ ] T066 [US4] Write integration tests for window transitions in tests/interfaces/test_rate_limiting_integration.py

**Validation Criteria**:
- ✅ Active window selected based on current time
- ✅ Counter resets when transitioning to new window
- ✅ Multiple windows per limit work independently
- ✅ Default 24-hour window used when no match

---

## Phase 8: User Story 6 - Model-Level Aggregation (P2)

**Story Goal**: Aggregate usage across all groups for model-level limits

**Independent Test**: Model limit=100. Group A sends 60, Group B sends 50. Verify both blocked after 100 total.

### Tasks

- [ ] T067 [US6] Update counter key generation to use model name (not group+model) for model-level limits
- [ ] T068 [US6] Implement model-level usage aggregation in check_limit() (query model-wide counter)
- [ ] T069 [US6] Write aggregation tests in tests/application/test_rate_limit_service.py (multi-group scenarios)
- [ ] T070 [US6] Write integration tests for model-level aggregation in tests/interfaces/test_rate_limiting_integration.py

**Validation Criteria**:
- ✅ Model-level limit counts requests from all groups
- ✅ Model limit reached blocks all groups
- ✅ Different models tracked independently

---

## Phase 9: Configuration & Global Limits

**Goal**: Load global rate limits from config.json and integrate with existing ConfigService

**Dependencies**: Phases 3-4 complete (need enforcement logic)

### Tasks

- [ ] T071 [P] Create domain/models/rate_limit_config.py with TimeWindow, GlobalRateLimitsConfig, RateLimitsConfig Pydantic models
- [ ] T072 [P] Update domain/models/configuration.py to add rate_limits field to AppConfig
- [ ] T073 Update AppConfig.load_from_json() to parse rate_limits section
- [ ] T074 Add config.json example with rate_limits section to config.json.example
- [ ] T075 Update application/services/config_service.py to expose get_global_rate_limits() method
- [ ] T076 Integrate global limits into RateLimitService.check_limit() (fallback when no DB limits)
- [ ] T077 Write config loading tests in tests/application/test_config_service.py (rate_limits parsing)
- [ ] T078 Write config validation tests in tests/domain/test_rate_limit_config.py (Pydantic validation)

**Validation Criteria**:
- ✅ config.json loads with rate_limits section
- ✅ Pydantic validation catches invalid config (duration_seconds > 0, at least one window)
- ✅ Global limits enforced when no database limits exist
- ✅ ConfigService reload updates global limits

---

## Phase 10: Polish & Cross-Cutting Concerns

**Goal**: Finalize observability, documentation, error handling, and edge cases

**Dependencies**: All user story phases complete

### Tasks

- [ ] T079 [P] Add structured logging to RateLimitService (limit hit, limit exceeded, cache miss)
- [ ] T080 [P] Add metrics emission: rate_limit.evaluation.duration_ms, rate_limit.exceeded.count
- [ ] T081 [P] Implement fail-open logic: If Redis unavailable, log error and allow request (config flag)
- [ ] T082 [P] Add Redis connection retry logic (1 retry, 100ms backoff) in rate_limit_counter.py
- [ ] T083 [P] Update OpenAPI spec in contracts/admin-rate-limits-api.yaml with all endpoints
- [ ] T084 [P] Create config schema JSON in contracts/config-schema.json for config.json validation
- [ ] T085 [P] Write quickstart.md with setup instructions, API examples, testing commands
- [ ] T086 [P] Update .github/copilot-instructions.md with rate limiting patterns
- [ ] T087 [P] Add health check endpoint: GET /admin/rate-limits/health (check Redis, DB)
- [ ] T088 [P] Write performance tests in tests/performance/test_rate_limit_performance.py (<10ms p99)
- [ ] T089 [P] Write concurrency tests in tests/integration/test_rate_limit_concurrency.py (1000+ concurrent)
- [ ] T090 [P] Add cleanup job for expired Redis keys (optional, Redis TTL handles this)

**Validation Criteria**:
- ✅ Metrics show rate limit latency <10ms p99
- ✅ Concurrent requests handle correctly (no race conditions)
- ✅ Redis failure doesn't crash gateway (fail-open mode)
- ✅ Logs provide debug visibility (scope, limit, usage)
- ✅ Documentation complete and accurate

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Task Dependencies                             │
└─────────────────────────────────────────────────────────────────────┘

Phase 1 (Setup)
  └─► Phase 2 (Foundation)
       ├─► Phase 3 (US1: Request Limiting) ◄── MVP REQUIRED
       │    └─► Phase 9 (Config & Global Limits)
       │
       ├─► Phase 4 (US2: Token Limiting) ◄── MVP REQUIRED
       │
       ├─► Phase 5 (US5: Admin API) ◄── MVP REQUIRED
       │
       ├─► Phase 6 (US3: Hierarchy) ◄── P2 ENHANCEMENT
       │
       ├─► Phase 7 (US4: Time Windows) ◄── P2 ENHANCEMENT
       │
       └─► Phase 8 (US6: Model Aggregation) ◄── P2 ENHANCEMENT

All User Story Phases
  └─► Phase 10 (Polish & Cross-Cutting)
```

**Story Completion Order**:
1. **Phase 1 + Phase 2** (Foundation) - MUST complete first
2. **Phase 3 (US1)** → Phase 4 (US2) → Phase 5 (US5) → Phase 9 → **MVP COMPLETE** ✅
3. Phase 6 (US3) + Phase 7 (US4) + Phase 8 (US6) - **P2 enhancements** (any order)
4. Phase 10 - **Final polish** (after all features)

---

## Parallel Execution Examples

### During Phase 2 (Foundation):
```bash
# Developer A: Domain models
Task T009, T010, T011, T012, T013

# Developer B: ORM models and mappers
Task T014, T015, T016

# Developer C: Repository implementation
Task T017, T018

# Developer D: Service skeleton
Task T019, T020
```

### During Phase 3 (US1):
```bash
# Developer A: Counter storage infrastructure
Task T021, T028

# Developer B: Service logic
Task T022, T023, T029

# Developer C: Exception handling
Task T024, T025, T031

# Developer D: API integration
Task T026, T027, T030
```

---

## Testing Strategy

### Test Organization (Mirrors Onion Architecture)

**Domain Tests** (`tests/domain/`):
- Pure unit tests, no external dependencies
- Test Pydantic validation, business logic, computed properties
- Example: `test_rate_limit_window_validation_requires_at_least_one_limit()`

**Application Tests** (`tests/application/`):
- Service layer tests with mocked infrastructure (repositories, cache)
- Test business orchestration, limit evaluation logic
- Example: `test_rate_limit_service_check_limit_blocks_when_exceeded()`

**Infrastructure Tests** (`tests/infrastructure/`):
- Repository tests with test database
- Cache tests with Redis (or mock Redis client)
- Example: `test_rate_limit_repository_create_persists_windows()`

**Interface Tests** (`tests/interfaces/`):
- API endpoint tests with FastAPI TestClient
- Integration tests hitting full stack (DB + cache + endpoints)
- Example: `test_admin_rate_limits_post_creates_model_limit()`

**Contract Tests** (`tests/interfaces/`):
- HTTP 429 response structure validation
- OpenAPI schema compliance
- Example: `test_rate_limit_exceeded_response_matches_openai_format()`

### Test Naming Convention

Format: `test_<module>_<function>_<scenario>()`

Examples:
- `test_rate_limit_model_scope_id_validation_rejects_invalid_format()`
- `test_rate_limit_service_check_limit_allows_when_under_limit()`
- `test_rate_limit_repository_get_by_scope_returns_none_if_not_found()`
- `test_admin_rate_limits_delete_removes_limit_from_database()`

---

## Implementation Checklist

### Definition of Done (per task):

- [ ] Code implemented following onion architecture (domain → application → infrastructure → interfaces)
- [ ] All functions have English docstrings (purpose, args, returns, exceptions)
- [ ] Full type hints on all function arguments and return values
- [ ] Unit tests written and passing (Arrange-Act-Assert structure)
- [ ] Integration tests written for cross-layer interactions (if applicable)
- [ ] No circular dependencies (domain never imports infrastructure)
- [ ] Pydantic validation rules enforced in domain models
- [ ] Database migrations tested (up and down)
- [ ] OpenAPI spec updated for new endpoints (if applicable)

### MVP Acceptance Criteria:

After completing Phases 1-5 + Phase 9:

- [ ] ✅ Request-based rate limiting enforced (US1)
- [ ] ✅ Token-based rate limiting enforced (US2)
- [ ] ✅ Admin API allows CRUD for model and group/model limits (US5)
- [ ] ✅ Global limits loaded from config.json
- [ ] ✅ HTTP 429 responses match OpenAI format
- [ ] ✅ Rate limit headers (Retry-After, X-RateLimit-*) present
- [ ] ✅ <10ms p99 latency for rate limit checks
- [ ] ✅ Changes propagate within 5 seconds
- [ ] ✅ All P1 user story tests pass independently

### Full Feature Acceptance Criteria:

After completing all phases:

- [ ] ✅ Hierarchical limit priority works (US3)
- [ ] ✅ Time window management with transitions (US4)
- [ ] ✅ Model-level usage aggregation (US6)
- [ ] ✅ All metrics emitting correctly
- [ ] ✅ Fail-open mode for Redis failures
- [ ] ✅ Documentation complete (quickstart, OpenAPI, schema)
- [ ] ✅ Performance tests pass (1000+ concurrent, <10ms p99)

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation Task |
|------|------------|--------|-----------------|
| Redis unavailable | Low | High (blocks all requests) | T081: Fail-open logic with config flag |
| Race conditions in counters | Medium | High (over-limit requests) | T089: Concurrency tests with 1000+ threads |
| Window transitions lose state | Low | Medium (incorrect limits) | T065, T066: Window transition tests |
| Config propagation >5s | Medium | Medium (SLA violation) | T053, T054: Propagation tests with timers |
| Performance >10ms | Medium | High (SLA violation) | T088: Performance tests with benchmarks |

---

## Notes

**MVP Delivery**: Phases 1-5 + 9 deliver complete P1 user stories (US1, US2, US5) with global config support. This is a fully functional rate limiting system.

**P2 Features**: Phases 6-8 add enhancements (hierarchy, time windows, aggregation) but are not blocking for MVP.

**Onion Architecture**: Tasks explicitly follow domain → application → infrastructure → interfaces order within each phase.

**Test-First**: Each phase includes test tasks. Consider writing tests before implementation (TDD) per constitution.

**Parallel Work**: Tasks marked [P] can be executed simultaneously by different developers.

**Independent Stories**: Each user story phase (3-8) can be implemented and tested independently after foundation (Phases 1-2).

---

**Document Status:** ✅ COMPLETE
**Total Tasks:** 90
**MVP Tasks:** 48 (Phases 1-5 + 9)
**P2 Tasks:** 16 (Phases 6-8)
**Polish Tasks:** 12 (Phase 10)
**Cross-Phase Tasks:** 14 (Foundation, Phase 2)
**Ready for:** Implementation Sprint Planning
