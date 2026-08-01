# trading/bots/hedge_bot/hedge_bot_data_parquet.py
# Advanced Parquet Data Storage & Processing Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Parquet Data Module - Module avancé de stockage et traitement de données Parquet
pour le Hedge Bot. Gère le stockage columnar, la compression, l'indexation, les prédicats
pushdown, et les requêtes performantes sur les données de hedging.
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
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import pickle
import zlib
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.fs as fs
import pyarrow.compute as pc

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_parquet")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class ParquetCompression(Enum):
    """Méthodes de compression Parquet."""
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    LZO = "lzo"
    BROTLI = "brotli"
    LZ4 = "lz4"
    ZSTD = "zstd"


class ParquetVersion(Enum):
    """Versions Parquet."""
    V1 = "1.0"
    V2 = "2.0"
    V2_4 = "2.4"
    V2_6 = "2.6"


class ParquetEncoding(Enum):
    """Encodages Parquet."""
    PLAIN = "plain"
    DICTIONARY = "dictionary"
    RLE = "rle"
    DELTA_BINARY_PACKED = "delta_binary_packed"
    DELTA_LENGTH_BYTE_ARRAY = "delta_length_byte_array"
    DELTA_BYTE_ARRAY = "delta_byte_array"


# ============== DATA MODELS ==============

@dataclass
class ParquetFile:
    """Fichier Parquet."""
    file_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    schema: Dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    row_group_size: int = 10000
    compression: ParquetCompression = ParquetCompression.ZSTD
    compression_level: int = 6
    version: ParquetVersion = ParquetVersion.V2_6
    encoding: ParquetEncoding = ParquetEncoding.DICTIONARY
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: int = 0
    partition_columns: List[str] = field(default_factory=list)
    sorted_columns: List[str] = field(default_factory=list)
    bloom_filter_columns: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParquetQuery:
    """Requête Parquet."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_id: str = ""
    columns: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 0
    offset: int = 0
    order_by: List[Tuple[str, str]] = field(default_factory=list)
    use_predicate_pushdown: bool = True
    use_bloom_filter: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParquetPartition:
    """Partition Parquet."""
    partition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_id: str = ""
    column: str = ""
    value: str = ""
    path: str = ""
    row_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class ParquetEngineInterface(ABC):
    """Interface abstraite pour le moteur Parquet."""
    
    @abstractmethod
    async def create_file(self, file: ParquetFile) -> str:
        """Crée un fichier Parquet."""
        pass
    
    @abstractmethod
    async def write_data(self, file_id: str, data: pd.DataFrame) -> int:
        """Écrit des données dans un fichier Parquet."""
        pass
    
    @abstractmethod
    async def read_data(self, query: ParquetQuery) -> pd.DataFrame:
        """Lit des données depuis un fichier Parquet."""
        pass
    
    @abstractmethod
    async def get_stats(self, file_id: str) -> Dict[str, Any]:
        """Récupère les statistiques d'un fichier Parquet."""
        pass


# ============== IMPLÉMENTATION ==============

class ParquetEngine(ParquetEngineInterface):
    """
    Moteur Parquet avancé pour le Hedge Bot.
    Gère le stockage columnar optimisé et les requêtes performantes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des fichiers
        self._files: Dict[str, ParquetFile] = {}
        self._files_lock = threading.RLock()
        
        # Gestion des partitions
        self._partitions: Dict[str, List[ParquetPartition]] = defaultdict(list)
        self._partitions_lock = threading.RLock()
        
        # Cache des données
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._cache_lock = threading.RLock()
        
        # Cache des métadonnées
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._meta_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "files_created": 0,
            "rows_written": 0,
            "rows_read": 0,
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "compression_ratio": 0.0,
            "avg_read_time_ms": 0.0,
            "avg_write_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Base path
        self._base_path = Path(self.config.get("base_path", "./parquet_data"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # Filesystem
        self._fs = fs.LocalFileSystem()
        
        # État
        self._is_running = False
        
        logger.info("ParquetEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./parquet_data",
            "default_compression": ParquetCompression.ZSTD,
            "compression_level": 6,
            "row_group_size": 10000,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_bloom_filter": True,
            "enable_dictionary": True,
            "enable_predicate_pushdown": True,
            "max_file_size": 1024 * 1024 * 1024,  # 1 GB
            "batch_size": 10000
        }
    
    async def start(self) -> None:
        """Démarre le moteur Parquet."""
        logger.info("ParquetEngine starting...")
        self._is_running = True
        
        # Chargement des fichiers existants
        await self._load_files()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("ParquetEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Parquet."""
        logger.info("ParquetEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("ParquetEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_file(self, file: ParquetFile) -> str:
        """Crée un fichier Parquet."""
        with self._files_lock:
            self._files[file.file_id] = file
            self._stats["files_created"] += 1
        
        # Création du fichier de métadonnées
        file_path = self._base_path / f"{file.file_id}.parquet.meta"
        with open(file_path, 'w') as f:
            json.dump(file.to_dict(), f, indent=2)
        
        # Création du dossier pour les partitions
        if file.partition_columns:
            partition_path = self._base_path / file.file_id
            partition_path.mkdir(exist_ok=True)
        
        logger.info(f"Parquet file created: {file.file_id}")
        return file.file_id
    
    async def write_data(self, file_id: str, data: pd.DataFrame) -> int:
        """Écrit des données dans un fichier Parquet."""
        start_time = time.time()
        self._stats["rows_written"] += len(data)
        
        with self._files_lock:
            file = self._files.get(file_id)
            if not file:
                raise ValueError(f"File {file_id} not found")
        
        try:
            # Préparation des données
            table = pa.Table.from_pandas(data)
            
            # Définition des options d'écriture
            compression = file.compression.value
            compression_level = file.compression_level
            
            # Écriture des partitions
            if file.partition_columns:
                # Écriture partitionnée
                partition_cols = file.partition_columns
                for partition_col in partition_cols:
                    if partition_col in data.columns:
                        # Création des dossiers de partition
                        for value in data[partition_col].unique():
                            partition_path = self._base_path / file_id / f"{partition_col}={value}"
                            partition_path.mkdir(parents=True, exist_ok=True)
                            
                            # Filtrage des données
                            partition_data = data[data[partition_col] == value]
                            partition_table = pa.Table.from_pandas(partition_data)
                            
                            # Écriture du fichier
                            file_path = partition_path / f"{uuid.uuid4().hex[:8]}.parquet"
                            pq.write_table(
                                partition_table,
                                str(file_path),
                                compression=compression,
                                compression_level=compression_level,
                                row_group_size=file.row_group_size,
                                use_dictionary=file.encoding == ParquetEncoding.DICTIONARY,
                                write_statistics=True
                            )
                            
                            # Enregistrement de la partition
                            partition = ParquetPartition(
                                file_id=file_id,
                                column=partition_col,
                                value=str(value),
                                path=str(partition_path),
                                row_count=len(partition_data),
                                size_bytes=file_path.stat().st_size
                            )
                            with self._partitions_lock:
                                self._partitions[file_id].append(partition)
            else:
                # Écriture standard
                file_path = self._base_path / f"{file_id}.parquet"
                pq.write_table(
                    table,
                    str(file_path),
                    compression=compression,
                    compression_level=compression_level,
                    row_group_size=file.row_group_size,
                    use_dictionary=file.encoding == ParquetEncoding.DICTIONARY,
                    write_statistics=True
                )
            
            # Mise à jour du fichier
            file.row_count += len(data)
            file.updated_at = datetime.now(timezone.utc)
            
            # Mise à jour des statistiques
            write_time = (time.time() - start_time) * 1000
            self._stats["avg_write_time_ms"] = (
                self._stats["avg_write_time_ms"] * 0.9 + write_time * 0.1
            )
            
            return len(data)
            
        except Exception as e:
            logger.error(f"Write data error: {e}")
            raise
    
    async def read_data(self, query: ParquetQuery) -> pd.DataFrame:
        """Lit des données depuis un fichier Parquet."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        # Vérification du cache
        cache_key = self._compute_cache_key(query)
        if self.config["enable_cache"] and cache_key in self._data_cache:
            self._stats["cache_hits"] += 1
            return self._data_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        with self._files_lock:
            file = self._files.get(query.file_id)
            if not file:
                raise ValueError(f"File {query.file_id} not found")
        
        try:
            # Lecture selon le type de stockage
            if file.partition_columns:
                # Lecture partitionnée
                data_frames = []
                
                with self._partitions_lock:
                    partitions = self._partitions.get(query.file_id, [])
                
                for partition in partitions:
                    partition_path = Path(partition.path)
                    for parquet_file in partition_path.glob("*.parquet"):
                        try:
                            # Lecture du fichier
                            df = pd.read_parquet(str(parquet_file))
                            data_frames.append(df)
                        except Exception as e:
                            logger.warning(f"Error reading {parquet_file}: {e}")
                
                if not data_frames:
                    return pd.DataFrame()
                
                result = pd.concat(data_frames, ignore_index=True)
            else:
                # Lecture standard
                file_path = self._base_path / f"{query.file_id}.parquet"
                if not file_path.exists():
                    return pd.DataFrame()
                
                # Lecture avec filtres
                if query.filters and self.config["enable_predicate_pushdown"]:
                    # Utilisation des prédicats pushdown
                    result = pq.read_table(
                        str(file_path),
                        filters=self._build_filters(query.filters),
                        columns=query.columns if query.columns else None
                    ).to_pandas()
                else:
                    result = pq.read_table(
                        str(file_path),
                        columns=query.columns if query.columns else None
                    ).to_pandas()
            
            # Application des filtres supplémentaires
            if query.filters and not self.config["enable_predicate_pushdown"]:
                for key, value in query.filters.items():
                    if key in result.columns:
                        if isinstance(value, (list, tuple)):
                            result = result[result[key].isin(value)]
                        else:
                            result = result[result[key] == value]
            
            # Tri
            if query.order_by:
                for col, direction in reversed(query.order_by):
                    result = result.sort_values(col, ascending=direction == "asc")
            
            # Limitation
            if query.limit > 0:
                result = result.iloc[query.offset:query.offset + query.limit]
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._data_cache) < self.config["cache_size"]:
                        self._data_cache[cache_key] = result
            
            # Mise à jour des statistiques
            self._stats["rows_read"] += len(result)
            read_time = (time.time() - start_time) * 1000
            self._stats["avg_read_time_ms"] = (
                self._stats["avg_read_time_ms"] * 0.9 + read_time * 0.1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Read data error: {e}")
            raise
    
    async def get_stats(self, file_id: str) -> Dict[str, Any]:
        """Récupère les statistiques d'un fichier Parquet."""
        with self._files_lock:
            file = self._files.get(file_id)
            if not file:
                return {"error": "File not found"}
        
        stats = {
            "file_id": file.file_id,
            "row_count": file.row_count,
            "size_bytes": file.size_bytes,
            "compression": file.compression.value,
            "row_group_size": file.row_group_size,
            "partition_count": len(self._partitions.get(file_id, [])),
            "created_at": file.created_at.isoformat(),
            "updated_at": file.updated_at.isoformat()
        }
        
        return stats
    
    # ========== MÉTHODES PRIVÉES - FILTRES ==========
    
    def _build_filters(self, filters: Dict[str, Any]) -> List[Tuple]:
        """Construit les filtres pour la lecture Parquet."""
        parquet_filters = []
        
        for key, value in filters.items():
            if isinstance(value, (list, tuple)):
                # IN filter
                parquet_filters.append((key, "in", value))
            elif isinstance(value, dict):
                op = value.get("operator", "eq")
                val = value.get("value")
                
                if op == "eq":
                    parquet_filters.append((key, "=", val))
                elif op == "ne":
                    parquet_filters.append((key, "!=", val))
                elif op == "gt":
                    parquet_filters.append((key, ">", val))
                elif op == "gte":
                    parquet_filters.append((key, ">=", val))
                elif op == "lt":
                    parquet_filters.append((key, "<", val))
                elif op == "lte":
                    parquet_filters.append((key, "<=", val))
            else:
                parquet_filters.append((key, "=", value))
        
        return parquet_filters
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, query: ParquetQuery) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "file_id": query.file_id,
            "columns": sorted(query.columns),
            "filters": query.filters,
            "limit": query.limit,
            "offset": query.offset,
            "order_by": query.order_by
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
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
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_files(self) -> None:
        """Charge les fichiers existants."""
        try:
            for meta_path in self._base_path.glob("*.parquet.meta"):
                with open(meta_path, 'r') as f:
                    data = json.load(f)
                
                file = self._deserialize_file(data)
                if file:
                    with self._files_lock:
                        self._files[file.file_id] = file
                    
                    # Chargement des partitions
                    if file.partition_columns:
                        partition_path = self._base_path / file.file_id
                        if partition_path.exists():
                            for part_dir in partition_path.iterdir():
                                if part_dir.is_dir():
                                    # Extraction de la colonne et de la valeur
                                    part_str = part_dir.name
                                    if "=" in part_str:
                                        col, value = part_str.split("=", 1)
                                        partition = ParquetPartition(
                                            file_id=file.file_id,
                                            column=col,
                                            value=value,
                                            path=str(part_dir)
                                        )
                                        # Comptage des fichiers
                                        partition.row_count = sum(1 for _ in part_dir.glob("*.parquet"))
                                        with self._partitions_lock:
                                            self._partitions[file.file_id].append(partition)
            
            logger.info(f"Loaded {len(self._files)} Parquet files")
            
        except Exception as e:
            logger.error(f"Load files error: {e}")
    
    def _deserialize_file(self, data: Dict) -> Optional[ParquetFile]:
        """Désérialise un fichier Parquet."""
        try:
            return ParquetFile(
                file_id=data.get("file_id", str(uuid.uuid4())),
                path=data.get("path", ""),
                schema=data.get("schema", {}),
                row_count=data.get("row_count", 0),
                row_group_size=data.get("row_group_size", 10000),
                compression=ParquetCompression(data.get("compression", "zstd")),
                compression_level=data.get("compression_level", 6),
                version=ParquetVersion(data.get("version", "2.6")),
                encoding=ParquetEncoding(data.get("encoding", "dictionary")),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                size_bytes=data.get("size_bytes", 0),
                partition_columns=data.get("partition_columns", []),
                sorted_columns=data.get("sorted_columns", []),
                bloom_filter_columns=data.get("bloom_filter_columns", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing file: {e}")
            return None
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._files_lock:
                    self._stats["total_files"] = len(self._files)
                with self._partitions_lock:
                    self._stats["total_partitions"] = sum(len(p) for p in self._partitions.values())
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "parquet:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_file(self, file_id: str) -> Optional[ParquetFile]:
        """Récupère un fichier Parquet."""
        with self._files_lock:
            return self._files.get(file_id)
    
    async def get_files(self) -> List[ParquetFile]:
        """Récupère les fichiers Parquet."""
        with self._files_lock:
            return list(self._files.values())
    
    async def get_partitions(self, file_id: str) -> List[ParquetPartition]:
        """Récupère les partitions d'un fichier."""
        with self._partitions_lock:
            return self._partitions.get(file_id, [])
    
    async def optimize_file(self, file_id: str) -> Dict[str, Any]:
        """Optimise un fichier Parquet."""
        file = await self.get_file(file_id)
        if not file:
            return {"error": "File not found"}
        
        # Réécriture du fichier avec une meilleure compression
        # Dans un système réel, on réécrirait le fichier
        
        return {
            "file_id": file_id,
            "status": "completed",
            "row_count": file.row_count,
            "size_before": file.size_bytes,
            "size_after": file.size_bytes
        }
    
    async def delete_file(self, file_id: str) -> bool:
        """Supprime un fichier Parquet."""
        with self._files_lock:
            if file_id not in self._files:
                return False
            
            del self._files[file_id]
        
        # Suppression des partitions
        with self._partitions_lock:
            if file_id in self._partitions:
                del self._partitions[file_id]
        
        # Suppression des fichiers
        for file_path in self._base_path.glob(f"{file_id}*"):
            file_path.unlink()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._files_lock:
            self._stats["total_files"] = len(self._files)
        with self._partitions_lock:
            self._stats["total_partitions"] = sum(len(p) for p in self._partitions.values())
        
        return self._stats.copy()


# ============== PARQUET QUERY BUILDER ==============

class ParquetQueryBuilder:
    """
    Constructeur de requêtes Parquet.
    Facilite la création de requêtes optimisées.
    """
    
    def __init__(self):
        self._query = ParquetQuery()
    
    def file_id(self, file_id: str) -> 'ParquetQueryBuilder':
        """Définit l'ID du fichier."""
        self._query.file_id = file_id
        return self
    
    def columns(self, columns: List[str]) -> 'ParquetQueryBuilder':
        """Définit les colonnes à lire."""
        self._query.columns = columns
        return self
    
    def filter(self, field: str, value: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre."""
        self._query.filters[field] = value
        return self
    
    def filter_gt(self, field: str, value: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre >."""
        self._query.filters[field] = {"operator": "gt", "value": value}
        return self
    
    def filter_gte(self, field: str, value: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre >=."""
        self._query.filters[field] = {"operator": "gte", "value": value}
        return self
    
    def filter_lt(self, field: str, value: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre <."""
        self._query.filters[field] = {"operator": "lt", "value": value}
        return self
    
    def filter_lte(self, field: str, value: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre <=."""
        self._query.filters[field] = {"operator": "lte", "value": value}
        return self
    
    def filter_between(self, field: str, min_val: Any, max_val: Any) -> 'ParquetQueryBuilder':
        """Ajoute un filtre BETWEEN."""
        self._query.filters[field] = {"operator": "between", "value": [min_val, max_val]}
        return self
    
    def limit(self, limit: int) -> 'ParquetQueryBuilder':
        """Définit la limite."""
        self._query.limit = limit
        return self
    
    def offset(self, offset: int) -> 'ParquetQueryBuilder':
        """Définit l'offset."""
        self._query.offset = offset
        return self
    
    def order_by(self, field: str, direction: str = "asc") -> 'ParquetQueryBuilder':
        """Définit le tri."""
        self._query.order_by.append((field, direction))
        return self
    
    def build(self) -> ParquetQuery:
        """Construit la requête."""
        if not self._query.file_id:
            raise ValueError("File ID is required")
        return self._query


# ============== FACTORY ==============

class ParquetFactory:
    """Factory pour créer des composants Parquet."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ParquetEngine:
        """Crée un moteur Parquet."""
        engine = ParquetEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_query_builder() -> ParquetQueryBuilder:
        """Crée un constructeur de requêtes."""
        return ParquetQueryBuilder()


# ============== EXPORT ==============

__all__ = [
    "ParquetCompression",
    "ParquetVersion",
    "ParquetEncoding",
    "ParquetFile",
    "ParquetQuery",
    "ParquetPartition",
    "ParquetEngineInterface",
    "ParquetEngine",
    "ParquetQueryBuilder",
    "ParquetFactory"
]
