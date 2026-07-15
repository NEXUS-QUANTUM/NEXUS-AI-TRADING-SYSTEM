
# ai/prediction/prediction_cache.py
"""
NEXUS AI TRADING SYSTEM - Prediction Cache Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import json
import pickle
import hashlib
import time
import os
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import redis
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PredictionCacheConfig:
    """Configuration pour Prediction Cache"""
    cache_type: str = 'memory'  # 'memory', 'redis', 'disk'
    max_size: int = 1000
    ttl: int = 300  # secondes
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    cache_dir: str = './cache/predictions'
    cleanup_interval: int = 60  # secondes
    enable_compression: bool = True
    use_pickle: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cache_type': self.cache_type,
            'max_size': self.max_size,
            'ttl': self.ttl,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'redis_db': self.redis_db,
            'cache_dir': self.cache_dir,
            'cleanup_interval': self.cleanup_interval,
            'enable_compression': self.enable_compression,
            'use_pickle': self.use_pickle,
        }


@dataclass
class CacheEntry:
    """Entrée de cache"""
    key: str
    value: Any
    timestamp: datetime
    expires_at: datetime
    hits: int = 0
    size: int = 0

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'hits': self.hits,
            'size': self.size,
        }


class PredictionCache:
    """
    Cache de prédictions pour l'IA de trading.

    Features:
    - Multiple backends (memory, Redis, disk)
    - TTL support
    - LRU eviction
    - Compression
    - Thread-safe
    - Statistics

    Example:
        ```python
        config = PredictionCacheConfig(
            cache_type='redis',
            ttl=300,
            max_size=10000
        )
        cache = PredictionCache(config)

        # Store prediction
        cache.set('BTC-USD_2024-01-01', prediction)

        # Get prediction
        prediction = cache.get('BTC-USD_2024-01-01')
        ```
    """

    def __init__(self, config: Optional[PredictionCacheConfig] = None):
        self.config = config or PredictionCacheConfig()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'expired': 0,
            'evictions': 0,
        }
        self._lock = threading.RLock()
        self._redis_client = None
        self._cleanup_thread = None
        self._running = False

        # Initialisation
        self._init_backend()
        self._start_cleanup()

        logger.info(f"PredictionCache initialisé ({self.config.cache_type})")

    def _init_backend(self):
        """Initialise le backend de cache"""
        if self.config.cache_type == 'redis':
            self._init_redis()
        elif self.config.cache_type == 'disk':
            self._init_disk()
        # memory ne nécessite pas d'initialisation

    def _init_redis(self):
        """Initialise Redis"""
        try:
            self._redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False
            )
            self._redis_client.ping()
            logger.info("Connexion Redis établie")
        except Exception as e:
            logger.error(f"Erreur de connexion Redis: {e}")
            self._redis_client = None
            self.config.cache_type = 'memory'

    def _init_disk(self):
        """Initialise le cache disque"""
        os.makedirs(self.config.cache_dir, exist_ok=True)
        logger.info(f"Cache disque initialisé: {self.config.cache_dir}")

    def _start_cleanup(self):
        """Démarre le thread de nettoyage"""
        if not self._running:
            self._running = True
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True
            )
            self._cleanup_thread.start()

    def _cleanup_loop(self):
        """Boucle de nettoyage du cache"""
        while self._running:
            time.sleep(self.config.cleanup_interval)
            self.cleanup()

    def _generate_key(self, *args, **kwargs) -> str:
        """Génère une clé de cache unique"""
        key_data = f"{args}{kwargs}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _serialize(self, value: Any) -> bytes:
        """Sérialise une valeur"""
        if self.config.use_pickle:
            return pickle.dumps(value)
        else:
            return json.dumps(value).encode()

    def _deserialize(self, data: bytes) -> Any:
        """Désérialise une valeur"""
        if self.config.use_pickle:
            return pickle.loads(data)
        else:
            return json.loads(data.decode())

    def _compress(self, data: bytes) -> bytes:
        """Compresse des données"""
        if not self.config.enable_compression:
            return data

        try:
            import zlib
            return zlib.compress(data)
        except:
            return data

    def _decompress(self, data: bytes) -> bytes:
        """Décompresse des données"""
        if not self.config.enable_compression:
            return data

        try:
            import zlib
            return zlib.decompress(data)
        except:
            return data

    def _evict_lru(self):
        """Supprime l'entrée la moins récemment utilisée"""
        if len(self._cache) >= self.config.max_size:
            key, _ = self._cache.popitem(last=False)
            self._stats['evictions'] += 1
            logger.debug(f"Éviction LRU: {key}")

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de cache
            value: Valeur à stocker
            ttl: Durée de vie (secondes)

        Returns:
            bool: True si stocké
        """
        ttl = ttl or self.config.ttl
        timestamp = datetime.now()
        expires_at = timestamp + timedelta(seconds=ttl)

        with self._lock:
            entry = CacheEntry(
                key=key,
                value=value,
                timestamp=timestamp,
                expires_at=expires_at
            )

            # Backend spécifique
            if self.config.cache_type == 'redis' and self._redis_client:
                try:
                    serialized = self._serialize(value)
                    compressed = self._compress(serialized)
                    self._redis_client.setex(
                        key,
                        ttl,
                        compressed
                    )
                    self._stats['sets'] += 1
                    return True
                except Exception as e:
                    logger.error(f"Erreur Redis set: {e}")

            elif self.config.cache_type == 'disk':
                try:
                    filepath = os.path.join(self.config.cache_dir, key)
                    with open(filepath, 'wb') as f:
                        pickle.dump((value, expires_at), f)
                    self._stats['sets'] += 1
                    return True
                except Exception as e:
                    logger.error(f"Erreur disk set: {e}")

            # Memory
            if len(self._cache) >= self.config.max_size:
                self._evict_lru()

            self._cache[key] = entry
            self._stats['sets'] += 1

        return True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur du cache.

        Args:
            key: Clé de cache
            default: Valeur par défaut

        Returns:
            Any: Valeur stockée ou default
        """
        with self._lock:
            # Redis
            if self.config.cache_type == 'redis' and self._redis_client:
                try:
                    data = self._redis_client.get(key)
                    if data is not None:
                        decompressed = self._decompress(data)
                        value = self._deserialize(decompressed)
                        self._stats['hits'] += 1
                        return value
                except Exception as e:
                    logger.error(f"Erreur Redis get: {e}")

            # Disk
            if self.config.cache_type == 'disk':
                try:
                    filepath = os.path.join(self.config.cache_dir, key)
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            value, expires_at = pickle.load(f)
                            if datetime.now() <= expires_at:
                                self._stats['hits'] += 1
                                return value
                            else:
                                os.remove(filepath)
                                self._stats['expired'] += 1
                except Exception as e:
                    logger.error(f"Erreur disk get: {e}")

            # Memory
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.hits += 1
                    self._cache.move_to_end(key)
                    self._stats['hits'] += 1
                    return entry.value
                else:
                    del self._cache[key]
                    self._stats['expired'] += 1

            self._stats['misses'] += 1
            return default

    def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache.

        Args:
            key: Clé de cache

        Returns:
            bool: True si supprimé
        """
        with self._lock:
            # Redis
            if self.config.cache_type == 'redis' and self._redis_client:
                try:
                    self._redis_client.delete(key)
                except:
                    pass

            # Disk
            if self.config.cache_type == 'disk':
                try:
                    filepath = os.path.join(self.config.cache_dir, key)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except:
                    pass

            # Memory
            if key in self._cache:
                del self._cache[key]
                self._stats['deletes'] += 1
                return True

            return False

    def cleanup(self) -> int:
        """
        Nettoie les entrées expirées.

        Returns:
            int: Nombre d'entrées supprimées
        """
        removed = 0

        with self._lock:
            # Memory
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]
                removed += 1

            self._stats['expired'] += removed

        logger.debug(f"Nettoyage cache: {removed} entrées supprimées")
        return removed

    def clear(self) -> None:
        """Vide complètement le cache"""
        with self._lock:
            # Redis
            if self.config.cache_type == 'redis' and self._redis_client:
                try:
                    self._redis_client.flushdb()
                except:
                    pass

            # Disk
            if self.config.cache_type == 'disk':
                try:
                    import shutil
                    shutil.rmtree(self.config.cache_dir)
                    os.makedirs(self.config.cache_dir, exist_ok=True)
                except:
                    pass

            # Memory
            self._cache.clear()
            logger.info("Cache vidé")

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        stats = self._stats.copy()
        stats.update({
            'size': len(self._cache),
            'max_size': self.config.max_size,
            'cache_type': self.config.cache_type,
            'ttl': self.config.ttl,
            'hit_rate': (
                stats['hits'] / (stats['hits'] + stats['misses'])
                if (stats['hits'] + stats['misses']) > 0 else 0
            ),
        })
        return stats

    def get_keys(self) -> List[str]:
        """Retourne toutes les clés du cache"""
        with self._lock:
            if self.config.cache_type == 'redis' and self._redis_client:
                try:
                    return [k.decode() for k in self._redis_client.keys()]
                except:
                    pass

            if self.config.cache_type == 'disk':
                try:
                    return os.listdir(self.config.cache_dir)
                except:
                    pass

            return list(self._cache.keys())

    def close(self):
        """Ferme le cache"""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)

        if self._redis_client:
            try:
                self._redis_client.close()
            except:
                pass

        logger.info("Cache fermé")


class CachedPredictor:
    """
    Wrapper pour prédicteur avec cache intégré.
    """

    def __init__(
        self,
        predictor: Any,
        cache: Optional[PredictionCache] = None,
        cache_key_prefix: str = 'pred_',
        ttl: Optional[int] = None
    ):
        self.predictor = predictor
        self.cache = cache or PredictionCache()
        self.cache_key_prefix = cache_key_prefix
        self.ttl = ttl

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Génère une clé de cache pour la prédiction"""
        import hashlib
        import json

        key_data = f"{args}{json.dumps(kwargs, sort_keys=True)}"
        return f"{self.cache_key_prefix}{hashlib.md5(key_data.encode()).hexdigest()}"

    def predict(self, *args, **kwargs) -> Any:
        """
        Effectue une prédiction avec cache.

        Args:
            *args: Arguments pour le prédicteur
            **kwargs: Arguments pour le prédicteur

        Returns:
            Any: Résultat de la prédiction
        """
        cache_key = self._get_cache_key(*args, **kwargs)

        # Vérifier le cache
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Prédiction
        result = self.predictor(*args, **kwargs)

        # Mise en cache
        self.cache.set(cache_key, result, self.ttl)

        return result


def create_prediction_cache(
    cache_type: str = 'memory',
    max_size: int = 1000,
    ttl: int = 300,
    **kwargs
) -> PredictionCache:
    """
    Factory pour créer un cache de prédictions.

    Args:
        cache_type: Type de cache ('memory', 'redis', 'disk')
        max_size: Taille maximale
        ttl: Durée de vie (secondes)
        **kwargs: Arguments supplémentaires

    Returns:
        PredictionCache: Cache de prédictions
    """
    config = PredictionCacheConfig(
        cache_type=cache_type,
        max_size=max_size,
        ttl=ttl,
        **kwargs
    )
    return PredictionCache(config)


__all__ = [
    'PredictionCache',
    'PredictionCacheConfig',
    'CacheEntry',
    'CachedPredictor',
    'create_prediction_cache',
]
