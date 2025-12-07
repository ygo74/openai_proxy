# Rate Limit Cache Architecture

## Vue d'ensemble

Le système de cache pour les rate limits a été refactorisé pour offrir une architecture claire et modulaire basée sur des protocoles, avec un support flexible pour différentes implémentations (in-memory ou Redis).

## Architecture

### 1. Protocol : `IRateLimitCache`

**Fichier** : `src/ygo74/fastapi_openai_rag/domain/protocols/rate_limit_cache_protocol.py`

Définit l'interface que toutes les implémentations de cache doivent respecter :

```python
class IRateLimitCache(Protocol):
    def get(self, scope_type: str, scope_id: Optional[str]) -> Optional[Any]
    def set(self, scope_type: str, scope_id: Optional[str], value: Any) -> None
    def publish_change(self, operation: str, scope_type: str, scope_id: Optional[str]) -> None
    def clear(self) -> None
    def get_stats(self) -> Dict[str, Any]
    def start_listener(self) -> None
    def stop_listener(self) -> None
```

### 2. Implémentation In-Memory : `InMemoryRateLimitCache`

**Fichier** : `src/ygo74/fastapi_openai_rag/infrastructure/cache/in_memory_rate_limit_cache.py`

**Caractéristiques** :
- Cache LRU avec TTL configurable (défaut: 64 entrées, 30s)
- Thread-safe avec locks
- Pas de synchronisation cross-instance (mode single-instance)
- Léger et sans dépendances externes

**Utilisation** :
```python
cache = InMemoryRateLimitCache(max_cache_size=64, ttl_seconds=30)
cache.set("model", "1", config_data)
result = cache.get("model", "1")
```

### 3. Implémentation Redis : `RedisRateLimitCache`

**Fichier** : `src/ygo74/fastapi_openai_rag/infrastructure/cache/redis_rate_limit_cache.py`

**Caractéristiques** :
- Cache local LRU + Redis pub/sub pour invalidation
- Synchronisation cross-instance via pub/sub
- Garantie de propagation <5s des changements
- Thread-safe avec listener en background

**Utilisation** :
```python
cache = RedisRateLimitCache(
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    max_cache_size=64,
    ttl_seconds=30
)
cache.start_listener()  # Démarre le listener pub/sub
```

### 4. Factory : `create_rate_limit_cache()`

**Fichier** : `src/ygo74/fastapi_openai_rag/infrastructure/cache/rate_limit_cache_factory.py`

**Logique de décision** :
1. Si `redis_config` est `None` ou `enabled=False` → `InMemoryRateLimitCache`
2. Si `redis_config.enabled=True` → Tente de créer `RedisRateLimitCache`
3. Si connexion Redis échoue → **Fallback automatique vers `InMemoryRateLimitCache`**

**Exemple** :
```python
from ygo74.fastapi_openai_rag.infrastructure.cache.rate_limit_cache_factory import (
    RedisCacheConfig,
    create_rate_limit_cache
)

# Configuration Redis
redis_config = RedisCacheConfig(
    enabled=True,
    host="localhost",
    port=6379,
    db=0
)

# Création avec fallback automatique
cache = create_rate_limit_cache(redis_config)
cache.start_listener()
```

## Configuration

### Architecture Complètement Unifiée

Le système de rate limiting utilise une **architecture complètement unifiée** basée sur le protocole `IRateLimitCache`. Tous les composants partagent :
1. **Configuration centralisée** : `RedisCacheConfig` depuis `AppConfig`
2. **Protocole unifié** : `IRateLimitCache` pour le stockage in-memory
3. **Même implémentation cache** : Counter et configuration utilisent la même instance

#### Architecture des Composants

```
config.json → AppConfig.redis_cache
    ↓
get_rate_limit_cache(redis_config)
    ├─→ InMemoryRateLimitCache (implémente IRateLimitCache)
    └─→ RedisRateLimitCache (implémente IRateLimitCache)

RateLimitCounter(redis_config, fallback_cache)
    ├─→ Redis : INCR/INCRBY atomiques (distribué)
    └─→ Fallback : IRateLimitCache (in-memory)
```

#### Bénéfices de l'Architecture Unifiée

1. **Protocole Unique** : `IRateLimitCache` utilisé pour config ET comptage
2. **Pas de Duplication** : Counter utilise le cache existant (pas de code dupliqué)
3. **Configuration Centralisée** : Un seul `RedisCacheConfig` depuis `AppConfig`
4. **Fallback Cohérent** : Même implémentation in-memory pour tout
5. **Séparation Claire** :
   - Redis INCR/INCRBY : opérations atomiques distribuées (~0.5ms)
   - IRateLimitCache : fallback in-memory thread-safe

#### Composants et Responsabilités

- **IRateLimitCache** : Protocole pour stockage (config + comptage)
- **InMemoryRateLimitCache** : Implémentation LRU thread-safe
- **RedisRateLimitCache** : Implémentation Redis + pub/sub
- **RateLimitCounter** : Comptage atomique via Redis ou IRateLimitCache
- **RateLimitService** : Orchestre counter et cache avec la même config

### Fichier `config.json`

Ajoutez la section `redis_cache` à votre fichier de configuration :

```json
{
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

### Intégration dans `AppConfig`

La configuration est automatiquement chargée depuis `config.json` via `AppConfig` :

```python
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig

# Chargement depuis config.json
app_config = AppConfig.load_from_json('config.json')

# Accès à la configuration Redis
redis_config = app_config.redis_cache
print(f"Enabled: {redis_config.enabled}")
print(f"Host: {redis_config.host}")
print(f"Port: {redis_config.port}")
```

## Utilisation dans RateLimitService

Le service utilise la configuration unifiée pour initialiser **à la fois** le counter et le cache depuis `AppConfig` :

```python
class RateLimitService:
    def __init__(self, uow, counter=None, cache=None, config_service=None, ...):
        from ...infrastructure.cache.rate_limit_counter import RateLimitCounter
        from ...infrastructure.cache.rate_limit_cache_factory import get_rate_limit_cache

        self._uow = uow
        self._config_service = config_service or ConfigService()

        # Charger la configuration Redis depuis AppConfig
        app_config = self._config_service.get_config()

        # Initialiser le counter avec la configuration Redis
        if counter is not None:
            self._counter = counter  # Pour les tests
        else:
            self._counter = RateLimitCounter(redis_config=app_config.redis_cache)

        # Initialiser le cache avec la même configuration Redis
        if cache is not None:
            self._cache = cache  # Pour les tests
        else:
            # Production: charge config depuis AppConfig
            app_config = self._config_service.get_config()
            self._cache = get_rate_limit_cache(app_config.redis_cache)
```

## Scénarios de déploiement

### 1. Single-instance (In-Memory)

**Configuration** :
```json
{
    "redis_cache": {
        "enabled": false
    }
}
```

**Comportement** :
- Utilise `InMemoryRateLimitCache`
- Pas de synchronisation nécessaire
- Idéal pour dev/test

### 2. Multi-instance (Redis)

**Configuration** :
```json
{
    "redis_cache": {
        "enabled": true,
        "host": "redis.prod.example.com",
        "port": 6379,
        "db": 0,
        "password": "your-password"
    }
}
```

**Comportement** :
- Utilise `RedisRateLimitCache`
- Cache local + pub/sub pour invalidation
- Synchronisation <5s entre instances

### 3. Multi-instance avec fallback

**Configuration** :
```json
{
    "redis_cache": {
        "enabled": true,
        "host": "redis.prod.example.com",
        "port": 6379
    }
}
```

**Comportement** :
- Au démarrage : tente de se connecter à Redis
- Si Redis indisponible : fallback automatique vers `InMemoryRateLimitCache`
- Log d'avertissement + mode dégradé sans synchronisation

## Tests

### Test de la factory

```bash
pytest tests/infrastructure/test_rate_limit_cache_factory.py -v
```

**Couverture** :
- ✅ Configuration par défaut
- ✅ Configuration personnalisée
- ✅ Création in-memory
- ✅ Création Redis
- ✅ Fallback automatique
- ✅ Conformité au protocole
- ✅ Opérations de base (get/set/clear)
- ✅ Statistiques

### Mock pour tests unitaires

```python
from unittest.mock import Mock

# Mock simple
mock_cache = Mock()
mock_cache.get.return_value = None
mock_cache.set.return_value = None

service = RateLimitService(uow, cache=mock_cache)
```

## Avantages de la nouvelle architecture

1. **Séparation des préoccupations** : Protocol, implémentations, factory
2. **Testabilité** : Chaque composant peut être testé indépendamment
3. **Flexibilité** : Facile d'ajouter de nouvelles implémentations (Memcached, etc.)
4. **Résilience** : Fallback automatique en cas de panne Redis
5. **Configuration claire** : Tout dans `config.json` ou variables d'env
6. **Pas de code mort** : Chaque classe a une responsabilité unique

## Migration depuis l'ancien code

L'ancienne classe `RateLimitCache` a été remplacée par :
- `InMemoryRateLimitCache` : Pour le cache local
- `RedisRateLimitCache` : Pour Redis avec pub/sub
- `rate_limit_cache_factory.py` : Pour l'instanciation

**Code avant** :
```python
from infrastructure.cache.rate_limit_cache import get_rate_limit_cache

cache = get_rate_limit_cache()  # Toujours Redis avec fallback in-memory
```

**Code après** :
```python
from infrastructure.cache.rate_limit_cache_factory import get_rate_limit_cache
from domain.models.configuration import AppConfig

# Configuration depuis config.json
app_config = AppConfig.load_from_json('config.json')
cache = get_rate_limit_cache(app_config.redis_cache)
```

## Monitoring

### Vérifier le type de cache utilisé

```python
stats = cache.get_stats()
print(f"Implementation: {stats['implementation']}")  # 'in-memory' ou 'redis'

if stats['implementation'] == 'redis':
    print(f"Redis connected: {stats['redis_connected']}")
    print(f"Pub/sub active: {stats['pubsub_active']}")
```

### Logs au démarrage

```
INFO - InMemoryRateLimitCache initialized: max_size=64, ttl=30s
```

ou

```
INFO - RedisRateLimitCache initialized: host=localhost, port=6379, db=0, max_size=64, ttl=30s
INFO - Redis pub/sub listener started on channel: rate_limit_config_changes
```

ou (fallback)

```
WARNING - Failed to connect to Redis (host=localhost, port=6379): Connection refused
INFO - Falling back to in-memory cache
```
