# trading/bots/hedge_bot/hedge_bot_data_cache.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Cache Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Cache Module

This module provides comprehensive data caching capabilities for the
NEXUS Hedge Bot system. It manages cached data, cache strategies,
and cache invalidation.

The module covers:
- Data Caching
- Cache Strategies
- Cache Invalidation
- Cache Persistence
- Distributed Caching
- Cache Warming
- Cache Eviction
- Cache Monitoring
"""

import os
import sys
import json
import logging
import time
import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import OrderedDict
import threading
import weakref

# Try to import Redis
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logger = logging.getLogger(__name__)


# ============================================================
# DATA CACHE ENUMS
# ============================================================

class CacheStrategy(Enum):
    """Cache strategies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live
    ADAPTIVE = "adaptive"


class CacheLevel(Enum):
    """Cache levels"""
    MEMORY = "memory"
    LOCAL = "local"
    DISTRIBUTED = "distributed"
    HYBRID = "hybrid"


@dataclass
class CacheConfig:
    """Cache configuration"""
    id: str
    name: str
    strategy: CacheStrategy
    max_size: int
    ttl_seconds: int = 300
    persistence: bool = False
    persistence_path: Optional[str] = None
    level: CacheLevel = CacheLevel.MEMORY
    distributed: bool = False
    redis_url: Optional[str] = None
    compression: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy.value,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "persistence": self.persistence,
            "persistence_path": self.persistence_path,
            "level": self.level.value,
            "distributed": self.distributed,
            "redis_url": self.redis_url,
            "compression": self.compression,
        }


@dataclass
class CacheStats:
    """Cache statistics"""
    name: str
    hits: int
    misses: int
    hit_rate: float
    size: int
    max_size: int
    utilization: float
    evictions: int
    avg_ttl: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "size": self.size,
            "max_size": self.max_size,
            "utilization": self.utilization,
            "evictions": self.evictions,
            "avg_ttl": self.avg_ttl,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CacheItem:
    """Cache item"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
            "size": self.size,
            "tags": self.tags,
        }


# ============================================================
# DATA CACHE ENGINE
# ============================================================

class DataCacheEngine:
    """
    Comprehensive data cache engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data cache engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_max_size = self.config.get("default_max_size", 1000)
        self.default_ttl = self.config.get("default_ttl", 300)
        self.default_strategy = self.config.get("default_strategy", CacheStrategy.LRU)
        
        # State
        self.caches: Dict[str, OrderedDict] = {}
        self.configs: Dict[str, CacheConfig] = {}
        self.stats: Dict[str, CacheStats] = {}
        self.locks: Dict[str, threading.Lock] = {}
        
        # Redis client
        self.redis_client = None
        if HAS_REDIS:
            self._init_redis()
        
        logger.info("Data cache engine initialized")
    
    # ============================================================
    # REDIS INITIALIZATION
    # ============================================================
    
    def _init_redis(self) -> None:
        """Initialize Redis client"""
        try:
            redis_url = self.config.get("redis_url", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis client initialized")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}")
            self.redis_client = None
    
    # ============================================================
    # CACHE MANAGEMENT
    # ============================================================
    
    def create_cache(
        self,
        name: str,
        max_size: Optional[int] = None,
        strategy: Optional[CacheStrategy] = None,
        ttl_seconds: int = 300,
        persistence: bool = False,
        persistence_path: Optional[str] = None,
        distributed: bool = False,
        redis_url: Optional[str] = None,
        compression: bool = False
    ) -> CacheConfig:
        """
        Create a cache
        
        Args:
            name: Cache name
            max_size: Maximum size
            strategy: Cache strategy
            ttl_seconds: TTL in seconds
            persistence: Enable persistence
            persistence_path: Persistence path
            distributed: Enable distributed cache
            redis_url: Redis URL
            compression: Enable compression
            
        Returns:
            CacheConfig
        """
        if max_size is None:
            max_size = self.default_max_size
        if strategy is None:
            strategy = self.default_strategy
        
        config = CacheConfig(
            id=f"cache_{int(time.time())}_{name}",
            name=name,
            strategy=strategy,
            max_size=max_size,
            ttl_seconds=ttl_seconds,
            persistence=persistence,
            persistence_path=persistence_path or f"cache_{name}.pkl",
            level=CacheLevel.DISTRIBUTED if distributed else CacheLevel.MEMORY,
            distributed=distributed,
            redis_url=redis_url,
            compression=compression,
        )
        
        self.configs[name] = config
        
        # Initialize cache
        if distributed and HAS_REDIS:
            self._init_distributed_cache(name, redis_url)
        else:
            self.caches[name] = OrderedDict()
        
        self.locks[name] = threading.Lock()
        
        # Initialize stats
        self.stats[name] = CacheStats(
            name=name,
            hits=0,
            misses=0,
            hit_rate=0.0,
            size=0,
            max_size=max_size,
            utilization=0.0,
            evictions=0,
            avg_ttl=0.0,
        )
        
        # Load from persistence
        if persistence and persistence_path:
            self._load_persistence(name)
        
        logger.info(f"Created cache: {name}")
        return config
    
    def _init_distributed_cache(self, name: str, redis_url: Optional[str] = None) -> None:
        """Initialize distributed cache"""
        if redis_url and HAS_REDIS:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.redis_client = None
    
    def delete_cache(self, name: str) -> bool:
        """
        Delete a cache
        
        Args:
            name: Cache name
            
        Returns:
            True if deleted
        """
        if name in self.caches or name in self.configs:
            if name in self.caches:
                with self.locks[name]:
                    self.caches[name].clear()
                    del self.caches[name]
            if name in self.configs:
                del self.configs[name]
            if name in self.locks:
                del self.locks[name]
            if name in self.stats:
                del self.stats[name]
            logger.info(f"Deleted cache: {name}")
            return True
        return False
    
    def get_cache_config(self, name: str) -> Optional[CacheConfig]:
        """
        Get cache configuration
        
        Args:
            name: Cache name
            
        Returns:
            CacheConfig or None
        """
        return self.configs.get(name)
    
    def get_cache_stats(self, name: str) -> Optional[CacheStats]:
        """
        Get cache statistics
        
        Args:
            name: Cache name
            
        Returns:
            CacheStats or None
        """
        return self.stats.get(name)
    
    # ============================================================
    # CACHE OPERATIONS
    # ============================================================
    
    def set(
        self,
        cache_name: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Set cache value
        
        Args:
            cache_name: Cache name
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Optional tags
            
        Returns:
            True if set
        """
        config = self.configs.get(cache_name)
        if not config:
            raise ValueError(f"Cache not found: {cache_name}")
        
        if config.distributed and self.redis_client:
            return self._set_distributed(cache_name, key, value, ttl or config.ttl_seconds, tags)
        
        with self.locks[cache_name]:
            cache = self.caches.get(cache_name)
            if not cache:
                return False
            
            # Check size limit
            if len(cache) >= config.max_size:
                self._evict_item(cache_name)
            
            # Create item
            now = datetime.now()
            expires_at = now + timedelta(seconds=ttl or config.ttl_seconds)
            
            item = CacheItem(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                tags=tags or [],
                size=len(str(value).encode()) if isinstance(value, str) else 1,
            )
            
            # Store
            cache[key] = item
            
            # Update stats
            self._update_stats(cache_name)
            
            # Persist if enabled
            if config.persistence:
                self._save_persistence(cache_name)
            
            return True
    
    def _set_distributed(
        self,
        cache_name: str,
        key: str,
        value: Any,
        ttl: int,
        tags: Optional[List[str]]
    ) -> bool:
        """Set distributed cache value"""
        try:
            # Serialize
            data = pickle.dumps(value)
            
            # Store in Redis
            self.redis_client.setex(
                f"{cache_name}:{key}",
                ttl,
                data
            )
            
            # Store tags if provided
            if tags:
                for tag in tags:
                    self.redis_client.sadd(f"{cache_name}:tags:{tag}", key)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set distributed cache: {e}")
            return False
    
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """
        Get cache value
        
        Args:
            cache_name: Cache name
            key: Cache key
            
        Returns:
            Value or None
        """
        config = self.configs.get(cache_name)
        if not config:
            raise ValueError(f"Cache not found: {cache_name}")
        
        if config.distributed and self.redis_client:
            return self._get_distributed(cache_name, key)
        
        with self.locks[cache_name]:
            cache = self.caches.get(cache_name)
            if not cache:
                return None
            
            if key not in cache:
                self.stats[cache_name].misses += 1
                self._update_stats(cache_name)
                return None
            
            item = cache[key]
            
            # Check expiry
            if item.expires_at and item.expires_at < datetime.now():
                del cache[key]
                self.stats[cache_name].misses += 1
                self._update_stats(cache_name)
                return None
            
            # Update access
            item.access_count += 1
            item.last_accessed = datetime.now()
            
            # Update stats
            self.stats[cache_name].hits += 1
            self._update_stats(cache_name)
            
            return item.value
    
    def _get_distributed(self, cache_name: str, key: str) -> Optional[Any]:
        """Get distributed cache value"""
        try:
            data = self.redis_client.get(f"{cache_name}:{key}")
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get distributed cache: {e}")
            return None
    
    def delete(self, cache_name: str, key: str) -> bool:
        """
        Delete cache value
        
        Args:
            cache_name: Cache name
            key: Cache key
            
        Returns:
            True if deleted
        """
        config = self.configs.get(cache_name)
        if not config:
            return False
        
        if config.distributed and self.redis_client:
            try:
                self.redis_client.delete(f"{cache_name}:{key}")
                return True
            except:
                return False
        
        with self.locks[cache_name]:
            cache = self.caches.get(cache_name)
            if cache and key in cache:
                del cache[key]
                self._update_stats(cache_name)
                if config.persistence:
                    self._save_persistence(cache_name)
                return True
        return False
    
    def clear(self, cache_name: str) -> None:
        """
        Clear cache
        
        Args:
            cache_name: Cache name
        """
        config = self.configs.get(cache_name)
        if not config:
            return
        
        if config.distributed and self.redis_client:
            try:
                keys = self.redis_client.keys(f"{cache_name}:*")
                if keys:
                    self.redis_client.delete(*keys)
                return
            except:
                pass
        
        with self.locks[cache_name]:
            cache = self.caches.get(cache_name)
            if cache:
                cache.clear()
                self._update_stats(cache_name)
                if config.persistence:
                    self._save_persistence(cache_name)
    
    def _evict_item(self, cache_name: str) -> None:
        """
        Evict item based on strategy
        
        Args:
            cache_name: Cache name
        """
        config = self.configs.get(cache_name)
        if not config:
            return
        
        cache = self.caches.get(cache_name)
        if not cache:
            return
        
        if config.strategy == CacheStrategy.LRU:
            # Evict least recently used
            if cache:
                key = next(iter(cache))
                del cache[key]
                self.stats[cache_name].evictions += 1
        
        elif config.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            if cache:
                min_item = min(cache.items(), key=lambda x: x[1].access_count)
                del cache[min_item[0]]
                self.stats[cache_name].evictions += 1
        
        elif config.strategy == CacheStrategy.FIFO:
            # Evict oldest
            if cache:
                key = next(iter(cache))
                del cache[key]
                self.stats[cache_name].evictions += 1
        
        elif config.strategy == CacheStrategy.TTL:
            # Evict expired items
            now = datetime.now()
            expired = [k for k, v in cache.items() if v.expires_at and v.expires_at < now]
            for k in expired:
                del cache[k]
                self.stats[cache_name].evictions += 1
    
    def _update_stats(self, cache_name: str) -> None:
        """
        Update cache statistics
        
        Args:
            cache_name: Cache name
        """
        config = self.configs.get(cache_name)
        if not config:
            return
        
        cache = self.caches.get(cache_name)
        stats = self.stats.get(cache_name)
        
        if not cache or not stats:
            return
        
        # Update stats
        stats.size = len(cache)
        stats.utilization = stats.size / config.max_size if config.max_size > 0 else 0
        
        # Calculate hit rate
        total = stats.hits + stats.misses
        stats.hit_rate = stats.hits / total if total > 0 else 0
        
        # Calculate average TTL
        ttl_values = [(v.expires_at - v.created_at).total_seconds() 
                     for v in cache.values() if v.expires_at]
        stats.avg_ttl = sum(ttl_values) / len(ttl_values) if ttl_values else config.ttl_seconds
    
    # ============================================================
    # PERSISTENCE
    # ============================================================
    
    def _save_persistence(self, cache_name: str) -> None:
        """
        Save cache to persistence
        
        Args:
            cache_name: Cache name
        """
        config = self.configs.get(cache_name)
        if not config or not config.persistence_path:
            return
        
        try:
            cache = self.caches.get(cache_name)
            if cache:
                # Convert to serializable format
                data = {
                    k: {
                        'value': v.value,
                        'created_at': v.created_at.isoformat(),
                        'expires_at': v.expires_at.isoformat() if v.expires_at else None,
                        'access_count': v.access_count,
                        'last_accessed': v.last_accessed.isoformat(),
                        'tags': v.tags,
                    }
                    for k, v in cache.items()
                }
                
                with open(config.persistence_path, 'wb') as f:
                    pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save persistence: {e}")
    
    def _load_persistence(self, cache_name: str) -> None:
        """
        Load cache from persistence
        
        Args:
            cache_name: Cache name
        """
        config = self.configs.get(cache_name)
        if not config or not config.persistence_path:
            return
        
        try:
            path = Path(config.persistence_path)
            if path.exists():
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                
                cache = self.caches.get(cache_name)
                if cache:
                    for key, item_data in data.items():
                        created_at = datetime.fromisoformat(item_data['created_at'])
                        expires_at = datetime.fromisoformat(item_data['expires_at']) if item_data['expires_at'] else None
                        last_accessed = datetime.fromisoformat(item_data['last_accessed'])
                        
                        item = CacheItem(
                            key=key,
                            value=item_data['value'],
                            created_at=created_at,
                            expires_at=expires_at,
                            access_count=item_data['access_count'],
                            last_accessed=last_accessed,
                            tags=item_data.get('tags', []),
                        )
                        cache[key] = item
                    
                    self._update_stats(cache_name)
        except Exception as e:
            logger.error(f"Failed to load persistence: {e}")
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Statistics dictionary
        """
        total_size = sum(s.size for s in self.stats.values())
        total_hits = sum(s.hits for s in self.stats.values())
        total_misses = sum(s.misses for s in self.stats.values())
        
        return {
            "total_caches": len(self.caches),
            "total_items": total_size,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0,
            "caches": [s.to_dict() for s in self.stats.values()],
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CacheStrategy",
    "CacheLevel",
    
    # Dataclasses
    "CacheConfig",
    "CacheStats",
    "CacheItem",
    
    # Classes
    "DataCacheEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
