# blockchain/nodes/node_cache.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Cache - Gestion du Cache des Nœuds

Ce module implémente un système complet de cache pour les nœuds blockchain,
supportant le caching des requêtes, des blocs, des transactions, et des
états pour optimiser les performances.

Fonctionnalités principales:
- Cache des requêtes RPC
- Cache des blocs et transactions
- Cache des états et balances
- Cache distribué (Redis)
- Politiques d'expiration
- Invalidation intelligente
- Compression des données
- Monitoring du cache
"""

import asyncio
import hashlib
import json
import logging
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, OrderedDict
from functools import lru_cache, wraps

import aiohttp
import redis.asyncio as redis
from redis.asyncio import Redis

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, CacheError
    )
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_node import BaseNode
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, CacheError
    )
    from ..core.metrics import MetricsCollector
    from ..core.retry import async_retry, RetryConfig
    from .base_node import BaseNode

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class CacheType(Enum):
    """Types de cache"""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class CacheStrategy(Enum):
    """Stratégies de cache"""
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    ADAPTIVE = "adaptive"


class CachePolicy(Enum):
    """Politiques de cache"""
    CACHE_ALL = "cache_all"
    CACHE_READS = "cache_reads"
    CACHE_WRITES = "cache_writes"
    CACHE_NONE = "cache_none"


@dataclass
class CacheConfig:
    """Configuration du cache"""
    cache_type: CacheType
    strategy: CacheStrategy
    max_size: int = 10000
    default_ttl: int = 300
    redis_url: Optional[str] = None
    redis_db: int = 0
    compression: bool = True
    policy: CachePolicy = CachePolicy.CACHE_READS
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "cache_type": self.cache_type.value,
            "strategy": self.strategy.value,
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "redis_url": self.redis_url,
            "redis_db": self.redis_db,
            "compression": self.compression,
            "policy": self.policy.value,
            "metadata": self.metadata,
        }


@dataclass
class CacheStats:
    """Statistiques du cache"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    memory_usage: int = 0
    hit_rate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "memory_usage": self.memory_usage,
            "hit_rate": self.hit_rate,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CacheEntry:
    """Entrée de cache"""
    key: str
    value: Any
    ttl: int
    created_at: datetime
    expires_at: datetime
    size: int
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "key": self.key,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "size": self.size,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }

    def is_expired(self) -> bool:
        """Vérifie si l'entrée est expirée"""
        return datetime.now() > self.expires_at


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeCache:
    """
    Gestionnaire de cache pour les nœuds blockchain
    """

    def __init__(
        self,
        config: CacheConfig,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialise le cache

        Args:
            config: Configuration du cache
            metrics_collector: Collecteur de métriques
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()

        # Cache mémoire
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._memory_access: Dict[str, int] = defaultdict(int)
        self._memory_lock = asyncio.Lock()

        # Cache Redis
        self._redis: Optional[Redis] = None
        self._redis_lock = asyncio.Lock()

        # Statistiques
        self._stats = CacheStats()

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Initialisation de Redis
        if config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            self._init_redis()

        logger.info(f"NodeCache initialisé avec {config.cache_type.value}")

    def _init_redis(self) -> None:
        """Initialise la connexion Redis"""
        try:
            if self.config.redis_url:
                self._redis = redis.from_url(
                    self.config.redis_url,
                    db=self.config.redis_db,
                    decode_responses=True,
                )
            else:
                self._redis = redis.Redis(
                    host="localhost",
                    port=6379,
                    db=self.config.redis_db,
                    decode_responses=True,
                )

            logger.info("Connexion Redis établie")

        except Exception as e:
            logger.error(f"Erreur de connexion Redis: {e}")
            self._redis = None
            raise CacheError(f"Erreur de connexion Redis: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur du cache

        Args:
            key: Clé de la valeur

        Returns:
            Valeur ou None
        """
        if self.config.policy == CachePolicy.CACHE_NONE:
            return None

        value = None

        # Récupération depuis Redis
        if self.config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            value = await self._get_redis(key)

        # Récupération depuis la mémoire
        if value is None and self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            value = await self._get_memory(key)

        if value is not None:
            self._stats.hits += 1
            self._update_metrics(True)
        else:
            self._stats.misses += 1
            self._update_metrics(False)

        return value

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Définit une valeur dans le cache

        Args:
            key: Clé de la valeur
            value: Valeur à stocker
            ttl: Durée de vie en secondes

        Returns:
            True si stocké avec succès
        """
        if self.config.policy == CachePolicy.CACHE_NONE:
            return False

        ttl = ttl or self.config.default_ttl

        # Compression si configurée
        if self.config.compression:
            value = await self._compress(value)

        # Stockage dans Redis
        if self.config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            await self._set_redis(key, value, ttl)

        # Stockage dans la mémoire
        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            await self._set_memory(key, value, ttl)

        self._stats.size += 1
        self._update_metrics()

        return True

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def delete(self, key: str) -> bool:
        """
        Supprime une valeur du cache

        Args:
            key: Clé à supprimer

        Returns:
            True si supprimé avec succès
        """
        if self.config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            await self._delete_redis(key)

        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            await self._delete_memory(key)

        self._stats.size = max(0, self._stats.size - 1)
        return True

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def clear(self) -> bool:
        """
        Vide le cache

        Returns:
            True si vidé avec succès
        """
        if self.config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            await self._clear_redis()

        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            await self._clear_memory()

        self._stats.size = 0
        return True

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def exists(self, key: str) -> bool:
        """
        Vérifie si une clé existe dans le cache

        Args:
            key: Clé à vérifier

        Returns:
            True si la clé existe
        """
        if self.config.cache_type in [CacheType.REDIS, CacheType.HYBRID]:
            exists = await self._redis.exists(key)
            if exists:
                return True

        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            return key in self._memory_cache

        return False

    @async_retry(max_attempts=3, initial_delay=0.1)
    async def get_stats(self) -> CacheStats:
        """
        Obtient les statistiques du cache

        Returns:
            Statistiques du cache
        """
        # Mise à jour du taux de hits
        total = self._stats.hits + self._stats.misses
        self._stats.hit_rate = self._stats.hits / max(1, total)

        # Mise à jour de l'utilisation mémoire
        if self.config.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
            self._stats.memory_usage = sum(
                entry.size for entry in self._memory_cache.values()
            )

        return self._stats

    # ============================================================
    # MÉTHODES DE CACHE MÉMOIRE
    # ============================================================

    async def _get_memory(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache mémoire"""
        async with self._memory_lock:
            entry = self._memory_cache.get(key)

            if not entry:
                return None

            if entry.is_expired():
                del self._memory_cache[key]
                return None

            entry.access_count += 1
            self._memory_access[key] += 1

            return entry.value

    async def _set_memory(self, key: str, value: Any, ttl: int) -> None:
        """Définit une valeur dans le cache mémoire"""
        async with self._memory_lock:
            # Vérification de la taille
            if len(self._memory_cache) >= self.config.max_size:
                await self._evict_memory()

            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=ttl),
                size=len(str(value)),
            )

            self._memory_cache[key] = entry

    async def _delete_memory(self, key: str) -> None:
        """Supprime une valeur du cache mémoire"""
        async with self._memory_lock:
            self._memory_cache.pop(key, None)
            self._memory_access.pop(key, None)

    async def _clear_memory(self) -> None:
        """Vide le cache mémoire"""
        async with self._memory_lock:
            self._memory_cache.clear()
            self._memory_access.clear()

    async def _evict_memory(self) -> None:
        """Éviction du cache mémoire"""
        if self.config.strategy == CacheStrategy.LRU:
            # Éviction LRU
            if self._memory_cache:
                oldest_key = min(
                    self._memory_cache.items(),
                    key=lambda x: x[1].access_count
                )[0]
                del self._memory_cache[oldest_key]
                self._stats.evictions += 1

        elif self.config.strategy == CacheStrategy.LFU:
            # Éviction LFU
            if self._memory_access:
                least_used = min(self._memory_access.items(), key=lambda x: x[1])[0]
                self._memory_cache.pop(least_used, None)
                self._memory_access.pop(least_used, None)
                self._stats.evictions += 1

        else:
            # Éviction FIFO
            if self._memory_cache:
                oldest_key = next(iter(self._memory_cache))
                del self._memory_cache[oldest_key]
                self._stats.evictions += 1

    # ============================================================
    # MÉTHODES DE CACHE REDIS
    # ============================================================

    async def _get_redis(self, key: str) -> Optional[Any]:
        """Récupère une valeur de Redis"""
        if not self._redis:
            return None

        try:
            value = await self._redis.get(key)

            if value is None:
                return None

            # Décompression
            if self.config.compression:
                value = await self._decompress(value)

            return value

        except Exception as e:
            logger.warning(f"Erreur de récupération Redis: {e}")
            return None

    async def _set_redis(self, key: str, value: Any, ttl: int) -> None:
        """Définit une valeur dans Redis"""
        if not self._redis:
            return

        try:
            # Compression
            if self.config.compression:
                value = await self._compress(value)

            await self._redis.setex(key, ttl, value)

        except Exception as e:
            logger.warning(f"Erreur de stockage Redis: {e}")

    async def _delete_redis(self, key: str) -> None:
        """Supprime une valeur de Redis"""
        if not self._redis:
            return

        try:
            await self._redis.delete(key)

        except Exception as e:
            logger.warning(f"Erreur de suppression Redis: {e}")

    async def _clear_redis(self) -> None:
        """Vide le cache Redis"""
        if not self._redis:
            return

        try:
            await self._redis.flushdb()

        except Exception as e:
            logger.warning(f"Erreur de vidage Redis: {e}")

    # ============================================================
    # MÉTHODES DE COMPRESSION
    # ============================================================

    async def _compress(self, data: Any) -> str:
        """Compresse des données"""
        try:
            json_data = json.dumps(data)
            compressed = zlib.compress(json_data.encode())
            return compressed.hex()
        except Exception as e:
            logger.warning(f"Erreur de compression: {e}")
            return str(data)

    async def _decompress(self, data: str) -> Any:
        """Décompresse des données"""
        try:
            compressed = bytes.fromhex(data)
            decompressed = zlib.decompress(compressed)
            return json.loads(decompressed.decode())
        except Exception as e:
            logger.warning(f"Erreur de décompression: {e}")
            return data

    # ============================================================
    # MÉTHODES DE MÉTRIQUES
    # ============================================================

    def _update_metrics(self, hit: Optional[bool] = None) -> None:
        """Met à jour les métriques"""
        # Taille du cache
        self.metrics.record_gauge(
            "node_cache_size",
            self._stats.size,
            {"type": self.config.cache_type.value},
        )

        # Taux de hits
        total = self._stats.hits + self._stats.misses
        hit_rate = self._stats.hits / max(1, total)
        self.metrics.record_gauge(
            "node_cache_hit_rate",
            hit_rate,
            {"type": self.config.cache_type.value},
        )

        # Hits/Misses
        if hit is True:
            self.metrics.record_increment(
                "node_cache_hit",
                1,
                {"type": self.config.cache_type.value},
            )
        elif hit is False:
            self.metrics.record_increment(
                "node_cache_miss",
                1,
                {"type": self.config.cache_type.value},
            )

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeCache...")

        self._memory_cache.clear()
        self._memory_access.clear()

        if self._redis:
            await self._redis.close()
            self._redis = None

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# DÉCORATEURS DE CACHE
# ============================================================

def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Décorateur pour mettre en cache les résultats

    Args:
        ttl: Durée de vie en secondes
        key_prefix: Préfixe pour la clé
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Génération de la clé
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            key = hashlib.sha256(":".join(key_parts).encode()).hexdigest()

            # Récupération du cache
            if hasattr(self, '_cache'):
                cached_value = await self._cache.get(key)
                if cached_value is not None:
                    return cached_value

            # Exécution
            result = await func(self, *args, **kwargs)

            # Stockage dans le cache
            if hasattr(self, '_cache'):
                await self._cache.set(key, result, ttl)

            return result

        return wrapper
    return decorator


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_cache(
    config: Dict[str, Any],
    **kwargs,
) -> NodeCache:
    """
    Crée une instance de NodeCache

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeCache
    """
    cache_config = CacheConfig(**config)
    return NodeCache(
        config=cache_config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeCache"""
    # Configuration
    config = {
        "cache_type": "hybrid",
        "strategy": "lru",
        "max_size": 1000,
        "default_ttl": 300,
        "redis_url": "redis://localhost:6379",
        "compression": True,
        "policy": "cache_reads",
    }

    # Création du cache
    cache = create_node_cache(config=config)

    # Stockage
    await cache.set("key1", {"data": "value1"}, ttl=60)
    await cache.set("key2", [1, 2, 3, 4, 5], ttl=120)

    # Récupération
    value1 = await cache.get("key1")
    value2 = await cache.get("key2")
    value3 = await cache.get("key3")  # Non existant

    print(f"Valeur 1: {value1}")
    print(f"Valeur 2: {value2}")
    print(f"Valeur 3: {value3}")

    # Vérification d'existence
    exists = await cache.exists("key1")
    print(f"key1 existe: {exists}")

    # Statistiques
    stats = await cache.get_stats()
    print(f"Statistiques: {stats.to_dict()}")

    # Suppression
    await cache.delete("key1")

    # Nettoyage
    await cache.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
