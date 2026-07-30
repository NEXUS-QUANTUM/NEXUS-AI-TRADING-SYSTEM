# trading/bots/hedge_bot/hedge_bot_data_distributed.py
# Advanced Distributed Data Layer for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Distributed Data Layer - Module de données distribué avancé pour le Hedge Bot.
Gère la collecte, le traitement et la distribution des données de marché, de portefeuille et de risque
à travers un cluster de nœuds pour une haute disponibilité et scalabilité.
"""

import asyncio
import json
import hashlib
import time
import zlib
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union, AsyncIterator, Coroutine
)
import uuid
import pickle
import base64
import struct
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import queue
import weakref

import numpy as np
import pandas as pd
import redis.asyncio as redis_async
import aioredis
import msgpack
import orjson

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_distributed")

# Config constants
from nexus.configs.constants import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD,
    DATA_PARTITION_COUNT, DATA_REPLICA_COUNT,
    DATA_CACHE_TTL, DATA_STREAM_BATCH_SIZE,
    DATA_COMPRESSION_THRESHOLD, DATA_MAX_MEMORY_MB
)


# ============== ENUMS & TYPES ==============

class DataType(Enum):
    """Types de données gérés par le système distribué."""
    MARKET = "market"
    PORTFOLIO = "portfolio"
    POSITION = "position"
    ORDER = "order"
    RISK = "risk"
    SIGNAL = "signal"
    PERFORMANCE = "performance"
    CONFIG = "config"
    HISTORICAL = "historical"
    STREAMING = "streaming"
    AGGREGATE = "aggregate"
    DERIVED = "derived"
    RAW = "raw"
    METADATA = "metadata"


class DataConsistency(Enum):
    """Niveaux de cohérence des données."""
    EVENTUAL = "eventual"
    STRONG = "strong"
    SESSION = "session"
    MONOTONIC = "monotonic"
    CAUSAL = "causal"


class DataPartitionStrategy(Enum):
    """Stratégies de partitionnement des données."""
    HASH = "hash"
    RANGE = "range"
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    CUSTOM = "custom"
    TIME_BASED = "time_based"
    SYMBOL_BASED = "symbol_based"
    USER_BASED = "user_based"


class DataReplicationStrategy(Enum):
    """Stratégies de réplication des données."""
    SYNC = "sync"
    ASYNC = "async"
    QUORUM = "quorum"
    CHAIN = "chain"


# ============== DATA MODELS ==============

@dataclass
class DataPartition:
    """Représente une partition de données."""
    partition_id: str
    partition_key: str
    data_type: DataType
    nodes: List[str]
    start_key: Optional[str] = None
    end_key: Optional[str] = None
    shard: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "partition_id": self.partition_id,
            "partition_key": self.partition_key,
            "data_type": self.data_type.value,
            "nodes": self.nodes,
            "start_key": self.start_key,
            "end_key": self.end_key,
            "shard": self.shard,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class DataRecord:
    """Enregistrement de données avec métadonnées."""
    key: str
    value: Any
    data_type: DataType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    partition_id: Optional[str] = None
    node_id: Optional[str] = None
    consistency: DataConsistency = DataConsistency.EVENTUAL
    ttl: Optional[int] = None
    compressed: bool = False
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_key: Optional[str] = None
    sequence: int = 0
    source: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "value": self.value,
            "data_type": self.data_type.value,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "partition_id": self.partition_id,
            "node_id": self.node_id,
            "consistency": self.consistency.value,
            "ttl": self.ttl,
            "compressed": self.compressed,
            "checksum": self.checksum,
            "metadata": self.metadata,
            "parent_key": self.parent_key,
            "sequence": self.sequence,
            "source": self.source
        }


@dataclass
class DataQuery:
    """Requête de données distribuée."""
    query_id: str
    data_type: DataType
    keys: List[str] = field(default_factory=list)
    partition_id: Optional[str] = None
    partition_key: Optional[str] = None
    filter_criteria: Dict[str, Any] = field(default_factory=dict)
    time_range: Optional[Tuple[datetime, datetime]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    sort_by: Optional[str] = None
    sort_desc: bool = True
    consistency: DataConsistency = DataConsistency.EVENTUAL
    timeout: float = 30.0
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "query_id": self.query_id,
            "data_type": self.data_type.value,
            "keys": self.keys,
            "partition_id": self.partition_id,
            "partition_key": self.partition_key,
            "filter_criteria": self.filter_criteria,
            "time_range": [self.time_range[0].isoformat(), self.time_range[1].isoformat()] if self.time_range else None,
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
            "sort_desc": self.sort_desc,
            "consistency": self.consistency.value,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DataQueryResult:
    """Résultat d'une requête de données distribuée."""
    query_id: str
    records: List[DataRecord]
    total_count: int
    node_id: str
    partition_id: str
    execution_time: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    from_replica: bool = False


@dataclass
class DataStream:
    """Flux de données en temps réel."""
    stream_id: str
    data_type: DataType
    partition_id: str
    records: List[DataRecord]
    sequence: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataNode:
    """Représente un nœud de données dans le cluster."""
    node_id: str
    host: str
    port: int
    is_primary: bool = False
    is_healthy: bool = True
    partitions: List[str] = field(default_factory=list)
    replicas: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    load: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    connection_pool_size: int = 10
    max_connections: int = 50
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "is_primary": self.is_primary,
            "is_healthy": self.is_healthy,
            "partitions": self.partitions,
            "replicas": self.replicas,
            "metadata": self.metadata,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "load": self.load,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "connection_pool_size": self.connection_pool_size,
            "max_connections": self.max_connections
        }


# ============== INTERFACES ==============

class DataNodeInterface(ABC):
    """Interface abstraite pour un nœud de données."""
    
    @abstractmethod
    async def store(self, record: DataRecord) -> bool:
        """Stocke un enregistrement."""
        pass
    
    @abstractmethod
    async def retrieve(self, key: str, data_type: DataType) -> Optional[DataRecord]:
        """Récupère un enregistrement."""
        pass
    
    @abstractmethod
    async def delete(self, key: str, data_type: DataType) -> bool:
        """Supprime un enregistrement."""
        pass
    
    @abstractmethod
    async def query(self, query: DataQuery) -> DataQueryResult:
        """Exécute une requête."""
        pass
    
    @abstractmethod
    async def stream(self, stream: DataStream) -> bool:
        """Émet un flux de données."""
        pass


class DataPartitionManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de partitions."""
    
    @abstractmethod
    async def get_partition(self, key: str, data_type: DataType) -> DataPartition:
        """Obtient la partition pour une clé."""
        pass
    
    @abstractmethod
    async def assign_partition(self, partition: DataPartition) -> bool:
        """Assigne une partition à un nœud."""
        pass
    
    @abstractmethod
    async def rebalance(self) -> bool:
        """Rééquilibre les partitions."""
        pass


class DataReplicationManagerInterface(ABC):
    """Interface abstraite pour le gestionnaire de réplication."""
    
    @abstractmethod
    async def replicate(self, record: DataRecord, replicas: List[str]) -> bool:
        """Réplique un enregistrement."""
        pass
    
    @abstractmethod
    async def get_replicas(self, partition_id: str) -> List[str]:
        """Obtient les réplicas d'une partition."""
        pass


# ============== IMPLÉMENTATIONS DE BASE ==============

class DistributedDataNode(DataNodeInterface):
    """Nœud de données distribué avancé avec cache, compression et performance optimisées."""
    
    def __init__(
        self,
        node_id: str,
        host: str,
        port: int,
        redis_client: Optional[redis_async.Redis] = None,
        is_primary: bool = False,
        max_memory_mb: int = DATA_MAX_MEMORY_MB,
        compression_threshold: int = DATA_COMPRESSION_THRESHOLD,
        cache_ttl: int = DATA_CACHE_TTL
    ):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.is_primary = is_primary
        self.max_memory_mb = max_memory_mb
        self.compression_threshold = compression_threshold
        self.cache_ttl = cache_ttl
        
        self._redis = redis_client or redis_async.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
            password=REDIS_PASSWORD,
            decode_responses=False
        )
        self._local_cache: Dict[str, DataRecord] = {}
        self._cache_memory: int = 0
        self._cache_lock = threading.RLock()
        self._stats: Dict[str, Any] = {
            "stores": 0,
            "retrieves": 0,
            "deletes": 0,
            "queries": 0,
            "streams": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "bytes_stored": 0,
            "bytes_retrieved": 0
        }
        
        # Thread pools pour les opérations I/O
        self._io_executor = ThreadPoolExecutor(max_workers=20)
        self._process_executor = ProcessPoolExecutor(max_workers=4)
        
        # Queue de streaming
        self._stream_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._stream_tasks: Set[asyncio.Task] = set()
        self._is_running = False
        
        # Métriques de performance
        self._latency_histogram: deque = deque(maxlen=1000)
        self._throughput_counter: int = 0
        
        logger.info(
            f"DistributedDataNode initialized: node_id={node_id}, "
            f"host={host}, port={port}, is_primary={is_primary}"
        )
    
    async def start(self) -> None:
        """Démarre le nœud de données."""
        self._is_running = True
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._stream_processor())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        logger.info(f"DistributedDataNode {self.node_id} started")
    
    async def stop(self) -> None:
        """Arrête le nœud de données."""
        self._is_running = False
        for task in self._stream_tasks:
            task.cancel()
        self._io_executor.shutdown(wait=True)
        self._process_executor.shutdown(wait=True)
        logger.info(f"DistributedDataNode {self.node_id} stopped")
    
    async def store(self, record: DataRecord) -> bool:
        """Stocke un enregistrement avec compression et cache optimisés."""
        start_time = time.time()
        self._stats["stores"] += 1
        record.node_id = self.node_id
        
        try:
            # Sérialisation avec compression
            serialized = self._serialize_record(record)
            
            if len(serialized) > self.compression_threshold:
                compressed = zlib.compress(serialized, level=6)
                record.compressed = True
                record.metadata["compressed_size"] = len(compressed)
                record.metadata["original_size"] = len(serialized)
                serialized = compressed
            
            # Stockage dans Redis avec TTL
            key = self._build_storage_key(record.data_type, record.key)
            redis_key = f"nexus:data:{key}"
            
            if record.ttl:
                await self._redis.setex(redis_key, record.ttl, serialized)
            else:
                await self._redis.set(redis_key, serialized)
            
            # Mise en cache local
            self._cache_record(record)
            
            # Indexation pour requêtes rapides
            await self._index_record(record)
            
            # Métriques
            self._stats["bytes_stored"] += len(serialized)
            self._latency_histogram.append(time.time() - start_time)
            self._throughput_counter += 1
            
            logger.debug(f"Stored record: key={record.key}, type={record.data_type.value}, "
                        f"compressed={record.compressed}, size={len(serialized)}")
            
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error storing record: {e}", exc_info=True)
            return False
    
    async def retrieve(self, key: str, data_type: DataType) -> Optional[DataRecord]:
        """Récupère un enregistrement avec cache intelligent."""
        start_time = time.time()
        self._stats["retrieves"] += 1
        
        # Vérification du cache local
        cache_key = self._build_cache_key(data_type, key)
        if cache_key in self._local_cache:
            record = self._local_cache[cache_key]
            if not self._is_cache_expired(record):
                self._stats["cache_hits"] += 1
                logger.debug(f"Cache hit: key={key}, type={data_type.value}")
                return record
            else:
                del self._local_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        try:
            # Récupération depuis Redis
            redis_key = f"nexus:data:{self._build_storage_key(data_type, key)}"
            data = await self._redis.get(redis_key)
            
            if not data:
                return None
            
            # Désérialisation
            record = self._deserialize_record(data, data_type, key)
            
            if record:
                # Mise en cache
                self._cache_record(record)
                
                # Métriques
                self._stats["bytes_retrieved"] += len(data)
                self._latency_histogram.append(time.time() - start_time)
                
                logger.debug(f"Retrieved record: key={key}, type={data_type.value}")
                return record
            
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error retrieving record: {e}", exc_info=True)
            return None
    
    async def delete(self, key: str, data_type: DataType) -> bool:
        """Supprime un enregistrement."""
        self._stats["deletes"] += 1
        
        try:
            redis_key = f"nexus:data:{self._build_storage_key(data_type, key)}"
            result = await self._redis.delete(redis_key)
            
            # Suppression du cache
            cache_key = self._build_cache_key(data_type, key)
            if cache_key in self._local_cache:
                del self._local_cache[cache_key]
            
            # Suppression des index
            await self._remove_index(key, data_type)
            
            logger.debug(f"Deleted record: key={key}, type={data_type.value}")
            return bool(result)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error deleting record: {e}", exc_info=True)
            return False
    
    async def query(self, query: DataQuery) -> DataQueryResult:
        """Exécute une requête optimisée avec indexation."""
        start_time = time.time()
        self._stats["queries"] += 1
        query.query_id = query.query_id or str(uuid.uuid4())
        
        try:
            records = []
            total_count = 0
            
            # Si des clés sont spécifiées
            if query.keys:
                for key in query.keys:
                    record = await self.retrieve(key, query.data_type)
                    if record:
                        records.append(record)
                total_count = len(records)
            
            # Sinon, utilisation des index pour la recherche
            else:
                index_key = f"nexus:index:{query.data_type.value}"
                keys = await self._redis.smembers(index_key)
                
                # Filtrage
                filtered_keys = await self._filter_keys(
                    [k.decode() for k in keys],
                    query.filter_criteria
                )
                
                # Pagination
                if query.limit:
                    start = query.offset or 0
                    end = start + query.limit
                    filtered_keys = filtered_keys[start:end]
                
                # Récupération des données
                for key in filtered_keys:
                    record = await self.retrieve(key, query.data_type)
                    if record:
                        records.append(record)
                
                total_count = len(records)
            
            # Tri
            if query.sort_by:
                records.sort(
                    key=lambda r: getattr(r, query.sort_by, ""),
                    reverse=query.sort_desc
                )
            
            result = DataQueryResult(
                query_id=query.query_id,
                records=records,
                total_count=total_count,
                node_id=self.node_id,
                partition_id=query.partition_id or "",
                execution_time=time.time() - start_time,
                cached=False,
                from_replica=False
            )
            
            self._latency_histogram.append(time.time() - start_time)
            
            logger.debug(f"Query executed: query_id={query.query_id}, "
                        f"count={len(records)}, time={result.execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error executing query: {e}", exc_info=True)
            return DataQueryResult(
                query_id=query.query_id,
                records=[],
                total_count=0,
                node_id=self.node_id,
                partition_id=query.partition_id or "",
                execution_time=time.time() - start_time,
                error=str(e)
            )
    
    async def stream(self, stream: DataStream) -> bool:
        """Émet un flux de données."""
        self._stats["streams"] += 1
        stream.source = self.node_id
        
        try:
            # Stockage du flux
            stream_key = f"nexus:stream:{stream.stream_id}"
            stream_data = self._serialize_stream(stream)
            
            await self._redis.xadd(
                stream_key,
                {"data": stream_data},
                maxlen=10000
            )
            
            # Mise en file d'attente pour traitement
            await self._stream_queue.put(stream)
            
            logger.debug(f"Stream emitted: stream_id={stream.stream_id}, "
                        f"records={len(stream.records)}, sequence={stream.sequence}")
            
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error emitting stream: {e}", exc_info=True)
            return False
    
    # ========== MÉTHODES PRIVÉES ==========
    
    def _build_storage_key(self, data_type: DataType, key: str) -> str:
        """Construit la clé de stockage."""
        return f"{data_type.value}:{key}"
    
    def _build_cache_key(self, data_type: DataType, key: str) -> str:
        """Construit la clé de cache."""
        return f"{data_type.value}:{key}:{self.node_id}"
    
    def _serialize_record(self, record: DataRecord) -> bytes:
        """Sérialise un enregistrement en utilisant MessagePack."""
        data = record.to_dict()
        # Conversion des datetime en string
        data["timestamp"] = data["timestamp"].isoformat()
        return msgpack.packb(data, default=self._msgpack_default)
    
    def _deserialize_record(self, data: bytes, data_type: DataType, key: str) -> Optional[DataRecord]:
        """Désérialise un enregistrement."""
        try:
            # Détection de compression
            if data[0:2] == b'\x78\x9c':  # zlib header
                data = zlib.decompress(data)
            
            unpacked = msgpack.unpackb(data, object_hook=self._msgpack_hook)
            
            # Conversion en DataRecord
            if isinstance(unpacked, dict):
                return DataRecord(
                    key=unpacked.get("key", key),
                    value=unpacked.get("value"),
                    data_type=data_type,
                    timestamp=datetime.fromisoformat(unpacked.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    version=unpacked.get("version", 1),
                    partition_id=unpacked.get("partition_id"),
                    node_id=unpacked.get("node_id"),
                    consistency=DataConsistency(unpacked.get("consistency", "eventual")),
                    ttl=unpacked.get("ttl"),
                    compressed=unpacked.get("compressed", False),
                    checksum=unpacked.get("checksum"),
                    metadata=unpacked.get("metadata", {}),
                    parent_key=unpacked.get("parent_key"),
                    sequence=unpacked.get("sequence", 0),
                    source=unpacked.get("source")
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error deserializing record: {e}")
            return None
    
    def _msgpack_default(self, obj: Any) -> Any:
        """Handler par défaut pour msgpack."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Unserializable object: {type(obj)}")
    
    def _msgpack_hook(self, obj: Dict) -> Any:
        """Handler pour msgpack."""
        return obj
    
    def _serialize_stream(self, stream: DataStream) -> bytes:
        """Sérialise un flux."""
        data = {
            "stream_id": stream.stream_id,
            "data_type": stream.data_type.value,
            "partition_id": stream.partition_id,
            "records": [r.to_dict() for r in stream.records],
            "sequence": stream.sequence,
            "timestamp": stream.timestamp.isoformat(),
            "batch_id": stream.batch_id,
            "source": stream.source,
            "metadata": stream.metadata
        }
        return msgpack.packb(data, default=self._msgpack_default)
    
    def _deserialize_stream(self, data: bytes) -> Optional[DataStream]:
        """Désérialise un flux."""
        try:
            unpacked = msgpack.unpackb(data, object_hook=self._msgpack_hook)
            if isinstance(unpacked, dict):
                records = []
                for r in unpacked.get("records", []):
                    records.append(DataRecord(
                        key=r.get("key", ""),
                        value=r.get("value"),
                        data_type=DataType(r.get("data_type", "market")),
                        timestamp=datetime.fromisoformat(r.get("timestamp", datetime.now(timezone.utc).isoformat())),
                        version=r.get("version", 1),
                        partition_id=r.get("partition_id"),
                        node_id=r.get("node_id"),
                        consistency=DataConsistency(r.get("consistency", "eventual")),
                        ttl=r.get("ttl"),
                        compressed=r.get("compressed", False),
                        checksum=r.get("checksum"),
                        metadata=r.get("metadata", {}),
                        parent_key=r.get("parent_key"),
                        sequence=r.get("sequence", 0),
                        source=r.get("source")
                    ))
                
                return DataStream(
                    stream_id=unpacked.get("stream_id", ""),
                    data_type=DataType(unpacked.get("data_type", "market")),
                    partition_id=unpacked.get("partition_id", ""),
                    records=records,
                    sequence=unpacked.get("sequence", 0),
                    timestamp=datetime.fromisoformat(unpacked.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    batch_id=unpacked.get("batch_id", str(uuid.uuid4())),
                    source=unpacked.get("source"),
                    metadata=unpacked.get("metadata", {})
                )
            return None
        except Exception as e:
            logger.error(f"Error deserializing stream: {e}")
            return None
    
    def _cache_record(self, record: DataRecord) -> None:
        """Cache un enregistrement en mémoire."""
        with self._cache_lock:
            cache_key = self._build_cache_key(record.data_type, record.key)
            size = len(str(record.value)) if record.value else 0
            
            # Éviction LRU si besoin
            while self._cache_memory + size > self.max_memory_mb * 1024 * 1024:
                if not self._local_cache:
                    break
                old_key = next(iter(self._local_cache))
                old_record = self._local_cache.pop(old_key)
                self._cache_memory -= len(str(old_record.value)) if old_record.value else 0
            
            self._local_cache[cache_key] = record
            self._cache_memory += size
    
    def _is_cache_expired(self, record: DataRecord) -> bool:
        """Vérifie si un cache est expiré."""
        if record.ttl is None:
            return False
        age = (datetime.now(timezone.utc) - record.timestamp).total_seconds()
        return age > record.ttl
    
    async def _index_record(self, record: DataRecord) -> None:
        """Indexe un enregistrement pour les requêtes rapides."""
        index_key = f"nexus:index:{record.data_type.value}"
        await self._redis.sadd(index_key, record.key)
        
        # Index secondaires
        if record.metadata:
            for key, value in record.metadata.items():
                secondary_key = f"nexus:index:{record.data_type.value}:{key}:{value}"
                await self._redis.sadd(secondary_key, record.key)
    
    async def _remove_index(self, key: str, data_type: DataType) -> None:
        """Supprime un enregistrement des index."""
        index_key = f"nexus:index:{data_type.value}"
        await self._redis.srem(index_key, key)
    
    async def _filter_keys(self, keys: List[str], criteria: Dict[str, Any]) -> List[str]:
        """Filtre les clés selon des critères."""
        if not criteria:
            return keys
        
        filtered = []
        for key in keys:
            record = await self.retrieve(key, DataType.METADATA)
            if record and self._matches_criteria(record, criteria):
                filtered.append(key)
        
        return filtered
    
    def _matches_criteria(self, record: DataRecord, criteria: Dict[str, Any]) -> bool:
        """Vérifie si un enregistrement correspond aux critères."""
        for key, value in criteria.items():
            if key == "data_type" and record.data_type.value != value:
                return False
            if key == "timestamp_after" and record.timestamp < datetime.fromisoformat(value):
                return False
            if key == "timestamp_before" and record.timestamp > datetime.fromisoformat(value):
                return False
            if key in record.metadata and record.metadata[key] != value:
                return False
            if hasattr(record, key) and getattr(record, key) != value:
                return False
        return True
    
    async def _heartbeat_loop(self) -> None:
        """Boucle de heartbeat."""
        while self._is_running:
            try:
                await self._redis.set(
                    f"nexus:node:{self.node_id}:heartbeat",
                    datetime.now(timezone.utc).isoformat(),
                    ex=10
                )
                
                # Métriques de nœud
                await self._redis.hset(
                    f"nexus:node:{self.node_id}:metrics",
                    mapping={
                        "load": self.load,
                        "memory_usage": self.memory_usage,
                        "cpu_usage": self.cpu_usage,
                        "stats": json.dumps(self._stats),
                        "cache_size": len(self._local_cache),
                        "cache_memory": self._cache_memory
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
            
            await asyncio.sleep(5)
    
    async def _stream_processor(self) -> None:
        """Traite les flux en continu."""
        while self._is_running:
            try:
                stream = await self._stream_queue.get()
                # Traitement asynchrone du flux
                task = asyncio.create_task(self._process_stream(stream))
                self._stream_tasks.add(task)
                task.add_done_callback(self._stream_tasks.discard)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stream processor: {e}")
    
    async def _process_stream(self, stream: DataStream) -> None:
        """Traite un flux de données."""
        try:
            # Agrégation des données
            aggregated = await self._aggregate_stream(stream)
            if aggregated:
                await self._store_aggregated(aggregated)
            
            # Émission vers les abonnés
            await self._emit_stream(stream)
            
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
    
    async def _aggregate_stream(self, stream: DataStream) -> Optional[DataRecord]:
        """Agrège les données d'un flux."""
        if not stream.records:
            return None
        
        # Agrégation selon le type
        if stream.data_type == DataType.MARKET:
            return self._aggregate_market_data(stream.records)
        elif stream.data_type == DataType.PORTFOLIO:
            return self._aggregate_portfolio_data(stream.records)
        elif stream.data_type == DataType.RISK:
            return self._aggregate_risk_data(stream.records)
        
        return None
    
    def _aggregate_market_data(self, records: List[DataRecord]) -> Optional[DataRecord]:
        """Agrège les données de marché."""
        try:
            values = []
            for r in records:
                if isinstance(r.value, (int, float)):
                    values.append(r.value)
                elif isinstance(r.value, dict) and "price" in r.value:
                    values.append(r.value["price"])
            
            if not values:
                return None
            
            aggregated = {
                "open": values[0],
                "close": values[-1],
                "high": max(values),
                "low": min(values),
                "volume": sum(v for v in values if isinstance(v, (int, float))),
                "mean": np.mean(values),
                "std": np.std(values),
                "count": len(values)
            }
            
            return DataRecord(
                key=f"aggregated_{records[0].key}",
                value=aggregated,
                data_type=DataType.AGGREGATE,
                timestamp=datetime.now(timezone.utc),
                metadata={"source_type": "market", "record_count": len(values)}
            )
            
        except Exception as e:
            logger.error(f"Error aggregating market data: {e}")
            return None
    
    def _aggregate_portfolio_data(self, records: List[DataRecord]) -> Optional[DataRecord]:
        """Agrège les données de portefeuille."""
        try:
            total_value = 0
            total_pnl = 0
            assets = {}
            
            for r in records:
                if isinstance(r.value, dict):
                    total_value += r.value.get("value", 0)
                    total_pnl += r.value.get("pnl", 0)
                    assets.update(r.value.get("assets", {}))
            
            aggregated = {
                "total_value": total_value,
                "total_pnl": total_pnl,
                "asset_count": len(assets),
                "assets": assets
            }
            
            return DataRecord(
                key=f"portfolio_aggregated_{records[0].key}",
                value=aggregated,
                data_type=DataType.AGGREGATE,
                timestamp=datetime.now(timezone.utc),
                metadata={"source_type": "portfolio", "record_count": len(records)}
            )
            
        except Exception as e:
            logger.error(f"Error aggregating portfolio data: {e}")
            return None
    
    def _aggregate_risk_data(self, records: List[DataRecord]) -> Optional[DataRecord]:
        """Agrège les données de risque."""
        try:
            var_values = []
            drawdowns = []
            sharpe_values = []
            
            for r in records:
                if isinstance(r.value, dict):
                    var_values.append(r.value.get("var", 0))
                    drawdowns.append(r.value.get("drawdown", 0))
                    sharpe_values.append(r.value.get("sharpe", 0))
            
            aggregated = {
                "avg_var": np.mean(var_values) if var_values else 0,
                "max_drawdown": max(drawdowns) if drawdowns else 0,
                "avg_sharpe": np.mean(sharpe_values) if sharpe_values else 0,
                "risk_score": np.mean(var_values) * 0.5 + max(drawdowns) * 0.3 + (1 - np.mean(sharpe_values)) * 0.2
            }
            
            return DataRecord(
                key=f"risk_aggregated_{records[0].key}",
                value=aggregated,
                data_type=DataType.AGGREGATE,
                timestamp=datetime.now(timezone.utc),
                metadata={"source_type": "risk", "record_count": len(records)}
            )
            
        except Exception as e:
            logger.error(f"Error aggregating risk data: {e}")
            return None
    
    async def _store_aggregated(self, record: DataRecord) -> None:
        """Stocke les données agrégées."""
        await self.store(record)
    
    async def _emit_stream(self, stream: DataStream) -> None:
        """Émet un flux vers les abonnés."""
        # Pub/Sub pour les abonnés
        await self._redis.publish(
            f"nexus:stream:{stream.data_type.value}",
            self._serialize_stream(stream)
        )
    
    async def _cache_cleaner(self) -> None:
        """Nettoie périodiquement le cache."""
        while self._is_running:
            await asyncio.sleep(60)  # Toutes les minutes
            
            with self._cache_lock:
                expired_keys = []
                for key, record in self._local_cache.items():
                    if self._is_cache_expired(record):
                        expired_keys.append(key)
                
                for key in expired_keys:
                    record = self._local_cache.pop(key, None)
                    if record:
                        self._cache_memory -= len(str(record.value)) if record.value else 0
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques de performance."""
        while self._is_running:
            await asyncio.sleep(30)
            
            # Calcul des métriques
            self.load = self._throughput_counter / 30.0
            self.memory_usage = self._cache_memory / (1024 * 1024)
            
            # Réinitialisation du compteur
            self._throughput_counter = 0
    
    @property
    def load(self) -> float:
        return self._stats.get("load", 0.0)
    
    @load.setter
    def load(self, value: float) -> None:
        self._stats["load"] = value
    
    @property
    def memory_usage(self) -> float:
        return self._stats.get("memory_usage", 0.0)
    
    @memory_usage.setter
    def memory_usage(self, value: float) -> None:
        self._stats["memory_usage"] = value
    
    @property
    def cpu_usage(self) -> float:
        return self._stats.get("cpu_usage", 0.0)
    
    @cpu_usage.setter
    def cpu_usage(self, value: float) -> None:
        self._stats["cpu_usage"] = value


class DistributedDataManager:
    """
    Gestionnaire de données distribué avancé.
    Orchestre les nœuds, les partitions, la réplication et le routage.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis_async.Redis] = None,
        partition_count: int = DATA_PARTITION_COUNT,
        replica_count: int = DATA_REPLICA_COUNT
    ):
        self._redis = redis_client or redis_async.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
            password=REDIS_PASSWORD,
            decode_responses=False
        )
        self.partition_count = partition_count
        self.replica_count = replica_count
        
        # Gestion des nœuds
        self._nodes: Dict[str, DistributedDataNode] = {}
        self._node_lock = threading.RLock()
        
        # Gestion des partitions
        self._partitions: Dict[str, DataPartition] = {}
        self._partition_lock = threading.RLock()
        
        # Cache de routage
        self._routing_cache: Dict[str, str] = {}
        self._routing_cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "queries": 0,
            "stores": 0,
            "deletes": 0,
            "streams": 0,
            "rebalances": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }
        
        logger.info(f"DistributedDataManager initialized: partition_count={partition_count}, "
                   f"replica_count={replica_count}")
    
    async def start(self) -> None:
        """Démarre le gestionnaire de données distribué."""
        logger.info("DistributedDataManager starting...")
        await self._load_cluster_state()
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._rebalance_loop())
        logger.info("DistributedDataManager started")
    
    async def stop(self) -> None:
        """Arrête le gestionnaire de données distribué."""
        logger.info("DistributedDataManager stopping...")
        for node in self._nodes.values():
            await node.stop()
        logger.info("DistributedDataManager stopped")
    
    async def register_node(self, node: DistributedDataNode) -> bool:
        """Enregistre un nœud dans le cluster."""
        with self._node_lock:
            self._nodes[node.node_id] = node
            await node.start()
        
        # Mise à jour de l'état du cluster
        await self._update_cluster_state()
        
        logger.info(f"Node registered: {node.node_id}")
        return True
    
    async def unregister_node(self, node_id: str) -> bool:
        """Désenregistre un nœud du cluster."""
        with self._node_lock:
            if node_id not in self._nodes:
                return False
            
            node = self._nodes.pop(node_id)
            await node.stop()
        
        # Mise à jour de l'état du cluster
        await self._update_cluster_state()
        
        logger.info(f"Node unregistered: {node_id}")
        return True
    
    async def get_node(self, node_id: str) -> Optional[DistributedDataNode]:
        """Obtient un nœud par son ID."""
        with self._node_lock:
            return self._nodes.get(node_id)
    
    async def get_nodes(self) -> List[DistributedDataNode]:
        """Obtient la liste de tous les nœuds."""
        with self._node_lock:
            return list(self._nodes.values())
    
    async def get_primary_node(self, partition_key: str) -> Optional[DistributedDataNode]:
        """Obtient le nœud primaire pour une partition."""
        partition = await self.get_partition(partition_key, DataType.MARKET)
        if not partition or not partition.nodes:
            return None
        
        # Routing par cache
        cache_key = f"{partition_key}:{partition.data_type.value}"
        with self._routing_cache_lock:
            if cache_key in self._routing_cache:
                node_id = self._routing_cache[cache_key]
                if node_id in self._nodes:
                    return self._nodes[node_id]
        
        # Sélection du nœud primaire
        primary_node_id = partition.nodes[0] if partition.nodes else None
        if primary_node_id and primary_node_id in self._nodes:
            with self._routing_cache_lock:
                self._routing_cache[cache_key] = primary_node_id
            return self._nodes[primary_node_id]
        
        return None
    
    async def get_replica_nodes(self, partition_key: str) -> List[DistributedDataNode]:
        """Obtient les nœuds de réplica pour une partition."""
        partition = await self.get_partition(partition_key, DataType.MARKET)
        if not partition or not partition.nodes:
            return []
        
        replica_nodes = []
        for node_id in partition.nodes[1:]:
            if node_id in self._nodes:
                replica_nodes.append(self._nodes[node_id])
        
        return replica_nodes
    
    async def get_partition(self, key: str, data_type: DataType) -> Optional[DataPartition]:
        """Obtient la partition pour une clé."""
        partition_key = self._compute_partition_key(key)
        
        with self._partition_lock:
            if partition_key in self._partitions:
                return self._partitions[partition_key]
        
        # Chargement depuis Redis
        partition_data = await self._redis.get(f"nexus:partition:{partition_key}")
        if partition_data:
            partition = self._deserialize_partition(partition_data)
            if partition:
                with self._partition_lock:
                    self._partitions[partition_key] = partition
                return partition
        
        return None
    
    async def create_partition(self, partition: DataPartition) -> bool:
        """Crée une nouvelle partition."""
        with self._partition_lock:
            self._partitions[partition.partition_key] = partition
        
        # Persistance
        await self._redis.set(
            f"nexus:partition:{partition.partition_key}",
            msgpack.packb(partition.to_dict())
        )
        
        logger.info(f"Partition created: {partition.partition_key}")
        return True
    
    async def assign_node_to_partition(self, partition_key: str, node_id: str) -> bool:
        """Assigne un nœud à une partition."""
        with self._partition_lock:
            if partition_key not in self._partitions:
                return False
            
            partition = self._partitions[partition_key]
            if node_id not in partition.nodes:
                partition.nodes.append(node_id)
                partition.updated_at = datetime.now(timezone.utc)
        
        # Persistance
        await self._redis.set(
            f"nexus:partition:{partition_key}",
            msgpack.packb(partition.to_dict())
        )
        
        logger.info(f"Node {node_id} assigned to partition {partition_key}")
        return True
    
    async def rebalance(self) -> bool:
        """Rééquilibre les partitions entre les nœuds."""
        self._stats["rebalances"] += 1
        
        try:
            with self._node_lock:
                nodes = list(self._nodes.keys())
            
            if not nodes:
                return False
            
            # Calcul du nombre de partitions par nœud
            partitions_per_node = self.partition_count // len(nodes)
            remainder = self.partition_count % len(nodes)
            
            # Répartition des partitions
            assignment = defaultdict(list)
            node_idx = 0
            
            for i in range(self.partition_count):
                partition_key = f"partition_{i}"
                assignment[nodes[node_idx]].append(partition_key)
                
                node_idx += 1
                if node_idx >= len(nodes):
                    node_idx = 0
            
            # Mise à jour des partitions
            for node_id, partition_keys in assignment.items():
                for partition_key in partition_keys:
                    await self.assign_node_to_partition(partition_key, node_id)
            
            logger.info(f"Rebalanced cluster: {len(nodes)} nodes, "
                       f"{self.partition_count} partitions")
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error during rebalance: {e}")
            return False
    
    async def store(
        self,
        key: str,
        value: Any,
        data_type: DataType = DataType.MARKET,
        consistency: DataConsistency = DataConsistency.EVENTUAL,
        ttl: Optional[int] = None
    ) -> bool:
        """Stocke des données dans le cluster."""
        self._stats["stores"] += 1
        
        try:
            # Sélection du nœud primaire
            primary_node = await self.get_primary_node(key)
            if not primary_node:
                logger.error(f"No primary node for key: {key}")
                return False
            
            record = DataRecord(
                key=key,
                value=value,
                data_type=data_type,
                consistency=consistency,
                ttl=ttl
            )
            
            # Stockage sur le nœud primaire
            success = await primary_node.store(record)
            
            if not success:
                return False
            
            # Réplication
            if consistency != DataConsistency.EVENTUAL:
                replica_nodes = await self.get_replica_nodes(key)
                if replica_nodes:
                    tasks = []
                    for node in replica_nodes:
                        tasks.append(node.store(record))
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    success = all(isinstance(r, bool) and r for r in results)
            
            # Mise à jour du cache de routage
            with self._routing_cache_lock:
                self._routing_cache[f"{key}:{data_type.value}"] = primary_node.node_id
            
            logger.debug(f"Stored data: key={key}, type={data_type.value}, "
                        f"node={primary_node.node_id}")
            
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error storing data: {e}")
            return False
    
    async def retrieve(
        self,
        key: str,
        data_type: DataType = DataType.MARKET,
        consistency: DataConsistency = DataConsistency.EVENTUAL
    ) -> Optional[Any]:
        """Récupère des données du cluster."""
        self._stats["queries"] += 1
        
        try:
            # Sélection du nœud
            if consistency == DataConsistency.STRONG:
                node = await self.get_primary_node(key)
            else:
                # Routage intelligent
                cache_key = f"{key}:{data_type.value}"
                with self._routing_cache_lock:
                    if cache_key in self._routing_cache:
                        node_id = self._routing_cache[cache_key]
                        if node_id in self._nodes:
                            node = self._nodes[node_id]
                        else:
                            node = await self.get_primary_node(key)
                    else:
                        node = await self.get_primary_node(key)
            
            if not node:
                logger.error(f"No node for key: {key}")
                return None
            
            record = await node.retrieve(key, data_type)
            
            if record:
                self._stats["cache_hits"] += 1
                return record.value
            
            self._stats["cache_misses"] += 1
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error retrieving data: {e}")
            return None
    
    async def delete(
        self,
        key: str,
        data_type: DataType = DataType.MARKET
    ) -> bool:
        """Supprime des données du cluster."""
        self._stats["deletes"] += 1
        
        try:
            # Suppression sur tous les nœuds
            nodes = await self.get_nodes()
            tasks = []
            for node in nodes:
                tasks.append(node.delete(key, data_type))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = any(isinstance(r, bool) and r for r in results)
            
            if success:
                # Suppression du cache de routage
                with self._routing_cache_lock:
                    self._routing_cache.pop(f"{key}:{data_type.value}", None)
            
            return success
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error deleting data: {e}")
            return False
    
    async def stream(
        self,
        stream_id: str,
        records: List[DataRecord],
        data_type: DataType = DataType.MARKET
    ) -> bool:
        """Émet un flux de données dans le cluster."""
        self._stats["streams"] += 1
        
        try:
            # Sélection de la partition
            partition_key = self._compute_partition_key(stream_id)
            partition = await self.get_partition(partition_key, data_type)
            
            if not partition:
                return False
            
            stream = DataStream(
                stream_id=stream_id,
                data_type=data_type,
                partition_id=partition.partition_id,
                records=records,
                sequence=len(records)
            )
            
            # Émission vers tous les nœuds de la partition
            tasks = []
            for node_id in partition.nodes:
                if node_id in self._nodes:
                    tasks.append(self._nodes[node_id].stream(stream))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = any(isinstance(r, bool) and r for r in results)
            
            return success
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error streaming data: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES ==========
    
    def _compute_partition_key(self, key: str) -> str:
        """Calcule la clé de partition pour une clé."""
        hash_value = hashlib.md5(key.encode()).digest()
        partition_id = struct.unpack_from(">I", hash_value, 0)[0] % self.partition_count
        return f"partition_{partition_id}"
    
    def _deserialize_partition(self, data: bytes) -> Optional[DataPartition]:
        """Désérialise une partition."""
        try:
            unpacked = msgpack.unpackb(data)
            if isinstance(unpacked, dict):
                return DataPartition(
                    partition_id=unpacked.get("partition_id", ""),
                    partition_key=unpacked.get("partition_key", ""),
                    data_type=DataType(unpacked.get("data_type", "market")),
                    nodes=unpacked.get("nodes", []),
                    start_key=unpacked.get("start_key"),
                    end_key=unpacked.get("end_key"),
                    shard=unpacked.get("shard", 0),
                    metadata=unpacked.get("metadata", {}),
                    created_at=datetime.fromisoformat(unpacked.get("created_at", datetime.now(timezone.utc).isoformat())),
                    updated_at=datetime.fromisoformat(unpacked.get("updated_at", datetime.now(timezone.utc).isoformat()))
                )
            return None
        except Exception as e:
            logger.error(f"Error deserializing partition: {e}")
            return None
    
    async def _load_cluster_state(self) -> None:
        """Charge l'état du cluster depuis Redis."""
        try:
            # Chargement des partitions
            partition_keys = await self._redis.keys("nexus:partition:*")
            for key in partition_keys:
                data = await self._redis.get(key)
                if data:
                    partition = self._deserialize_partition(data)
                    if partition:
                        with self._partition_lock:
                            self._partitions[partition.partition_key] = partition
            
            logger.info(f"Loaded {len(self._partitions)} partitions from Redis")
            
        except Exception as e:
            logger.error(f"Error loading cluster state: {e}")
    
    async def _update_cluster_state(self) -> None:
        """Met à jour l'état du cluster dans Redis."""
        try:
            # Mise à jour des partitions
            for partition in self._partitions.values():
                await self._redis.set(
                    f"nexus:partition:{partition.partition_key}",
                    msgpack.packb(partition.to_dict())
                )
            
            # Mise à jour des nœuds
            for node_id, node in self._nodes.items():
                await self._redis.hset(
                    f"nexus:node:{node_id}",
                    mapping=node.to_dict()
                )
            
            logger.info("Cluster state updated in Redis")
            
        except Exception as e:
            logger.error(f"Error updating cluster state: {e}")
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while True:
            await asyncio.sleep(30)
            
            try:
                with self._node_lock:
                    for node_id, node in list(self._nodes.items()):
                        # Vérification du heartbeat
                        heartbeat = await self._redis.get(
                            f"nexus:node:{node_id}:heartbeat"
                        )
                        
                        if not heartbeat:
                            logger.warning(f"Node {node_id} is unhealthy, removing...")
                            await node.stop()
                            del self._nodes[node_id]
                        
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _rebalance_loop(self) -> None:
        """Boucle de rééquilibrage automatique."""
        while True:
            await asyncio.sleep(300)  # Toutes les 5 minutes
            
            try:
                # Vérification du déséquilibre
                with self._node_lock:
                    if not self._nodes:
                        continue
                    
                    # Distribution idéale
                    ideal_count = self.partition_count // len(self._nodes)
                    
                    # Vérification du déséquilibre
                    imbalances = []
                    for node in self._nodes.values():
                        if hasattr(node, "partitions"):
                            count = len(node.partitions)
                            if abs(count - ideal_count) > 2:
                                imbalances.append((node.node_id, count))
                    
                    if len(imbalances) > 1:
                        logger.info("Detected imbalance, rebalancing...")
                        await self.rebalance()
                        
            except Exception as e:
                logger.error(f"Error in rebalance loop: {e}")


# ============== FACTORY ==============

class DistributedDataFactory:
    """Factory pour créer des composants de données distribués."""
    
    @staticmethod
    async def create_node(
        node_id: str,
        host: str,
        port: int,
        is_primary: bool = False,
        redis_client: Optional[redis_async.Redis] = None
    ) -> DistributedDataNode:
        """Crée un nœud de données distribué."""
        node = DistributedDataNode(
            node_id=node_id,
            host=host,
            port=port,
            redis_client=redis_client,
            is_primary=is_primary
        )
        await node.start()
        return node
    
    @staticmethod
    async def create_manager(
        redis_client: Optional[redis_async.Redis] = None,
        partition_count: int = DATA_PARTITION_COUNT,
        replica_count: int = DATA_REPLICA_COUNT
    ) -> DistributedDataManager:
        """Crée un gestionnaire de données distribué."""
        manager = DistributedDataManager(
            redis_client=redis_client,
            partition_count=partition_count,
            replica_count=replica_count
        )
        await manager.start()
        return manager
    
    @staticmethod
    async def create_cluster(
        nodes_config: List[Dict[str, Any]],
        partition_count: int = DATA_PARTITION_COUNT,
        replica_count: int = DATA_REPLICA_COUNT
    ) -> DistributedDataManager:
        """Crée un cluster complet de données distribuées."""
        manager = await DistributedDataFactory.create_manager(
            partition_count=partition_count,
            replica_count=replica_count
        )
        
        # Création des nœuds
        for config in nodes_config:
            node = await DistributedDataFactory.create_node(
                node_id=config["node_id"],
                host=config["host"],
                port=config["port"],
                is_primary=config.get("is_primary", False)
            )
            await manager.register_node(node)
        
        # Création des partitions
        for i in range(partition_count):
            partition = DataPartition(
                partition_id=f"partition_{i}",
                partition_key=f"partition_{i}",
                data_type=DataType.MARKET,
                nodes=[],  # Sera rempli par le rééquilibrage
                shard=i
            )
            await manager.create_partition(partition)
        
        # Rééquilibrage initial
        await manager.rebalance()
        
        return manager


# ============== EXPORT ==============

__all__ = [
    "DataType",
    "DataConsistency",
    "DataPartitionStrategy",
    "DataReplicationStrategy",
    "DataPartition",
    "DataRecord",
    "DataQuery",
    "DataQueryResult",
    "DataStream",
    "DataNode",
    "DataNodeInterface",
    "DataPartitionManagerInterface",
    "DataReplicationManagerInterface",
    "DistributedDataNode",
    "DistributedDataManager",
    "DistributedDataFactory"
]
