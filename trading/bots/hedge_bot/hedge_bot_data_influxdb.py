# trading/bots/hedge_bot/hedge_bot_data_influxdb.py
# Advanced InfluxDB Integration & Time-Series Data Management for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot InfluxDB Integration Module - Module d'intégration avancé avec InfluxDB pour le Hedge Bot.
Gère le stockage de séries temporelles, les métriques en temps réel, les agrégations,
les requêtes de performance et l'analyse des données de hedging.
"""

import asyncio
import json
import time
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import aiohttp
import aiohttp.client_exceptions

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_influxdb")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class InfluxDBDataType(Enum):
    """Types de données InfluxDB."""
    METRIC = "metric"
    EVENT = "event"
    TRACE = "trace"
    LOG = "log"
    MARKET_DATA = "market_data"
    TRADING_DATA = "trading_data"
    RISK_DATA = "risk_data"
    PERFORMANCE_DATA = "performance_data"
    SYSTEM_DATA = "system_data"


class InfluxDBPrecision(Enum):
    """Précisions temporelles InfluxDB."""
    NANOSECONDS = "ns"
    MICROSECONDS = "us"
    MILLISECONDS = "ms"
    SECONDS = "s"
    MINUTES = "m"
    HOURS = "h"


class InfluxDBRetention(Enum):
    """Politiques de rétention InfluxDB."""
    HOURS_1 = "1h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    DAYS_180 = "180d"
    DAYS_365 = "365d"
    INFINITE = "infinite"


# ============== DATA MODELS ==============

@dataclass
class InfluxDBPoint:
    """Point de données InfluxDB."""
    measurement: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    precision: InfluxDBPrecision = InfluxDBPrecision.MILLISECONDS
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_line_protocol(self) -> str:
        """Convertit en format Line Protocol."""
        # Measurement
        line = f"{self.measurement}"
        
        # Tags
        if self.tags:
            tag_str = ",".join([f"{k}={v}" for k, v in self.tags.items()])
            line += f",{tag_str}"
        
        # Fields
        field_strs = []
        for k, v in self.fields.items():
            if isinstance(v, (int, float)):
                field_strs.append(f"{k}={v}")
            elif isinstance(v, bool):
                field_strs.append(f"{k}={str(v).lower()}")
            elif isinstance(v, str):
                field_strs.append(f"{k}=\"{v}\"")
            else:
                field_strs.append(f"{k}=\"{str(v)}\"")
        line += f" {','.join(field_strs)}"
        
        # Timestamp
        if self.timestamp:
            ns = int(self.timestamp.timestamp() * 1e9)
            line += f" {ns}"
        
        return line


@dataclass
class InfluxDBQuery:
    """Requête InfluxDB."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    measurement: str = ""
    fields: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    group_by: Optional[List[str]] = None
    aggregate: Optional[str] = None
    aggregate_interval: Optional[str] = None
    limit: int = 0
    offset: int = 0
    order: str = "asc"
    fill: str = "none"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfluxDBResult:
    """Résultat de requête InfluxDB."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str = ""
    measurement: str = ""
    series: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfluxDBBucket:
    """Bucket InfluxDB."""
    bucket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    data_type: InfluxDBDataType = InfluxDBDataType.METRIC
    retention_policy: InfluxDBRetention = InfluxDBRetention.DAYS_30
    shard_group_duration: str = "1d"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class InfluxDBEngineInterface(ABC):
    """Interface abstraite pour le moteur InfluxDB."""
    
    @abstractmethod
    async def write_point(self, point: InfluxDBPoint) -> bool:
        """Écrit un point de données."""
        pass
    
    @abstractmethod
    async def write_batch(self, points: List[InfluxDBPoint]) -> int:
        """Écrit un batch de points."""
        pass
    
    @abstractmethod
    async def query(self, query: InfluxDBQuery) -> InfluxDBResult:
        """Exécute une requête."""
        pass
    
    @abstractmethod
    async def create_bucket(self, bucket: InfluxDBBucket) -> str:
        """Crée un bucket."""
        pass


# ============== IMPLÉMENTATION ==============

class InfluxDBEngine(InfluxDBEngineInterface):
    """
    Moteur InfluxDB avancé pour le Hedge Bot.
    Gère le stockage de séries temporelles, les métriques et les requêtes de performance.
    """
    
    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.url = url.rstrip('/')
        self.token = token
        self.org = org
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Gestion des buckets
        self._buckets: Dict[str, InfluxDBBucket] = {}
        self._buckets_lock = threading.RLock()
        
        # Cache des requêtes
        self._query_cache: Dict[str, InfluxDBResult] = {}
        self._cache_lock = threading.RLock()
        
        # Queue d'écriture
        self._write_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "points_written": 0,
            "batches_written": 0,
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "avg_write_time_ms": 0.0,
            "avg_query_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("InfluxDBEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "batch_size": 1000,
            "flush_interval": 5,
            "write_timeout": 30,
            "query_timeout": 60,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_compression": True,
            "default_precision": InfluxDBPrecision.MILLISECONDS,
            "default_bucket": "nexus_hedge_bot",
            "max_points_per_batch": 5000,
            "retry_count": 3,
            "retry_delay": 1.0
        }
    
    async def start(self) -> None:
        """Démarre le moteur InfluxDB."""
        logger.info("InfluxDBEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.config["write_timeout"])
        )
        
        # Chargement des buckets existants
        await self._load_buckets()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._write_processor())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("InfluxDBEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur InfluxDB."""
        logger.info("InfluxDBEngine stopping...")
        self._is_running = False
        
        # Vidage de la queue
        await self._flush_write_queue()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("InfluxDBEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def write_point(self, point: InfluxDBPoint) -> bool:
        """Écrit un point de données."""
        try:
            # Mise en queue
            await self._write_queue.put(point)
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Write point error: {e}")
            return False
    
    async def write_batch(self, points: List[InfluxDBPoint]) -> int:
        """Écrit un batch de points."""
        if not points:
            return 0
        
        start_time = time.time()
        
        try:
            # Construction du payload
            lines = [p.to_line_protocol() for p in points]
            payload = "\n".join(lines)
            
            # Compression
            if self.config["enable_compression"]:
                import gzip
                payload = gzip.compress(payload.encode())
                headers = {"Content-Encoding": "gzip"}
            else:
                headers = {}
            
            # Envoi à InfluxDB
            url = f"{self.url}/api/v2/write"
            params = {
                "org": self.org,
                "bucket": self.config["default_bucket"],
                "precision": self.config["default_precision"].value
            }
            
            async with self._session.post(
                url,
                params=params,
                data=payload,
                headers=headers
            ) as response:
                if response.status == 204:
                    self._stats["points_written"] += len(points)
                    self._stats["batches_written"] += 1
                    
                    write_time = (time.time() - start_time) * 1000
                    self._stats["avg_write_time_ms"] = (
                        self._stats["avg_write_time_ms"] * 0.9 + write_time * 0.1
                    )
                    
                    logger.debug(f"Wrote {len(points)} points to InfluxDB")
                    return len(points)
                else:
                    error_text = await response.text()
                    logger.error(f"Write error: {response.status} - {error_text}")
                    self._stats["errors"] += 1
                    return 0
                    
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Batch write error: {e}")
            return 0
    
    async def query(self, query: InfluxDBQuery) -> InfluxDBResult:
        """Exécute une requête InfluxDB."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(query)
            if self.config["enable_cache"] and cache_key in self._query_cache:
                self._stats["cache_hits"] += 1
                return self._query_cache[cache_key]
            
            self._stats["cache_misses"] += 1
            
            # Construction de la requête Flux
            flux_query = self._build_flux_query(query)
            
            # Envoi de la requête
            url = f"{self.url}/api/v2/query"
            params = {"org": self.org}
            
            payload = {
                "query": flux_query,
                "type": "flux",
                "dialect": {
                    "header": True,
                    "delimiter": ",",
                    "commentPrefix": "#",
                    "dateTimeFormat": "RFC3339",
                    "annotations": ["datatype", "group", "default"]
                }
            }
            
            async with self._session.post(
                url,
                params=params,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result = self._parse_query_result(query, data)
                    
                    # Mise en cache
                    if self.config["enable_cache"]:
                        with self._cache_lock:
                            if len(self._query_cache) < self.config["cache_size"]:
                                self._query_cache[cache_key] = result
                    
                    # Métriques
                    query_time = (time.time() - start_time) * 1000
                    self._stats["avg_query_time_ms"] = (
                        self._stats["avg_query_time_ms"] * 0.9 + query_time * 0.1
                    )
                    
                    logger.debug(f"Query executed: {query.query_id} "
                               f"rows={result.row_count} time={query_time:.2f}ms")
                    
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Query error: {response.status} - {error_text}")
                    return InfluxDBResult(
                        query_id=query.query_id,
                        error=error_text,
                        execution_time_ms=(time.time() - start_time) * 1000
                    )
                    
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query error: {e}")
            return InfluxDBResult(
                query_id=query.query_id,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def create_bucket(self, bucket: InfluxDBBucket) -> str:
        """Crée un bucket InfluxDB."""
        with self._buckets_lock:
            self._buckets[bucket.bucket_id] = bucket
        
        try:
            # Création du bucket via l'API
            url = f"{self.url}/api/v2/buckets"
            payload = {
                "name": bucket.name,
                "orgID": self.org,
                "retentionRules": [
                    {
                        "type": "expire",
                        "everySeconds": self._parse_retention_duration(
                            bucket.retention_policy
                        )
                    }
                ]
            }
            
            async with self._session.post(url, json=payload) as response:
                if response.status in [201, 200]:
                    logger.info(f"Bucket created: {bucket.name}")
                    return bucket.bucket_id
                else:
                    error_text = await response.text()
                    logger.error(f"Bucket creation error: {response.status} - {error_text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Bucket creation error: {e}")
            return ""
    
    # ========== MÉTHODES PRIVÉES - FLUX ==========
    
    def _build_flux_query(self, query: InfluxDBQuery) -> str:
        """Construit une requête Flux."""
        parts = []
        
        # from
        parts.append(f'from(bucket: "{self.config["default_bucket"]}")')
        
        # range
        if query.start_time:
            start = query.start_time.isoformat()
            if query.end_time:
                end = query.end_time.isoformat()
                parts.append(f'|> range(start: {start}, stop: {end})')
            else:
                parts.append(f'|> range(start: {start})')
        else:
            parts.append('|> range(start: -30d)')
        
        # filter
        if query.measurement:
            parts.append(f'|> filter(fn: (r) => r._measurement == "{query.measurement}")')
        
        if query.tags:
            for key, value in query.tags.items():
                parts.append(f'|> filter(fn: (r) => r.{key} == "{value}")')
        
        # fields
        if query.fields:
            field_filter = " or ".join([f'r._field == "{f}"' for f in query.fields])
            parts.append(f'|> filter(fn: (r) => {field_filter})')
        
        # aggregate
        if query.aggregate and query.aggregate_interval:
            if query.group_by:
                group = ", ".join([f'"{g}"' for g in query.group_by])
                parts.append(f'|> aggregateWindow(every: {query.aggregate_interval}, fn: {query.aggregate}, by: [{group}])')
            else:
                parts.append(f'|> aggregateWindow(every: {query.aggregate_interval}, fn: {query.aggregate})')
        elif query.group_by:
            group = ", ".join([f'"{g}"' for g in query.group_by])
            parts.append(f'|> group(by: [{group}])')
        
        # limit
        if query.limit > 0:
            parts.append(f'|> limit(n: {query.limit})')
        
        # sort
        if query.order:
            parts.append(f'|> sort(columns: ["_time"], desc: {query.order == "desc"})')
        
        # yield
        parts.append('|> yield(name: "result")')
        
        return "\n".join(parts)
    
    def _parse_query_result(self, query: InfluxDBQuery, data: Dict) -> InfluxDBResult:
        """Parse le résultat d'une requête."""
        series = []
        row_count = 0
        
        try:
            if "results" in data:
                for result in data["results"]:
                    if "series" in result:
                        for serie in result["series"]:
                            series.append(serie)
                            if "values" in serie:
                                row_count += len(serie["values"])
        
        except Exception as e:
            logger.error(f"Parse result error: {e}")
        
        return InfluxDBResult(
            query_id=query.query_id,
            measurement=query.measurement,
            series=series,
            row_count=row_count
        )
    
    def _parse_retention_duration(self, retention: InfluxDBRetention) -> int:
        """Parse la durée de rétention en secondes."""
        duration_map = {
            InfluxDBRetention.HOURS_1: 3600,
            InfluxDBRetention.HOURS_24: 86400,
            InfluxDBRetention.DAYS_7: 604800,
            InfluxDBRetention.DAYS_30: 2592000,
            InfluxDBRetention.DAYS_90: 7776000,
            InfluxDBRetention.DAYS_180: 15552000,
            InfluxDBRetention.DAYS_365: 31536000,
            InfluxDBRetention.INFINITE: 0
        }
        return duration_map.get(retention, 2592000)
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, query: InfluxDBQuery) -> str:
        """Calcule une clé de cache."""
        import hashlib
        key_data = {
            "measurement": query.measurement,
            "fields": sorted(query.fields),
            "tags": query.tags,
            "start": query.start_time.isoformat() if query.start_time else None,
            "end": query.end_time.isoformat() if query.end_time else None,
            "group_by": sorted(query.group_by) if query.group_by else None,
            "aggregate": query.aggregate,
            "aggregate_interval": query.aggregate_interval,
            "limit": query.limit,
            "order": query.order
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._query_cache) > self.config["cache_size"]:
                        keys = list(self._query_cache.keys())
                        for key in keys[:len(self._query_cache) - self.config["cache_size"]]:
                            del self._query_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PRIVÉES - ÉCRITURE ==========
    
    async def _write_processor(self) -> None:
        """Traite les écritures en batch."""
        while self._is_running:
            try:
                points = []
                start_time = time.time()
                
                # Collecte des points
                while len(points) < self.config["batch_size"]:
                    try:
                        point = await asyncio.wait_for(
                            self._write_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        points.append(point)
                    except asyncio.TimeoutError:
                        break
                
                if points:
                    # Écriture du batch
                    written = await self.write_batch(points)
                    
                    # Si des points n'ont pas été écrits, réessayer
                    if written < len(points):
                        for point in points[written:]:
                            await self._write_queue.put(point)
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Write processor error: {e}")
                await asyncio.sleep(1)
    
    async def _flush_write_queue(self) -> None:
        """Vide la queue d'écriture."""
        points = []
        while not self._write_queue.empty():
            try:
                point = self._write_queue.get_nowait()
                points.append(point)
            except asyncio.QueueEmpty:
                break
        
        if points:
            await self.write_batch(points)
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_buckets(self) -> None:
        """Charge les buckets existants."""
        try:
            url = f"{self.url}/api/v2/buckets"
            params = {"org": self.org}
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for bucket_data in data.get("buckets", []):
                        bucket = InfluxDBBucket(
                            name=bucket_data.get("name", ""),
                            retention_policy=InfluxDBRetention.DAYS_30
                        )
                        with self._buckets_lock:
                            self._buckets[bucket.bucket_id] = bucket
                    
                    logger.info(f"Loaded {len(self._buckets)} buckets")
                else:
                    logger.warning(f"Failed to load buckets: {response.status}")
                    
        except Exception as e:
            logger.error(f"Load buckets error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._buckets_lock:
                    self._stats["buckets"] = len(self._buckets)
                with self._cache_lock:
                    self._stats["cache_size"] = len(self._query_cache)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "influxdb:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_bucket(self, bucket_id: str) -> Optional[InfluxDBBucket]:
        """Récupère un bucket."""
        with self._buckets_lock:
            return self._buckets.get(bucket_id)
    
    async def get_buckets(self) -> List[InfluxDBBucket]:
        """Récupère les buckets."""
        with self._buckets_lock:
            return list(self._buckets.values())
    
    async def delete_bucket(self, bucket_id: str) -> bool:
        """Supprime un bucket."""
        with self._buckets_lock:
            if bucket_id not in self._buckets:
                return False
            
            bucket = self._buckets[bucket_id]
            del self._buckets[bucket_id]
        
        try:
            url = f"{self.url}/api/v2/buckets/{bucket_id}"
            async with self._session.delete(url) as response:
                if response.status in [200, 204]:
                    logger.info(f"Bucket deleted: {bucket.name}")
                    return True
                else:
                    logger.error(f"Delete bucket error: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Delete bucket error: {e}")
            return False
    
    async def get_measurements(self) -> List[str]:
        """Récupère les mesures disponibles."""
        query = InfluxDBQuery(
            measurement="",
            fields=[],
            tags={},
            limit=100
        )
        query.sql = "SHOW MEASUREMENTS"
        
        # Dans un système réel, on exécuterait la requête
        return []
    
    async def get_tags(self, measurement: str) -> Dict[str, List[str]]:
        """Récupère les tags d'une mesure."""
        query = InfluxDBQuery(
            measurement=measurement,
            fields=[],
            tags={}
        )
        query.sql = f"SHOW TAG KEYS FROM {measurement}"
        
        # Dans un système réel, on exécuterait la requête
        return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._buckets_lock:
            self._stats["total_buckets"] = len(self._buckets)
        with self._cache_lock:
            self._stats["cached_queries"] = len(self._query_cache)
        
        return self._stats.copy()


# ============== INFLUXDB POINT BUILDER ==============

class InfluxDBPointBuilder:
    """
    Constructeur de points InfluxDB.
    Facilite la création de points de données.
    """
    
    def __init__(self):
        self._point = InfluxDBPoint()
    
    def measurement(self, measurement: str) -> 'InfluxDBPointBuilder':
        """Définit la mesure."""
        self._point.measurement = measurement
        return self
    
    def tag(self, key: str, value: str) -> 'InfluxDBPointBuilder':
        """Ajoute un tag."""
        self._point.tags[key] = value
        return self
    
    def field(self, key: str, value: Any) -> 'InfluxDBPointBuilder':
        """Ajoute un champ."""
        self._point.fields[key] = value
        return self
    
    def timestamp(self, timestamp: datetime) -> 'InfluxDBPointBuilder':
        """Définit le timestamp."""
        self._point.timestamp = timestamp
        return self
    
    def precision(self, precision: InfluxDBPrecision) -> 'InfluxDBPointBuilder':
        """Définit la précision."""
        self._point.precision = precision
        return self
    
    def build(self) -> InfluxDBPoint:
        """Construit le point."""
        if not self._point.measurement:
            raise ValueError("Measurement is required")
        if not self._point.fields:
            raise ValueError("At least one field is required")
        return self._point


# ============== FACTORY ==============

class InfluxDBFactory:
    """Factory pour créer des composants InfluxDB."""
    
    @staticmethod
    async def create_engine(
        url: str,
        token: str,
        org: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> InfluxDBEngine:
        """Crée un moteur InfluxDB."""
        engine = InfluxDBEngine(
            url=url,
            token=token,
            org=org,
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_point_builder() -> InfluxDBPointBuilder:
        """Crée un constructeur de points."""
        return InfluxDBPointBuilder()
    
    @staticmethod
    def create_bucket(
        name: str,
        data_type: InfluxDBDataType = InfluxDBDataType.METRIC,
        retention: InfluxDBRetention = InfluxDBRetention.DAYS_30
    ) -> InfluxDBBucket:
        """Crée un bucket."""
        return InfluxDBBucket(
            name=name,
            data_type=data_type,
            retention_policy=retention
        )


# ============== EXPORT ==============

__all__ = [
    "InfluxDBDataType",
    "InfluxDBPrecision",
    "InfluxDBRetention",
    "InfluxDBPoint",
    "InfluxDBQuery",
    "InfluxDBResult",
    "InfluxDBBucket",
    "InfluxDBEngineInterface",
    "InfluxDBEngine",
    "InfluxDBPointBuilder",
    "InfluxDBFactory"
]
