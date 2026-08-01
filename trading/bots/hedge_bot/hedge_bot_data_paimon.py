# trading/bots/hedge_bot/hedge_bot_data_paimon.py
# Advanced Apache Paimon Integration & Lakehouse Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Paimon Integration Module - Module d'intégration avancé avec Apache Paimon pour le Hedge Bot.
Gère le data lakehouse, les tables ACID, le streaming, le time travel, l'optimisation
des requêtes, et la gestion des métadonnées pour les données de hedging.
"""

import asyncio
import json
import time
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import threading
import concurrent.futures
import pickle
import zlib
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.fs as fs

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_paimon")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class PaimonTableType(Enum):
    """Types de tables Paimon."""
    PRIMARY_KEY = "primary_key"        # Table avec clé primaire
    APPEND_ONLY = "append_only"        # Table append-only
    CHANGELOG = "changelog"            # Table changelog
    ANALYTICS = "analytics"            # Table analytique


class PaimonBucketType(Enum):
    """Types de bucket Paimon."""
    HASH = "hash"                      # Bucketing par hachage
    RANGE = "range"                    # Bucketing par plage
    KEY = "key"                        # Bucketing par clé
    NONE = "none"                      # Pas de bucket


class PaimonCompression(Enum):
    """Méthodes de compression Paimon."""
    NONE = "none"
    ZSTD = "zstd"
    LZ4 = "lz4"
    SNAPPY = "snappy"
    GZIP = "gzip"


class PaimonChangelogMode(Enum):
    """Modes de changelog Paimon."""
    NONE = "none"
    INPUT = "input"
    UPSERT = "upsert"
    FULL = "full"


# ============== DATA MODELS ==============

@dataclass
class PaimonTable:
    """Modèle de table Paimon."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    database: str = "default"
    table_type: PaimonTableType = PaimonTableType.APPEND_ONLY
    primary_keys: List[str] = field(default_factory=list)
    partition_keys: List[str] = field(default_factory=list)
    bucket_type: PaimonBucketType = PaimonBucketType.NONE
    bucket_count: int = 1
    changelog_mode: PaimonChangelogMode = PaimonChangelogMode.NONE
    compression: PaimonCompression = PaimonCompression.ZSTD
    schema: Dict[str, str] = field(default_factory=dict)
    location: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    snapshot_count: int = 0
    active: bool = True
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "database": self.database,
            "table_type": self.table_type.value,
            "primary_keys": self.primary_keys,
            "partition_keys": self.partition_keys,
            "bucket_type": self.bucket_type.value,
            "bucket_count": self.bucket_count,
            "changelog_mode": self.changelog_mode.value,
            "compression": self.compression.value,
            "schema": self.schema,
            "location": self.location,
            "properties": self.properties,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "snapshot_count": self.snapshot_count,
            "active": self.active,
            "version": self.version
        }


@dataclass
class PaimonSnapshot:
    """Snapshot Paimon."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_id: str = ""
    snapshot_number: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_records: int = 0
    total_size: int = 0
    operation: str = "create"  # create, append, compact, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class PaimonRecord:
    """Enregistrement Paimon."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    operation: str = "insert"  # insert, update, delete
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    partition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaimonQuery:
    """Requête Paimon."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    database: str = "default"
    filters: Dict[str, Any] = field(default_factory=dict)
    columns: List[str] = field(default_factory=list)
    partitions: List[str] = field(default_factory=list)
    limit: int = 1000
    snapshot: Optional[int] = None
    time_travel: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class PaimonEngineInterface(ABC):
    """Interface abstraite pour le moteur Paimon."""
    
    @abstractmethod
    async def create_table(self, table: PaimonTable) -> bool:
        """Crée une table Paimon."""
        pass
    
    @abstractmethod
    async def write_records(self, table_name: str, records: List[PaimonRecord]) -> int:
        """Écrit des enregistrements."""
        pass
    
    @abstractmethod
    async def read_snapshot(self, query: PaimonQuery) -> pd.DataFrame:
        """Lit un snapshot."""
        pass
    
    @abstractmethod
    async def time_travel(self, table_name: str, timestamp: datetime) -> pd.DataFrame:
        """Time travel sur une table."""
        pass


# ============== IMPLÉMENTATION ==============

class PaimonEngine(PaimonEngineInterface):
    """
    Moteur Paimon avancé pour le Hedge Bot.
    Gère l'intégration avec Apache Paimon, le data lakehouse et le streaming.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des tables
        self._tables: Dict[str, PaimonTable] = {}
        self._tables_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: Dict[str, PaimonSnapshot] = {}
        self._snapshots_lock = threading.RLock()
        
        # Gestion des enregistrements
        self._records: Dict[str, List[PaimonRecord]] = defaultdict(list)
        self._records_lock = threading.RLock()
        
        # Cache des données
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "tables_created": 0,
            "records_written": 0,
            "records_read": 0,
            "snapshots_created": 0,
            "time_travel_ops": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "data_volume_mb": 0.0,
            "avg_write_time_ms": 0.0,
            "avg_read_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Base path pour les tables
        self._base_path = Path(self.config.get("base_path", "./paimon_data"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # Filesystem PyArrow
        self._fs = fs.LocalFileSystem()
        
        # État
        self._is_running = False
        
        logger.info("PaimonEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./paimon_data",
            "default_compression": PaimonCompression.ZSTD,
            "default_table_type": PaimonTableType.APPEND_ONLY,
            "default_bucket_count": 1,
            "changelog_mode": PaimonChangelogMode.NONE,
            "snapshot_retention": 30,  # jours
            "enable_cache": True,
            "cache_size": 10000,
            "batch_size": 10000,
            "compression_level": 6,
            "enable_compression": True,
            "max_file_size": 1024 * 1024 * 1024  # 1 GB
        }
    
    async def start(self) -> None:
        """Démarre le moteur Paimon."""
        logger.info("PaimonEngine starting...")
        self._is_running = True
        
        # Chargement des tables existantes
        await self._load_tables()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._snapshot_cleanup_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("PaimonEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Paimon."""
        logger.info("PaimonEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("PaimonEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, table: PaimonTable) -> bool:
        """Crée une table Paimon."""
        with self._tables_lock:
            self._tables[table.table_id] = table
            self._stats["tables_created"] += 1
        
        # Création du dossier de la table
        table_path = self._base_path / table.database / table.name
        table_path.mkdir(parents=True, exist_ok=True)
        
        # Création des métadonnées
        metadata_path = table_path / "_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(table.to_dict(), f, indent=2)
        
        # Création du schéma
        schema_path = table_path / "_schema.json"
        with open(schema_path, 'w') as f:
            json.dump(table.schema, f, indent=2)
        
        logger.info(f"Paimon table created: {table.database}.{table.name} at {table_path}")
        return True
    
    async def write_records(self, table_name: str, records: List[PaimonRecord]) -> int:
        """Écrit des enregistrements."""
        start_time = time.time()
        self._stats["records_written"] += len(records)
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Organisation des enregistrements par partition
            partition_data = defaultdict(list)
            for record in records:
                partition_key = record.partition or "default"
                partition_data[partition_key].append(record)
            
            # Écriture par partition
            total_written = 0
            for partition_key, partition_records in partition_data.items():
                # Création du dossier de partition
                partition_path = self._base_path / table.database / table.name / partition_key
                partition_path.mkdir(parents=True, exist_ok=True)
                
                # Conversion en DataFrame
                data = [r.data for r in partition_records]
                df = pd.DataFrame(data)
                
                # Compression
                compression = table.compression.value if table.compression != PaimonCompression.NONE else None
                
                # Écriture des fichiers Parquet
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                file_name = f"data_{timestamp}_{uuid.uuid4().hex[:8]}.parquet"
                file_path = partition_path / file_name
                
                # Écriture avec PyArrow
                table_arrow = pa.Table.from_pandas(df)
                pq.write_table(
                    table_arrow,
                    str(file_path),
                    compression=compression,
                    use_dictionary=True,
                    write_statistics=True
                )
                
                total_written += len(partition_records)
                
                # Mise à jour de la taille
                table.size_bytes += file_path.stat().st_size
            
            # Mise à jour du row count
            table.row_count += total_written
            
            # Création du snapshot
            snapshot = PaimonSnapshot(
                table_id=table.table_id,
                snapshot_number=table.snapshot_count + 1,
                total_records=total_written,
                total_size=sum(len(pickle.dumps(r.data)) for r in records),
                operation="append",
                metadata={"partition_count": len(partition_data)}
            )
            
            with self._snapshots_lock:
                self._snapshots[snapshot.snapshot_id] = snapshot
                self._stats["snapshots_created"] += 1
            
            table.snapshot_count += 1
            table.updated_at = datetime.now(timezone.utc)
            
            # Mise à jour des statistiques
            write_time = (time.time() - start_time) * 1000
            self._stats["avg_write_time_ms"] = (
                self._stats["avg_write_time_ms"] * 0.9 + write_time * 0.1
            )
            
            # Mise à jour du cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    cache_key = f"{table_name}_latest"
                    self._data_cache[cache_key] = pd.DataFrame([r.data for r in records])
            
            logger.info(f"Records written to {table_name}: {total_written} records")
            return total_written
            
        except Exception as e:
            logger.error(f"Write records error: {e}")
            raise
    
    async def read_snapshot(self, query: PaimonQuery) -> pd.DataFrame:
        """Lit un snapshot."""
        start_time = time.time()
        self._stats["records_read"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(query.table_name, query.database)
            if not table:
                raise ValueError(f"Table {query.table_name} not found")
            
            # Vérification du cache
            cache_key = self._compute_cache_key(query)
            if self.config["enable_cache"] and cache_key in self._data_cache:
                self._stats["cache_hits"] += 1
                return self._data_cache[cache_key]
            
            self._stats["cache_misses"] += 1
            
            # Lecture des données
            table_path = self._base_path / table.database / table.name
            
            # Sélection des partitions
            partition_paths = []
            if query.partitions:
                for partition in query.partitions:
                    partition_paths.append(table_path / partition)
            else:
                partition_paths = [p for p in table_path.iterdir() if p.is_dir()]
            
            # Lecture des fichiers
            data_frames = []
            for partition_path in partition_paths:
                for file_path in partition_path.glob("*.parquet"):
                    try:
                        df = pd.read_parquet(str(file_path))
                        data_frames.append(df)
                    except Exception as e:
                        logger.warning(f"Error reading file {file_path}: {e}")
            
            if not data_frames:
                return pd.DataFrame()
            
            # Fusion des DataFrames
            result = pd.concat(data_frames, ignore_index=True)
            
            # Application des filtres
            if query.filters:
                for key, value in query.filters.items():
                    if key in result.columns:
                        if isinstance(value, (list, tuple)):
                            result = result[result[key].isin(value)]
                        else:
                            result = result[result[key] == value]
            
            # Sélection des colonnes
            if query.columns:
                result = result[query.columns]
            
            # Limitation
            if query.limit > 0:
                result = result.head(query.limit)
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._data_cache) < self.config["cache_size"]:
                        self._data_cache[cache_key] = result
            
            # Mise à jour des statistiques
            read_time = (time.time() - start_time) * 1000
            self._stats["avg_read_time_ms"] = (
                self._stats["avg_read_time_ms"] * 0.9 + read_time * 0.1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Read snapshot error: {e}")
            raise
    
    async def time_travel(self, table_name: str, timestamp: datetime) -> pd.DataFrame:
        """Time travel sur une table."""
        self._stats["time_travel_ops"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Recherche du snapshot le plus proche
            snapshot = None
            with self._snapshots_lock:
                for snap in self._snapshots.values():
                    if snap.table_id == table.table_id and snap.timestamp <= timestamp:
                        if snapshot is None or snap.timestamp > snapshot.timestamp:
                            snapshot = snap
            
            if snapshot:
                # Lecture du snapshot
                query = PaimonQuery(
                    table_name=table_name,
                    database=table.database,
                    snapshot=snapshot.snapshot_number
                )
                return await self.read_snapshot(query)
            else:
                return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Time travel error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES ==========
    
    async def _snapshot_cleanup_loop(self) -> None:
        """Nettoie les vieux snapshots."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=self.config["snapshot_retention"]
                )
                
                with self._snapshots_lock:
                    for snapshot_id in list(self._snapshots.keys()):
                        snapshot = self._snapshots[snapshot_id]
                        if snapshot.timestamp < cutoff:
                            del self._snapshots[snapshot_id]
                
            except Exception as e:
                logger.error(f"Snapshot cleanup error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._data_cache) > self.config["cache_size"]:
                        keys = list(self._data_cache.keys())
                        for key in keys[:len(self._data_cache) - self.config["cache_size"]]:
                            del self._data_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._tables_lock:
                    self._stats["total_tables"] = len(self._tables)
                with self._snapshots_lock:
                    self._stats["total_snapshots"] = len(self._snapshots)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "paimon:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _load_tables(self) -> None:
        """Charge les tables existantes."""
        try:
            for db_path in self._base_path.iterdir():
                if db_path.is_dir():
                    for table_path in db_path.iterdir():
                        if table_path.is_dir():
                            metadata_path = table_path / "_metadata.json"
                            if metadata_path.exists():
                                with open(metadata_path, 'r') as f:
                                    data = json.load(f)
                                
                                table = self._deserialize_table(data)
                                if table:
                                    with self._tables_lock:
                                        self._tables[table.table_id] = table
                                    
                                    # Chargement des snapshots
                                    # Dans un système réel, on chargerait les snapshots
            
            logger.info(f"Loaded {len(self._tables)} tables")
            
        except Exception as e:
            logger.error(f"Load tables error: {e}")
    
    def _deserialize_table(self, data: Dict) -> Optional[PaimonTable]:
        """Désérialise une table."""
        try:
            return PaimonTable(
                table_id=data.get("table_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                database=data.get("database", "default"),
                table_type=PaimonTableType(data.get("table_type", "append_only")),
                primary_keys=data.get("primary_keys", []),
                partition_keys=data.get("partition_keys", []),
                bucket_type=PaimonBucketType(data.get("bucket_type", "none")),
                bucket_count=data.get("bucket_count", 1),
                changelog_mode=PaimonChangelogMode(data.get("changelog_mode", "none")),
                compression=PaimonCompression(data.get("compression", "zstd")),
                schema=data.get("schema", {}),
                location=data.get("location", ""),
                properties=data.get("properties", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                row_count=data.get("row_count", 0),
                size_bytes=data.get("size_bytes", 0),
                snapshot_count=data.get("snapshot_count", 0),
                active=data.get("active", True),
                version=data.get("version", 1)
            )
        except Exception as e:
            logger.error(f"Error deserializing table: {e}")
            return None
    
    def _compute_cache_key(self, query: PaimonQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "table": query.table_name,
            "database": query.database,
            "filters": query.filters,
            "columns": sorted(query.columns),
            "partitions": sorted(query.partitions),
            "limit": query.limit,
            "snapshot": query.snapshot
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_table(self, table_id: str) -> Optional[PaimonTable]:
        """Récupère une table."""
        with self._tables_lock:
            return self._tables.get(table_id)
    
    async def get_table_by_name(self, name: str, database: str = "default") -> Optional[PaimonTable]:
        """Récupère une table par son nom."""
        with self._tables_lock:
            for table in self._tables.values():
                if table.name == name and table.database == database:
                    return table
        return None
    
    async def get_tables(self, database: Optional[str] = None) -> List[PaimonTable]:
        """Récupère les tables."""
        with self._tables_lock:
            tables = list(self._tables.values())
            if database:
                tables = [t for t in tables if t.database == database]
            return tables
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[PaimonSnapshot]:
        """Récupère un snapshot."""
        with self._snapshots_lock:
            return self._snapshots.get(snapshot_id)
    
    async def get_snapshots(self, table_name: str) -> List[PaimonSnapshot]:
        """Récupère les snapshots d'une table."""
        table = await self.get_table_by_name(table_name)
        if not table:
            return []
        
        with self._snapshots_lock:
            return [s for s in self._snapshots.values() if s.table_id == table.table_id]
    
    async def compact_table(self, table_name: str) -> Dict[str, Any]:
        """Compacte une table."""
        table = await self.get_table_by_name(table_name)
        if not table:
            return {"error": "Table not found"}
        
        # Simulation de compaction
        # Dans un système réel, on exécuterait la compaction Paimon
        
        return {
            "table": table_name,
            "status": "completed",
            "records_compacted": table.row_count,
            "size_before": table.size_bytes,
            "size_after": table.size_bytes
        }
    
    async def delete_table(self, table_name: str, database: str = "default") -> bool:
        """Supprime une table."""
        table = await self.get_table_by_name(table_name, database)
        if not table:
            return False
        
        # Suppression du dossier
        import shutil
        table_path = self._base_path / database / table_name
        if table_path.exists():
            shutil.rmtree(table_path)
        
        # Suppression de la table
        with self._tables_lock:
            del self._tables[table.table_id]
        
        # Suppression des snapshots
        with self._snapshots_lock:
            for snapshot_id in list(self._snapshots.keys()):
                if self._snapshots[snapshot_id].table_id == table.table_id:
                    del self._snapshots[snapshot_id]
        
        logger.info(f"Table deleted: {database}.{table_name}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._tables_lock:
            self._stats["tables"] = len(self._tables)
        with self._snapshots_lock:
            self._stats["snapshots"] = len(self._snapshots)
        with self._cache_lock:
            self._stats["cache_entries"] = len(self._data_cache)
        
        return self._stats.copy()


# ============== PAIMON RECORD BUILDER ==============

class PaimonRecordBuilder:
    """
    Constructeur d'enregistrements Paimon.
    Facilite la création d'enregistrements pour les tables Paimon.
    """
    
    def __init__(self):
        self._record = PaimonRecord()
    
    def table(self, table_name: str) -> 'PaimonRecordBuilder':
        """Définit la table."""
        self._record.table_id = table_name
        return self
    
    def data(self, data: Dict[str, Any]) -> 'PaimonRecordBuilder':
        """Définit les données."""
        self._record.data = data
        return self
    
    def operation(self, operation: str) -> 'PaimonRecordBuilder':
        """Définit l'opération."""
        self._record.operation = operation
        return self
    
    def partition(self, partition: str) -> 'PaimonRecordBuilder':
        """Définit la partition."""
        self._record.partition = partition
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'PaimonRecordBuilder':
        """Définit les métadonnées."""
        self._record.metadata = metadata
        return self
    
    def build(self) -> PaimonRecord:
        """Construit l'enregistrement."""
        if not self._record.table_id:
            raise ValueError("Table name is required")
        if not self._record.data:
            raise ValueError("Data is required")
        return self._record


# ============== FACTORY ==============

class PaimonFactory:
    """Factory pour créer des composants Paimon."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PaimonEngine:
        """Crée un moteur Paimon."""
        engine = PaimonEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_record_builder() -> PaimonRecordBuilder:
        """Crée un constructeur d'enregistrements."""
        return PaimonRecordBuilder()


# ============== EXPORT ==============

__all__ = [
    "PaimonTableType",
    "PaimonBucketType",
    "PaimonCompression",
    "PaimonChangelogMode",
    "PaimonTable",
    "PaimonSnapshot",
    "PaimonRecord",
    "PaimonQuery",
    "PaimonEngineInterface",
    "PaimonEngine",
    "PaimonRecordBuilder",
    "PaimonFactory"
]
