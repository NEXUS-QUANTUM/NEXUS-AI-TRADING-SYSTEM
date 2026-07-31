# trading/bots/hedge_bot/hedge_bot_data_iceberg.py
# Advanced Apache Iceberg Integration & Data Lakehouse Management for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Iceberg Integration Module - Module d'intégration avancé avec Apache Iceberg pour le Hedge Bot.
Gère le data lakehouse, les tables ACID, le schema evolution, le time travel, l'optimisation
des requêtes et la gestion des métadonnées pour les données de hedging.
"""

import asyncio
import json
import time
import os
import subprocess
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
import tempfile
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.fs as fs

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_iceberg")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class IcebergTableFormat(Enum):
    """Formats de table Iceberg."""
    PARQUET = "parquet"
    ORC = "orc"
    AVRO = "avro"


class IcebergEvolutionType(Enum):
    """Types d'évolution de schéma."""
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    RENAME_COLUMN = "rename_column"
    UPDATE_COLUMN = "update_column"
    ADD_PARTITION = "add_partition"
    REMOVE_PARTITION = "remove_partition"


class IcebergSnapshotAction(Enum):
    """Actions sur les snapshots."""
    CREATE = "create"
    REPLACE = "replace"
    FAST_FORWARD = "fast_forward"
    ROLLBACK = "rollback"


class IcebergBranch(Enum):
    """Branches Iceberg."""
    MAIN = "main"
    DEVELOPMENT = "development"
    STAGING = "staging"
    FEATURE = "feature"
    HOTFIX = "hotfix"


# ============== DATA MODELS ==============

@dataclass
class IcebergTable:
    """Modèle de table Iceberg."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    namespace: str = "default"
    location: str = ""
    format: IcebergTableFormat = IcebergTableFormat.PARQUET
    schema: pa.Schema = field(default_factory=pa.schema)
    partition_spec: List[Dict[str, str]] = field(default_factory=list)
    sort_order: List[Dict[str, str]] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    current_snapshot_id: Optional[str] = None
    branch: IcebergBranch = IcebergBranch.MAIN
    active: bool = True
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "namespace": self.namespace,
            "location": self.location,
            "format": self.format.value,
            "schema": self.schema,
            "partition_spec": self.partition_spec,
            "sort_order": self.sort_order,
            "properties": self.properties,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "current_snapshot_id": self.current_snapshot_id,
            "branch": self.branch.value,
            "active": self.active,
            "version": self.version
        }


@dataclass
class IcebergSnapshot:
    """Modèle de snapshot Iceberg."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    parent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    operation: IcebergSnapshotAction = IcebergSnapshotAction.CREATE
    manifest_list: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    schema_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "snapshot_id": self.snapshot_id,
            "table_name": self.table_name,
            "parent_id": self.parent_id,
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation.value,
            "manifest_list": self.manifest_list,
            "summary": self.summary,
            "schema_id": self.schema_id,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class IcebergManifest:
    """Modèle de manifeste Iceberg."""
    manifest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    snapshot_id: str = ""
    file_path: str = ""
    file_format: IcebergTableFormat = IcebergTableFormat.PARQUET
    partition_values: Dict[str, Any] = field(default_factory=dict)
    row_count: int = 0
    file_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IcebergTableVersion:
    """Version d'une table Iceberg."""
    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    version_number: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    changes: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class IcebergEngineInterface(ABC):
    """Interface abstraite pour le moteur Iceberg."""
    
    @abstractmethod
    async def create_table(self, table: IcebergTable) -> bool:
        """Crée une table Iceberg."""
        pass
    
    @abstractmethod
    async def write_data(self, table_name: str, data: pa.Table) -> IcebergSnapshot:
        """Écrit des données dans une table."""
        pass
    
    @abstractmethod
    async def read_data(self, table_name: str, snapshot_id: Optional[str] = None) -> pa.Table:
        """Lit des données d'une table."""
        pass
    
    @abstractmethod
    async def time_travel(self, table_name: str, timestamp: datetime) -> pa.Table:
        """Time travel sur une table."""
        pass


# ============== IMPLÉMENTATION ==============

class IcebergEngine(IcebergEngineInterface):
    """
    Moteur Iceberg avancé pour le Hedge Bot.
    Gère l'intégration avec Apache Iceberg, le data lakehouse, le schema evolution
    et le time travel.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des tables
        self._tables: Dict[str, IcebergTable] = {}
        self._tables_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: Dict[str, IcebergSnapshot] = {}
        self._snapshots_lock = threading.RLock()
        
        # Gestion des manifests
        self._manifests: Dict[str, IcebergManifest] = {}
        self._manifests_lock = threading.RLock()
        
        # Gestion des versions
        self._versions: Dict[str, IcebergTableVersion] = {}
        self._versions_lock = threading.RLock()
        
        # Cache des métadonnées
        self._metadata_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "tables_created": 0,
            "snapshots_created": 0,
            "data_writes": 0,
            "data_reads": 0,
            "time_travel_ops": 0,
            "schema_evolutions": 0,
            "data_volume_mb": 0.0,
            "avg_write_time": 0.0,
            "avg_read_time": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Base path pour les tables
        self._base_path = Path(self.config.get("base_path", "./iceberg_data"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # État
        self._is_running = False
        
        # Filesystem PyArrow
        self._fs = fs.LocalFileSystem()
        
        logger.info("IcebergEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./iceberg_data",
            "default_format": IcebergTableFormat.PARQUET,
            "default_branch": IcebergBranch.MAIN,
            "max_table_size": 100 * 1024 * 1024 * 1024,  # 100 GB
            "min_compress_size": 1024 * 1024,  # 1 MB
            "snapshot_retention": 30,  # jours
            "enable_cache": True,
            "cache_size": 10000,
            "enable_compression": True,
            "compression_codec": "snappy",
            "simulation_mode": True,
            "iceberg_jar_path": "/opt/iceberg/iceberg-runtime.jar"
        }
    
    async def start(self) -> None:
        """Démarre le moteur Iceberg."""
        logger.info("IcebergEngine starting...")
        self._is_running = True
        
        # Chargement des tables existantes
        await self._load_tables()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._snapshot_cleanup_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("IcebergEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Iceberg."""
        logger.info("IcebergEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("IcebergEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, table: IcebergTable) -> bool:
        """Crée une table Iceberg."""
        with self._tables_lock:
            self._tables[table.table_id] = table
            self._stats["tables_created"] += 1
        
        # Création du dossier de la table
        table_path = self._base_path / table.namespace / table.name
        table_path.mkdir(parents=True, exist_ok=True)
        
        # Création du fichier de métadonnées
        metadata_path = table_path / "metadata.json"
        metadata = {
            "schema": table.schema,
            "partition_spec": table.partition_spec,
            "sort_order": table.sort_order,
            "properties": table.properties,
            "version": table.version
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Iceberg table created: {table.namespace}.{table.name} at {table_path}")
        return True
    
    async def write_data(self, table_name: str, data: pa.Table) -> IcebergSnapshot:
        """Écrit des données dans une table."""
        start_time = time.time()
        self._stats["data_writes"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Compression
            if self.config["enable_compression"] and data.nbytes > self.config["min_compress_size"]:
                # Utilisation de la compression
                compression = self.config["compression_codec"]
            else:
                compression = None
            
            # Écriture des données
            table_path = self._base_path / table.namespace / table.name
            
            # Écriture des fichiers de données
            data_path = table_path / "data"
            data_path.mkdir(exist_ok=True)
            
            # Écriture des fichiers Parquet
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            file_name = f"data_{timestamp}_{uuid.uuid4().hex[:8]}.parquet"
            file_path = data_path / file_name
            
            # Écriture avec PyArrow
            pq.write_table(
                data,
                str(file_path),
                compression=compression,
                use_dictionary=True,
                write_statistics=True
            )
            
            # Création du manifeste
            manifest = IcebergManifest(
                snapshot_id="",
                file_path=str(file_path),
                file_format=table.format,
                row_count=data.num_rows,
                file_size=file_path.stat().st_size
            )
            
            with self._manifests_lock:
                self._manifests[manifest.manifest_id] = manifest
            
            # Création du snapshot
            snapshot = IcebergSnapshot(
                table_name=table_name,
                parent_id=table.current_snapshot_id,
                operation=IcebergSnapshotAction.CREATE,
                manifest_list=manifest.manifest_id,
                summary={
                    "records": data.num_rows,
                    "file_count": 1,
                    "total_size": file_path.stat().st_size
                }
            )
            
            with self._snapshots_lock:
                self._snapshots[snapshot.snapshot_id] = snapshot
                self._stats["snapshots_created"] += 1
            
            # Mise à jour de la table
            table.current_snapshot_id = snapshot.snapshot_id
            table.row_count += data.num_rows
            table.size_bytes += file_path.stat().st_size
            table.updated_at = datetime.now(timezone.utc)
            
            # Mise à jour des statistiques
            self._stats["data_volume_mb"] += file_path.stat().st_size / (1024 * 1024)
            self._stats["avg_write_time"] = (
                self._stats["avg_write_time"] * 0.9 +
                (time.time() - start_time) * 1000 * 0.1
            )
            
            logger.info(f"Data written to {table_name}: {data.num_rows} rows "
                       f"size={file_path.stat().st_size / 1024:.1f}KB")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Write data error: {e}")
            raise
    
    async def read_data(
        self,
        table_name: str,
        snapshot_id: Optional[str] = None
    ) -> pa.Table:
        """Lit des données d'une table."""
        start_time = time.time()
        self._stats["data_reads"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Récupération des fichiers de données
            table_path = self._base_path / table.namespace / table.name
            data_path = table_path / "data"
            
            # Filtrage par snapshot
            if snapshot_id:
                # Récupération du manifeste
                with self._snapshots_lock:
                    snapshot = self._snapshots.get(snapshot_id)
                    if snapshot:
                        manifest = self._manifests.get(snapshot.manifest_list)
                        if manifest:
                            file_path = Path(manifest.file_path)
                            if file_path.exists():
                                data = pq.read_table(str(file_path))
                                self._stats["avg_read_time"] = (
                                    self._stats["avg_read_time"] * 0.9 +
                                    (time.time() - start_time) * 1000 * 0.1
                                )
                                return data
            
            # Lecture de tous les fichiers
            tables = []
            for file_path in data_path.glob("*.parquet"):
                tables.append(pq.read_table(str(file_path)))
            
            if tables:
                # Concaténation des tables
                combined = pa.concat_tables(tables)
                self._stats["avg_read_time"] = (
                    self._stats["avg_read_time"] * 0.9 +
                    (time.time() - start_time) * 1000 * 0.1
                )
                return combined
            
            return pa.Table.from_pydict({})
            
        except Exception as e:
            logger.error(f"Read data error: {e}")
            raise
    
    async def time_travel(self, table_name: str, timestamp: datetime) -> pa.Table:
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
                    if snap.table_name == table_name and snap.timestamp <= timestamp:
                        if snapshot is None or snap.timestamp > snapshot.timestamp:
                            snapshot = snap
            
            if snapshot:
                return await self.read_data(table_name, snapshot.snapshot_id)
            else:
                return pa.Table.from_pydict({})
            
        except Exception as e:
            logger.error(f"Time travel error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - ÉVOLUTION ==========
    
    async def evolve_schema(
        self,
        table_name: str,
        evolution_type: IcebergEvolutionType,
        changes: Dict[str, Any]
    ) -> bool:
        """Évolue le schéma d'une table."""
        self._stats["schema_evolutions"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Création de la version
            version = IcebergTableVersion(
                table_name=table_name,
                version_number=table.version + 1,
                changes=[{
                    "type": evolution_type.value,
                    "changes": changes
                }]
            )
            
            # Application des changements
            if evolution_type == IcebergEvolutionType.ADD_COLUMN:
                # Ajout de colonne
                field_name = changes.get("name")
                field_type = changes.get("type")
                if field_name and field_type:
                    new_field = pa.field(field_name, pa.from_arrow_type(field_type))
                    table.schema = table.schema.append(new_field)
            
            elif evolution_type == IcebergEvolutionType.DROP_COLUMN:
                # Suppression de colonne
                field_name = changes.get("name")
                if field_name:
                    # Suppression du champ
                    current_fields = list(table.schema)
                    new_fields = [f for f in current_fields if f.name != field_name]
                    table.schema = pa.schema(new_fields)
            
            elif evolution_type == IcebergEvolutionType.RENAME_COLUMN:
                # Renommage de colonne
                old_name = changes.get("old_name")
                new_name = changes.get("new_name")
                if old_name and new_name:
                    # Renommage du champ
                    current_fields = list(table.schema)
                    new_fields = []
                    for field in current_fields:
                        if field.name == old_name:
                            new_fields.append(pa.field(new_name, field.type))
                        else:
                            new_fields.append(field)
                    table.schema = pa.schema(new_fields)
            
            # Mise à jour de la table
            table.version += 1
            table.updated_at = datetime.now(timezone.utc)
            
            # Stockage de la version
            with self._versions_lock:
                self._versions[version.version_id] = version
            
            logger.info(f"Schema evolved for {table_name}: {evolution_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Schema evolution error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
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
                            # Suppression du manifeste
                            manifest = self._manifests.get(snapshot.manifest_list)
                            if manifest:
                                file_path = Path(manifest.file_path)
                                if file_path.exists():
                                    file_path.unlink()
                                del self._manifests[snapshot.manifest_list]
                            
                            # Suppression du snapshot
                            del self._snapshots[snapshot_id]
                
                logger.debug("Snapshot cleanup completed")
                
            except Exception as e:
                logger.error(f"Snapshot cleanup error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._metadata_cache) > self.config["cache_size"]:
                        keys = list(self._metadata_cache.keys())
                        for key in keys[:len(self._metadata_cache) - self.config["cache_size"]]:
                            del self._metadata_cache[key]
                
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
                with self._manifests_lock:
                    self._stats["total_manifests"] = len(self._manifests)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "iceberg:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_tables(self) -> None:
        """Charge les tables existantes."""
        try:
            # Parcours du dossier de base
            for ns_path in self._base_path.iterdir():
                if ns_path.is_dir():
                    for table_path in ns_path.iterdir():
                        if table_path.is_dir():
                            metadata_path = table_path / "metadata.json"
                            if metadata_path.exists():
                                with open(metadata_path, 'r') as f:
                                    metadata = json.load(f)
                                
                                # Création de l'objet table
                                table = IcebergTable(
                                    name=table_path.name,
                                    namespace=ns_path.name,
                                    location=str(table_path),
                                    schema=metadata.get("schema", pa.schema([])),
                                    partition_spec=metadata.get("partition_spec", []),
                                    sort_order=metadata.get("sort_order", []),
                                    properties=metadata.get("properties", {}),
                                    version=metadata.get("version", 1)
                                )
                                
                                with self._tables_lock:
                                    self._tables[table.table_id] = table
                                
                                logger.info(f"Loaded table: {ns_path.name}.{table_path.name}")
            
            logger.info(f"Loaded {len(self._tables)} tables")
            
        except Exception as e:
            logger.error(f"Load tables error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_table(self, table_id: str) -> Optional[IcebergTable]:
        """Récupère une table Iceberg."""
        with self._tables_lock:
            return self._tables.get(table_id)
    
    async def get_table_by_name(self, name: str, namespace: str = "default") -> Optional[IcebergTable]:
        """Récupère une table par son nom."""
        with self._tables_lock:
            for table in self._tables.values():
                if table.name == name and table.namespace == namespace:
                    return table
        return None
    
    async def get_tables(self, namespace: Optional[str] = None) -> List[IcebergTable]:
        """Récupère toutes les tables."""
        with self._tables_lock:
            tables = list(self._tables.values())
            if namespace:
                tables = [t for t in tables if t.namespace == namespace]
            return tables
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[IcebergSnapshot]:
        """Récupère un snapshot."""
        with self._snapshots_lock:
            return self._snapshots.get(snapshot_id)
    
    async def get_snapshots(self, table_name: str) -> List[IcebergSnapshot]:
        """Récupère les snapshots d'une table."""
        with self._snapshots_lock:
            return [s for s in self._snapshots.values() if s.table_name == table_name]
    
    async def get_manifest(self, manifest_id: str) -> Optional[IcebergManifest]:
        """Récupère un manifeste."""
        with self._manifests_lock:
            return self._manifests.get(manifest_id)
    
    async def get_table_version(self, version_id: str) -> Optional[IcebergTableVersion]:
        """Récupère une version de table."""
        with self._versions_lock:
            return self._versions.get(version_id)
    
    async def get_table_history(self, table_name: str) -> List[IcebergTableVersion]:
        """Récupère l'historique d'une table."""
        with self._versions_lock:
            return [v for v in self._versions.values() if v.table_name == table_name]
    
    async def delete_table(self, table_name: str, namespace: str = "default") -> bool:
        """Supprime une table Iceberg."""
        try:
            table = await self.get_table_by_name(table_name, namespace)
            if not table:
                return False
            
            # Suppression du dossier
            import shutil
            table_path = self._base_path / namespace / table_name
            if table_path.exists():
                shutil.rmtree(table_path)
            
            # Suppression de la table
            with self._tables_lock:
                del self._tables[table.table_id]
            
            # Suppression des snapshots
            with self._snapshots_lock:
                for snapshot_id in list(self._snapshots.keys()):
                    if self._snapshots[snapshot_id].table_name == table_name:
                        del self._snapshots[snapshot_id]
            
            logger.info(f"Table deleted: {namespace}.{table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Delete table error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._tables_lock:
            self._stats["tables"] = len(self._tables)
        with self._snapshots_lock:
            self._stats["snapshots"] = len(self._snapshots)
        with self._manifests_lock:
            self._stats["manifests"] = len(self._manifests)
        with self._cache_lock:
            self._stats["cache_entries"] = len(self._metadata_cache)
        
        return self._stats.copy()


# ============== ICEBERG SCHEMA BUILDER ==============

class IcebergSchemaBuilder:
    """
    Constructeur de schéma Iceberg.
    Facilite la création de schémas pour les tables Iceberg.
    """
    
    def __init__(self):
        self._fields = []
    
    def add_field(self, name: str, field_type: Any, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ."""
        self._fields.append(pa.field(name, field_type, nullable=nullable))
        return self
    
    def add_string(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ string."""
        return self.add_field(name, pa.string(), nullable)
    
    def add_int64(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ int64."""
        return self.add_field(name, pa.int64(), nullable)
    
    def add_int32(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ int32."""
        return self.add_field(name, pa.int32(), nullable)
    
    def add_float64(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ float64."""
        return self.add_field(name, pa.float64(), nullable)
    
    def add_float32(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ float32."""
        return self.add_field(name, pa.float32(), nullable)
    
    def add_bool(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ booléen."""
        return self.add_field(name, pa.bool_(), nullable)
    
    def add_timestamp(self, name: str, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute un champ timestamp."""
        return self.add_field(name, pa.timestamp('us'), nullable)
    
    def add_list(self, name: str, value_type: Any, nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute une liste."""
        return self.add_field(name, pa.list_(value_type), nullable)
    
    def add_struct(self, name: str, fields: List[pa.Field], nullable: bool = True) -> 'IcebergSchemaBuilder':
        """Ajoute une structure."""
        return self.add_field(name, pa.struct(fields), nullable)
    
    def build(self) -> pa.Schema:
        """Construit le schéma."""
        if not self._fields:
            raise ValueError("Schema must have at least one field")
        return pa.schema(self._fields)


# ============== FACTORY ==============

class IcebergFactory:
    """Factory pour créer des composants Iceberg."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> IcebergEngine:
        """Crée un moteur Iceberg."""
        engine = IcebergEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_schema_builder() -> IcebergSchemaBuilder:
        """Crée un constructeur de schéma."""
        return IcebergSchemaBuilder()


# ============== EXPORT ==============

__all__ = [
    "IcebergTableFormat",
    "IcebergEvolutionType",
    "IcebergSnapshotAction",
    "IcebergBranch",
    "IcebergTable",
    "IcebergSnapshot",
    "IcebergManifest",
    "IcebergTableVersion",
    "IcebergEngineInterface",
    "IcebergEngine",
    "IcebergSchemaBuilder",
    "IcebergFactory"
]
