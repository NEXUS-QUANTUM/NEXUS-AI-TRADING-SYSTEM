# trading/bots/hedge_bot/hedge_bot_data_lake.py
# Advanced Data Lake & Storage Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Lake Module - Module avancé de data lake et de gestion de stockage pour le Hedge Bot.
Gère le stockage de données massives, l'organisation des partitions, l'optimisation des coûts,
la gestion du cycle de vie des données et l'accès aux données pour l'ensemble du système.
"""

import asyncio
import json
import time
import os
import shutil
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
import hashlib
import pickle
import zlib
import gzip
from pathlib import Path
import aiofiles
import aiofiles.os

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_lake")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class DataLakeStorage(Enum):
    """Types de stockage du data lake."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    HDFS = "hdfs"
    ICEBERG = "iceberg"
    DELTA = "delta"
    HUDI = "hudi"


class DataLakeFormat(Enum):
    """Formats de données du data lake."""
    PARQUET = "parquet"
    ORC = "orc"
    AVRO = "avro"
    JSON = "json"
    CSV = "csv"
    ARROW = "arrow"
    HDF5 = "hdf5"
    PROTOBUF = "protobuf"


class DataLakePartition(Enum):
    """Types de partitionnement."""
    DATE = "date"
    HOUR = "hour"
    SYMBOL = "symbol"
    DATA_TYPE = "data_type"
    CUSTOM = "custom"
    COMPOSITE = "composite"


class DataLakeCompression(Enum):
    """Méthodes de compression."""
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    ZLIB = "zlib"
    ZSTD = "zstd"
    LZ4 = "lz4"


# ============== DATA MODELS ==============

@dataclass
class DataLakeTable:
    """Table du data lake."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    data_type: DataType = DataType.MARKET
    storage: DataLakeStorage = DataLakeStorage.LOCAL
    format: DataLakeFormat = DataLakeFormat.PARQUET
    partition_by: List[DataLakePartition] = field(default_factory=list)
    partition_fields: List[str] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=dict)
    compression: DataLakeCompression = DataLakeCompression.SNAPPY
    location: str = ""
    retention_days: int = 365
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "data_type": self.data_type.value,
            "storage": self.storage.value,
            "format": self.format.value,
            "partition_by": [p.value for p in self.partition_by],
            "partition_fields": self.partition_fields,
            "schema": self.schema,
            "compression": self.compression.value,
            "location": self.location,
            "retention_days": self.retention_days,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "active": self.active
        }


@dataclass
class DataLakePartition:
    """Partition du data lake."""
    partition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_id: str = ""
    partition_key: str = ""
    partition_value: str = ""
    location: str = ""
    row_count: int = 0
    size_bytes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataLakeQuery:
    """Requête sur le data lake."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    filter: Dict[str, Any] = field(default_factory=dict)
    columns: List[str] = field(default_factory=list)
    partitions: Dict[str, str] = field(default_factory=dict)
    limit: int = 1000
    offset: int = 0
    order_by: List[Tuple[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class DataLakeEngineInterface(ABC):
    """Interface abstraite pour le moteur de data lake."""
    
    @abstractmethod
    async def create_table(self, table: DataLakeTable) -> str:
        """Crée une table dans le data lake."""
        pass
    
    @abstractmethod
    async def write_data(self, table_name: str, data: pd.DataFrame) -> int:
        """Écrit des données dans le data lake."""
        pass
    
    @abstractmethod
    async def read_data(self, query: DataLakeQuery) -> pd.DataFrame:
        """Lit des données du data lake."""
        pass


# ============== IMPLÉMENTATION ==============

class DataLakeEngine(DataLakeEngineInterface):
    """
    Moteur de data lake avancé pour le Hedge Bot.
    Gère le stockage massif de données, les partitions, l'optimisation des coûts.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des tables
        self._tables: Dict[str, DataLakeTable] = {}
        self._tables_lock = threading.RLock()
        
        # Gestion des partitions
        self._partitions: Dict[str, List[DataLakePartition]] = defaultdict(list)
        self._partitions_lock = threading.RLock()
        
        # Base du data lake
        self._base_path = Path(self.config.get("base_path", "./datalake"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # Cache des données
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "tables_created": 0,
            "partitions_created": 0,
            "rows_written": 0,
            "rows_read": 0,
            "data_volume_mb": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("DataLakeEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./datalake",
            "default_format": DataLakeFormat.PARQUET,
            "default_compression": DataLakeCompression.SNAPPY,
            "default_storage": DataLakeStorage.LOCAL,
            "batch_size": 10000,
            "max_file_size": 1024 * 1024 * 1024,  # 1 GB
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_compression": True,
            "enable_encryption": False,
            "partitioning_enabled": True,
            "auto_compact": True,
            "compact_threshold": 10
        }
    
    async def start(self) -> None:
        """Démarre le moteur de data lake."""
        logger.info("DataLakeEngine starting...")
        self._is_running = True
        
        # Chargement des tables existantes
        await self._load_tables()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._compaction_loop())
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("DataLakeEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de data lake."""
        logger.info("DataLakeEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("DataLakeEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, table: DataLakeTable) -> str:
        """Crée une table dans le data lake."""
        # Création du répertoire de la table
        table_path = self._base_path / table.name
        table_path.mkdir(parents=True, exist_ok=True)
        
        # Mise à jour de l'emplacement
        table.location = str(table_path)
        
        with self._tables_lock:
            self._tables[table.table_id] = table
            self._stats["tables_created"] += 1
        
        # Création du fichier de métadonnées
        metadata_path = table_path / "_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(table.to_dict(), f, indent=2)
        
        logger.info(f"Data lake table created: {table.name} at {table_path}")
        return table.table_id
    
    async def write_data(self, table_name: str, data: pd.DataFrame) -> int:
        """Écrit des données dans le data lake."""
        start_time = time.time()
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Préparation des données
            data = self._prepare_data(data, table)
            
            # Partitionnement
            partitions = await self._partition_data(data, table)
            
            # Écriture des partitions
            total_rows = 0
            for partition_key, partition_data in partitions.items():
                rows = await self._write_partition(table, partition_key, partition_data)
                total_rows += rows
            
            # Mise à jour de la table
            table.row_count += total_rows
            table.updated_at = datetime.now(timezone.utc)
            
            # Mise à jour des statistiques
            self._stats["rows_written"] += total_rows
            
            # Mise à jour du cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    self._data_cache[table_name] = data
            
            execution_time = time.time() - start_time
            logger.info(f"Data written to {table_name}: {total_rows} rows "
                       f"in {execution_time:.2f}s")
            
            return total_rows
            
        except Exception as e:
            logger.error(f"Write data error: {e}")
            raise
    
    async def read_data(self, query: DataLakeQuery) -> pd.DataFrame:
        """Lit des données du data lake."""
        start_time = time.time()
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(query)
            if self.config["enable_cache"] and cache_key in self._data_cache:
                self._stats["cache_hits"] += 1
                logger.debug(f"Cache hit for {cache_key}")
                return self._data_cache[cache_key]
            
            self._stats["cache_misses"] += 1
            
            # Récupération de la table
            table = await self.get_table_by_name(query.table_name)
            if not table:
                raise ValueError(f"Table {query.table_name} not found")
            
            # Lecture des données
            data = await self._read_partitions(table, query)
            
            # Filtrage
            if query.filter:
                data = self._apply_filters(data, query.filter)
            
            # Sélection des colonnes
            if query.columns:
                data = data[query.columns]
            
            # Tri
            if query.order_by:
                for col, direction in reversed(query.order_by):
                    data = data.sort_values(col, ascending=direction == "asc")
            
            # Limitation
            if query.limit > 0:
                data = data.iloc[query.offset:query.offset + query.limit]
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._data_cache) < self.config["cache_size"]:
                        self._data_cache[cache_key] = data
            
            self._stats["rows_read"] += len(data)
            
            execution_time = time.time() - start_time
            logger.debug(f"Data read from {query.table_name}: {len(data)} rows "
                       f"in {execution_time:.2f}s")
            
            return data
            
        except Exception as e:
            logger.error(f"Read data error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - ÉCRITURE ==========
    
    async def _write_partition(
        self,
        table: DataLakeTable,
        partition_key: str,
        data: pd.DataFrame
    ) -> int:
        """Écrit une partition."""
        if data.empty:
            return 0
        
        # Création du répertoire de partition
        partition_path = Path(table.location) / partition_key
        partition_path.mkdir(parents=True, exist_ok=True)
        
        # Nom du fichier
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_name = f"data_{timestamp}.{table.format.value}"
        file_path = partition_path / file_name
        
        # Écriture selon le format
        if table.format == DataLakeFormat.PARQUET:
            data.to_parquet(
                file_path,
                compression=table.compression.value,
                index=False
            )
        elif table.format == DataLakeFormat.CSV:
            data.to_csv(file_path, index=False)
        elif table.format == DataLakeFormat.JSON:
            data.to_json(file_path, orient="records", lines=True)
        else:
            # Par défaut: Parquet
            data.to_parquet(file_path, index=False)
        
        # Enregistrement de la partition
        partition = DataLakePartition(
            table_id=table.table_id,
            partition_key=partition_key.split("=")[0] if "=" in partition_key else "default",
            partition_value=partition_key.split("=")[1] if "=" in partition_key else partition_key,
            location=str(partition_path),
            row_count=len(data),
            size_bytes=file_path.stat().st_size
        )
        
        with self._partitions_lock:
            self._partitions[table.table_id].append(partition)
            self._stats["partitions_created"] += 1
        
        # Mise à jour de la taille de la table
        table.size_bytes += file_path.stat().st_size
        
        return len(data)
    
    async def _partition_data(
        self,
        data: pd.DataFrame,
        table: DataLakeTable
    ) -> Dict[str, pd.DataFrame]:
        """Partitionne les données."""
        partitions = {}
        
        if not self.config["partitioning_enabled"] or not table.partition_fields:
            # Pas de partitionnement
            partitions["default"] = data
            return partitions
        
        # Partitionnement par champs
        for field in table.partition_fields:
            if field in data.columns:
                for value in data[field].unique():
                    partition_key = f"{field}={value}"
                    partition_data = data[data[field] == value]
                    partitions[partition_key] = partition_data
        
        return partitions
    
    def _prepare_data(self, data: pd.DataFrame, table: DataLakeTable) -> pd.DataFrame:
        """Prépare les données pour l'écriture."""
        # Gestion des valeurs manquantes
        data = data.fillna("")
        
        # Conversion des types
        for col, dtype in table.schema.items():
            if col in data.columns:
                try:
                    if dtype == "int64":
                        data[col] = data[col].astype(np.int64)
                    elif dtype == "float64":
                        data[col] = data[col].astype(np.float64)
                    elif dtype == "datetime64":
                        data[col] = pd.to_datetime(data[col])
                    elif dtype == "object":
                        data[col] = data[col].astype(str)
                except:
                    pass
        
        return data
    
    # ========== MÉTHODES PRIVÉES - LECTURE ==========
    
    async def _read_partitions(
        self,
        table: DataLakeTable,
        query: DataLakeQuery
    ) -> pd.DataFrame:
        """Lit les partitions d'une table."""
        data_frames = []
        
        # Sélection des partitions
        partitions = await self._select_partitions(table, query)
        
        for partition in partitions:
            partition_path = Path(partition.location)
            
            for file_path in partition_path.glob(f"*.{table.format.value}"):
                try:
                    if table.format == DataLakeFormat.PARQUET:
                        df = pd.read_parquet(file_path)
                    elif table.format == DataLakeFormat.CSV:
                        df = pd.read_csv(file_path)
                    elif table.format == DataLakeFormat.JSON:
                        df = pd.read_json(file_path, lines=True)
                    else:
                        df = pd.read_parquet(file_path)
                    
                    if not df.empty:
                        data_frames.append(df)
                        
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
        
        if not data_frames:
            return pd.DataFrame()
        
        # Fusion des DataFrames
        combined = pd.concat(data_frames, ignore_index=True)
        return combined
    
    async def _select_partitions(
        self,
        table: DataLakeTable,
        query: DataLakeQuery
    ) -> List[DataLakePartition]:
        """Sélectionne les partitions à lire."""
        partitions = []
        
        with self._partitions_lock:
            all_partitions = self._partitions.get(table.table_id, [])
            
            if query.partitions:
                # Filtrage par partitions
                for partition in all_partitions:
                    match = True
                    for key, value in query.partitions.items():
                        if partition.partition_key == key:
                            if partition.partition_value != value:
                                match = False
                                break
                    if match:
                        partitions.append(partition)
            else:
                partitions = all_partitions
        
        return partitions
    
    def _apply_filters(self, data: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
        """Applique des filtres aux données."""
        result = data.copy()
        
        for key, value in filters.items():
            if key in result.columns:
                if isinstance(value, (list, tuple)):
                    result = result[result[key].isin(value)]
                elif isinstance(value, dict):
                    op = value.get("operator", "eq")
                    val = value.get("value")
                    
                    if op == "eq":
                        result = result[result[key] == val]
                    elif op == "ne":
                        result = result[result[key] != val]
                    elif op == "gt":
                        result = result[result[key] > val]
                    elif op == "gte":
                        result = result[result[key] >= val]
                    elif op == "lt":
                        result = result[result[key] < val]
                    elif op == "lte":
                        result = result[result[key] <= val]
                    elif op == "contains":
                        result = result[result[key].str.contains(val, na=False)]
                else:
                    result = result[result[key] == value]
        
        return result
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _compaction_loop(self) -> None:
        """Boucle de compaction des données."""
        if not self.config["auto_compact"]:
            return
        
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                with self._tables_lock:
                    for table in self._tables.values():
                        await self._compact_table(table)
                
            except Exception as e:
                logger.error(f"Compaction loop error: {e}")
    
    async def _compact_table(self, table: DataLakeTable) -> None:
        """Compacte une table."""
        with self._partitions_lock:
            partitions = self._partitions.get(table.table_id, [])
            
            if len(partitions) < self.config["compact_threshold"]:
                return
            
            # Groupement par partition
            partition_groups = defaultdict(list)
            for partition in partitions:
                key = f"{partition.partition_key}={partition.partition_value}"
                partition_groups[key].append(partition)
            
            # Compaction de chaque groupe
            for key, group in partition_groups.items():
                if len(group) > 1:
                    await self._compact_partition_group(table, key, group)
    
    async def _compact_partition_group(
        self,
        table: DataLakeTable,
        partition_key: str,
        partitions: List[DataLakePartition]
    ) -> None:
        """Compacte un groupe de partitions."""
        data_frames = []
        
        # Lecture des données
        for partition in partitions:
            partition_path = Path(partition.location)
            for file_path in partition_path.glob(f"*.{table.format.value}"):
                try:
                    if table.format == DataLakeFormat.PARQUET:
                        df = pd.read_parquet(file_path)
                    else:
                        df = pd.read_csv(file_path)
                    if not df.empty:
                        data_frames.append(df)
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
        
        if not data_frames:
            return
        
        # Fusion
        combined = pd.concat(data_frames, ignore_index=True)
        
        # Réécriture
        partition_path = Path(table.location) / partition_key
        partition_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_name = f"data_{timestamp}.{table.format.value}"
        file_path = partition_path / file_name
        
        if table.format == DataLakeFormat.PARQUET:
            combined.to_parquet(file_path, compression=table.compression.value, index=False)
        else:
            combined.to_csv(file_path, index=False)
        
        # Suppression des anciens fichiers
        for partition in partitions:
            partition_path = Path(partition.location)
            if partition_path.exists():
                shutil.rmtree(partition_path)
        
        # Mise à jour des partitions
        with self._partitions_lock:
            self._partitions[table.table_id] = [
                p for p in self._partitions[table.table_id]
                if p not in partitions
            ]
        
        # Création de la nouvelle partition
        new_partition = DataLakePartition(
            table_id=table.table_id,
            partition_key=partition_key.split("=")[0],
            partition_value=partition_key.split("=")[1],
            location=str(partition_path),
            row_count=len(combined),
            size_bytes=file_path.stat().st_size
        )
        
        with self._partitions_lock:
            self._partitions[table.table_id].append(new_partition)
        
        logger.info(f"Compacted partition {partition_key} for table {table.name}")
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage des données expirées."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=365)
                
                with self._tables_lock:
                    for table in self._tables.values():
                        if table.retention_days > 0:
                            # Suppression des données expirées
                            pass
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
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
    
    def _compute_cache_key(self, query: DataLakeQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "table": query.table_name,
            "filter": query.filter,
            "columns": sorted(query.columns),
            "partitions": query.partitions,
            "limit": query.limit,
            "order": query.order_by
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_tables(self) -> None:
        """Charge les tables existantes."""
        try:
            for table_dir in self._base_path.iterdir():
                if table_dir.is_dir():
                    metadata_path = table_dir / "_metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r') as f:
                            data = json.load(f)
                        
                        table = self._deserialize_table(data)
                        if table:
                            with self._tables_lock:
                                self._tables[table.table_id] = table
                            
                            # Chargement des partitions
                            for partition_dir in table_dir.iterdir():
                                if partition_dir.is_dir() and not partition_dir.name.startswith("_"):
                                    partition = DataLakePartition(
                                        table_id=table.table_id,
                                        partition_key=partition_dir.name.split("=")[0],
                                        partition_value=partition_dir.name.split("=")[1],
                                        location=str(partition_dir)
                                    )
                                    with self._partitions_lock:
                                        self._partitions[table.table_id].append(partition)
            
            logger.info(f"Loaded {len(self._tables)} tables")
            
        except Exception as e:
            logger.error(f"Load tables error: {e}")
    
    def _deserialize_table(self, data: Dict) -> Optional[DataLakeTable]:
        """Désérialise une table."""
        try:
            return DataLakeTable(
                table_id=data.get("table_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                data_type=DataType(data.get("data_type", "market")),
                storage=DataLakeStorage(data.get("storage", "local")),
                format=DataLakeFormat(data.get("format", "parquet")),
                partition_by=[DataLakePartition(p) for p in data.get("partition_by", [])],
                partition_fields=data.get("partition_fields", []),
                schema=data.get("schema", {}),
                compression=DataLakeCompression(data.get("compression", "snappy")),
                location=data.get("location", ""),
                retention_days=data.get("retention_days", 365),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                row_count=data.get("row_count", 0),
                size_bytes=data.get("size_bytes", 0),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing table: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_table(self, table_id: str) -> Optional[DataLakeTable]:
        """Récupère une table."""
        with self._tables_lock:
            return self._tables.get(table_id)
    
    async def get_table_by_name(self, name: str) -> Optional[DataLakeTable]:
        """Récupère une table par son nom."""
        with self._tables_lock:
            for table in self._tables.values():
                if table.name == name:
                    return table
        return None
    
    async def get_tables(self) -> List[DataLakeTable]:
        """Récupère les tables."""
        with self._tables_lock:
            return list(self._tables.values())
    
    async def get_partitions(self, table_id: str) -> List[DataLakePartition]:
        """Récupère les partitions d'une table."""
        with self._partitions_lock:
            return self._partitions.get(table_id, [])
    
    async def delete_table(self, table_name: str) -> bool:
        """Supprime une table."""
        table = await self.get_table_by_name(table_name)
        if not table:
            return False
        
        # Suppression du répertoire
        import shutil
        table_path = Path(table.location)
        if table_path.exists():
            shutil.rmtree(table_path)
        
        # Suppression de la table
        with self._tables_lock:
            del self._tables[table.table_id]
        
        # Suppression des partitions
        with self._partitions_lock:
            if table.table_id in self._partitions:
                del self._partitions[table.table_id]
        
        logger.info(f"Table deleted: {table_name}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._tables_lock:
            self._stats["tables"] = len(self._tables)
        with self._partitions_lock:
            self._stats["partitions"] = sum(len(p) for p in self._partitions.values())
        
        return self._stats.copy()


# ============== FACTORY ==============

class DataLakeFactory:
    """Factory pour créer des composants de data lake."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DataLakeEngine:
        """Crée un moteur de data lake."""
        engine = DataLakeEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "DataLakeStorage",
    "DataLakeFormat",
    "DataLakePartition",
    "DataLakeCompression",
    "DataLakeTable",
    "DataLakePartition",
    "DataLakeQuery",
    "DataLakeEngineInterface",
    "DataLakeEngine",
    "DataLakeFactory"
]
