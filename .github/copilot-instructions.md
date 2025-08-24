# 🔧 GitHub Copilot Instructions for FastAPI OpenAI Proxy

## 🎯 Project Overview

FastAPI-based LLM proxy supporting OpenAI-compatible APIs for multiple providers (OpenAI, Azure OpenAI, Anthropic) with enterprise features:
- **OpenAI-compatible API** (`/v1/chat/completions`, `/v1/completions`, `/v1/models`)
- **Dual authentication**: OAuth2/Keycloak for management + API keys for chat endpoints
- **Model management**: Groups, authorization, status tracking via admin endpoints
- **Enterprise features**: Corporate proxy support, SSL config, retry logic, Azure AD integration
- **Langchain integration**: Drop-in replacement via `tools/langchain_call_proxy.py`

## 🧱 Onion Architecture

**Critical dependency rule**: Dependencies point inward only. Infrastructure never imported by domain.

- **`domain/`**: Pure business models (`Group`, `LlmModel`, `ChatCompletionRequest`) + protocols
- **`application/`**: Business logic services (`ChatCompletionService`, `ModelService`)
- **`infrastructure/`**: External concerns (DB via SQLAlchemy, LLM clients, HTTP)
- **`interfaces/`**: API endpoints, auth decorators, exception handlers

**Key files**:
- `domain/protocols/llm_client.py` - Protocol all LLM clients implement
- `infrastructure/llm/client_factory.py` - Creates provider-specific clients
- `interfaces/api/auth.py` - Dual auth system implementation

## 🔑 Authentication Pattern

Two distinct auth flows:

**Management endpoints** (`@require_oauth_role(["admin"])`):
```python
@app.get("/admin/models")
@require_oauth_role(required_roles=["admin"])
async def admin_endpoint(request: Request, user: dict = None):
```

**Chat endpoints** (`@require_apikey_or_bearer()`):
```python
@app.post("/v1/chat/completions")
@require_apikey_or_bearer()
async def chat_endpoint(request: Request, user: dict = None):
```

## 🤖 LLM Client Architecture

**Protocol-based design**: All LLM clients implement `LLMClientProtocol`
- `OpenAIProxyClient` - Generic OpenAI-compatible providers
- `AzureOpenAIProxyClient` - Azure-specific with API versioning
- Client factory creates appropriate client based on `LlmModel.provider`

**Smart routing**: Clients auto-convert completions↔chat completions based on model capabilities

## 🏗️ Development Workflows

**Start development**:
```powershell
docker compose -f .\docker-compose-backend.yml up -d  # Start Keycloak
poetry run uvicorn src.ygo74.fastapi_openai_rag.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

**Configuration**: Copy `config.json.example` → `config.json` with your model configurations

**Testing**:
```powershell
pytest tests/                              # All tests
pytest tests/domain/                        # Domain layer only
pytest --log-cli-level=DEBUG tests/        # With debug logging
```

## 🧩 Domain Models vs ORM

**Strict separation enforced**:
- **Domain models**: `domain/models/group.py` (Pydantic, no DB deps)
- **ORM models**: `infrastructure/db/models/group_orm.py` (SQLAlchemy)
- **Mappers**: `infrastructure/db/mappers/group_mapper.py` (Explicit conversion functions)

Example pattern:
```python
# Domain
class Group(BaseModel):
    name: str
    models: List['LlmModel'] = []

# ORM
class GroupORM(Base):
    name: Mapped[str] = mapped_column(String(100))
    models: Mapped[List["ModelORM"]] = relationship(...)

# Mapper
class GroupMapper:
    @staticmethod
    def to_domain(orm: GroupORM) -> Group: ...
```

## 🧪 Testing Strategy

**Layer-based test organization** matching onion architecture:
- `tests/domain/` - Pure unit tests, no external deps
- `tests/application/` - Service layer tests with mocked infrastructure
- `tests/infrastructure/` - Integration tests with mocked external APIs
- `tests/interfaces/` - API endpoint tests

**Naming**: `test_<module>_<function>_<case>()`
**Mock externals**: All HTTP calls, DB operations in unit tests
**Test structure**: Arrange-Act-Assert pattern

## 💼 Enterprise Features

**Corporate proxy support**: All HTTP clients use `HttpClientFactory` with proxy/SSL config
**Retry logic**: `@with_enterprise_retry` decorator on external calls
**Azure integration**: `AzureAuthClient` for management API access
**SSL flexibility**: Custom CA certs, client certificates, SSL verification controls

## 🔧 Code Style

- **English documentation** for all functions/classes
- **Full typing**: All function args, returns, variables
- **Class-based imports**: Prefer `MyClass.static_method()` over standalone functions
- **Pydantic models**: Use for validation, serialization in domain layer

## 🎯 Objectif global

Créer une API proxy FastAPI pour différents LLMs (OpenAI, Anthropic, etc.) avec :

- Transformation des requêtes OpenAI vers formats propriétaires.
- Authentification par utilisateur + autorisation par modèle.
- Logging du nombre de tokens in/out, latence, utilisateur.
- Rate limiting configurable.
- Intégration de NVIDIA Guardrails.
- Architecture Onion.
- Base de données PostgreSQL avec ORM SQLAlchemy.
- Séparation stricte des modèles : domaine vs base de données.

## 🧱 Architecture onion

Respect strict des couches logiques :

- **domain/** : modèles métiers purs, sans dépendance externe.
- **application/** : logique métier (use cases), services, orchestrations.
- **infrastructure/** : accès DB (SQLAlchemy), API externes, fichiers, cache.
- **interfaces/** : exposer via HTTP (FastAPI), CLI, etc.

Les dépendances ne peuvent pointer que vers l’intérieur :

- `infrastructure` dépend de `domain`, jamais l’inverse.

## 🧩 Organisation des modèles

- Les **modèles de domaine** (dans `domain/models.py`) sont indépendants de l’ORM. Exemples : `User`, `TokenLog`, `RequestMetadata`.
- Les **modèles ORM SQLAlchemy** (dans `infrastructure/db/models.py`) sont mappés à la DB (`UserORM`, etc.).
- Créer des **fonctions de mapping explicites** entre les deux.

## Development stylye

- always add function documentation in english
- always use typed variables, function arguments and function result
- always use class against function to import. Use static function when the class doesn't required to be instantiated

## 🧪 Tests unitaires et mocks

- Chaque fonction ou méthode doit être accompagnée d’un test unitaire `pytest`.
- Tous les appels vers des ressources externes (LLM API, Redis, DB) doivent être mockés.
- Le nom des tests suit le format : `test_<fichier>_<fonction>_<cas>()`.
- Les tests doivent être regroupés en fonction de l'architecture en onnion afin de pouvoir tester séparemment la partie infrastructure, core ou api
- Exemple :

  ```python
  def test_auth_validate_user_valid_key():
      # arrange
      # act
      # assert

## project structure

Project root is the namespace of the fastapi proxy inside the src folder

project-root/
├── src/
│   └── ygo74/
│       └── fastapi_openai_rag/
│           ├── __init__.py
│           ├── domain/
│           │   └── [model_name].py
│           ├── application/
│           │   └── [model_name or scope_name]_service.py
│           ├── infrastructure/
│           │   ├── db/
│           │   │   ├── models
│           │   │   │   ├── base.py
│           │   │   │   ├── [model_name]_orm.py
│           │   │   ├── mappers
│           │   │   │   ├── [model_name]_mapper.py
│           │   │   ├── repositories
│           │   │   │   ├── [model_name]_repository.py
│           │   │   │── session.py
│           │   └── llm/
│           │       └── openai_client.py
│           ├── interfaces/
│           │   └── api/
│           │   │   └── [endpoint_name].py
│           │   │── v1.py
│           └── config/
│               └── settings.py
├── tests/
│   ├── application/
│   ├── domain/
│   ├── infrastructure/
│   └── interfaces/
├── .github/
│   └── copilot-instructions.md
├── pyproject.toml
├── README.md
└── .env
