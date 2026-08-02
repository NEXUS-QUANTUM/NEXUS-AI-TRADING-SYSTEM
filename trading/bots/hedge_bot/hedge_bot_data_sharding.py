# trading/bots/hedge_bot/hedge_bot_data_sharding.py

import asyncio
import logging
import time
import json
import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class ShardStrategy(str, Enum):
    RANGE = "range"
    HASH = "hash"
    MODULO = "modulo"
    CONSISTENT = "consistent"
    ROUND_ROBIN = "round_robin"
    DYNAMIC = "dynamic"
    KEY = "key"
    COMPOSITE = "composite"
    TIME_BASED = "time_based"
    GEO = "geo"


class ShardStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REBALANCING = "rebalancing"
    DRAINING = "draining"
    INITIALIZING = "initializing"
    ERROR = "error"
    READONLY = "readonly"


@dataclass
class Shard:
    id: str
    name: str
    key: str
    status: ShardStatus
    size: int
    capacity: int
    load: float
    location: str
    created_at: float
    updated_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    range_start: Optional[Any] = None
    range_end: Optional[Any] = None
    hash_range: Optional[Tuple[int, int]] = None
    replica_ids: List[str] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ShardConfig:
    id: str
    name: str
    strategy: ShardStrategy
    num_shards: int
    shard_key: str
    replication_factor: int = 1
    min_shard_size: int = 1024 * 1024
    max_shard_size: int = 1024 * 1024 * 100
    rebalance_threshold: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShardData:
    id: str
    shard_id: str
    key: str
    value: Any
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShardOperation:
    id: str
    shard_id: str
    type: str
    data: Any
    timestamp: float
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShardStats:
    shard_id: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_latency: float
    max_latency: float
    min_latency: float
    current_load: float
    storage_used: int
    storage_capacity: int
    active_connections: int
    last_updated: float


class DataShardingManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._shards: Dict[str, Shard] = {}
        self._configs: Dict[str, ShardConfig] = {}
        self._data: Dict[str, Dict[str, ShardData]] = defaultdict(dict)
        self._operations: Dict[str, ShardOperation] = {}
        self._stats: Dict[str, ShardStats] = {}
        self._consistency_rings: Dict[str, List[str]] = {}
        self._hash_ring: Dict[str, Dict[int, str]] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_configs()

    def _initialize_default_configs(self) -> None:
        default_configs = [
            ShardConfig(
                id="trading_data",
                name="Trading Data Shard",
                strategy=ShardStrategy.HASH,
                num_shards=10,
                shard_key="symbol",
                replication_factor=2
            ),
            ShardConfig(
                id="historical_data",
                name="Historical Data Shard",
                strategy=ShardStrategy.TIME_BASED,
                num_shards=12,
                shard_key="timestamp",
                replication_factor=1
            ),
            ShardConfig(
                id="user_data",
                name="User Data Shard",
                strategy=ShardStrategy.KEY,
                num_shards=8,
                shard_key="user_id",
                replication_factor=2
            )
        ]
        
        for config in default_configs:
            self._configs[config.id] = config

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_shard_config(
        self,
        name: str,
        strategy: ShardStrategy,
        num_shards: int,
        shard_key: str,
        replication_factor: int = 1,
        min_shard_size: int = 1024 * 1024,
        max_shard_size: int = 1024 * 1024 * 100,
        rebalance_threshold: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ShardConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = ShardConfig(
                id=config_id,
                name=name,
                strategy=strategy,
                num_shards=num_shards,
                shard_key=shard_key,
                replication_factor=replication_factor,
                min_shard_size=min_shard_size,
                max_shard_size=max_shard_size,
                rebalance_threshold=rebalance_threshold,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            await self._initialize_shards(config)
            await self._notify_observers("config_created", config)
            
            return config

    async def _initialize_shards(self, config: ShardConfig) -> None:
        for i in range(config.num_shards):
            shard_id = hashlib.md5(f"{config.id}_{i}_{time.time()}".encode()).hexdigest()
            
            shard = Shard(
                id=shard_id,
                name=f"{config.name}_shard_{i}",
                key=config.shard_key,
                status=ShardStatus.INITIALIZING,
                size=0,
                capacity=config.max_shard_size,
                load=0.0,
                location=f"node_{i % 3}",
                created_at=time.time(),
                updated_at=time.time(),
                metadata=config.metadata
            )
            
            self._shards[shard_id] = shard
            self._stats[shard_id] = ShardStats(
                shard_id=shard_id,
                total_operations=0,
                successful_operations=0,
                failed_operations=0,
                avg_latency=0,
                max_latency=0,
                min_latency=0,
                current_load=0,
                storage_used=0,
                storage_capacity=config.max_shard_size,
                active_connections=0,
                last_updated=time.time()
            )
            
            shard.status = ShardStatus.ACTIVE
        
        await self._build_consistency_ring(config)

    async def _build_consistency_ring(self, config: ShardConfig) -> None:
        ring = []
        shard_ids = list(self._shards.keys())
        
        for i, shard_id in enumerate(shard_ids):
            ring.append(shard_id)
        
        self._consistency_rings[config.id] = ring
        
        if config.strategy == ShardStrategy.CONSISTENT:
            hash_ring = {}
            for shard_id in shard_ids:
                for j in range(100):
                    hash_key = hashlib.md5(f"{shard_id}_{j}".encode()).hexdigest()
                    hash_val = int(hash_key[:8], 16)
                    hash_ring[hash_val] = shard_id
            self._hash_ring[config.id] = hash_ring

    async def get_shard(
        self,
        config_id: str,
        key: Any,
        operation: str = "read"
    ) -> Optional[Shard]:
        if config_id not in self._configs:
            return None
        
        config = self._configs[config_id]
        
        if config.strategy == ShardStrategy.HASH:
            return await self._get_shard_hash(config, key)
        elif config.strategy == ShardStrategy.MODULO:
            return await self._get_shard_modulo(config, key)
        elif config.strategy == ShardStrategy.RANGE:
            return await self._get_shard_range(config, key)
        elif config.strategy == ShardStrategy.CONSISTENT:
            return await self._get_shard_consistent(config, key)
        elif config.strategy == ShardStrategy.ROUND_ROBIN:
            return await self._get_shard_round_robin(config, key)
        elif config.strategy == ShardStrategy.KEY:
            return await self._get_shard_key(config, key)
        elif config.strategy == ShardStrategy.TIME_BASED:
            return await self._get_shard_time(config, key)
        elif config.strategy == ShardStrategy.COMPOSITE:
            return await self._get_shard_composite(config, key)
        
        return None

    async def _get_shard_hash(self, config: ShardConfig, key: Any) -> Shard:
        hash_val = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        idx = hash_val % config.num_shards
        
        shard_ids = [s for s in self._shards.values() if s.key == config.shard_key]
        if idx < len(shard_ids):
            return shard_ids[idx]
        
        return None

    async def _get_shard_modulo(self, config: ShardConfig, key: Any) -> Shard:
        idx = int(str(key) if isinstance(key, (int, float)) else hash(str(key))) % config.num_shards
        
        shard_ids = [s for s in self._shards.values() if s.key == config.shard_key]
        if idx < len(shard_ids):
            return shard_ids[idx]
        
        return None

    async def _get_shard_range(self, config: ShardConfig, key: Any) -> Shard:
        shards = [s for s in self._shards.values() if s.key == config.shard_key]
        for shard in shards:
            if shard.range_start is not None and shard.range_end is not None:
                if shard.range_start <= key <= shard.range_end:
                    return shard
        return shards[0] if shards else None

    async def _get_shard_consistent(self, config: ShardConfig, key: Any) -> Shard:
        hash_val = hashlib.md5(str(key).encode()).hexdigest()
        hash_int = int(hash_val[:8], 16)
        
        hash_ring = self._hash_ring.get(config.id, {})
        if not hash_ring:
            shards = [s for s in self._shards.values() if s.key == config.shard_key]
            return shards[0] if shards else None
        
        # Find first node with hash >= hash_int
        sorted_keys = sorted(hash_ring.keys())
        for ring_hash in sorted_keys:
            if ring_hash >= hash_int:
                return self._shards.get(hash_ring[ring_hash])
        
        # Wrap around
        return self._shards.get(hash_ring[sorted_keys[0]])

    async def _get_shard_round_robin(self, config: ShardConfig, key: Any) -> Shard:
        shards = [s for s in self._shards.values() if s.key == config.shard_key]
        
        if not shards:
            return None
        
        idx = int(time.time()) % len(shards)
        return shards[idx]

    async def _get_shard_key(self, config: ShardConfig, key: Any) -> Shard:
        shards = [s for s in self._shards.values() if s.key == config.shard_key]
        
        for shard in shards:
            if shard.key == str(key):
                return shard
        
        return shards[0] if shards else None

    async def _get_shard_time(self, config: ShardConfig, key: Any) -> Shard:
        timestamp = key if isinstance(key, (int, float)) else time.time()
        
        # Group by hour/day/month
        period = config.metadata.get("period", "day")
        if period == "hour":
            period_key = int(timestamp / 3600)
        elif period == "day":
            period_key = int(timestamp / 86400)
        elif period == "month":
            period_key = int(timestamp / 2592000)
        else:
            period_key = int(timestamp / 86400)
        
        idx = period_key % config.num_shards
        
        shards = [s for s in self._shards.values() if s.key == config.shard_key]
        if idx < len(shards):
            return shards[idx]
        
        return shards[0] if shards else None

    async def _get_shard_composite(self, config: ShardConfig, key: Any) -> Shard:
        composite_key = config.metadata.get("composite_keys", [])
        composite_value = ""
        
        if isinstance(key, dict):
            for k in composite_key:
                composite_value += str(key.get(k, ""))
        else:
            composite_value = str(key)
        
        hash_val = hashlib.md5(composite_value.encode()).hexdigest()
        idx = int(hash_val[:8], 16) % config.num_shards
        
        shards = [s for s in self._shards.values() if s.key == config.shard_key]
        if idx < len(shards):
            return shards[idx]
        
        return shards[0] if shards else None

    async def store_data(
        self,
        config_id: str,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ShardData]:
        shard = await self.get_shard(config_id, key, "write")
        if not shard:
            return None
        
        data_id = hashlib.md5(f"{shard.id}_{key}_{time.time()}".encode()).hexdigest()
        
        data = ShardData(
            id=data_id,
            shard_id=shard.id,
            key=key,
            value=value,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self._data[shard.id][key] = data
        shard.size += len(str(value))
        shard.updated_at = time.time()
        
        await self._update_stats(shard.id, "write", 0.1, True)
        await self._notify_observers("data_stored", data)
        
        # Replicate if needed
        config = self._configs[config_id]
        if config.replication_factor > 1:
            await self._replicate_data(config_id, data)
        
        return data

    async def _replicate_data(self, config_id: str, data: ShardData) -> None:
        replicas = self._consistency_rings.get(config_id, [])
        replicas = [r for r in replicas if r != data.shard_id]
        
        for replica_id in replicas[:self._configs[config_id].replication_factor - 1]:
            if replica_id in self._shards:
                replica_shard = self._shards[replica_id]
                replica_data = ShardData(
                    id=data.id,
                    shard_id=replica_shard.id,
                    key=data.key,
                    value=data.value,
                    timestamp=data.timestamp,
                    metadata=data.metadata
                )
                self._data[replica_shard.id][data.key] = replica_data
                replica_shard.size += len(str(data.value))
                replica_shard.updated_at = time.time()

    async def read_data(self, config_id: str, key: str) -> Optional[ShardData]:
        shard = await self.get_shard(config_id, key, "read")
        if not shard:
            return None
        
        data = self._data.get(shard.id, {}).get(key)
        
        if data:
            await self._update_stats(shard.id, "read", 0.05, True)
        
        return data

    async def delete_data(self, config_id: str, key: str) -> bool:
        shard = await self.get_shard(config_id, key, "delete")
        if not shard:
            return False
        
        if key in self._data.get(shard.id, {}):
            del self._data[shard.id][key]
            shard.size -= len(str(key))
            shard.updated_at = time.time()
            
            await self._update_stats(shard.id, "delete", 0.05, True)
            await self._notify_observers("data_deleted", shard.id, key)
            
            return True
        
        return False

    async def _update_stats(
        self,
        shard_id: str,
        operation: str,
        latency: float,
        success: bool
    ) -> None:
        if shard_id not in self._stats:
            return
        
        stats = self._stats[shard_id]
        stats.total_operations += 1
        
        if success:
            stats.successful_operations += 1
        else:
            stats.failed_operations += 1
        
        stats.avg_latency = (stats.avg_latency * (stats.total_operations - 1) + latency) / stats.total_operations
        stats.max_latency = max(stats.max_latency, latency)
        stats.min_latency = min(stats.min_latency, latency) if stats.min_latency > 0 else latency
        
        shard = self._shards.get(shard_id)
        if shard:
            stats.current_load = shard.size / shard.capacity if shard.capacity > 0 else 0
            stats.storage_used = shard.size
        
        stats.last_updated = time.time()

    async def rebalance(self, config_id: str) -> Dict[str, Any]:
        async with self._lock:
            if config_id not in self._configs:
                return {"status": "error", "message": "Config not found"}
            
            config = self._configs[config_id]
            shards = [s for s in self._shards.values() if s.key == config.shard_key]
            
            if not shards:
                return {"status": "error", "message": "No shards found"}
            
            total_size = sum(s.size for s in shards)
            avg_size = total_size / len(shards)
            
            rebalanced = 0
            for shard in shards:
                load_ratio = shard.size / avg_size if avg_size > 0 else 1
                
                if load_ratio > config.rebalance_threshold:
                    shard.status = ShardStatus.REBALANCING
                    rebalanced += 1
            
            for shard in shards:
                shard.status = ShardStatus.ACTIVE
            
            return {
                "status": "success",
                "rebalanced": rebalanced,
                "total_shards": len(shards),
                "avg_size": avg_size,
                "total_size": total_size
            }

    async def get_stats(self, config_id: Optional[str] = None) -> Dict[str, Any]:
        stats = {}
        
        if config_id:
            shards = [s for s in self._shards.values() if s.key == self._configs[config_id].shard_key]
            for shard in shards:
                stats[shard.id] = self._stats.get(shard.id)
        else:
            for shard_id, stat in self._stats.items():
                stats[shard_id] = stat
        
        return stats

    async def get_shards(self, config_id: Optional[str] = None) -> List[Shard]:
        if config_id:
            config = self._configs.get(config_id)
            if config:
                return [s for s in self._shards.values() if s.key == config.shard_key]
            return []
        
        return list(self._shards.values())

    async def get_config(self, config_id: str) -> Optional[ShardConfig]:
        return self._configs.get(config_id)

    async def get_configs(self) -> List[ShardConfig]:
        return list(self._configs.values())

    async def get_data(self, shard_id: str, limit: int = 100) -> List[ShardData]:
        if shard_id not in self._data:
            return []
        
        return list(self._data[shard_id].values())[:limit]

    async def get_operation(self, operation_id: str) -> Optional[ShardOperation]:
        return self._operations.get(operation_id)

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        total_shards = len(self._shards)
        total_data = sum(len(d) for d in self._data.values())
        total_operations = sum(s.total_operations for s in self._stats.values())
        
        return {
            "configs": len(self._configs),
            "shards": total_shards,
            "data_entries": total_data,
            "total_operations": total_operations,
            "running": self._running
        }


__all__ = [
    "ShardStrategy",
    "ShardStatus",
    "Shard",
    "ShardConfig",
    "ShardData",
    "ShardOperation",
    "ShardStats",
    "DataShardingManager"
]
