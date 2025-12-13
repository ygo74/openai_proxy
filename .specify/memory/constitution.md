<!--
SYNC IMPACT REPORT
==================
Version Change: 1.4.0 → 1.5.0
Rationale: Added DRY Principle (Don't Repeat Yourself) to Core Principles - CRITICAL for code maintainability

Modified Principles:
  - Renumbered: IV→VI (Performance), V→VII (Management Client), VI→VIII (SOLID) due to new principle insertion
  - IV. DRY Principle: NEW - CRITICAL - Mandatory search before implementation, reuse existing code, forbidden duplication
  - VII. Management Client Parity: Updated examples to reflect actual client structure (client.commands.*)
  - VIII. SOLID Principles Adherence: Added comprehensive SOLID guidelines with examples

Added Sections:
  - Core Principles / IV. DRY Principle (v1.5.0) - CRITICAL
    * Mandatory search before implementation (grep_search, semantic_search)
    * Reuse existing code when functionality exists
    * Create new code only when none found or existing violates architecture
    * Refactoring for reuse: shared utilities, strategy pattern, base classes
    * Exceptions: Test fixtures, layer-specific DTOs, mappers per layer
    * Detection: IDE search, code review checklist, CI/CD linting
    * Examples: Time conversion reuse, domain validators, repository methods

  - Core Principles / VIII. SOLID Principles Adherence (v1.4.0)
    * Single Responsibility: One reason to change per class/module
    * Open/Closed: Extend via protocols, don't modify existing code
    * Liskov Substitution: Implementations substitutable for protocols
    * Interface Segregation: Specific protocols, not bloated interfaces
    * Dependency Inversion: Depend on abstractions, inject dependencies
    * Examples: Correct patterns vs violations for each principle

  - Architecture Standards / Interface Layer Responsibilities (v1.2.0)
    * Prohibition: Business logic, validation, auth, error handling in endpoints
    * Requirement: Endpoints limited to service invocation + object mapping only
    * Auth via dependency injection (Depends())
    * Error handling via centralized ExceptionHandlers class
    * Examples: Correct endpoint pattern vs anti-patterns

  - Architecture Standards / Mapper Layer Separation (v1.3.0) - CRITICAL
    * API Mappers (interfaces/api/mappers/): Pydantic ↔ Domain
    * ORM Mappers (infrastructure/db/mappers/): Domain ↔ SQLAlchemy
    * Forbidden: Infrastructure importing API models, single mapper mixing concerns
    * Rationale: Preserve onion architecture dependencies, enable independent layer testing

Validation Against Implementation:
  ✅ Onion architecture - Confirmed (domain/, application/, infrastructure/, interfaces/)
  ✅ Repository/UoW patterns - Confirmed (SQLUnitOfWork, SQL*Repository classes)
  ✅ LLM Protocol-based design - Confirmed (LLMClientProtocol, BaseOpenAIClient)
  ✅ Dual auth - Confirmed (require_admin_role, auth_jwt_or_api_key dependencies)
  ✅ Centralized exception handlers - Confirmed (ExceptionHandlers class in interfaces/api/)
  ✅ Thin endpoints - Confirmed (endpoints delegate to ChatCompletionService, UserService, etc.)
  ✅ Mapper layer separation - Confirmed (interfaces/api/mappers/ for API, infrastructure/db/mappers/ for ORM)
  ✅ DRY principle - Confirmed (time conversion utilities reused, no duplicate mapper logic)
  ✅ SOLID principles - Confirmed (SRP in services, DIP via protocols, LSP in implementations)
  ✅ Management client - Partially implemented (users/groups/models done, rate_limits pending)

Templates Status:
  ✅ Implementation validated against constitution principles
  ⚠ Management client for rate limits still TODO

Follow-up TODOs:
  - TODO(CLIENT_SDK): Implement rate limit admin endpoints client methods (client/commands/rate_limits.py)
  - TODO(VALIDATION): Add constitution compliance check to CI/CD pipeline
  - TODO(DOCS): Add architecture decision records (ADRs) for key patterns
  - TODO(DRY_ENFORCEMENT): Add CI/CD linting for duplicate code detection (e.g., pylint duplicate-code)
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

### IV. DRY Principle - Don't Repeat Yourself (CRITICAL)

**Code duplication is forbidden. MUST search for existing implementations before creating new functions or classes.**

- **Before implementation**:
  - Search codebase for similar functionality using `grep`, `semantic_search`, or IDE search
  - Check existing services, utilities, mappers, helpers for reusable code
  - Review related modules in the same layer (e.g., other services, other mappers)
  - Document search results in PR description if creating new function

- **Reuse existing code when**:
  - Functionality already exists (use as-is)
  - Similar functionality exists with minor differences (refactor to accept parameters)
  - Partial functionality exists (extend existing function/class)

- **Create new code only when**:
  - No existing implementation found after thorough search
  - Existing implementation is in wrong layer (e.g., need domain function but only exists in infrastructure)
  - Existing implementation violates SOLID or onion architecture (don't reuse bad patterns)
  - Reusing would create inappropriate coupling between layers

- **Refactoring for reuse**:
  - Extract common logic to shared utilities (`interfaces/api/utils/`, `infrastructure/utils/`, `domain/utils/`)
  - Use strategy pattern or protocols for variations
  - Create base classes for shared behavior (respecting LSP)
  - Move duplicated validation to Pydantic models or domain validators

**Examples**:

```python
# ❌ DUPLICATION: Reimplementing existing time conversion
# File: interfaces/api/admin/rate_limits.py
def str_to_time(time_str: str) -> time:
    parts = time_str.split(':')
    return time(int(parts[0]), int(parts[1]))

# ✅ CORRECT: Reusing existing utility
# File: interfaces/api/mappers/rate_limit_mapper.py (already exists)
from ..mappers.rate_limit_mapper import str_to_time

# ❌ DUPLICATION: Copying user validation logic
# File: interfaces/api/endpoints/new_feature.py
def validate_username(username: str) -> bool:
    return len(username) >= 3 and username.isalnum()

# ✅ CORRECT: Using domain validator
# File: domain/models/user.py (add validator if missing)
class User(BaseModel):
    username: str = Field(..., min_length=3, pattern=r'^[a-zA-Z0-9]+$')

# ❌ DUPLICATION: Multiple services doing same DB query
# File: application/services/group_service.py
def get_active_users(self):
    return self._user_repository.get_all_users().filter(is_active=True)

# ✅ CORRECT: Add method to repository
# File: domain/repositories/user_repository.py
class IUserRepository(Protocol):
    def get_active_users(self) -> List[User]: ...
```

**Exceptions where duplication is acceptable**:
- Test fixtures (duplicating setup across test files is OK for isolation)
- Layer-specific DTOs/models (API models vs domain models are intentionally separate)
- Mappers for different layers (API mapper ≠ ORM mapper, even if similar structure)

**Detection and prevention**:
- Use `grep_search` or `semantic_search` tools before coding
- IDE "Find Usages" to discover existing implementations
- Code review checklist: "Did you search for existing implementation?"
- CI/CD linting for common duplication patterns (e.g., duplicate string literals, copy-pasted functions)

**Rationale**: DRY prevents bugs (fix once, not in N places), reduces maintenance burden, improves code clarity, and enforces single source of truth. Duplication violates SRP (logic exists in multiple places) and increases cognitive load. Searching first respects existing architecture and prevents accidental reimplementation of solved problems.

### V. Performance & Observability

### VI. Performance & Observability

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

### VII. Management Client Parity (NON-NEGOTIABLE)

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

**Management endpoints requiring client support**:

- User management: `/admin/users/*` → `client.commands.users.*` (list, create, get, update, deactivate, api-keys)
- Group management: `/admin/groups/*` → `client.commands.groups.*` (list, create, get, update, delete)
- Model management: `/admin/models/*` → `client.commands.models.*` (list, create, get, update, delete, groups association)
- Rate limits: `/admin/rate-limits/*` → **TODO**: Client implementation pending

**Rationale**: Management operations require programmatic access for automation, CI/CD pipelines, and infrastructure-as-code workflows. A well-maintained client SDK reduces integration friction, enforces consistent error handling, and provides type safety for API consumers. The client serves as executable documentation and enables testing management workflows without manual API calls.

### VIII. SOLID Principles Adherence

**All code MUST follow SOLID principles to ensure maintainability, extensibility, and testability.**

- **Single Responsibility Principle (SRP)**:
  - Each class/module has ONE reason to change
  - Services handle ONE business domain (e.g., `UserService` for users only, not users + groups)
  - Mappers separate API vs ORM concerns (e.g., `RateLimitApiMapper` ≠ `RateLimitMapper`)
  - Endpoints delegate to services (no business logic in controllers)

- **Open/Closed Principle (OCP)**:
  - Open for extension (add new LLM providers without modifying existing code)
  - Closed for modification (use protocols/interfaces, not concrete classes)
  - Example: `LLMClientProtocol` allows adding `AnthropicClient` without changing `ChatCompletionService`

- **Liskov Substitution Principle (LSP)**:
  - Implementations MUST be substitutable for their protocols/interfaces
  - All `LLMClientProtocol` implementations MUST handle streaming, retries identically
  - Repository implementations MUST honor base repository contracts

- **Interface Segregation Principle (ISP)**:
  - Clients MUST NOT depend on interfaces they don't use
  - Use specific protocols (e.g., `IUserRepository`, `IGroupRepository`) instead of generic `IRepository`
  - Domain protocols define minimal required methods only

- **Dependency Inversion Principle (DIP)**:
  - High-level modules (services) depend on abstractions (protocols), not concrete implementations
  - Infrastructure (repositories, LLM clients) implements domain protocols
  - Dependency injection used throughout (FastAPI `Depends()`, constructor injection in services)
  - Example: `UserService` depends on `IUserRepository` protocol, not `SQLUserRepository`

**Examples**:

```python
# ✅ SOLID: Service depends on protocol (DIP), single responsibility (SRP)
class UserService:
    def __init__(self, uow: UnitOfWork, user_repository: IUserRepository):
        self._uow = uow
        self._repository = user_repository

    def create_user(self, user: User) -> User:  # Single responsibility
        # Business logic only, no DB/HTTP concerns
        ...

# ✅ SOLID: Protocol allows substitution (LSP, OCP)
class LLMClientProtocol(Protocol):
    def create_completion(self, request: ChatCompletionRequest) -> ChatCompletion:
        ...

# ✅ SOLID: Specific interface (ISP)
class IUserRepository(Protocol):
    def get_by_id(self, user_id: str) -> Optional[User]: ...
    def add(self, user: User) -> User: ...
    # Only user-specific methods, not generic CRUD

# ❌ VIOLATION: Service doing multiple things (SRP)
class UserAndGroupService:  # ❌ Two responsibilities
    def create_user(...): ...
    def create_group(...): ...

# ❌ VIOLATION: Concrete dependency (DIP)
class UserService:
    def __init__(self, repo: SQLUserRepository):  # ❌ Depends on concrete class
        ...
```

**Rationale**: SOLID principles create maintainable, testable code that adapts to change. SRP ensures focused classes that are easy to understand and test. OCP enables adding features without breaking existing code. LSP ensures reliable polymorphism. ISP prevents bloated interfaces. DIP decouples business logic from implementation details, enabling layer independence and comprehensive mocking in tests.

## Architecture Standards

### Interface Layer Responsibilities

**The interface layer MUST enforce strict separation of concerns: endpoints are limited to service invocation and object mapping only.**

- **Forbidden in endpoints**: Business logic, validation logic, authentication logic, error handling logic, database operations, external API calls
- **Allowed in endpoints**:
  - Invoking service layer methods
  - Mapping between API DTOs and domain models
  - HTTP-specific concerns (status codes, headers, streaming responses)
- **Business logic**: MUST be implemented in `application/services/` layer
- **Authentication**: MUST use dependency injection (`Depends(require_admin_role)`, `Depends(auth_jwt_or_api_key)`)
- **Error handling**: MUST use centralized exception handlers in `interfaces/api/exception_handlers.py`
- **Validation**: MUST use Pydantic models with domain validation rules
- **Cross-cutting concerns**: Logging, metrics, auditing MUST be handled by middleware or decorators, NOT in endpoint code

**Example of correct endpoint implementation**:
```python
@router.post("/admin/users")
async def create_user(
    request: CreateUserRequest,  # Pydantic validation
    user: AuthenticatedUser = Depends(require_admin_role)  # Auth dependency
) -> UserResponse:
    """Create a new user (endpoint delegates to service)."""
    # Map API request to domain model
    domain_user = User(
        username=request.username,
        email=request.email,
        # ... mapping only
    )

    # Delegate all business logic to service
    created_user = await user_service.create_user(domain_user)

    # Map domain model back to API response
    return UserResponse.from_domain(created_user)
```

**Anti-pattern** (business logic in endpoint):
```python
@router.post("/admin/users")
async def create_user(request: CreateUserRequest):
    # ❌ WRONG: Manual auth check in endpoint
    if not is_admin(request.token):
        raise HTTPException(401)

    # ❌ WRONG: Validation logic in endpoint
    if len(request.username) < 3:
        raise HTTPException(400, "Username too short")

    # ❌ WRONG: Business logic in endpoint
    if user_repository.exists(request.username):
        raise HTTPException(409, "User exists")

    # ❌ WRONG: Direct database access in endpoint
    user_orm = UserORM(username=request.username)
    db.add(user_orm)
    db.commit()

    return {"id": user_orm.id}
```

**Rationale**: Thin endpoints ensure business logic remains testable in isolation, enable logic reuse across different interfaces (REST API, CLI, gRPC), and prevent HTTP concerns from leaking into business rules. Centralized error handling provides consistent API responses and simplifies debugging.

### Domain Model Separation

- **Domain models**: Pydantic models in `domain/models/` (e.g., `User`, `Group`, `LlmModel`, `ChatCompletionRequest`)
- **ORM models**: SQLAlchemy models in `infrastructure/db/models/` with `ORM` suffix (e.g., `UserORM`, `GroupORM`)
- **Mappers**: Explicit conversion functions in `infrastructure/db/mappers/` (e.g., `UserMapper.to_domain()`, `UserMapper.to_orm()`)
- Domain models MUST NOT import SQLAlchemy or reference ORM concerns

### Mapper Layer Separation (CRITICAL)

**Each architectural layer MUST have its own mappers with clear responsibilities. Mixing mapper concerns violates the onion architecture.**

- **API Mappers** (`interfaces/api/mappers/`):
  - **Responsibility**: Convert between Pydantic API models (requests/responses) and domain entities
  - **Example**: `RateLimitApiMapper.create_request_to_domain()`, `RateLimitApiMapper.domain_to_response()`
  - **Dependencies**: Interfaces → Domain (allowed)
  - **Location**: `interfaces/api/mappers/<entity>_mapper.py`
  - **Used by**: API endpoints only

- **ORM Mappers** (`infrastructure/db/mappers/`):
  - **Responsibility**: Convert between domain entities and SQLAlchemy ORM models
  - **Example**: `UserMapper.to_domain()`, `UserMapper.to_orm()`
  - **Dependencies**: Infrastructure → Domain (allowed)
  - **Location**: `infrastructure/db/mappers/<entity>_mapper.py`
  - **Used by**: Repositories only

- **Forbidden patterns**:
  - ❌ Infrastructure mappers importing API models (violates onion: Infrastructure → Interfaces)
  - ❌ API mappers handling ORM conversions (wrong layer responsibility)
  - ❌ Single mapper file mixing API and ORM conversions (breaks separation of concerns)

**Rationale**: Mapper separation ensures each layer only knows about layers below it in the onion architecture. API mappers handle HTTP concerns (JSON, validation), ORM mappers handle persistence concerns (DB types, relationships). Mixing these responsibilities creates tight coupling and prevents independent layer testing.

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

**Version**: 1.4.0 | **Ratified**: 2025-12-06 | **Last Amended**: 2025-12-10
