<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 1.1.0
Rationale: Added new principle for Management Client Parity - all admin endpoints must have corresponding client methods

Modified Principles: N/A
Added Sections:
  - V. Management Client Parity (NON-NEGOTIABLE)
    * Requirement: All /admin/* endpoints must be callable from client SDK
    * Location: client/src/ygo74/fastapi_openai_rag_client/
    * Workflow: Define endpoint → Implement handler → Implement client method → Write tests → Update docs
    * Examples: users, groups, models, rate-limits client methods

Removed Sections: N/A

Templates Status:
  ✅ plan-template.md - Needs review (add client implementation to task phases)
  ✅ spec-template.md - Needs review (add client SDK requirements to acceptance criteria)
  ✅ tasks-template.md - Needs review (add client implementation tasks for admin endpoints)
  ⚠ Commands requiring updates:
    - Any commands creating admin endpoints should remind to implement client method
    - Rate limit admin endpoints need client implementation (pending)

Follow-up TODOs:
  - TODO(CLIENT_SDK): Implement rate limit admin endpoints in management client
  - TODO(TEMPLATES): Update plan/spec/tasks templates to include client SDK requirements
  - TODO(CHECKLIST): Add "Client method implemented" to PR checklist for admin endpoints
  - TODO(DOCS): Document client SDK architecture and testing patterns
-->

# FastAPI OpenAI Proxy Constitution

## Core Principles

### I. Onion Architecture Integrity

**Dependencies MUST point inward only. Infrastructure layer NEVER imported by domain.**

- **Domain layer** (`domain/`) contains pure business models, protocols, and repository interfaces with ZERO external dependencies (no SQLAlchemy, no HTTP clients, no framework imports)
- **Application layer** (`application/`) orchestrates business logic through services, depends only on domain protocols
- **Infrastructure layer** (`infrastructure/`) implements domain protocols (LLM clients, DB repositories via SQLAlchemy, HTTP clients)
- **Interfaces layer** (`interfaces/`) exposes API endpoints, CLI, handles auth/middleware
- All external integrations (OpenAI, Anthropic, Azure, databases) MUST be abstracted behind domain protocols
- Repository pattern and Unit of Work pattern MUST be used for all data access

**Rationale**: Ensures testability through dependency injection, enables swapping implementations without touching business logic, prevents infrastructure concerns from leaking into domain models. This architecture makes the codebase resilient to provider changes and facilitates independent layer testing.

### II. Test-First Development (NON-NEGOTIABLE)

**Every function/method MUST have accompanying unit tests before implementation. Red-Green-Refactor cycle strictly enforced.**

- Tests written → User approved → Tests fail → Then implement
- Test organization mirrors onion architecture: `tests/domain/`, `tests/application/`, `tests/infrastructure/`, `tests/interfaces/`
- All external dependencies (LLM APIs, databases, Redis, HTTP calls) MUST be mocked in unit tests
- Test naming convention: `test_<module>_<function>_<case>()` using Arrange-Act-Assert pattern
- Layer-specific testing requirements:
  - **Domain tests**: Pure unit tests, no external dependencies
  - **Application tests**: Service layer tests with mocked repositories and infrastructure
  - **Infrastructure tests**: Integration tests with mocked external APIs
  - **Interface tests**: API endpoint tests with mocked services
- Contract tests required for API endpoints against OpenAI compatibility
- Integration tests required for: new LLM provider integrations, authentication flows, inter-service communication

**Rationale**: Test-first prevents defects at design time, documents expected behavior, enables fearless refactoring. The layer-based test organization ensures each architectural layer can be tested in isolation, making the test suite fast, reliable, and maintainable.

### III. Type Safety & Documentation

**Full type hints required for all code. English documentation mandatory for all public functions and classes.**

- **Type hints**: All function arguments, return types, and variables MUST be typed
- **Function docstrings**: Purpose, arguments (with types), return value, exceptions raised
- **Class docstrings**: Overview, attributes, key methods
- **Pydantic models**: Use for validation and serialization in domain and interface layers
- **Protocol classes**: Define interfaces in domain layer for infrastructure implementations
- Prefer class-based imports (`MyClass.static_method()`) over standalone functions
- Domain models and ORM models MUST be strictly separated with explicit mapper functions

**Rationale**: Type safety catches errors at development time (not runtime), enables IDE autocomplete and refactoring tools, documents intent. English documentation ensures knowledge transfer and reduces onboarding friction. The domain/ORM separation maintains clean architecture and prevents database concerns from polluting business logic.

### IV. Performance & Observability

**System MUST meet enterprise performance requirements with comprehensive monitoring and retry logic.**

- **Performance targets**:
  - API response time: <200ms p95 for non-streaming endpoints
  - Streaming first-token latency: <500ms p95
  - Support 1000+ concurrent requests
  - Database query optimization: <50ms p95 per query
- **Observability requirements**:
  - Structured logging for all external calls (LLM APIs, database operations)
  - Token usage tracking (input/output) per request
  - Request latency metrics per endpoint and per LLM provider
  - Error rate monitoring per provider
  - Audit logging for authentication events
- **Reliability**:
  - Corporate proxy support via `HttpClientFactory` with configurable SSL/CA certs
  - Retry logic with exponential backoff on transient failures (`@with_enterprise_retry` decorator)
  - Circuit breaker pattern for external provider failures
  - Graceful degradation when providers are unavailable

**Rationale**: Enterprise deployments require predictable performance, comprehensive monitoring for debugging production issues, and resilience to external service failures. Token tracking enables cost attribution, while structured logging facilitates rapid incident response.

### V. Management Client Parity (NON-NEGOTIABLE)

**All management endpoints MUST be callable from the gateway management client. Adding an admin route requires implementing the corresponding client method.**

- **Client location**: `client/src/ygo74/fastapi_openai_rag_client/` contains the management client SDK
- **Endpoint-to-client mapping**: Every route in `interfaces/api/admin/*` MUST have a corresponding method in the client
- **Client implementation requirements**:
  - Method signature matches endpoint semantics (same parameters, return types)
  - Proper error handling (HTTP status codes mapped to client exceptions)
  - Type hints and docstrings matching server endpoint documentation
  - Support for all endpoint features (pagination, filtering, etc.)
- **Testing requirements**:
  - Client method tests MUST mock HTTP calls (no live server required)
  - Integration tests MUST verify client works against real server
  - Contract tests ensure client expectations match server responses
- **Implementation workflow**:
  1. Define admin endpoint route with OpenAPI documentation
  2. Implement endpoint handler in `interfaces/api/admin/`
  3. Implement corresponding client method in `client/src/ygo74/fastapi_openai_rag_client/`
  4. Write client method tests
  5. Update client README with usage examples
- **Client versioning**: Client version MUST match gateway version (semantic versioning)

**Examples of management endpoints requiring client support**:

- `GET/POST /admin/users` → `client.users.list()`, `client.users.create()`
- `GET/POST/DELETE /admin/groups` → `client.groups.list()`, `client.groups.create()`, `client.groups.delete()`
- `GET/POST/DELETE /admin/models` → `client.models.list()`, `client.models.create()`, `client.models.delete()`
- `GET/POST/DELETE /admin/rate-limits` → `client.rate_limits.list()`, `client.rate_limits.create()`, `client.rate_limits.delete()`

**Rationale**: Management operations require programmatic access for automation, CI/CD pipelines, and infrastructure-as-code workflows. A well-maintained client SDK reduces integration friction, enforces consistent error handling, and provides type safety for API consumers. The client serves as executable documentation and enables testing management workflows without manual API calls.

## Architecture Standards

### Domain Model Separation

- **Domain models**: Pydantic models in `domain/models/` (e.g., `User`, `Group`, `LlmModel`, `ChatCompletionRequest`)
- **ORM models**: SQLAlchemy models in `infrastructure/db/models/` with `ORM` suffix (e.g., `UserORM`, `GroupORM`)
- **Mappers**: Explicit conversion functions in `infrastructure/db/mappers/` (e.g., `UserMapper.to_domain()`, `UserMapper.to_orm()`)
- Domain models MUST NOT import SQLAlchemy or reference ORM concerns

### Repository & Unit of Work Patterns

- **Repository interfaces**: Protocol classes in `domain/repositories/` define data access contracts
- **Repository implementations**: SQLAlchemy implementations in `infrastructure/db/repositories/`
- **Unit of Work**: Protocol in `domain/unit_of_work.py`, SQLAlchemy implementation in `infrastructure/db/unit_of_work.py`
- All database transactions MUST go through Unit of Work for proper commit/rollback handling

### LLM Client Architecture

- **Protocol-based design**: All LLM clients implement `LLMClientProtocol` from `domain/protocols/`
- **Client implementations**: `OpenAIClient`, `AzureOpenAIClient`, `AnthropicClient` in `infrastructure/llm/`
- **Client factory**: `ClientFactory` creates appropriate client based on provider configuration
- Clients MUST handle streaming, retries, and format conversions transparently

### Authentication & Authorization

- **Dual auth system**:
  - Management endpoints: OAuth2/Keycloak JWT (`require_admin_role` dependency)
  - Chat endpoints: JWT or API key (`auth_jwt_or_api_key` dependency)
- **Group-based authorization**: Users assigned to groups, groups authorized for specific models
- API keys stored securely with bcrypt hashing

## Development Workflow

### Quality Gates

1. **Pre-implementation**: Tests written and approved by user
2. **Implementation**: Tests must fail (red phase)
3. **Development**: Implement until tests pass (green phase)
4. **Refinement**: Refactor while keeping tests green
5. **Code review**: Verify constitution compliance, test coverage, type hints, documentation
6. **Merge**: All tests passing, no type errors, documentation complete

### Testing Commands

```powershell
pytest tests/                           # All tests must pass
pytest tests/domain/                    # Domain layer isolation
pytest tests/application/               # Service layer with mocks
pytest tests/infrastructure/            # Infrastructure integration tests
pytest tests/interfaces/                # API endpoint tests
pytest --log-cli-level=DEBUG tests/    # Debug mode
```

### Development Environment

```powershell
docker compose -f .\docker-compose-backend.yml up -d  # Start Keycloak, PostgreSQL
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

### Configuration Management

- Model configurations in `config.json` (copy from `config.json.example`)
- Environment variables for secrets (database credentials, API keys)
- Provider-specific settings (Azure API versions, retry configs) in model configuration

## Governance

**This constitution supersedes all other development practices. All PRs and code reviews MUST verify compliance.**

- **Amendment procedure**: Proposed changes require justification, impact analysis on existing code, approval from tech lead, migration plan if breaking changes introduced
- **Version policy**: MAJOR (architectural changes, removed principles), MINOR (new principles, expanded guidance), PATCH (clarifications, typo fixes)
- **Compliance review**: Each PR checklist item for each principle (architecture integrity checked, tests written first, types complete, documentation present, performance considered)
- **Runtime guidance**: Detailed implementation patterns in `.github/copilot-instructions.md` for AI assistants
- **Constitution authority**: When practices conflict, constitution wins. Deviations require explicit justification in PR description

**Version**: 1.1.0 | **Ratified**: 2025-12-06 | **Last Amended**: 2025-12-07
