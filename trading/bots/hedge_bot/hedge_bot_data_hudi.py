# trading/bots/hedge_bot/hedge_bot_data_hudi.py
# Advanced Apache Hudi Integration & Data Lake Management for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Hudi Integration Module - Module d'intégration avancé avec Apache Hudi pour le Hedge Bot.
Gère le data lake, les tables ACID, les upserts, les time travel, l'incremental processing
et l'optimisation des coûts de stockage pour les données de hedging.
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

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_hudi")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class HudiTableType(Enum):
    """Types de tables Hudi."""
    COPY_ON_WRITE = "cow"              # Copy on Write
    MERGE_ON_READ = "mor"              # Merge on Read
    BULK_INSERT = "bulk_insert"        # Bulk Insert


class HudiRecordType(Enum):
    """Types d'enregistrements Hudi."""
    INSERT = "insert"
    UPSERT = "upsert"
    DELETE = "delete"
    BULK_INSERT = "bulk_insert"


class HudiPrecombineField(Enum):
    """Champs de précombinaison Hudi."""
    TIMESTAMP = "timestamp"
    VERSION = "version"
    SEQUENCE = "sequence"
    CUSTOM = "custom"


class HudiIndexType(Enum):
    """Types d'index Hudi."""
    BLOOM = "bloom"
    HBASE = "hbase"
    BUCKET = "bucket"
    SIMPLE = "simple"
    GLOBAL = "global"


class HudiStorageType(Enum):
    """Types de stockage Hudi."""
    DFS = "dfs"
    S3 = "s3"
    GCS = "gcs"
    ADLS = "adls"
    LOCAL = "local"


# ============== DATA MODELS ==============

@dataclass
class HudiTable:
    """Modèle de table Hudi."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    base_path: str = ""
    table_type: HudiTableType = HudiTableType.COPY_ON_WRITE
    record_key: str = "id"
    precombine_field: str = "timestamp"
    partition_fields: List[str] = field(default_factory=list)
    schema: Dict[str, str] = field(default_factory=dict)
    index_type: HudiIndexType = HudiIndexType.BLOOM
    storage_type: HudiStorageType = HudiStorageType.DFS
    bloom_filter: bool = True
    bloom_filter_entries: int = 60000
    bloom_filter_error_rate: float = 0.00001
    write_batch_size: int = 10000
    compaction_strategy: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    last_commit: Optional[str] = None
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "base_path": self.base_path,
            "table_type": self.table_type.value,
            "record_key": self.record_key,
            "precombine_field": self.precombine_field,
            "partition_fields": self.partition_fields,
            "schema": self.schema,
            "index_type": self.index_type.value,
            "storage_type": self.storage_type.value,
            "bloom_filter": self.bloom_filter,
            "bloom_filter_entries": self.bloom_filter_entries,
            "bloom_filter_error_rate": self.bloom_filter_error_rate,
            "write_batch_size": self.write_batch_size,
            "compaction_strategy": self.compaction_strategy,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "last_commit": self.last_commit,
            "active": self.active
        }


@dataclass
class HudiRecord:
    """Modèle d'enregistrement Hudi."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    operation: HudiRecordType = HudiRecordType.UPSERT
    data: Dict[str, Any] = field(default_factory=dict)
    partition: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class HudiCommit:
    """Modèle de commit Hudi."""
    commit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int = 0
    insert_count: int = 0
    upsert_count: int = 0
    delete_count: int = 0
    total_size: int = 0
    duration_ms: float = 0.0
    previous_commit: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HudiSnapshot:
    """Modèle de snapshot Hudi."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    commit_id: str = ""
    total_records: int = 0
    size_bytes: int = 0
    partitions: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class HudiEngineInterface(ABC):
    """Interface abstraite pour le moteur Hudi."""
    
    @abstractmethod
    async def create_table(self, table: HudiTable) -> bool:
        """Crée une table Hudi."""
        pass
    
    @abstractmethod
    async def write_records(self, table_name: str, records: List[HudiRecord]) -> HudiCommit:
        """Écrit des enregistrements."""
        pass
    
    @abstractmethod
    async def read_snapshot(self, table_name: str, snapshot_id: Optional[str] = None) -> HudiSnapshot:
        """Lit un snapshot."""
        pass
    
    @abstractmethod
    async def time_travel(self, table_name: str, timestamp: datetime) -> List[HudiRecord]:
        """Time travel sur une table."""
        pass


# ============== IMPLÉMENTATION ==============

class HudiEngine(HudiEngineInterface):
    """
    Moteur Hudi avancé pour le Hedge Bot.
    Gère l'intégration avec Apache Hudi, le data lake, les opérations ACID et le time travel.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des tables
        self._tables: Dict[str, HudiTable] = {}
        self._tables_lock = threading.RLock()
        
        # Gestion des commits
        self._commits: Dict[str, HudiCommit] = {}
        self._commits_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: Dict[str, HudiSnapshot] = {}
        self._snapshots_lock = threading.RLock()
        
        # Cache des données
        self._data_cache: Dict[str, List[HudiRecord]] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "tables_created": 0,
            "records_written": 0,
            "commits_processed": 0,
            "snapshots_taken": 0,
            "time_travel_ops": 0,
            "data_volume_mb": 0.0,
            "avg_write_time": 0.0,
            "avg_read_time": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # Base path pour les tables
        self._base_path = Path(self.config.get("base_path", "./hudi_data"))
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        # État
        self._is_running = False
        
        logger.info("HudiEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "base_path": "./hudi_data",
            "default_table_type": HudiTableType.MERGE_ON_READ,
            "default_index_type": HudiIndexType.BLOOM,
            "default_storage_type": HudiStorageType.LOCAL,
            "write_batch_size": 10000,
            "read_batch_size": 10000,
            "enable_cache": True,
            "cache_size": 10000,
            "compaction_interval": 3600,
            "clean_interval": 86400,
            "max_commits": 1000,
            "simulation_mode": True,
            "hudi_jar_path": "/opt/hudi/hudi-utilities.jar"
        }
    
    async def start(self) -> None:
        """Démarre le moteur Hudi."""
        logger.info("HudiEngine starting...")
        self._is_running = True
        
        # Chargement des tables existantes
        await self._load_tables()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._compaction_loop())
        asyncio.create_task(self._clean_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("HudiEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Hudi."""
        logger.info("HudiEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("HudiEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, table: HudiTable) -> bool:
        """Crée une table Hudi."""
        with self._tables_lock:
            self._tables[table.table_id] = table
            self._stats["tables_created"] += 1
        
        # Création du dossier de la table
        table_path = self._base_path / table.name
        table_path.mkdir(parents=True, exist_ok=True)
        
        # Création du fichier de schéma
        schema_path = table_path / "schema.json"
        with open(schema_path, 'w') as f:
            json.dump(table.schema, f, indent=2)
        
        # Création du fichier de configuration
        config_path = table_path / "config.json"
        config_data = {
            "table_type": table.table_type.value,
            "record_key": table.record_key,
            "precombine_field": table.precombine_field,
            "partition_fields": table.partition_fields,
            "index_type": table.index_type.value,
            "storage_type": table.storage_type.value
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Hudi table created: {table.name} at {table_path}")
        return True
    
    async def write_records(
        self,
        table_name: str,
        records: List[HudiRecord]
    ) -> HudiCommit:
        """Écrit des enregistrements."""
        start_time = time.time()
        self._stats["records_written"] += len(records)
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Organisation des enregistrements par opération
            inserts = [r for r in records if r.operation == HudiRecordType.INSERT]
            upserts = [r for r in records if r.operation == HudiRecordType.UPSERT]
            deletes = [r for r in records if r.operation == HudiRecordType.DELETE]
            
            # Simulation d'écriture Hudi
            if self.config["simulation_mode"]:
                await self._simulate_write(table, records)
            else:
                await self._write_to_hudi(table, records)
            
            # Création du commit
            commit = HudiCommit(
                table_name=table_name,
                records_count=len(records),
                insert_count=len(inserts),
                upsert_count=len(upserts),
                delete_count=len(deletes),
                duration_ms=(time.time() - start_time) * 1000,
                previous_commit=table.last_commit,
                metadata={
                    "table_type": table.table_type.value,
                    "batch_size": len(records)
                }
            )
            
            # Mise à jour de la table
            table.row_count += len(records)
            table.last_commit = commit.commit_id
            table.updated_at = datetime.now(timezone.utc)
            
            # Stockage du commit
            with self._commits_lock:
                self._commits[commit.commit_id] = commit
                self._stats["commits_processed"] += 1
            
            # Mise à jour du cache
            if self.config["enable_cache"]:
                await self._update_cache(table_name, records)
            
            logger.info(f"Records written to {table_name}: {len(records)} records "
                       f"(inserts={len(inserts)}, upserts={len(upserts)}, deletes={len(deletes)})")
            
            return commit
            
        except Exception as e:
            logger.error(f"Write records error: {e}")
            raise
    
    async def read_snapshot(
        self,
        table_name: str,
        snapshot_id: Optional[str] = None
    ) -> HudiSnapshot:
        """Lit un snapshot."""
        start_time = time.time()
        self._stats["snapshots_taken"] += 1
        
        try:
            # Récupération de la table
            table = await self.get_table_by_name(table_name)
            if not table:
                raise ValueError(f"Table {table_name} not found")
            
            # Récupération des données
            records = await self._read_data(table_name, snapshot_id)
            
            # Création du snapshot
            snapshot = HudiSnapshot(
                table_name=table_name,
                commit_id=snapshot_id or table.last_commit or "",
                total_records=len(records),
                partitions={},
                metadata={
                    "read_time_ms": (time.time() - start_time) * 1000
                }
            )
            
            # Analyse des partitions
            for record in records:
                if record.partition:
                    snapshot.partitions[record.partition] = snapshot.partitions.get(record.partition, 0) + 1
            
            # Stockage du snapshot
            with self._snapshots_lock:
                self._snapshots[snapshot.snapshot_id] = snapshot
            
            logger.info(f"Snapshot read from {table_name}: {len(records)} records")
            return snapshot
            
        except Exception as e:
            logger.error(f"Read snapshot error: {e}")
            raise
    
    async def time_travel(
        self,
        table_name: str,
        timestamp: datetime
    ) -> List[HudiRecord]:
        """Time travel sur une table."""
        self._stats["time_travel_ops"] += 1
        
        try:
            # Récupération des données historiques
            # Dans Hudi, on utilise le time travel avec les commits
            records = await self._read_data_at_time(table_name, timestamp)
            
            logger.info(f"Time travel on {table_name} at {timestamp.isoformat()}: {len(records)} records")
            return records
            
        except Exception as e:
            logger.error(f"Time travel error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - SIMULATION ==========
    
    async def _simulate_write(self, table: HudiTable, records: List[HudiRecord]) -> None:
        """Simule l'écriture Hudi."""
        # Simulation de délai
        await asyncio.sleep(len(records) / 1000)
        
        # Écriture dans le dossier de la table
        table_path = self._base_path / table.name
        data_file = table_path / f"data_{datetime.now(timezone.utc).timestamp()}.json"
        
        with open(data_file, 'w') as f:
            for record in records:
                json.dump(record.data, f)
                f.write("\n")
        
        # Mise à jour des métriques de taille
        table.size_bytes += data_file.stat().st_size
    
    async def _write_to_hudi(self, table: HudiTable, records: List[HudiRecord]) -> None:
        """Écrit vers Hudi via CLI."""
        # Dans un système réel, on utiliserait l'API Hudi
        # ou la ligne de commande hudi-utilities
        try:
            table_path = self._base_path / table.name
            
            # Création du fichier temporaire
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                for record in records:
                    json.dump(record.data, f)
                    f.write("\n")
                temp_file = f.name
            
            # Commande Hudi
            cmd = [
                "spark-submit",
                "--class", "org.apache.hudi.utilities.HoodieClusteringJob",
                self.config["hudi_jar_path"],
                "--base-path", str(table_path),
                "--table-name", table.name,
                "--operation", "upsert",
                "--record-key", table.record_key,
                "--precombine-field", table.precombine_field,
                "--source-file", temp_file
            ]
            
            # Exécution
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Nettoyage
            os.unlink(temp_file)
            
            if process.returncode != 0:
                raise Exception(f"Hudi write failed: {stderr.decode()}")
            
        except Exception as e:
            logger.error(f"Hudi write error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - LECTURE ==========
    
    async def _read_data(
        self,
        table_name: str,
        snapshot_id: Optional[str] = None
    ) -> List[HudiRecord]:
        """Lit les données d'une table."""
        # Vérification du cache
        cache_key = f"{table_name}_{snapshot_id or 'latest'}"
        with self._cache_lock:
            if cache_key in self._data_cache:
                logger.debug(f"Cache hit for {cache_key}")
                return self._data_cache[cache_key]
        
        # Lecture depuis le stockage
        table_path = self._base_path / table_name
        records = []
        
        # Lecture des fichiers de données
        for data_file in table_path.glob("data_*.json"):
            with open(data_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        record = HudiRecord(
                            table_name=table_name,
                            data=data,
                            timestamp=datetime.now(timezone.utc)
                        )
                        records.append(record)
                    except:
                        continue
        
        # Mise en cache
        if self.config["enable_cache"]:
            with self._cache_lock:
                if len(self._data_cache) < self.config["cache_size"]:
                    self._data_cache[cache_key] = records
        
        return records
    
    async def _read_data_at_time(
        self,
        table_name: str,
        timestamp: datetime
    ) -> List[HudiRecord]:
        """Lit les données à un moment donné."""
        # Dans un système réel, on utiliserait le time travel de Hudi
        # Lecture depuis les fichiers avec timestamp
        table_path = self._base_path / table_name
        records = []
        
        for data_file in table_path.glob("data_*.json"):
            # Extraction du timestamp du fichier
            try:
                file_ts = float(data_file.stem.split("_")[1])
                file_dt = datetime.fromtimestamp(file_ts, tz=timezone.utc)
                
                if file_dt <= timestamp:
                    with open(data_file, 'r') as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                record = HudiRecord(
                                    table_name=table_name,
                                    data=data,
                                    timestamp=file_dt
                                )
                                records.append(record)
                            except:
                                continue
            except:
                continue
        
        return records
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _compaction_loop(self) -> None:
        """Boucle de compaction."""
        while self._is_running:
            await asyncio.sleep(self.config["compaction_interval"])
            
            try:
                # Compaction des tables Merge-On-Read
                with self._tables_lock:
                    for table in self._tables.values():
                        if table.table_type == HudiTableType.MERGE_ON_READ:
                            await self._compact_table(table)
                
                logger.debug("Compaction completed")
                
            except Exception as e:
                logger.error(f"Compaction error: {e}")
    
    async def _compact_table(self, table: HudiTable) -> None:
        """Compacte une table."""
        # Dans un système réel, on lancerait la compaction Hudi
        logger.debug(f"Compacting table {table.name}")
        # Simulation de compaction
        await asyncio.sleep(0.1)
    
    async def _clean_loop(self) -> None:
        """Boucle de nettoyage."""
        while self._is_running:
            await asyncio.sleep(self.config["clean_interval"])
            
            try:
                # Nettoyage des anciens commits
                with self._commits_lock:
                    if len(self._commits) > self.config["max_commits"]:
                        keys = sorted(self._commits.keys())
                        for key in keys[:len(self._commits) - self.config["max_commits"]]:
                            del self._commits[key]
                
                logger.debug("Clean completed")
                
            except Exception as e:
                logger.error(f"Clean error: {e}")
    
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
                    total_size = sum(t.size_bytes for t in self._tables.values())
                    self._stats["data_volume_mb"] = total_size / (1024 * 1024)
                
                with self._commits_lock:
                    self._stats["total_commits"] = len(self._commits)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "hudi:metrics",
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
            for table_dir in self._base_path.iterdir():
                if table_dir.is_dir():
                    # Lecture du fichier de configuration
                    config_path = table_dir / "config.json"
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            config_data = json.load(f)
                        
                        # Création de l'objet table
                        table = HudiTable(
                            name=table_dir.name,
                            base_path=str(table_dir),
                            table_type=HudiTableType(config_data.get("table_type", "mor")),
                            record_key=config_data.get("record_key", "id"),
                            precombine_field=config_data.get("precombine_field", "timestamp"),
                            partition_fields=config_data.get("partition_fields", []),
                            index_type=HudiIndexType(config_data.get("index_type", "bloom")),
                            storage_type=HudiStorageType(config_data.get("storage_type", "local"))
                        )
                        
                        with self._tables_lock:
                            self._tables[table.table_id] = table
                        
                        logger.info(f"Loaded table: {table.name}")
            
            logger.info(f"Loaded {len(self._tables)} tables")
            
        except Exception as e:
            logger.error(f"Load tables error: {e}")
    
    async def _update_cache(
        self,
        table_name: str,
        records: List[HudiRecord]
    ) -> None:
        """Met à jour le cache."""
        with self._cache_lock:
            cache_key = f"{table_name}_latest"
            if cache_key not in self._data_cache:
                self._data_cache[cache_key] = []
            
            # Mise à jour du cache
            for record in records:
                # Recherche et remplacement pour upsert
                if record.operation in [HudiRecordType.UPSERT, HudiRecordType.INSERT]:
                    # Suppression des anciennes versions
                    record_key = record.data.get("id")
                    if record_key:
                        self._data_cache[cache_key] = [
                            r for r in self._data_cache[cache_key]
                            if r.data.get("id") != record_key
                        ]
                    self._data_cache[cache_key].append(record)
                
                elif record.operation == HudiRecordType.DELETE:
                    record_key = record.data.get("id")
                    if record_key:
                        self._data_cache[cache_key] = [
                            r for r in self._data_cache[cache_key]
                            if r.data.get("id") != record_key
                        ]
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_table(self, table_id: str) -> Optional[HudiTable]:
        """Récupère une table Hudi."""
        with self._tables_lock:
            return self._tables.get(table_id)
    
    async def get_table_by_name(self, name: str) -> Optional[HudiTable]:
        """Récupère une table par son nom."""
        with self._tables_lock:
            for table in self._tables.values():
                if table.name == name:
                    return table
        return None
    
    async def get_tables(self) -> List[HudiTable]:
        """Récupère toutes les tables."""
        with self._tables_lock:
            return list(self._tables.values())
    
    async def get_commit(self, commit_id: str) -> Optional[HudiCommit]:
        """Récupère un commit."""
        with self._commits_lock:
            return self._commits.get(commit_id)
    
    async def get_commits(self, table_name: str, limit: int = 100) -> List[HudiCommit]:
        """Récupère les commits d'une table."""
        with self._commits_lock:
            commits = [c for c in self._commits.values() if c.table_name == table_name]
            return sorted(commits, key=lambda c: c.timestamp, reverse=True)[:limit]
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[HudiSnapshot]:
        """Récupère un snapshot."""
        with self._snapshots_lock:
            return self._snapshots.get(snapshot_id)
    
    async def get_snapshots(self, table_name: str) -> List[HudiSnapshot]:
        """Récupère les snapshots d'une table."""
        with self._snapshots_lock:
            return [s for s in self._snapshots.values() if s.table_name == table_name]
    
    async def delete_table(self, table_name: str) -> bool:
        """Supprime une table Hudi."""
        try:
            table = await self.get_table_by_name(table_name)
            if not table:
                return False
            
            # Suppression du dossier
            import shutil
            shutil.rmtree(self._base_path / table_name)
            
            # Suppression de la table
            with self._tables_lock:
                del self._tables[table.table_id]
            
            # Suppression des commits
            with self._commits_lock:
                for commit_id in list(self._commits.keys()):
                    if self._commits[commit_id].table_name == table_name:
                        del self._commits[commit_id]
            
            logger.info(f"Table deleted: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Delete table error: {e}")
            return False
    
    async def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Récupère les statistiques d'une table."""
        table = await self.get_table_by_name(table_name)
        if not table:
            return {"error": "Table not found"}
        
        return {
            "name": table.name,
            "type": table.table_type.value,
            "row_count": table.row_count,
            "size_bytes": table.size_bytes,
            "partition_count": len(table.partition_fields),
            "last_commit": table.last_commit,
            "created_at": table.created_at.isoformat(),
            "updated_at": table.updated_at.isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._tables_lock:
            self._stats["tables"] = len(self._tables)
        with self._commits_lock:
            self._stats["commits"] = len(self._commits)
        with self._snapshots_lock:
            self._stats["snapshots"] = len(self._snapshots)
        with self._cache_lock:
            self._stats["cache_entries"] = len(self._data_cache)
        
        return self._stats.copy()


# ============== HUDI RECORD BUILDER ==============

class HudiRecordBuilder:
    """
    Constructeur d'enregistrements Hudi.
    Facilite la création d'enregistrements pour les tables Hudi.
    """
    
    def __init__(self):
        self._record = HudiRecord()
    
    def table(self, table_name: str) -> 'HudiRecordBuilder':
        """Définit la table."""
        self._record.table_name = table_name
        return self
    
    def operation(self, op: HudiRecordType) -> 'HudiRecordBuilder':
        """Définit l'opération."""
        self._record.operation = op
        return self
    
    def data(self, data: Dict[str, Any]) -> 'HudiRecordBuilder':
        """Définit les données."""
        self._record.data = data
        return self
    
    def partition(self, partition: str) -> 'HudiRecordBuilder':
        """Définit la partition."""
        self._record.partition = partition
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'HudiRecordBuilder':
        """Définit les métadonnées."""
        self._record.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'HudiRecordBuilder':
        """Définit les tags."""
        self._record.tags = tags
        return self
    
    def build(self) -> HudiRecord:
        """Construit l'enregistrement."""
        if not self._record.table_name:
            raise ValueError("Table name is required")
        if not self._record.data:
            raise ValueError("Data is required")
        return self._record


# ============== FACTORY ==============

class HudiFactory:
    """Factory pour créer des composants Hudi."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> HudiEngine:
        """Crée un moteur Hudi."""
        engine = HudiEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_record_builder() -> HudiRecordBuilder:
        """Crée un constructeur d'enregistrements."""
        return HudiRecordBuilder()


# ============== EXPORT ==============

__all__ = [
    "HudiTableType",
    "HudiRecordType",
    "HudiPrecombineField",
    "HudiIndexType",
    "HudiStorageType",
    "HudiTable",
    "HudiRecord",
    "HudiCommit",
    "HudiSnapshot",
    "HudiEngineInterface",
    "HudiEngine",
    "HudiRecordBuilder",
    "HudiFactory"
]
