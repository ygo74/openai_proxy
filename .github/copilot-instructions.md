# 🔧 Instructions personnalisées pour GitHub Copilot Agent

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
