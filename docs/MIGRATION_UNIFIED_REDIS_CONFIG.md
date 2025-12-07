# Migration: Configuration Redis Unifiée

## Vue d'ensemble

Cette migration unifie la configuration Redis pour tous les composants du système de rate limiting (counter et cache) en utilisant `RedisCacheConfig` depuis `AppConfig`.

## Changements

### Avant

**Configuration divisée** :
- `RateLimitCounter` : paramètres hard-codés dans l'initialisation
- Cache : configuration via `settings.py` (variables d'environnement)
- Deux sources de configuration différentes

```python
# Old RateLimitCounter
counter = RateLimitCounter(
    host="localhost",
    port=6379,
    db=0,
    password=None
)

# Old cache via settings.py
from config.settings import Settings
settings = Settings()
cache = create_rate_limit_cache(settings.redis_cache)
```

### Après

**Configuration unifiée** :
- `RateLimitCounter` : accepte `RedisCacheConfig` depuis `AppConfig`
- Cache : utilise `RedisCacheConfig` depuis `AppConfig`
- Une seule source : `config.json` → `AppConfig`

```python
# New unified configuration
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_counter import RateLimitCounter
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory import get_rate_limit_cache

# Load config
app_config = AppConfig.load_from_json('config.json')

# Both use the same config
counter = RateLimitCounter(redis_config=app_config.redis_cache)
cache = get_rate_limit_cache(app_config.redis_cache)
```

## Modifications du Code

### 1. RateLimitCounter

**Fichier** : `src/ygo74/fastapi_openai_rag/infrastructure/cache/rate_limit_counter.py`

**Changements** :
```python
# Ancienne signature
def __init__(self,
             host: str = "localhost",
             port: int = 6379,
             db: int = 0,
             password: Optional[str] = None,
             ...):

# Nouvelle signature
def __init__(self,
             redis_config: Optional[RedisCacheConfig] = None,
             connection_timeout: float = 0.5,
             ...):
```

**Comportement** :
- Si `redis_config is None` ou `redis_config.enabled=False` → in-memory
- Si `redis_config.enabled=True` mais connexion échoue → fallback in-memory
- Si `redis_config.enabled=True` et connexion réussit → Redis

### 2. RateLimitService

**Fichier** : `src/ygo74/fastapi_openai_rag/application/services/rate_limit_service.py`

**Changements** :
```python
# Ancien __init__
def __init__(self, uow, counter=None, cache=None, config_service=None):
    self._counter = counter if counter is not None else RateLimitCounter()

    if cache is not None:
        self._cache = cache
    else:
        settings = Settings()
        self._cache = get_rate_limit_cache(settings.redis_cache)

# Nouveau __init__
def __init__(self, uow, counter=None, cache=None, config_service=None):
    self._config_service = config_service if config_service is not None else ConfigService()

    # Get Redis configuration from AppConfig
    app_config = self._config_service.get_config()

    # Initialize counter with configuration (only if not provided for testing)
    if counter is not None:
        self._counter = counter
    else:
        self._counter = RateLimitCounter(redis_config=app_config.redis_cache)

    # Initialize cache with configuration (only if not provided for testing)
    if cache is not None:
        self._cache = cache
    else:
        self._cache = get_rate_limit_cache(app_config.redis_cache)
```

### 3. Configuration

**Fichier** : `config.json`

**Ajout de la section `redis_cache`** :
```json
{
    "db_url": "...",
    "model_configs": [...],
    "forwarders": [...],
    "audit": {...},
    "rate_limits": {...},
    "redis_cache": {
        "enabled": false,
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": null,
        "max_cache_size": 64,
        "ttl_seconds": 30
    }
}
```

**Suppression de `RedisCacheSettings` dans `settings.py`** :
- La classe `RedisCacheSettings` a été retirée de `config/settings.py`
- Les variables d'environnement `REDIS_*` ne sont plus utilisées
- Toute la configuration Redis est maintenant dans `config.json`

## Tests

### Nouveaux Tests

**Fichier** : `tests/infrastructure/test_rate_limit_counter_config.py`

9 tests couvrant :
- ✅ Counter avec Redis désactivé
- ✅ Counter sans configuration
- ✅ Counter avec Redis activé mais indisponible (fallback)
- ✅ Counter avec Redis activé et disponible
- ✅ Incrémentation avec in-memory
- ✅ Récupération de count avec in-memory
- ✅ Count non-existant retourne 0
- ✅ Incrémentation de tokens avec in-memory
- ✅ Configuration depuis AppConfig.load_from_json()

### Tests Existants

**Fichier** : `tests/infrastructure/test_rate_limit_cache_factory.py`

12 tests mis à jour pour utiliser `RedisCacheConfig` depuis domain :
- ✅ Configuration par défaut
- ✅ Configuration personnalisée
- ✅ Création sans config (in-memory)
- ✅ Config désactivée (in-memory)
- ✅ Config activée (Redis)
- ✅ Fallback Redis → in-memory
- ✅ Conformité au protocole (in-memory)
- ✅ Opérations basiques (in-memory)
- ✅ Stats (in-memory)
- ✅ Conformité au protocole (Redis)
- ✅ Opérations basiques (Redis)
- ✅ Stats (Redis)

## Exemples

### Exemple Complet

**Fichier** : `examples/unified_redis_config_example.py`

Démontre :
1. Configuration in-memory (Redis désactivé)
2. Configuration Redis avec fallback automatique
3. Chargement depuis `config.json`
4. Intégration dans `RateLimitService`

**Exécution** :
```bash
python examples/unified_redis_config_example.py
```

## Documentation

### Mise à jour

**Fichier** : `docs/RATE_LIMIT_CACHE_ARCHITECTURE.md`

**Ajouts** :
- Section "Configuration Unifiée Redis"
- Bénéfices de l'approche unifiée
- Liste des composants utilisant `RedisCacheConfig`
- Mise à jour de la section "Utilisation dans RateLimitService"

## Migration pour Développeurs

### Si vous utilisez directement RateLimitCounter

**Avant** :
```python
counter = RateLimitCounter(
    host="localhost",
    port=6379,
    db=0
)
```

**Après** :
```python
from ygo74.fastapi_openai_rag.domain.models.configuration import RedisCacheConfig

config = RedisCacheConfig(
    enabled=True,
    host="localhost",
    port=6379,
    db=0
)
counter = RateLimitCounter(redis_config=config)
```

**Ou mieux, via AppConfig** :
```python
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig

app_config = AppConfig.load_from_json('config.json')
counter = RateLimitCounter(redis_config=app_config.redis_cache)
```

### Si vous utilisez RateLimitService

**Aucun changement requis** ! Le service charge automatiquement la configuration depuis `AppConfig`.

```python
# Fonctionne automatiquement
service = RateLimitService(uow=uow)
```

### Si vous avez des tests

**Avant** :
```python
counter = RateLimitCounter(host="localhost", port=6379)
```

**Après** :
```python
from ygo74.fastapi_openai_rag.domain.models.configuration import RedisCacheConfig

config = RedisCacheConfig(enabled=False)  # In-memory pour les tests
counter = RateLimitCounter(redis_config=config)
```

**Ou simplement** :
```python
counter = RateLimitCounter()  # Defaults to in-memory
```

## Avantages

### 1. Cohérence
- ✅ Même configuration pour counter et cache
- ✅ Un seul fichier de configuration (`config.json`)
- ✅ Pas de variables d'environnement à gérer

### 2. Simplicité
- ✅ Activer/désactiver Redis avec un seul flag
- ✅ Pas besoin de synchroniser plusieurs configurations
- ✅ Configuration centralisée dans domain layer

### 3. Robustesse
- ✅ Fallback automatique vers in-memory
- ✅ Même comportement pour counter et cache
- ✅ Tests exhaustifs couvrant tous les cas

### 4. Déploiement
- ✅ Développement : `"enabled": false` (in-memory)
- ✅ Production : `"enabled": true` (Redis)
- ✅ Pas de changement de code requis

## Checklist de Migration

- [x] Mise à jour de `RateLimitCounter.__init__()` pour accepter `redis_config`
- [x] Ajout de TYPE_CHECKING pour `RedisCacheConfig` dans counter
- [x] Mise à jour de `RateLimitService.__init__()` pour passer la config au counter
- [x] Suppression de `RedisCacheSettings` dans `settings.py`
- [x] Ajout de `redis_cache` dans `config.json`
- [x] Création de tests pour `RateLimitCounter` avec configuration
- [x] Mise à jour des tests existants pour utiliser domain `RedisCacheConfig`
- [x] Création de `examples/unified_redis_config_example.py`
- [x] Mise à jour de `docs/RATE_LIMIT_CACHE_ARCHITECTURE.md`
- [x] Création de `docs/MIGRATION_UNIFIED_REDIS_CONFIG.md` (ce document)

## Support

Pour toute question ou problème :
1. Consultez `docs/RATE_LIMIT_CACHE_ARCHITECTURE.md`
2. Exécutez `examples/unified_redis_config_example.py`
3. Vérifiez les tests dans `tests/infrastructure/test_rate_limit_counter_config.py`
