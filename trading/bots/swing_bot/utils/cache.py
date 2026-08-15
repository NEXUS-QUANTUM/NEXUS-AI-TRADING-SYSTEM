"""
Swing Bot Cache Utilities Module
==================================

This module provides caching utilities for the Swing Bot trading system.
Includes memory cache, disk cache, and distributed cache implementations.
"""

import time
import json
import pickle
import hashlib
import threading
import asyncio
import functools
from typing import Any, Dict, Optional, Union, List, Callable, TypeVar
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
import redis
import diskcache
from collections import OrderedDict


T = TypeVar('T')


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = 0.0
    size: int = 0


@dataclass
class CacheStats:
    """Cache statistics."""
    size: int = 0
    max_size: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    hit_rate: float = 0.0
    avg_get_time: float = 0.0
    avg_set_time: float = 0.0


class BaseCache:
    """Base cache class."""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._lock = threading.RLock()
        self._stats = CacheStats(max_size=max_size)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        raise NotImplementedError
    
    def clear(self) -> None:
        """Clear all values from the cache."""
        raise NotImplementedError
    
    def has(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        raise NotImplementedError
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats


class MemoryCache(BaseCache):
    """
    In-memory cache implementation.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = 300):
        super().__init__(max_size, default_ttl)
        self._cache: Dict[str, CacheEntry] = {}
        self._order = OrderedDict()
        self._cleanup_thread = None
        self._stop_cleanup = False
        self._start_cleanup()
    
    def _start_cleanup(self) -> None:
        """Start the cleanup thread."""
        def cleanup():
            while not self._stop_cleanup:
                time.sleep(60)  # Run every minute
                self._cleanup_expired()
        
        self._cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and entry.expires_at < time.time()
            ]
            for key in expired_keys:
                del self._cache[key]
                if key in self._order:
                    del self._order[key]
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full."""
        if len(self._cache) >= self.max_size:
            # Remove oldest 10% of entries
            evict_count = max(1, int(self.max_size * 0.1))
            for _ in range(evict_count):
                if self._order:
                    oldest_key, _ = self._order.popitem(last=False)
                    if oldest_key in self._cache:
                        del self._cache[oldest_key]
                        self._stats.evictions += 1
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                # Check if expired
                if entry.expires_at and entry.expires_at < time.time():
                    del self._cache[key]
                    if key in self._order:
                        del self._order[key]
                    self._stats.misses += 1
                    return default
                
                # Update metadata
                entry.access_count += 1
                entry.last_accessed = time.time()
                
                # Move to end of order (most recent)
                if key in self._order:
                    del self._order[key]
                self._order[key] = key
                
                self._stats.hits += 1
                return entry.value
            
            self._stats.misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        with self._lock:
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl else None
            
            # Create entry
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                expires_at=expires_at,
                size=len(str(value)) if value else 0
            )
            
            # Add to cache
            self._cache[key] = entry
            self._order[key] = key
            
            # Evict if needed
            self._evict_if_needed()
            
            self._stats.size = len(self._cache)
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._order:
                    del self._order[key]
                self._stats.size = len(self._cache)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all values from the cache."""
        with self._lock:
            self._cache.clear()
            self._order.clear()
            self._stats.size = 0
    
    def has(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        with self._lock:
            return key in self._cache
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.hit_rate = (
                self._stats.hits / (self._stats.hits + self._stats.misses)
                if (self._stats.hits + self._stats.misses) > 0 else 0
            )
            return self._stats
    
    def __del__(self):
        """Clean up resources."""
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1)


class DiskCache(BaseCache):
    """
    Disk-based cache implementation.
    """
    
    def __init__(
        self,
        cache_dir: Union[str, Path] = '.cache',
        max_size: int = 1000,
        default_ttl: Optional[int] = 300,
        max_disk_size: int = 1024 * 1024 * 1024  # 1GB
    ):
        super().__init__(max_size, default_ttl)
        self.cache_dir = Path(cache_dir)
        self.max_disk_size = max_disk_size
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(self.cache_dir))
    
    def _get_key_hash(self, key: str) -> str:
        """Get hash of key for disk storage."""
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        try:
            value = self._cache.get(key)
            if value is None:
                self._stats.misses += 1
                return default
            
            self._stats.hits += 1
            return value
        except Exception:
            self._stats.misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        try:
            ttl = ttl or self.default_ttl
            
            # Check disk size
            if self._check_disk_size():
                self._cache.expire()
            
            self._cache.set(key, value, expire=ttl)
            self._stats.size = len(self._cache)
        except Exception:
            pass
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        try:
            result = self._cache.delete(key)
            self._stats.size = len(self._cache)
            return result
        except Exception:
            return False
    
    def clear(self) -> None:
        """Clear all values from the cache."""
        try:
            self._cache.clear()
            self._stats.size = 0
        except Exception:
            pass
    
    def has(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        try:
            return key in self._cache
        except Exception:
            return False
    
    def _check_disk_size(self) -> bool:
        """Check if disk size exceeds limit."""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob('**/*') if f.is_file())
            return total_size > self.max_disk_size
        except Exception:
            return False
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        try:
            self._stats.size = len(self._cache)
            self._stats.hit_rate = (
                self._stats.hits / (self._stats.hits + self._stats.misses)
                if (self._stats.hits + self._stats.misses) > 0 else 0
            )
        except Exception:
            pass
        return self._stats


class DistributedCache(BaseCache):
    """
    Distributed cache using Redis.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = 'cache:',
        default_ttl: Optional[int] = 300,
        max_size: int = 1000
    ):
        super().__init__(max_size, default_ttl)
        self.redis = redis_client
        self.key_prefix = key_prefix
        self._stats = CacheStats()
    
    def _get_redis_key(self, key: str) -> str:
        """Get Redis key with prefix."""
        return f"{self.key_prefix}{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache."""
        try:
            value = self.redis.get(self._get_redis_key(key))
            if value is None:
                self._stats.misses += 1
                return default
            
            # Try to deserialize
            try:
                result = pickle.loads(value)
                self._stats.hits += 1
                return result
            except Exception:
                self._stats.misses += 1
                return default
        except Exception:
            self._stats.misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        try:
            ttl = ttl or self.default_ttl
            serialized = pickle.dumps(value)
            if ttl:
                self.redis.setex(self._get_redis_key(key), ttl, serialized)
            else:
                self.redis.set(self._get_redis_key(key), serialized)
            self._stats.size += 1
        except Exception:
            pass
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        try:
            result = self.redis.delete(self._get_redis_key(key))
            if result:
                self._stats.size -= 1
            return bool(result)
        except Exception:
            return False
    
    def clear(self) -> None:
        """Clear all values from the cache."""
        try:
            # Delete all keys with prefix
            keys = self.redis.keys(f"{self.key_prefix}*")
            if keys:
                self.redis.delete(*keys)
            self._stats.size = 0
        except Exception:
            pass
    
    def has(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        try:
            return self.redis.exists(self._get_redis_key(key)) > 0
        except Exception:
            return False
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        try:
            self._stats.size = len(self.redis.keys(f"{self.key_prefix}*"))
            self._stats.hit_rate = (
                self._stats.hits / (self._stats.hits + self._stats.misses)
                if (self._stats.hits + self._stats.misses) > 0 else 0
            )
        except Exception:
            pass
        return self._stats


def cached(
    cache: Optional[BaseCache] = None,
    ttl: Optional[int] = None,
    key_prefix: str = ''
):
    """
    Decorator to cache function results.
    
    Args:
        cache: Cache instance (creates MemoryCache if None)
        ttl: Time-to-live in seconds
        key_prefix: Key prefix for cache keys
    
    Returns:
        Decorated function
    """
    if cache is None:
        cache = MemoryCache()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            
            # Add positional arguments
            for arg in args:
                key_parts.append(str(arg))
            
            # Add keyword arguments (sorted)
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}:{kwargs[k]}")
            
            key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


def async_cached(
    cache: Optional[BaseCache] = None,
    ttl: Optional[int] = None,
    key_prefix: str = ''
):
    """
    Decorator to cache async function results.
    
    Args:
        cache: Cache instance (creates MemoryCache if None)
        ttl: Time-to-live in seconds
        key_prefix: Key prefix for cache keys
    
    Returns:
        Decorated async function
    """
    if cache is None:
        cache = MemoryCache()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            
            # Add positional arguments
            for arg in args:
                key_parts.append(str(arg))
            
            # Add keyword arguments (sorted)
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}:{kwargs[k]}")
            
            key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Compute and cache
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


__all__ = [
    # Classes
    'CacheEntry',
    'CacheStats',
    'BaseCache',
    'MemoryCache',
    'DiskCache',
    'DistributedCache',
    
    # Decorators
    'cached',
    'async_cached',
]
