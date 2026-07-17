"""
NEXUS AI TRADING SYSTEM - Indicator Cache for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/indicators/indicator_cache.py
Description: Système de cache intelligent pour les indicateurs techniques.
             Supporte le caching en mémoire, sur disque, avec TTL,
             invalidation automatique, persistance, et optimisation
             des performances pour les calculs répétitifs.
"""

import logging
import time
import hashlib
import json
import pickle
import os
import sqlite3
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
import threading
import asyncio

import pandas as pd
import numpy as np

from trading.bots.ai_bot.indicators.base_indicator import IndicatorResult
from shared.exceptions import CacheError

# Configuration du logging
logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """Backends de cache."""
    MEMORY = "memory"
    DISK = "disk"
    REDIS = "redis"
    SQLITE = "sqlite"
    HYBRID = "hybrid"


@dataclass
class CacheConfig:
    """
    Configuration du cache d'indicateurs.
    """
    # Backend
    backend: CacheBackend = CacheBackend.MEMORY
    
    # Taille et durée
    max_size: int = 1000
    ttl: int = 3600  # secondes
    disk_ttl: int = 86400  # 24 heures
    
    # Paramètres disque
    disk_path: str = "data/indicator_cache/"
    disk_compression: bool = True
    
    # Paramètres Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: Optional[str] = None
    
    # Paramètres SQLite
    sqlite_path: str = "data/indicator_cache.db"
    sqlite_table: str = "indicator_cache"
    
    # Paramètres de performance
    async_operations: bool = True
    batch_size: int = 100
    compression_enabled: bool = True
    compression_level: int = 6
    
    # Paramètres d'optimisation
    precompute_on_startup: bool = False
    warmup_count: int = 10
    cleanup_interval: int = 3600
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.max_size < 1:
            raise CacheError("max_size doit être >= 1")
        
        if self.ttl < 0:
            raise CacheError("ttl doit être >= 0")
        
        if self.disk_ttl < 0:
            raise CacheError("disk_ttl doit être >= 0")
        
        # Création des répertoires
        if self.backend in [CacheBackend.DISK, CacheBackend.HYBRID]:
            os.makedirs(self.disk_path, exist_ok=True)
        
        if self.backend == CacheBackend.SQLITE:
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)


@dataclass
class CacheEntry:
    """
    Entrée de cache.
    """
    # Identifiants
    key: str
    indicator_name: str
    symbol: str
    timeframe: str
    
    # Données
    result: IndicatorResult
    data_hash: str
    computed_at: datetime
    
    # Métadonnées
    size_bytes: int = 0
    access_count: int = 0
    last_access: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Statut
    is_valid: bool = True
    is_persistent: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'key': self.key,
            'indicator_name': self.indicator_name,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'computed_at': self.computed_at.isoformat(),
            'size_bytes': self.size_bytes,
            'access_count': self.access_count,
            'last_access': self.last_access.isoformat() if self.last_access else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_valid': self.is_valid,
            'is_persistent': self.is_persistent
        }


class IndicatorCache:
    """
    Système de cache intelligent pour les indicateurs.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialise le cache d'indicateurs.
        
        Args:
            config: Configuration du cache.
        """
        self.config = config or CacheConfig()
        
        # Cache mémoire
        self._memory_cache: OrderedDict = OrderedDict()
        self._memory_entries: Dict[str, CacheEntry] = {}
        
        # Cache disque
        self._disk_cache: Dict[str, CacheEntry] = {}
        
        # Cache Redis (optionnel)
        self._redis_client = None
        
        # Cache SQLite
        self._sqlite_connection = None
        
        # Statistiques
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'size': 0,
            'disk_size': 0
        }
        
        # Verrous
        self._lock = threading.Lock()
        
        # État
        self._initialized = False
        self._running = False
        
        # Initialisation
        self._initialize()
        
        logger.info("IndicatorCache initialisé")
        logger.info(f"Backend: {self.config.backend.value}")
        logger.info(f"Max size: {self.config.max_size}, TTL: {self.config.ttl}s")
    
    def _initialize(self) -> None:
        """
        Initialise le cache.
        """
        try:
            # Initialisation du backend
            if self.config.backend == CacheBackend.MEMORY:
                self._init_memory()
            elif self.config.backend == CacheBackend.DISK:
                self._init_disk()
            elif self.config.backend == CacheBackend.REDIS:
                self._init_redis()
            elif self.config.backend == CacheBackend.SQLITE:
                self._init_sqlite()
            elif self.config.backend == CacheBackend.HYBRID:
                self._init_hybrid()
            
            self._initialized = True
            
            # Warmup
            if self.config.precompute_on_startup:
                self._warmup()
            
            # Démarrer la tâche de nettoyage
            if self.config.cleanup_interval > 0:
                self._start_cleanup_task()
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation du cache: {e}")
            # Fallback en mémoire
            if self.config.backend != CacheBackend.MEMORY:
                logger.warning("Fallback vers le cache mémoire")
                self.config.backend = CacheBackend.MEMORY
                self._init_memory()
    
    def _init_memory(self) -> None:
        """Initialise le cache mémoire."""
        self._memory_cache = OrderedDict()
        self._memory_entries = {}
        logger.info("Cache mémoire initialisé")
    
    def _init_disk(self) -> None:
        """Initialise le cache disque."""
        os.makedirs(self.config.disk_path, exist_ok=True)
        
        # Chargement des entrées existantes
        for filename in os.listdir(self.config.disk_path):
            if filename.endswith('.pkl'):
                try:
                    filepath = os.path.join(self.config.disk_path, filename)
                    with open(filepath, 'rb') as f:
                        entry = pickle.load(f)
                    key = filename.replace('.pkl', '')
                    self._disk_cache[key] = entry
                except Exception as e:
                    logger.warning(f"Erreur de chargement {filename}: {e}")
        
        logger.info(f"Cache disque initialisé: {len(self._disk_cache)} entrées")
    
    def _init_redis(self) -> None:
        """Initialise le cache Redis."""
        try:
            import redis
            
            self._redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False
            )
            self._redis_client.ping()
            logger.info("Cache Redis initialisé")
            
        except ImportError:
            logger.warning("Redis non disponible, fallback mémoire")
            self._init_memory()
        except Exception as e:
            logger.error(f"Erreur Redis: {e}")
            self._init_memory()
    
    def _init_sqlite(self) -> None:
        """Initialise le cache SQLite."""
        try:
            self._sqlite_connection = sqlite3.connect(
                self.config.sqlite_path,
                check_same_thread=False
            )
            
            # Création de la table
            cursor = self._sqlite_connection.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.config.sqlite_table} (
                    key TEXT PRIMARY KEY,
                    indicator_name TEXT,
                    symbol TEXT,
                    timeframe TEXT,
                    data BLOB,
                    data_hash TEXT,
                    computed_at TEXT,
                    expires_at TEXT,
                    access_count INTEGER DEFAULT 0,
                    last_access TEXT,
                    is_valid INTEGER DEFAULT 1,
                    is_persistent INTEGER DEFAULT 0
                )
            """)
            
            # Création des index
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.sqlite_table}_name 
                ON {self.config.sqlite_table}(indicator_name)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.sqlite_table}_symbol 
                ON {self.config.sqlite_table}(symbol)
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.config.sqlite_table}_expires 
                ON {self.config.sqlite_table}(expires_at)
            """)
            
            self._sqlite_connection.commit()
            logger.info("Cache SQLite initialisé")
            
        except Exception as e:
            logger.error(f"Erreur SQLite: {e}")
            self._init_memory()
    
    def _init_hybrid(self) -> None:
        """Initialise le cache hybride."""
        self._init_memory()
        self._init_disk()
        logger.info("Cache hybride initialisé")
    
    # ============================================================
    # MÉTHODES PRINCIPALES
    # ============================================================
    
    def get(
        self,
        indicator_name: str,
        symbol: str,
        timeframe: str,
        data_hash: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[IndicatorResult]:
        """
        Récupère un résultat du cache.
        
        Args:
            indicator_name: Nom de l'indicateur.
            symbol: Symbole.
            timeframe: Timeframe.
            data_hash: Hash des données.
            params: Paramètres de l'indicateur.
            
        Returns:
            Résultat de l'indicateur ou None.
        """
        key = self._generate_key(indicator_name, symbol, timeframe, data_hash, params)
        
        # Vérification du cache
        entry = self._get_entry(key)
        
        if entry and entry.is_valid:
            # Vérification de l'expiration
            if entry.expires_at and entry.expires_at < datetime.now():
                self.delete(key)
                return None
            
            # Mise à jour des statistiques
            self._stats['hits'] += 1
            entry.access_count += 1
            entry.last_access = datetime.now()
            
            return entry.result
        
        self._stats['misses'] += 1
        return None
    
    def set(
        self,
        indicator_name: str,
        symbol: str,
        timeframe: str,
        data_hash: str,
        result: IndicatorResult,
        params: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        persistent: bool = False
    ) -> None:
        """
        Stocke un résultat dans le cache.
        
        Args:
            indicator_name: Nom de l'indicateur.
            symbol: Symbole.
            timeframe: Timeframe.
            data_hash: Hash des données.
            result: Résultat à stocker.
            params: Paramètres de l'indicateur.
            ttl: Durée de vie spécifique.
            persistent: Stockage persistant.
        """
        key = self._generate_key(indicator_name, symbol, timeframe, data_hash, params)
        
        # Création de l'entrée
        entry = CacheEntry(
            key=key,
            indicator_name=indicator_name,
            symbol=symbol,
            timeframe=timeframe,
            result=result,
            data_hash=data_hash,
            computed_at=datetime.now(),
            is_persistent=persistent
        )
        
        # TTL
        ttl_seconds = ttl or self.config.ttl
        if ttl_seconds > 0:
            entry.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        # Taille approximative
        entry.size_bytes = self._estimate_size(result)
        
        # Stockage
        self._set_entry(key, entry, persistent)
        
        self._stats['sets'] += 1
        
        # Nettoyage si nécessaire
        if len(self._memory_cache) > self.config.max_size:
            self._evict()
    
    def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache.
        
        Args:
            key: Clé de l'entrée.
            
        Returns:
            True si supprimée.
        """
        with self._lock:
            deleted = False
            
            # Suppression mémoire
            if key in self._memory_cache:
                del self._memory_cache[key]
                del self._memory_entries[key]
                deleted = True
            
            # Suppression disque
            if key in self._disk_cache:
                del self._disk_cache[key]
                filepath = os.path.join(self.config.disk_path, f"{key}.pkl")
                if os.path.exists(filepath):
                    os.remove(filepath)
                deleted = True
            
            # Suppression Redis
            if self._redis_client:
                self._redis_client.delete(key)
                deleted = True
            
            # Suppression SQLite
            if self._sqlite_connection:
                cursor = self._sqlite_connection.cursor()
                cursor.execute(f"DELETE FROM {self.config.sqlite_table} WHERE key = ?", (key,))
                self._sqlite_connection.commit()
                deleted = True
            
            if deleted:
                self._stats['deletes'] += 1
            
            return deleted
    
    def clear(self, indicator_name: Optional[str] = None) -> None:
        """
        Vide le cache.
        
        Args:
            indicator_name: Nom de l'indicateur (optionnel).
        """
        with self._lock:
            if indicator_name:
                # Suppression par indicateur
                keys_to_remove = []
                for key, entry in self._memory_entries.items():
                    if entry.indicator_name == indicator_name:
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    self.delete(key)
                
                logger.info(f"Cache vidé pour {indicator_name}")
            else:
                # Suppression totale
                self._memory_cache.clear()
                self._memory_entries.clear()
                self._disk_cache.clear()
                
                if self._redis_client:
                    self._redis_client.flushdb()
                
                if self._sqlite_connection:
                    cursor = self._sqlite_connection.cursor()
                    cursor.execute(f"DELETE FROM {self.config.sqlite_table}")
                    self._sqlite_connection.commit()
                
                # Nettoyage disque
                for filename in os.listdir(self.config.disk_path):
                    if filename.endswith('.pkl'):
                        os.remove(os.path.join(self.config.disk_path, filename))
                
                self._stats = {k: 0 for k in self._stats}
                logger.info("Cache complètement vidé")
    
    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================
    
    def _generate_key(
        self,
        indicator_name: str,
        symbol: str,
        timeframe: str,
        data_hash: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Génère une clé de cache.
        
        Args:
            indicator_name: Nom de l'indicateur.
            symbol: Symbole.
            timeframe: Timeframe.
            data_hash: Hash des données.
            params: Paramètres.
            
        Returns:
            Clé de cache.
        """
        params_str = json.dumps(params or {}, sort_keys=True)
        key_str = f"{indicator_name}_{symbol}_{timeframe}_{data_hash}_{params_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_entry(self, key: str) -> Optional[CacheEntry]:
        """
        Récupère une entrée du cache.
        
        Args:
            key: Clé de l'entrée.
            
        Returns:
            Entrée de cache ou None.
        """
        # Vérification mémoire
        if key in self._memory_entries:
            return self._memory_entries[key]
        
        # Vérification disque
        if key in self._disk_cache:
            entry = self._disk_cache[key]
            # Chargement en mémoire
            self._memory_cache[key] = entry.result
            self._memory_entries[key] = entry
            return entry
        
        # Vérification Redis
        if self._redis_client:
            data = self._redis_client.get(key)
            if data:
                entry = pickle.loads(data)
                # Chargement en mémoire
                self._memory_cache[key] = entry.result
                self._memory_entries[key] = entry
                return entry
        
        # Vérification SQLite
        if self._sqlite_connection:
            cursor = self._sqlite_connection.cursor()
            cursor.execute(
                f"SELECT data FROM {self.config.sqlite_table} WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                entry = pickle.loads(row[0])
                # Chargement en mémoire
                self._memory_cache[key] = entry.result
                self._memory_entries[key] = entry
                return entry
        
        return None
    
    def _set_entry(self, key: str, entry: CacheEntry, persistent: bool) -> None:
        """
        Stocke une entrée dans le cache.
        
        Args:
            key: Clé de l'entrée.
            entry: Entrée à stocker.
            persistent: Stockage persistant.
        """
        with self._lock:
            # Stockage mémoire
            self._memory_cache[key] = entry.result
            self._memory_entries[key] = entry
            
            # Stockage disque (si persistant ou backend disque)
            if persistent or self.config.backend in [CacheBackend.DISK, CacheBackend.HYBRID]:
                self._disk_cache[key] = entry
                filepath = os.path.join(self.config.disk_path, f"{key}.pkl")
                with open(filepath, 'wb') as f:
                    pickle.dump(entry, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Stockage Redis
            if self._redis_client:
                data = pickle.dumps(entry)
                ttl_seconds = self.config.disk_ttl if persistent else self.config.ttl
                self._redis_client.setex(key, ttl_seconds, data)
            
            # Stockage SQLite
            if self._sqlite_connection:
                data = pickle.dumps(entry)
                cursor = self._sqlite_connection.cursor()
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {self.config.sqlite_table}
                    (key, indicator_name, symbol, timeframe, data, data_hash, 
                     computed_at, expires_at, access_count, last_access, is_valid, is_persistent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    entry.indicator_name,
                    entry.symbol,
                    entry.timeframe,
                    data,
                    entry.data_hash,
                    entry.computed_at.isoformat(),
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    entry.access_count,
                    entry.last_access.isoformat() if entry.last_access else None,
                    1 if entry.is_valid else 0,
                    1 if entry.is_persistent else 0
                ))
                self._sqlite_connection.commit()
    
    def _evict(self) -> None:
        """
        Évite les entrées les moins récemment utilisées.
        """
        with self._lock:
            if len(self._memory_cache) <= self.config.max_size:
                return
            
            # Supprimer les entrées les plus anciennes
            n_to_remove = len(self._memory_cache) - self.config.max_size
            for _ in range(n_to_remove):
                key, _ = self._memory_cache.popitem(last=False)
                if key in self._memory_entries:
                    del self._memory_entries[key]
                self._stats['evictions'] += 1
            
            logger.debug(f"Éviction: {n_to_remove} entrées supprimées")
    
    def _estimate_size(self, result: IndicatorResult) -> int:
        """
        Estime la taille d'un résultat.
        
        Args:
            result: Résultat.
            
        Returns:
            Taille estimée en octets.
        """
        try:
            data = pickle.dumps(result)
            return len(data)
        except:
            return 1024  # Taille par défaut
    
    def _warmup(self) -> None:
        """
        Warmup du cache.
        """
        # Chargement des entrées les plus récentes
        entries = []
        
        if self._sqlite_connection:
            cursor = self._sqlite_connection.cursor()
            cursor.execute(f"""
                SELECT key, data FROM {self.config.sqlite_table}
                ORDER BY computed_at DESC LIMIT {self.config.warmup_count}
            """)
            rows = cursor.fetchall()
            for row in rows:
                try:
                    entry = pickle.loads(row[1])
                    entries.append(entry)
                except:
                    continue
        
        # Chargement en mémoire
        for entry in entries:
            self._memory_cache[entry.key] = entry.result
            self._memory_entries[entry.key] = entry
        
        if entries:
            logger.info(f"Warmup: {len(entries)} entrées chargées")
    
    def _start_cleanup_task(self) -> None:
        """
        Démarre la tâche de nettoyage.
        """
        def cleanup_loop():
            while self._running:
                time.sleep(self.config.cleanup_interval)
                self._cleanup()
        
        self._running = True
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def _cleanup(self) -> None:
        """
        Nettoie les entrées expirées.
        """
        with self._lock:
            now = datetime.now()
            keys_to_remove = []
            
            # Vérification des entrées mémoire
            for key, entry in self._memory_entries.items():
                if entry.expires_at and entry.expires_at < now:
                    keys_to_remove.append(key)
            
            # Suppression
            for key in keys_to_remove:
                self.delete(key)
            
            if keys_to_remove:
                logger.debug(f"Nettoyage: {len(keys_to_remove)} entrées supprimées")
    
    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du cache.
        
        Returns:
            Statistiques du cache.
        """
        hit_rate = 0
        total_requests = self._stats['hits'] + self._stats['misses']
        if total_requests > 0:
            hit_rate = self._stats['hits'] / total_requests
        
        return {
            **self._stats,
            'hit_rate': hit_rate,
            'memory_size': len(self._memory_cache),
            'disk_size': len(self._disk_cache),
            'backend': self.config.backend.value,
            'max_size': self.config.max_size,
            'ttl': self.config.ttl
        }
    
    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Retourne les clés du cache.
        
        Args:
            pattern: Filtre optionnel.
            
        Returns:
            Liste des clés.
        """
        keys = list(self._memory_entries.keys())
        
        if pattern:
            keys = [k for k in keys if pattern in k]
        
        return keys
    
    def get_entries(self, pattern: Optional[str] = None) -> List[CacheEntry]:
        """
        Retourne les entrées du cache.
        
        Args:
            pattern: Filtre optionnel.
            
        Returns:
            Liste des entrées.
        """
        entries = list(self._memory_entries.values())
        
        if pattern:
            entries = [e for e in entries if pattern in e.key]
        
        return entries
    
    def get_size(self) -> int:
        """
        Retourne la taille du cache.
        
        Returns:
            Taille du cache.
        """
        return len(self._memory_cache)
    
    def close(self) -> None:
        """
        Ferme le cache.
        """
        self._running = False
        
        if self._sqlite_connection:
            self._sqlite_connection.close()
        
        if self._redis_client:
            self._redis_client.close()
        
        logger.info("Cache fermé")


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def create_indicator_cache(
    backend: str = "memory",
    max_size: int = 1000,
    ttl: int = 3600,
    **kwargs
) -> IndicatorCache:
    """
    Crée un cache d'indicateurs.
    
    Args:
        backend: Backend de cache.
        max_size: Taille maximale.
        ttl: Durée de vie.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Instance du cache.
    """
    backend_map = {
        'memory': CacheBackend.MEMORY,
        'disk': CacheBackend.DISK,
        'redis': CacheBackend.REDIS,
        'sqlite': CacheBackend.SQLITE,
        'hybrid': CacheBackend.HYBRID
    }
    
    config = CacheConfig(
        backend=backend_map.get(backend, CacheBackend.MEMORY),
        max_size=max_size,
        ttl=ttl,
        **kwargs
    )
    
    return IndicatorCache(config)


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'IndicatorCache',
    'CacheConfig',
    'CacheEntry',
    'CacheBackend',
    'create_indicator_cache'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
