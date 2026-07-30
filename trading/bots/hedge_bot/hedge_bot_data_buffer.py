# trading/bots/hedge_bot/hedge_bot_data_buffer.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Buffer Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Buffer Module

This module provides comprehensive data buffering and caching capabilities
for the NEXUS Hedge Bot system. It manages data flow, buffering strategies,
and memory optimization.

The module covers:
- Data Buffering
- Data Caching
- Memory Management
- Buffer Strategies
- Data Flow Control
- Cache Invalidation
- Buffer Optimization
- Memory Pooling
- Data Prefetching
- Buffer Monitoring
"""

import os
import sys
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable, Generator
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import queue
import weakref

logger = logging.getLogger(__name__)


# ============================================================
# DATA BUFFER ENUMS
# ============================================================

class BufferStrategy(Enum):
    """Buffer strategies"""
    FIFO = "fifo"
    LIFO = "lifo"
    LEAST_RECENTLY_USED = "lru"
    MOST_RECENTLY_USED = "mru"
    SIZE_BASED = "size_based"
    TIME_BASED = "time_based"
    ADAPTIVE = "adaptive"


class BufferStatus(Enum):
    """Buffer status"""
    EMPTY = "empty"
    PARTIAL = "partial"
    FULL = "full"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"


class CacheLevel(Enum):
    """Cache levels"""
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"
    DISK = "disk"


@dataclass
class BufferConfig:
    """Buffer configuration"""
    id: str
    name: str
    strategy: BufferStrategy
    max_size: int
    max_age_seconds: int = 300
    batch_size: int = 100
    cache_level: CacheLevel = CacheLevel.L1
    compressed: bool = False
    persistent: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy.value,
            "max_size": self.max_size,
            "max_age_seconds": self.max_age_seconds,
            "batch_size": self.batch_size,
            "cache_level": self.cache_level.value,
            "compressed": self.compressed,
            "persistent": self.persistent,
        }


@dataclass
class BufferStats:
    """Buffer statistics"""
    name: str
    current_size: int
    max_size: int
    utilization: float
    hits: int
    misses: int
    hit_rate: float
    evictions: int
    avg_age: float
    status: BufferStatus
    last_access: datetime
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "utilization": self.utilization,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "evictions": self.evictions,
            "avg_age": self.avg_age,
            "status": self.status.value,
            "last_access": self.last_access.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BufferItem:
    """Buffer item"""
    id: str
    data: Any
    timestamp: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata,
            "size": self.size,
        }


# ============================================================
# DATA BUFFER ENGINE
# ============================================================

class DataBufferEngine:
    """
    Comprehensive data buffer engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data buffer engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_max_size = self.config.get("default_max_size", 1000)
        self.default_max_age = self.config.get("default_max_age", 300)
        self.default_strategy = self.config.get("default_strategy", BufferStrategy.LRU)
        
        # State
        self.buffers: Dict[str, Dict[str, BufferItem]] = {}
        self.configs: Dict[str, BufferConfig] = {}
        self.stats: Dict[str, BufferStats] = {}
        self.locks: Dict[str, threading.Lock] = {}
        
        # Access tracking
        self.access_history: Dict[str, List[datetime]] = {}
        
        logger.info("Data buffer engine initialized")
    
    # ============================================================
    # BUFFER CONFIGURATION
    # ============================================================
    
    def create_buffer(
        self,
        name: str,
        max_size: Optional[int] = None,
        strategy: Optional[BufferStrategy] = None,
        max_age_seconds: int = 300,
        batch_size: int = 100,
        cache_level: CacheLevel = CacheLevel.L1,
        compressed: bool = False,
        persistent: bool = False
    ) -> BufferConfig:
        """
        Create a buffer
        
        Args:
            name: Buffer name
            max_size: Maximum size
            strategy: Buffer strategy
            max_age_seconds: Maximum age in seconds
            batch_size: Batch size
            cache_level: Cache level
            compressed: Enable compression
            persistent: Enable persistence
            
        Returns:
            BufferConfig
        """
        if max_size is None:
            max_size = self.default_max_size
        if strategy is None:
            strategy = self.default_strategy
        
        config = BufferConfig(
            id=f"buffer_{int(time.time())}_{name}",
            name=name,
            strategy=strategy,
            max_size=max_size,
            max_age_seconds=max_age_seconds,
            batch_size=batch_size,
            cache_level=cache_level,
            compressed=compressed,
            persistent=persistent,
        )
        
        self.configs[name] = config
        self.buffers[name] = {}
        self.locks[name] = threading.Lock()
        self.access_history[name] = []
        
        # Initialize stats
        self.stats[name] = BufferStats(
            name=name,
            current_size=0,
            max_size=max_size,
            utilization=0.0,
            hits=0,
            misses=0,
            hit_rate=0.0,
            evictions=0,
            avg_age=0.0,
            status=BufferStatus.EMPTY,
            last_access=datetime.now(),
            created_at=datetime.now(),
        )
        
        logger.info(f"Created buffer: {name}")
        return config
    
    def delete_buffer(self, name: str) -> bool:
        """
        Delete a buffer
        
        Args:
            name: Buffer name
            
        Returns:
            True if deleted
        """
        if name in self.buffers:
            with self.locks[name]:
                self.buffers[name].clear()
                del self.buffers[name]
                del self.configs[name]
                del self.locks[name]
                del self.stats[name]
                del self.access_history[name]
            logger.info(f"Deleted buffer: {name}")
            return True
        return False
    
    def get_buffer_config(self, name: str) -> Optional[BufferConfig]:
        """
        Get buffer configuration
        
        Args:
            name: Buffer name
            
        Returns:
            BufferConfig or None
        """
        return self.configs.get(name)
    
    def get_buffer_stats(self, name: str) -> Optional[BufferStats]:
        """
        Get buffer statistics
        
        Args:
            name: Buffer name
            
        Returns:
            BufferStats or None
        """
        return self.stats.get(name)
    
    # ============================================================
    # DATA OPERATIONS
    # ============================================================
    
    def put(
        self,
        buffer_name: str,
        item_id: str,
        data: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Put data into buffer
        
        Args:
            buffer_name: Buffer name
            item_id: Item ID
            data: Data to store
            ttl: Time to live in seconds
            metadata: Additional metadata
            
        Returns:
            True if stored
        """
        config = self.configs.get(buffer_name)
        if not config:
            raise ValueError(f"Buffer not found: {buffer_name}")
        
        with self.locks[buffer_name]:
            buffer = self.buffers[buffer_name]
            
            # Check if buffer is full
            if len(buffer) >= config.max_size:
                self._evict_item(buffer_name)
            
            # Create item
            timestamp = datetime.now()
            expires_at = timestamp + timedelta(seconds=ttl) if ttl else None
            
            item = BufferItem(
                id=item_id,
                data=data,
                timestamp=timestamp,
                expires_at=expires_at,
                metadata=metadata or {},
                size=len(str(data).encode()) if isinstance(data, str) else 1,
            )
            
            # Store item
            buffer[item_id] = item
            
            # Update stats
            self._update_stats(buffer_name)
            
            return True
    
    def get(self, buffer_name: str, item_id: str) -> Optional[Any]:
        """
        Get data from buffer
        
        Args:
            buffer_name: Buffer name
            item_id: Item ID
            
        Returns:
            Data or None
        """
        config = self.configs.get(buffer_name)
        if not config:
            raise ValueError(f"Buffer not found: {buffer_name}")
        
        with self.locks[buffer_name]:
            buffer = self.buffers[buffer_name]
            
            if item_id not in buffer:
                self.stats[buffer_name].misses += 1
                self._update_stats(buffer_name)
                return None
            
            item = buffer[item_id]
            
            # Check expiry
            if item.expires_at and item.expires_at < datetime.now():
                del buffer[item_id]
                self.stats[buffer_name].misses += 1
                self._update_stats(buffer_name)
                return None
            
            # Update access
            item.access_count += 1
            item.last_accessed = datetime.now()
            
            # Update access history
            self.access_history[buffer_name].append(datetime.now())
            if len(self.access_history[buffer_name]) > 1000:
                self.access_history[buffer_name] = self.access_history[buffer_name][-1000:]
            
            self.stats[buffer_name].hits += 1
            self._update_stats(buffer_name)
            
            return item.data
    
    def remove(self, buffer_name: str, item_id: str) -> bool:
        """
        Remove item from buffer
        
        Args:
            buffer_name: Buffer name
            item_id: Item ID
            
        Returns:
            True if removed
        """
        with self.locks[buffer_name]:
            buffer = self.buffers[buffer_name]
            if item_id in buffer:
                del buffer[item_id]
                self._update_stats(buffer_name)
                return True
        return False
    
    def clear(self, buffer_name: str) -> None:
        """
        Clear buffer
        
        Args:
            buffer_name: Buffer name
        """
        with self.locks[buffer_name]:
            self.buffers[buffer_name].clear()
            self._update_stats(buffer_name)
    
    def _evict_item(self, buffer_name: str) -> None:
        """
        Evict item based on strategy
        
        Args:
            buffer_name: Buffer name
        """
        config = self.configs.get(buffer_name)
        if not config:
            return
        
        buffer = self.buffers[buffer_name]
        if not buffer:
            return
        
        # Evict based on strategy
        if config.strategy == BufferStrategy.FIFO:
            # Evict oldest
            oldest = min(buffer.items(), key=lambda x: x[1].timestamp)
            del buffer[oldest[0]]
            
        elif config.strategy == BufferStrategy.LIFO:
            # Evict newest
            newest = max(buffer.items(), key=lambda x: x[1].timestamp)
            del buffer[newest[0]]
            
        elif config.strategy == BufferStrategy.LRU:
            # Evict least recently used
            lru = min(buffer.items(), key=lambda x: x[1].last_accessed)
            del buffer[lru[0]]
            
        elif config.strategy == BufferStrategy.MRU:
            # Evict most recently used
            mru = max(buffer.items(), key=lambda x: x[1].last_accessed)
            del buffer[mru[0]]
            
        elif config.strategy == BufferStrategy.TIME_BASED:
            # Evict expired items
            now = datetime.now()
            expired = [k for k, v in buffer.items() if v.expires_at and v.expires_at < now]
            for k in expired:
                del buffer[k]
            if not expired:
                # Fallback to FIFO
                oldest = min(buffer.items(), key=lambda x: x[1].timestamp)
                del buffer[oldest[0]]
        
        self.stats[buffer_name].evictions += 1
        self._update_stats(buffer_name)
    
    def _update_stats(self, buffer_name: str) -> None:
        """
        Update buffer statistics
        
        Args:
            buffer_name: Buffer name
        """
        config = self.configs.get(buffer_name)
        if not config:
            return
        
        buffer = self.buffers[buffer_name]
        stats = self.stats[buffer_name]
        
        current_size = len(buffer)
        stats.current_size = current_size
        stats.utilization = current_size / config.max_size if config.max_size > 0 else 0
        
        # Determine status
        if current_size == 0:
            stats.status = BufferStatus.EMPTY
        elif current_size >= config.max_size:
            stats.status = BufferStatus.FULL
        elif current_size > config.max_size:
            stats.status = BufferStatus.OVERFLOW
        else:
            stats.status = BufferStatus.PARTIAL
        
        # Calculate hit rate
        total = stats.hits + stats.misses
        stats.hit_rate = stats.hits / total if total > 0 else 0
        
        # Calculate average age
        if current_size > 0:
            ages = [(datetime.now() - v.timestamp).total_seconds() for v in buffer.values()]
            stats.avg_age = sum(ages) / len(ages) if ages else 0
        
        stats.last_access = datetime.now()
    
    # ============================================================
    # BUFFER ANALYSIS
    # ============================================================
    
    def analyze_buffer(self, buffer_name: str) -> Dict[str, Any]:
        """
        Analyze buffer performance
        
        Args:
            buffer_name: Buffer name
            
        Returns:
            Analysis results
        """
        config = self.configs.get(buffer_name)
        if not config:
            return {}
        
        buffer = self.buffers[buffer_name]
        stats = self.stats[buffer_name]
        
        # Analyze access patterns
        access_history = self.access_history.get(buffer_name, [])
        if len(access_history) > 1:
            time_diffs = [(access_history[i] - access_history[i-1]).total_seconds() 
                         for i in range(1, len(access_history))]
            avg_interval = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        else:
            avg_interval = 0
        
        # Analyze item sizes
        sizes = [v.size for v in buffer.values()]
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        
        # Analyze item ages
        ages = [(datetime.now() - v.timestamp).total_seconds() for v in buffer.values()]
        avg_age = sum(ages) / len(ages) if ages else 0
        
        return {
            "name": buffer_name,
            "config": config.to_dict(),
            "stats": stats.to_dict(),
            "analysis": {
                "avg_item_age": avg_age,
                "avg_item_size": avg_size,
                "avg_access_interval": avg_interval,
                "access_frequency": len(access_history),
                "hit_rate": stats.hit_rate,
                "eviction_rate": stats.evictions / max(1, stats.hits + stats.misses),
            }
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get buffer statistics
        
        Returns:
            Statistics dictionary
        """
        total_size = sum(len(b) for b in self.buffers.values())
        total_hits = sum(s.hits for s in self.stats.values())
        total_misses = sum(s.misses for s in self.stats.values())
        
        return {
            "total_buffers": len(self.buffers),
            "total_items": total_size,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0,
            "buffers": [self.stats[name].to_dict() for name in self.buffers.keys()],
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BufferStrategy",
    "BufferStatus",
    "CacheLevel",
    
    # Dataclasses
    "BufferConfig",
    "BufferStats",
    "BufferItem",
    
    # Classes
    "DataBufferEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
