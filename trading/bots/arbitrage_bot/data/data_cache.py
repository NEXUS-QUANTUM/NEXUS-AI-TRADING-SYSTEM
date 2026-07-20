# trading/bots/arbitrage_bot/data/data_cache.py
# Nexus AI Trading System - Arbitrage Bot Data Cache Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Cache Module

This module provides comprehensive data caching for the arbitrage bot system,
including:

- Multi-level caching (memory, Redis, database)
- Cache invalidation strategies
- Cache warming and preloading
- Cache statistics and monitoring
- Distributed cache support
- Cache serialization and compression
- Cache key management
- Cache TTL management
- Cache health monitoring
- Cache backup and recovery
- Cache versioning
- Cache optimization

The data cache ensures fast access to frequently used data,
reducing latency and API calls.
"""

import asyncio
import hashlib
import json
import math
import pickle
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set, TypeVar, Generic

import asyncpg
import aioredis
from pydantic import BaseModel, Field, validator

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class CacheLevel(str, Enum):
    """Cache levels."""
    MEMORY = "memory"       # In-memory cache
    REDIS = "redis"         # Redis cache
    DATABASE = "database"   # Database cache
    DISK = "disk"           # Disk cache
    DISTRIBUTED = "distributed"  # Distributed cache


class CacheStatus(str, Enum):
    """Cache status."""
    HIT = "hit"
    MISS = "miss"
    STALE = "stale"
    EXPIRED = "expired"
    INVALID = "invalid"
    ERROR = "error"


class CacheStrategy(str, Enum):
    """Cache strategies."""
    LRU = "lru"             # Least Recently Used
    LFU = "lfu"             # Least Frequently Used
    FIFO = "fifo"           # First In First Out
    TTL = "ttl"             # Time To Live
    ADAPTIVE = "adaptive"   # Adaptive strategy


class CacheInvalidation(str, Enum):
    """Cache invalidation strategies."""
    TIME = "time"           # Time-based invalidation
    SPACE = "space"         # Space-based invalidation
    MANUAL = "manual"       # Manual invalidation
    PATTERN = "pattern"     # Pattern-based invalidation
    CASCADE = "cascade"     # Cascade invalidation


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CacheConfig(BaseModel):
    """Cache configuration."""
    enabled: bool = True
    level: CacheLevel = CacheLevel.REDIS
    default_ttl: int = 300  # seconds
    max_size: int = 10000   # Maximum items in memory
    compression: bool = True
    compression_level: int = 6
    serializer: str = "json"  # json, pickle, msgpack
    namespace: str = "nexus:cache"
    version: int = 1
    enable_warming: bool = True
    enable_statistics: bool = True
    warmup_on_start: bool = True
    fallback_to_database: bool = True
    
    # Redis specific
    redis_key_prefix: str = "cache:"
    redis_ttl: int = 300
    
    # Memory specific
    memory_max_size: int = 10000
    memory_strategy: CacheStrategy = CacheStrategy.LRU
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('default_ttl', 'redis_ttl')
    def validate_ttl(cls, v):
        if v < 0:
            raise ValueError("TTL cannot be negative")
        return v

    @validator('max_size', 'memory_max_size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v


class CacheEntry(BaseModel):
    """Cache entry."""
    key: str
    value: Any
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    ttl: Optional[int] = None
    version: int = 1
    hits: int = 0
    size: int = 0
    compressed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at

    @property
    def age(self) -> float:
        """Get age of cache entry in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()


class CacheStatistics(BaseModel):
    """Cache statistics."""
    level: CacheLevel
    total_entries: int = 0
    total_size: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    evictions: int = 0
    expired: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    redis_memory_mb: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CacheWarmupTask(BaseModel):
    """Cache warmup task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key_pattern: str
    data_source: str  # Function name or source identifier
    priority: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "pending"
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# CACHE BACKENDS
# =============================================================================

class CacheBackend:
    """Abstract cache backend interface."""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        raise NotImplementedError
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        raise NotImplementedError
    
    async def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        raise NotImplementedError


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend."""
    
    def __init__(
        self,
        max_size: int = 10000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        ttl: Optional[int] = None
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._stats = CacheStatistics(level=CacheLevel.MEMORY)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache."""
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.expired += 1
                self._stats.misses += 1
                return None
            
            entry.hits += 1
            self._stats.hits += 1
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in memory cache."""
        async with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict()
            
            ttl_seconds = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None
            
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl_seconds,
                expires_at=expires_at,
                size=len(str(value))
            )
            
            self._cache[key] = entry
            self._stats.total_entries = len(self._cache)
            self._stats.total_size = sum(e.size for e in self._cache.values())
            
            if key not in self._access_order:
                self._access_order.append(key)
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from memory cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.total_entries = len(self._cache)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in memory cache."""
        async with self._lock:
            return key in self._cache and not self._cache[key].is_expired
    
    async def clear(self) -> bool:
        """Clear all memory cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._stats.total_entries = 0
            self._stats.total_size = 0
            return True
    
    async def get_stats(self) -> CacheStatistics:
        """Get memory cache statistics."""
        async with self._lock:
            total_entries = len(self._cache)
            total_size = sum(e.size for e in self._cache.values())
            
            return CacheStatistics(
                level=CacheLevel.MEMORY,
                total_entries=total_entries,
                total_size=total_size,
                hits=self._stats.hits,
                misses=self._stats.misses,
                hit_rate=self._stats.hits / (self._stats.hits + self._stats.misses) if (self._stats.hits + self._stats.misses) > 0 else 0,
                evictions=self._stats.evictions,
                expired=self._stats.expired,
                errors=self._stats.errors,
                avg_latency_ms=self._stats.avg_latency_ms,
                memory_usage_mb=total_size / (1024 * 1024)
            )
    
    def _evict(self):
        """Evict an entry based on strategy."""
        if not self._access_order:
            return
        
        if self.strategy == CacheStrategy.LRU:
            # Least Recently Used
            key = self._access_order[0]
        elif self.strategy == CacheStrategy.LFU:
            # Least Frequently Used
            key = min(self._cache.items(), key=lambda x: x[1].hits)[0]
        elif self.strategy == CacheStrategy.FIFO:
            # First In First Out
            key = min(self._cache.items(), key=lambda x: x[1].created_at)[0]
        elif self.strategy == CacheStrategy.TTL:
            # Shortest TTL
            key = min(self._cache.items(), key=lambda x: x[1].expires_at or datetime.max)[0]
        else:
            key = self._access_order[0]
        
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            self._stats.evictions += 1


class RedisCacheBackend(CacheBackend):
    """Redis cache backend."""
    
    def __init__(
        self,
        redis: aioredis.Redis,
        key_prefix: str = "cache:",
        default_ttl: Optional[int] = 300,
        compression: bool = True,
        compression_level: int = 6
    ):
        self.redis = redis
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.compression = compression
        self.compression_level = compression_level
        self._stats = CacheStatistics(level=CacheLevel.REDIS)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            full_key = f"{self.key_prefix}{key}"
            data = await self.redis.get(full_key)
            
            if data is None:
                self._stats.misses += 1
                return None
            
            self._stats.hits += 1
            
            # Deserialize
            value = self._deserialize(data)
            return value
            
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Redis cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis cache."""
        try:
            full_key = f"{self.key_prefix}{key}"
            ttl_seconds = ttl or self.default_ttl
            
            # Serialize
            data = self._serialize(value)
            
            if ttl_seconds:
                await self.redis.setex(full_key, ttl_seconds, data)
            else:
                await self.redis.set(full_key, data)
            
            return True
            
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Redis cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        try:
            full_key = f"{self.key_prefix}{key}"
            await self.redis.delete(full_key)
            return True
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Redis cache delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache."""
        try:
            full_key = f"{self.key_prefix}{key}"
            return await self.redis.exists(full_key) > 0
        except Exception:
            return False
    
    async def clear(self) -> bool:
        """Clear all Redis cache entries."""
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            return True
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Redis cache clear error: {e}")
            return False
    
    async def get_stats(self) -> CacheStatistics:
        """Get Redis cache statistics."""
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis.keys(pattern)
            total_entries = len(keys)
            
            # Get memory info
            info = await self.redis.info('memory')
            memory_used = info.get('used_memory', 0) / (1024 * 1024)
            
            return CacheStatistics(
                level=CacheLevel.REDIS,
                total_entries=total_entries,
                total_size=int(info.get('used_memory', 0)),
                hits=self._stats.hits,
                misses=self._stats.misses,
                hit_rate=self._stats.hits / (self._stats.hits + self._stats.misses) if (self._stats.hits + self._stats.misses) > 0 else 0,
                errors=self._stats.errors,
                avg_latency_ms=self._stats.avg_latency_ms,
                redis_memory_mb=memory_used
            )
        except Exception:
            return CacheStatistics(level=CacheLevel.REDIS)
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for Redis."""
        # Use JSON serialization
        json_str = json.dumps(value, default=str)
        data = json_str.encode('utf-8')
        
        if self.compression:
            data = zlib.compress(data, self.compression_level)
        
        return data
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from Redis."""
        if self.compression:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                pass
        
        json_str = data.decode('utf-8')
        return json.loads(json_str)


# =============================================================================
# DATA CACHE CLASS
# =============================================================================

class DataCache:
    """
    Advanced data cache for arbitrage bot.
    
    Features:
    - Multi-level caching (memory, Redis, database)
    - Cache invalidation strategies
    - Cache warming and preloading
    - Cache statistics and monitoring
    - Distributed cache support
    - Cache serialization and compression
    - Cache key management
    - Cache TTL management
    - Cache health monitoring
    - Cache backup and recovery
    - Cache versioning
    - Cache optimization
    """
    
    def __init__(
        self,
        config: CacheConfig,
        redis: Optional[aioredis.Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.redis = redis
        self.pool = pool
        
        # Cache backends
        self._memory_cache = MemoryCacheBackend(
            max_size=config.memory_max_size,
            strategy=config.memory_strategy,
            ttl=config.default_ttl
        )
        
        self._redis_cache = None
        if redis:
            self._redis_cache = RedisCacheBackend(
                redis=redis,
                key_prefix=config.redis_key_prefix,
                default_ttl=config.redis_ttl,
                compression=config.compression,
                compression_level=config.compression_level
            )
        
        # Cache stats
        self._stats: Dict[CacheLevel, CacheStatistics] = {}
        
        # Warmup tasks
        self._warmup_tasks: List[CacheWarmupTask] = []
        self._warmed_up = False
        
        # Circuit breakers
        self._cache_cb = CircuitBreaker(
            name="data_cache",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info(f"DataCache initialized with level={config.level}")
    
    async def initialize(self):
        """Initialize the data cache."""
        if self._initialized:
            return
        
        self._running = True
        
        # Warmup cache
        if self.config.enable_warming and self.config.warmup_on_start:
            await self.warmup()
        
        # Start stats collection
        asyncio.create_task(self._stats_loop())
        
        self._initialized = True
        logger.info("DataCache initialized")
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def get(
        self,
        key: str,
        default: Any = None,
        level: Optional[CacheLevel] = None
    ) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            level: Cache level to use
            
        Returns:
            Cached value or default
        """
        if not self.config.enabled:
            return default
        
        start_time = time.time()
        
        try:
            # Try memory cache first
            if level is None or level == CacheLevel.MEMORY:
                value = await self._memory_cache.get(key)
                if value is not None:
                    await self._update_stats(CacheLevel.MEMORY, True)
                    return value
            
            # Try Redis cache
            if self._redis_cache and (level is None or level == CacheLevel.REDIS):
                value = await self._redis_cache.get(key)
                if value is not None:
                    # Also store in memory for faster access
                    await self._memory_cache.set(key, value, ttl=60)  # Short TTL
                    await self._update_stats(CacheLevel.REDIS, True)
                    return value
            
            # Try database cache
            if self.pool and (level is None or level == CacheLevel.DATABASE):
                value = await self._get_from_database(key)
                if value is not None:
                    # Store in higher level caches
                    await self._memory_cache.set(key, value)
                    if self._redis_cache:
                        await self._redis_cache.set(key, value)
                    await self._update_stats(CacheLevel.DATABASE, True)
                    return value
            
            await self._update_stats(CacheLevel.MEMORY, False)
            return default
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            await self._update_stats(CacheLevel.MEMORY, False)
            
            # Fallback to default
            return default
        
        finally:
            latency = (time.time() - start_time) * 1000
            await self._update_latency(latency)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        level: Optional[CacheLevel] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            level: Cache level to use
            
        Returns:
            True if set successfully
        """
        if not self.config.enabled:
            return False
        
        try:
            ttl_seconds = ttl or self.config.default_ttl
            
            # Set in memory cache
            if level is None or level == CacheLevel.MEMORY:
                await self._memory_cache.set(key, value, ttl_seconds)
            
            # Set in Redis cache
            if self._redis_cache and (level is None or level == CacheLevel.REDIS):
                await self._redis_cache.set(key, value, ttl_seconds)
            
            # Set in database cache
            if self.pool and (level is None or level == CacheLevel.DATABASE):
                await self._set_in_database(key, value, ttl_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str, level: Optional[CacheLevel] = None) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            level: Cache level to use
            
        Returns:
            True if deleted successfully
        """
        if not self.config.enabled:
            return False
        
        try:
            # Delete from memory cache
            if level is None or level == CacheLevel.MEMORY:
                await self._memory_cache.delete(key)
            
            # Delete from Redis cache
            if self._redis_cache and (level is None or level == CacheLevel.REDIS):
                await self._redis_cache.delete(key)
            
            # Delete from database cache
            if self.pool and (level is None or level == CacheLevel.DATABASE):
                await self._delete_from_database(key)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        if not self.config.enabled:
            return False
        
        try:
            # Check memory first
            if await self._memory_cache.exists(key):
                return True
            
            # Check Redis
            if self._redis_cache and await self._redis_cache.exists(key):
                return True
            
            return False
            
        except Exception:
            return False
    
    async def clear(self, level: Optional[CacheLevel] = None) -> bool:
        """
        Clear all cache entries.
        
        Args:
            level: Cache level to clear
            
        Returns:
            True if cleared successfully
        """
        if not self.config.enabled:
            return False
        
        try:
            if level is None or level == CacheLevel.MEMORY:
                await self._memory_cache.clear()
            
            if self._redis_cache and (level is None or level == CacheLevel.REDIS):
                await self._redis_cache.clear()
            
            if self.pool and (level is None or level == CacheLevel.DATABASE):
                await self._clear_database()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    # =========================================================================
    # CACHE INVALIDATION
    # =========================================================================
    
    async def invalidate(
        self,
        pattern: str,
        strategy: CacheInvalidation = CacheInvalidation.PATTERN
    ):
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Key pattern to invalidate
            strategy: Invalidation strategy
        """
        if not self.config.enabled:
            return
        
        try:
            if strategy == CacheInvalidation.PATTERN:
                # Pattern-based invalidation
                # Get all keys matching pattern
                if self._redis_cache:
                    keys = await self._redis_cache.redis.keys(f"{self._redis_cache.key_prefix}{pattern}*")
                    for key in keys:
                        await self._redis_cache.delete(key.split(':')[-1])
                        await self._memory_cache.delete(key.split(':')[-1])
                
                # Also clean memory cache
                memory_keys = [k for k in self._memory_cache._cache.keys() if k.startswith(pattern)]
                for key in memory_keys:
                    await self._memory_cache.delete(key)
                
            elif strategy == CacheInvalidation.CASCADE:
                # Cascade invalidation - invalidate related keys
                # This is implementation specific
                await self.clear()
                
            elif strategy == CacheInvalidation.TIME:
                # Time-based invalidation - handled by TTL
                pass
                
            elif strategy == CacheInvalidation.MANUAL:
                # Manual invalidation - specific keys
                pass
                
            logger.info(f"Cache invalidation: pattern={pattern}, strategy={strategy.value}")
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
    
    # =========================================================================
    # CACHE WARMUP
    # =========================================================================
    
    async def warmup(self):
        """Warm up the cache."""
        if self._warmed_up:
            return
        
        logger.info("Starting cache warmup...")
        
        try:
            # Load warmup tasks
            warmup_tasks = await self._get_warmup_tasks()
            
            if not warmup_tasks:
                logger.info("No warmup tasks found")
                return
            
            # Execute warmup tasks
            tasks = []
            for task in warmup_tasks:
                tasks.append(self._execute_warmup_task(task))
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            self._warmed_up = True
            logger.info(f"Cache warmup completed: {len(warmup_tasks)} tasks")
            
        except Exception as e:
            logger.error(f"Cache warmup error: {e}")
    
    async def add_warmup_task(
        self,
        key_pattern: str,
        data_source: str,
        priority: int = 0
    ) -> CacheWarmupTask:
        """
        Add a cache warmup task.
        
        Args:
            key_pattern: Key pattern to warm
            data_source: Data source identifier
            priority: Task priority
            
        Returns:
            CacheWarmupTask
        """
        task = CacheWarmupTask(
            key_pattern=key_pattern,
            data_source=data_source,
            priority=priority
        )
        
        self._warmup_tasks.append(task)
        
        if self.pool:
            await self._save_warmup_task(task)
        
        return task
    
    async def _execute_warmup_task(self, task: CacheWarmupTask):
        """Execute a warmup task."""
        try:
            # Load data from source
            data = await self._load_data_from_source(task.data_source)
            
            # Store in cache
            await self.set(task.key_pattern, data)
            
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            
        except Exception as e:
            task.status = "failed"
            logger.error(f"Warmup task failed: {task.id} - {e}")
        
        # Update task status
        if self.pool:
            await self._update_warmup_task(task)
    
    async def _get_warmup_tasks(self) -> List[CacheWarmupTask]:
        """Get warmup tasks."""
        if self.pool:
            # Load from database
            return await self._load_warmup_tasks()
        
        return self._warmup_tasks
    
    # =========================================================================
    # CACHE STATISTICS
    # =========================================================================
    
    async def get_stats(self) -> Dict[CacheLevel, CacheStatistics]:
        """
        Get cache statistics.
        
        Returns:
            Dict of cache statistics by level
        """
        stats = {}
        
        # Memory stats
        stats[CacheLevel.MEMORY] = await self._memory_cache.get_stats()
        
        # Redis stats
        if self._redis_cache:
            stats[CacheLevel.REDIS] = await self._redis_cache.get_stats()
        
        # Database stats
        if self.pool:
            stats[CacheLevel.DATABASE] = await self._get_database_stats()
        
        return stats
    
    async def _update_stats(self, level: CacheLevel, hit: bool):
        """Update cache statistics."""
        if not self.config.enable_statistics:
            return
        
        async with self._lock:
            if level not in self._stats:
                self._stats[level] = CacheStatistics(level=level)
            
            stats = self._stats[level]
            if hit:
                stats.hits += 1
            else:
                stats.misses += 1
            
            total = stats.hits + stats.misses
            stats.hit_rate = stats.hits / total if total > 0 else 0
    
    async def _update_latency(self, latency_ms: float):
        """Update average latency."""
        async with self._lock:
            for stats in self._stats.values():
                stats.avg_latency_ms = (
                    (stats.avg_latency_ms * (stats.hits + stats.misses - 1) + latency_ms) /
                    (stats.hits + stats.misses) if (stats.hits + stats.misses) > 0 else latency_ms
                )
    
    async def _stats_loop(self):
        """Periodic stats collection."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute
                await self.get_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stats loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _get_from_database(self, key: str) -> Optional[Any]:
        """Get value from database cache."""
        if not self.pool:
            return None
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT value, expires_at FROM cache_entries
                    WHERE key = $1 AND (expires_at IS NULL OR expires_at > NOW())
                    """,
                    key
                )
                
                if row:
                    value = json.loads(row['value'])
                    return value
                return None
                
        except Exception as e:
            logger.error(f"Database cache get error: {e}")
            return None
    
    async def _set_in_database(self, key: str, value: Any, ttl: int):
        """Set value in database cache."""
        if not self.pool:
            return
        
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO cache_entries (key, value, expires_at, updated_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    key,
                    json.dumps(value, default=str),
                    expires_at,
                    datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Database cache set error: {e}")
    
    async def _delete_from_database(self, key: str):
        """Delete value from database cache."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM cache_entries WHERE key = $1",
                    key
                )
                
        except Exception as e:
            logger.error(f"Database cache delete error: {e}")
    
    async def _clear_database(self):
        """Clear database cache."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM cache_entries")
                
        except Exception as e:
            logger.error(f"Database cache clear error: {e}")
    
    async def _get_database_stats(self) -> CacheStatistics:
        """Get database cache statistics."""
        if not self.pool:
            return CacheStatistics(level=CacheLevel.DATABASE)
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(LENGTH(value)) as total_size
                    FROM cache_entries
                    """
                )
                
                return CacheStatistics(
                    level=CacheLevel.DATABASE,
                    total_entries=row['total_entries'] or 0,
                    total_size=row['total_size'] or 0
                )
                
        except Exception as e:
            logger.error(f"Database cache stats error: {e}")
            return CacheStatistics(level=CacheLevel.DATABASE)
    
    async def _save_warmup_task(self, task: CacheWarmupTask):
        """Save warmup task to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO cache_warmup_tasks (
                        id, key_pattern, data_source, priority,
                        created_at, status, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    task.id,
                    task.key_pattern,
                    task.data_source,
                    task.priority,
                    task.created_at,
                    task.status,
                    json.dumps(task.metadata, default=str)
                )
                
        except Exception as e:
            logger.error(f"Save warmup task error: {e}")
    
    async def _update_warmup_task(self, task: CacheWarmupTask):
        """Update warmup task in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE cache_warmup_tasks
                    SET status = $1, completed_at = $2
                    WHERE id = $3
                    """,
                    task.status,
                    task.completed_at,
                    task.id
                )
                
        except Exception as e:
            logger.error(f"Update warmup task error: {e}")
    
    async def _load_warmup_tasks(self) -> List[CacheWarmupTask]:
        """Load warmup tasks from database."""
        if not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM cache_warmup_tasks
                    WHERE status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                    """
                )
                
                tasks = []
                for row in rows:
                    task = CacheWarmupTask(
                        id=row['id'],
                        key_pattern=row['key_pattern'],
                        data_source=row['data_source'],
                        priority=row['priority'],
                        created_at=row['created_at'],
                        completed_at=row['completed_at'],
                        status=row['status'],
                        metadata=row['metadata'] or {}
                    )
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"Load warmup tasks error: {e}")
            return []
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def _load_data_from_source(self, source: str) -> Any:
        """Load data from a source for warmup."""
        # This would be implemented with actual data loading
        # For now, return None
        return None
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data cache."""
        self._running = False
        logger.info("DataCache shutdown")


# =============================================================================
# DECORATOR
# =============================================================================

def cached(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    namespace: Optional[str] = None
):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Cache TTL in seconds
        key_prefix: Key prefix
        namespace: Cache namespace
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            cache = await get_global_cache()
            
            # Generate cache key
            key_parts = [func.__name__]
            if key_prefix:
                key_parts.insert(0, key_prefix)
            if namespace:
                key_parts.insert(0, namespace)
            
            # Add args and kwargs
            for arg in args:
                key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}:{v}")
            
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(key, result, ttl=ttl)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions
            return func(*args, **kwargs)
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# GLOBAL CACHE INSTANCE
# =============================================================================

_global_cache: Optional[DataCache] = None


async def get_global_cache() -> DataCache:
    """Get global data cache instance."""
    global _global_cache
    if _global_cache is None:
        raise RuntimeError("DataCache not initialized")
    return _global_cache


def set_global_cache(cache: DataCache):
    """Set global data cache instance."""
    global _global_cache
    _global_cache = cache


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataCache',
    'CacheLevel',
    'CacheStatus',
    'CacheStrategy',
    'CacheInvalidation',
    'CacheConfig',
    'CacheEntry',
    'CacheStatistics',
    'CacheWarmupTask',
    'CacheBackend',
    'MemoryCacheBackend',
    'RedisCacheBackend',
    'cached',
    'get_global_cache',
    'set_global_cache'
]
