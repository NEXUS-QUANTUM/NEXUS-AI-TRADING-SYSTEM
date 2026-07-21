"""
NEXUS AI TRADING SYSTEM - Hedge Bot Cache Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de cache pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import time
import json
import hashlib
import pickle
import zlib
import functools
import logging
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    Tuple,
    Generic,
    Iterator,
    Coroutine,
    Awaitable
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
from enum import Enum
import threading
import redis
from pathlib import Path
import os
import weakref
import gc

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# CACHE STRATEGIES
# ============================================================

class CacheStrategy(Enum):
    """Stratégies d'éviction de cache"""
    LRU = "lru"          # Least Recently Used
    LFU = "lfu"          # Least Frequently Used
    FIFO = "fifo"        # First In First Out
    TTL = "ttl"          # Time To Live
    RANDOM = "random"    # Random eviction
    ARC = "arc"          # Adaptive Replacement Cache
    LIRS = "lirs"        # Low Inter-reference Recency Set

@dataclass
class CacheConfig:
    """Configuration de cache"""
    max_size: int = 1000
    default_ttl: int = 300  # seconds
    strategy: CacheStrategy = CacheStrategy.LRU
    namespace: str = "nexus_cache"
    compress: bool = False
    compression_level: int = 6
    serializer: str = "pickle"  # pickle | json
    enable_stats: bool = True
    enable_persistence: bool = False
    persist_path: Optional[str] = None
    persist_interval: int = 60  # seconds


@dataclass
class CacheStats:
    """Statistiques de cache"""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 1000
    evictions: int = 0
    total_entries: int = 0
    hit_rate: float = 0.0
    memory_usage: int = 0  # bytes
    avg_latency: float = 0.0
    total_latency: float = 0.0


# ============================================================
# CACHE ENTRY
# ============================================================

@dataclass
class CacheEntry(Generic[T]):
    """Entrée de cache"""
    key: str
    value: T
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    last_access: float = field(default_factory=time.time)
    access_count: int = 0
    size: int = 0
    compressed: bool = False
    hash: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Vérifie si l'entrée est expirée"""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at
    
    @property
    def age(self) -> float:
        """Âge de l'entrée en secondes"""
        return time.time() - self.created_at
    
    def touch(self):
        """Met à jour le dernier accès"""
        self.last_access = time.time()
        self.access_count += 1


# ============================================================
# BASE CACHE
# ============================================================

class BaseCache(Generic[T]):
    """
    Cache de base avec stratégies d'éviction
    
    Implémente un cache en mémoire avec différentes stratégies d'éviction
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialise le cache
        
        Args:
            config: Configuration de cache
        """
        self.config = config or CacheConfig()
        self._cache: Dict[str, CacheEntry[T]] = OrderedDict()
        self._stats = CacheStats(max_size=self.config.max_size)
        self._lock = threading.RLock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Pour les stratégies avancées
        self._frequency: Dict[str, int] = {}
        self._recency: Dict[str, float] = {}
        self._arc_trust = 0.0
        
        # Persistance
        if self.config.enable_persistence and self.config.persist_path:
            self._load_persistent()
            self._start_persist_task()
        
        logger.info(f"Cache initialized with strategy: {self.config.strategy.value}")
    
    # ============================================================
    # CRUD OPERATIONS
    # ============================================================
    
    def get(self, key: str, default: Any = None) -> Optional[T]:
        """
        Récupère une valeur du cache
        
        Args:
            key: Clé de l'entrée
            default: Valeur par défaut si la clé n'existe pas
            
        Returns:
            Optional[T]: Valeur ou default
        """
        start_time = time.perf_counter()
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                self._update_latency(start_time)
                return default
            
            if entry.is_expired:
                self._delete_entry(key)
                self._stats.misses += 1
                self._update_latency(start_time)
                return default
            
            # Décompresser si nécessaire
            if entry.compressed:
                entry.value = self._decompress(entry.value)
                entry.compressed = False
            
            entry.touch()
            self._stats.hits += 1
            
            # Mettre à jour les statistiques pour les stratégies
            if self.config.strategy == CacheStrategy.LFU:
                self._frequency[key] = self._frequency.get(key, 0) + 1
            
            if self.config.strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)
            
            if self.config.strategy == CacheStrategy.ARC:
                self._update_arc(key)
            
            self._update_latency(start_time)
            return entry.value
    
    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        compress: Optional[bool] = None
    ):
        """
        Ajoute ou met à jour une valeur dans le cache
        
        Args:
            key: Clé de l'entrée
            value: Valeur à stocker
            ttl: TTL en secondes (override config)
            compress: Compresser la valeur (override config)
        """
        start_time = time.perf_counter()
        
        with self._lock:
            # Vérifier la taille
            size = self._estimate_size(key, value)
            
            # Supprimer l'ancienne entrée si elle existe
            if key in self._cache:
                self._delete_entry(key)
            
            # Vérifier si le cache est plein
            if len(self._cache) >= self.config.max_size:
                self._evict()
            
            # Créer la nouvelle entrée
            expires_at = None
            if ttl is None:
                ttl = self.config.default_ttl
            
            if ttl > 0:
                expires_at = time.time() + ttl
            
            # Compresser si nécessaire
            should_compress = compress or self.config.compress
            if should_compress:
                value = self._compress(value)
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size=size,
                compressed=should_compress
            )
            
            self._cache[key] = entry
            
            # Mettre à jour les statistiques
            self._stats.total_entries += 1
            self._stats.size = len(self._cache)
            self._stats.memory_usage += size
            
            # Initialiser les métriques pour les stratégies
            if self.config.strategy == CacheStrategy.LFU:
                self._frequency[key] = 1
            
            if self.config.strategy == CacheStrategy.ARC:
                self._recency[key] = time.time()
            
            self._update_latency(start_time)
    
    def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache
        
        Args:
            key: Clé de l'entrée
            
        Returns:
            bool: True si supprimée, False sinon
        """
        with self._lock:
            return self._delete_entry(key)
    
    def clear(self):
        """Vide le cache"""
        with self._lock:
            self._cache.clear()
            self._frequency.clear()
            self._recency.clear()
            self._stats.size = 0
            self._stats.total_entries = 0
            self._stats.evictions += len(self._cache)
            self._stats.memory_usage = 0
    
    def _delete_entry(self, key: str) -> bool:
        """
        Supprime une entrée du cache (interne)
        
        Args:
            key: Clé de l'entrée
            
        Returns:
            bool: True si supprimée, False sinon
        """
        if key in self._cache:
            entry = self._cache[key]
            self._stats.memory_usage -= entry.size
            del self._cache[key]
            if key in self._frequency:
                del self._frequency[key]
            if key in self._recency:
                del self._recency[key]
            self._stats.size = len(self._cache)
            return True
        return False
    
    def _evict(self):
        """Évince une entrée selon la stratégie"""
        if len(self._cache) < self.config.max_size:
            return
        
        key_to_evict = self._select_eviction_candidate()
        
        if key_to_evict:
            self._delete_entry(key_to_evict)
            self._stats.evictions += 1
    
    def _select_eviction_candidate(self) -> Optional[str]:
        """
        Sélectionne un candidat à l'éviction selon la stratégie
        
        Returns:
            Optional[str]: Clé à évincer
        """
        if not self._cache:
            return None
        
        if self.config.strategy == CacheStrategy.LRU:
            # Évincer la plus anciennement utilisée
            return next(iter(self._cache))
        
        elif self.config.strategy == CacheStrategy.LFU:
            # Évincer la moins fréquemment utilisée
            if self._frequency:
                return min(self._frequency, key=self._frequency.get)
        
        elif self.config.strategy == CacheStrategy.FIFO:
            # Évincer la plus ancienne
            oldest = min(self._cache.items(), key=lambda x: x[1].created_at)
            return oldest[0]
        
        elif self.config.strategy == CacheStrategy.RANDOM:
            # Évincer une entrée aléatoire
            import random
            return random.choice(list(self._cache.keys()))
        
        elif self.config.strategy == CacheStrategy.TTL:
            # Évincer la plus proche de l'expiration
            if any(entry.expires_at is not None for entry in self._cache.values()):
                candidates = [
                    (key, entry.expires_at or float('inf'))
                    for key, entry in self._cache.items()
                ]
                return min(candidates, key=lambda x: x[1])[0]
        
        elif self.config.strategy == CacheStrategy.ARC:
            # ARC adaptatif
            return self._select_arc_candidate()
        
        elif self.config.strategy == CacheStrategy.LIRS:
            return self._select_lirs_candidate()
        
        # Default: LRU
        return next(iter(self._cache))
    
    def _select_arc_candidate(self) -> Optional[str]:
        """Sélectionne un candidat pour ARC"""
        if len(self._cache) < 2:
            return next(iter(self._cache))
        
        # Simuler ARC - simplifié
        return next(iter(self._cache))
    
    def _select_lirs_candidate(self) -> Optional[str]:
        """Sélectionne un candidat pour LIRS"""
        if len(self._cache) < 2:
            return next(iter(self._cache))
        
        # Simuler LIRS - simplifié
        return next(iter(self._cache))
    
    def _update_arc(self, key: str):
        """Met à jour ARC"""
        self._recency[key] = time.time()
    
    def _estimate_size(self, key: str, value: Any) -> int:
        """
        Estime la taille d'une entrée en bytes
        
        Args:
            key: Clé de l'entrée
            value: Valeur de l'entrée
            
        Returns:
            int: Taille estimée en bytes
        """
        try:
            # Taille de la clé
            size = len(key) * 2
            
            if isinstance(value, (str, int, float, bool)):
                size += len(str(value))
            elif isinstance(value, dict):
                size += len(json.dumps(value))
            elif isinstance(value, (list, tuple)):
                size += len(str(value))
            elif isinstance(value, bytes):
                size += len(value)
            else:
                size += len(pickle.dumps(value))
            
            return size
        
        except Exception:
            return 1024  # Taille par défaut
    
    def _compress(self, value: Any) -> bytes:
        """
        Compresse une valeur
        
        Args:
            value: Valeur à compresser
            
        Returns:
            bytes: Valeur compressée
        """
        try:
            data = pickle.dumps(value)
            return zlib.compress(data, self.config.compression_level)
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return pickle.dumps(value)
    
    def _decompress(self, data: bytes) -> Any:
        """
        Décompresse une valeur
        
        Args:
            data: Données compressées
            
        Returns:
            Any: Valeur décompressée
        """
        try:
            decompressed = zlib.decompress(data)
            return pickle.loads(decompressed)
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            return pickle.loads(data)
    
    def _update_latency(self, start_time: float):
        """Met à jour les statistiques de latence"""
        latency = time.perf_counter() - start_time
        self._stats.total_latency += latency
        self._stats.avg_latency = (
            self._stats.total_latency / (self._stats.hits + self._stats.misses)
        )
    
    # ============================================================
    # PERSISTENCE
    # ============================================================
    
    def _start_persist_task(self):
        """Démarre la tâche de persistance"""
        def persist_loop():
            while True:
                time.sleep(self.config.persist_interval)
                self._save_persistent()
        
        thread = threading.Thread(target=persist_loop, daemon=True)
        thread.start()
    
    def _load_persistent(self):
        """Charge les données persistantes"""
        if not self.config.persist_path:
            return
        
        path = Path(self.config.persist_path)
        if not path.exists():
            return
        
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            if isinstance(data, dict):
                for key, entry_data in data.items():
                    if isinstance(entry_data, dict):
                        entry = CacheEntry(
                            key=key,
                            value=entry_data.get('value'),
                            created_at=entry_data.get('created_at', time.time()),
                            expires_at=entry_data.get('expires_at'),
                            last_access=entry_data.get('last_access', time.time()),
                            access_count=entry_data.get('access_count', 0),
                            size=entry_data.get('size', 0)
                        )
                        self._cache[key] = entry
            
            logger.info(f"Loaded {len(self._cache)} entries from persistence")
        
        except Exception as e:
            logger.error(f"Failed to load persistence: {e}")
    
    def _save_persistent(self):
        """Sauvegarde les données persistantes"""
        if not self.config.persist_path:
            return
        
        try:
            data = {}
            with self._lock:
                for key, entry in self._cache.items():
                    data[key] = {
                        'value': entry.value,
                        'created_at': entry.created_at,
                        'expires_at': entry.expires_at,
                        'last_access': entry.last_access,
                        'access_count': entry.access_count,
                        'size': entry.size
                    }
            
            path = Path(self.config.persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.debug(f"Saved {len(data)} entries to persistence")
        
        except Exception as e:
            logger.error(f"Failed to save persistence: {e}")
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def exists(self, key: str) -> bool:
        """
        Vérifie si une clé existe dans le cache
        
        Args:
            key: Clé de l'entrée
            
        Returns:
            bool: True si la clé existe
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._delete_entry(key)
                return False
            return True
    
    def keys(self) -> List[str]:
        """
        Récupère toutes les clés du cache
        
        Returns:
            List[str]: Liste des clés
        """
        with self._lock:
            return list(self._cache.keys())
    
    def items(self) -> List[Tuple[str, T]]:
        """
        Récupère toutes les entrées du cache
        
        Returns:
            List[Tuple[str, T]]: Liste des entrées
        """
        with self._lock:
            return [(k, v.value) for k, v in self._cache.items() if not v.is_expired]
    
    def size(self) -> int:
        """
        Récupère la taille du cache
        
        Returns:
            int: Nombre d'entrées
        """
        with self._lock:
            return len(self._cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques du cache
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            hit_rate = self._stats.hits / (self._stats.hits + self._stats.misses) 
                       if (self._stats.hits + self._stats.misses) > 0 else 0
            
            return {
                'hits': self._stats.hits,
                'misses': self._stats.misses,
                'size': self._stats.size,
                'max_size': self._stats.max_size,
                'evictions': self._stats.evictions,
                'total_entries': self._stats.total_entries,
                'hit_rate': hit_rate,
                'memory_usage': self._stats.memory_usage,
                'avg_latency': self._stats.avg_latency,
                'strategy': self.config.strategy.value,
                'compression': self.config.compress,
                'persistence': self.config.enable_persistence,
            }
    
    def cleanup(self):
        """Nettoie les entrées expirées"""
        with self._lock:
            expired = []
            for key, entry in self._cache.items():
                if entry.is_expired:
                    expired.append(key)
            
            for key in expired:
                self._delete_entry(key)
    
    def cleanup_async(self):
        """Nettoie les entrées expirées de manière asynchrone"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
        
        async def _cleanup():
            while True:
                await asyncio.sleep(60)  # Nettoyer toutes les minutes
                self.cleanup()
        
        self._cleanup_task = asyncio.create_task(_cleanup())
    
    def __contains__(self, key: str) -> bool:
        """Vérifie si une clé est dans le cache"""
        return self.exists(key)
    
    def __len__(self) -> int:
        """Taille du cache"""
        return self.size()


# ============================================================
# DECORATED CACHE
# ============================================================

def cache_result(
    ttl: int = 300,
    key_prefix: str = "",
    namespace: str = "cache",
    ignore_args: List[int] = None,
    ignore_kwargs: List[str] = None,
    include_kwargs: bool = True,
    use_cache: Optional[BaseCache] = None
) -> Callable:
    """
    Décorateur pour mettre en cache le résultat d'une fonction
    
    Args:
        ttl: TTL en secondes
        key_prefix: Préfixe de la clé
        namespace: Espace de noms
        ignore_args: Indices des arguments à ignorer
        ignore_kwargs: Noms des arguments nommés à ignorer
        include_kwargs: Inclure les arguments nommés dans la clé
        use_cache: Instance de cache à utiliser
        
    Returns:
        Callable: Décorateur
    """
    if ignore_args is None:
        ignore_args = []
    if ignore_kwargs is None:
        ignore_kwargs = []
    
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        _cache = use_cache or BaseCache()
        _namespace = f"{namespace}:{func.__module__}:{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            # Générer la clé
            key_parts = [_namespace]
            
            # Ajouter les arguments positionnels
            for i, arg in enumerate(args):
                if i not in ignore_args:
                    key_parts.append(str(arg))
            
            # Ajouter les arguments nommés
            if include_kwargs:
                for k, v in sorted(kwargs.items()):
                    if k not in ignore_kwargs:
                        key_parts.append(f"{k}={v}")
            
            # Ajouter le préfixe
            if key_prefix:
                key_parts.insert(1, key_prefix)
            
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            full_key = f"{_namespace}:{key}"
            
            # Vérifier le cache
            cached = _cache.get(full_key)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached
            
            # Exécuter la fonction
            result = func(*args, **kwargs)
            
            # Mettre en cache
            _cache.set(full_key, result, ttl=ttl)
            logger.debug(f"Cache miss for {func.__name__}, stored")
            
            return result
        
        return wrapper
    
    return decorator

def cache_result_async(
    ttl: int = 300,
    key_prefix: str = "",
    namespace: str = "cache",
    ignore_args: List[int] = None,
    ignore_kwargs: List[str] = None,
    include_kwargs: bool = True,
    use_cache: Optional[BaseCache] = None
) -> Callable:
    """
    Décorateur asynchrone pour mettre en cache le résultat d'une fonction
    
    Args:
        ttl: TTL en secondes
        key_prefix: Préfixe de la clé
        namespace: Espace de noms
        ignore_args: Indices des arguments à ignorer
        ignore_kwargs: Noms des arguments nommés à ignorer
        include_kwargs: Inclure les arguments nommés dans la clé
        use_cache: Instance de cache à utiliser
        
    Returns:
        Callable: Décorateur
    """
    if ignore_args is None:
        ignore_args = []
    if ignore_kwargs is None:
        ignore_kwargs = []
    
    def decorator(func: Callable[..., Coroutine[Any, Any, R]]) -> Callable[..., Coroutine[Any, Any, R]]:
        _cache = use_cache or BaseCache()
        _namespace = f"{namespace}:{func.__module__}:{func.__name__}"
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            # Générer la clé
            key_parts = [_namespace]
            
            # Ajouter les arguments positionnels
            for i, arg in enumerate(args):
                if i not in ignore_args:
                    key_parts.append(str(arg))
            
            # Ajouter les arguments nommés
            if include_kwargs:
                for k, v in sorted(kwargs.items()):
                    if k not in ignore_kwargs:
                        key_parts.append(f"{k}={v}")
            
            # Ajouter le préfixe
            if key_prefix:
                key_parts.insert(1, key_prefix)
            
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            full_key = f"{_namespace}:{key}"
            
            # Vérifier le cache
            cached = _cache.get(full_key)
            if cached is not None:
                logger.debug(f"Async cache hit for {func.__name__}")
                return cached
            
            # Exécuter la fonction
            result = await func(*args, **kwargs)
            
            # Mettre en cache
            _cache.set(full_key, result, ttl=ttl)
            logger.debug(f"Async cache miss for {func.__name__}, stored")
            
            return result
        
        return wrapper
    
    return decorator


# ============================================================
# CACHE MANAGER
# ============================================================

class CacheManager:
    """
    Gestionnaire de caches
    
    Gère plusieurs instances de cache avec différents espaces de noms
    """
    
    def __init__(self):
        self._caches: Dict[str, BaseCache] = {}
        self._default_config = CacheConfig()
        self._lock = threading.RLock()
        self._stats = {
            'total_caches': 0,
            'total_entries': 0,
            'total_memory': 0,
        }
    
    def get_cache(
        self,
        namespace: str,
        config: Optional[CacheConfig] = None
    ) -> BaseCache:
        """
        Récupère ou crée un cache
        
        Args:
            namespace: Espace de noms du cache
            config: Configuration du cache
            
        Returns:
            BaseCache: Instance du cache
        """
        with self._lock:
            if namespace not in self._caches:
                if config is None:
                    config = CacheConfig(namespace=namespace)
                else:
                    config.namespace = namespace
                
                self._caches[namespace] = BaseCache(config)
                self._stats['total_caches'] += 1
                logger.info(f"Created cache for namespace: {namespace}")
            
            return self._caches[namespace]
    
    def clear_cache(self, namespace: str):
        """
        Vide un cache
        
        Args:
            namespace: Espace de noms du cache
        """
        with self._lock:
            if namespace in self._caches:
                self._caches[namespace].clear()
                logger.info(f"Cleared cache for namespace: {namespace}")
    
    def clear_all(self):
        """Vide tous les caches"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            logger.info("Cleared all caches")
    
    def get_stats(self, namespace: str) -> Dict[str, Any]:
        """
        Récupère les statistiques d'un cache
        
        Args:
            namespace: Espace de noms du cache
            
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            if namespace in self._caches:
                return self._caches[namespace].get_stats()
            return {}
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les statistiques de tous les caches
        
        Returns:
            Dict[str, Dict[str, Any]]: Statistiques par namespace
        """
        with self._lock:
            return {
                namespace: cache.get_stats()
                for namespace, cache in self._caches.items()
            }
    
    def cleanup_all(self):
        """Nettoie tous les caches"""
        with self._lock:
            for cache in self._caches.values():
                cache.cleanup()
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques globales
        
        Returns:
            Dict[str, Any]: Statistiques globales
        """
        with self._lock:
            total_entries = sum(len(cache) for cache in self._caches.values())
            total_memory = sum(
                cache.get_stats().get('memory_usage', 0)
                for cache in self._caches.values()
            )
            
            return {
                'total_caches': self._stats['total_caches'],
                'total_entries': total_entries,
                'total_memory': total_memory,
                'caches': self.get_all_stats()
            }


# ============================================================
# SINGLETON INSTANCE
# ============================================================

_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    """Récupère le gestionnaire de caches (singleton)"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'CacheStrategy',
    
    # Data Classes
    'CacheConfig',
    'CacheStats',
    'CacheEntry',
    
    # Classes
    'BaseCache',
    'CacheManager',
    
    # Décorateurs
    'cache_result',
    'cache_result_async',
    
    # Fonctions
    'get_cache_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Cache utilities module initialized")
