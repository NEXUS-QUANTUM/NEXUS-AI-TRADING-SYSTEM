# trading/bots/hedge_bot/hedge_bot_data_hive.py
# Advanced Apache Hive Integration & Data Warehouse Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Hive Integration Module - Module d'intégration avancé avec Apache Hive pour le Hedge Bot.
Gère le data warehouse, l'analytique distribuée, les requêtes SQL sur de grands volumes de données,
et l'intégration avec l'écosystème Hadoop pour le traitement des données de hedging.
"""

import asyncio
import json
import time
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
import subprocess
import tempfile
import os
import re

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_hive")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class HiveTableType(Enum):
    """Types de tables Hive."""
    MANAGED = "managed"
    EXTERNAL = "external"
    TEMPORARY = "temporary"
    PARTITIONED = "partitioned"
    BUCKETED = "bucketed"
    ACID = "acid"


class HiveStorageFormat(Enum):
    """Formats de stockage Hive."""
    TEXTFILE = "textfile"
    SEQUENCEFILE = "sequencefile"
    RCFILE = "rcfile"
    ORC = "orc"
    PARQUET = "parquet"
    AVRO = "avro"
    JSON = "json"


class HiveCompression(Enum):
    """Méthodes de compression Hive."""
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    LZO = "lzo"
    ZLIB = "zlib"
    ZSTD = "zstd"


class HiveQueryType(Enum):
    """Types de requêtes Hive."""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    ALTER = "alter"
    DROP = "drop"
    ANALYZE = "analyze"


# ============== DATA MODELS ==============

@dataclass
class HiveTable:
    """Modèle de table Hive."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    database: str = "default"
    table_type: HiveTableType = HiveTableType.MANAGED
    storage_format: HiveStorageFormat = HiveStorageFormat.ORC
    compression: HiveCompression = HiveCompression.SNAPPY
    columns: List[Dict[str, str]] = field(default_factory=list)
    partitions: List[str] = field(default_factory=list)
    buckets: int = 0
    bucket_columns: List[str] = field(default_factory=list)
    location: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "database": self.database,
            "table_type": self.table_type.value,
            "storage_format": self.storage_format.value,
            "compression": self.compression.value,
            "columns": self.columns,
            "partitions": self.partitions,
            "buckets": self.buckets,
            "bucket_columns": self.bucket_columns,
            "location": self.location,
            "properties": self.properties,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "row_count": self.row_count,
            "size_bytes": self.size_bytes
        }


@dataclass
class HiveQuery:
    """Modèle de requête Hive."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_type: HiveQueryType = HiveQueryType.SELECT
    sql: str = ""
    database: str = "default"
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 3600
    result_limit: int = 10000
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    row_count: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None
    result_data: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict:
        return {
            "query_id": self.query_id,
            "query_type": self.query_type.value,
            "sql": self.sql,
            "database": self.database,
            "parameters": self.parameters,
            "timeout": self.timeout,
            "result_limit": self.result_limit,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "row_count": self.row_count,
            "execution_time": self.execution_time,
            "error": self.error,
            "result_data": self.result_data
        }


@dataclass
class HivePartition:
    """Modèle de partition Hive."""
    partition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    database: str = "default"
    partition_key: str = ""
    partition_value: str = ""
    location: Optional[str] = None
    row_count: int = 0
    size_bytes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class HiveEngineInterface(ABC):
    """Interface abstraite pour le moteur Hive."""
    
    @abstractmethod
    async def create_table(self, table: HiveTable) -> bool:
        """Crée une table Hive."""
        pass
    
    @abstractmethod
    async def execute_query(self, query: HiveQuery) -> HiveQuery:
        """Exécute une requête Hive."""
        pass
    
    @abstractmethod
    async def get_table(self, table_name: str) -> Optional[HiveTable]:
        """Récupère une table Hive."""
        pass


# ============== IMPLÉMENTATION ==============

class HiveEngine(HiveEngineInterface):
    """
    Moteur Hive avancé pour le Hedge Bot.
    Gère l'intégration avec Apache Hive, le data warehouse et l'analytique distribuée.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des tables
        self._tables: Dict[str, HiveTable] = {}
        self._tables_lock = threading.RLock()
        
        # Gestion des requêtes
        self._queries: Dict[str, HiveQuery] = {}
        self._queries_lock = threading.RLock()
        
        # Gestion des partitions
        self._partitions: Dict[str, HivePartition] = {}
        self._partitions_lock = threading.RLock()
        
        # Cache des métadonnées
        self._metadata_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "tables_created": 0,
            "queries_executed": 0,
            "queries_completed": 0,
            "queries_failed": 0,
            "rows_processed": 0,
            "data_volume_mb": 0.0,
            "avg_query_time": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Connexion Hive (simulée)
        self._hive_connection = None
        
        logger.info("HiveEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "hive_host": "localhost",
            "hive_port": 10000,
            "hive_user": "hive",
            "hive_password": "",
            "default_database": "default",
            "default_storage_format": HiveStorageFormat.ORC,
            "default_compression": HiveCompression.SNAPPY,
            "query_timeout": 3600,
            "max_query_results": 10000,
            "cache_ttl": 3600,
            "auto_create_tables": True,
            "enable_partitioning": True,
            "enable_bucketing": False,
            "enable_acid": False,
            "simulation_mode": True,
            "hive_bin_path": "/usr/bin/hive",
            "beeline_bin_path": "/usr/bin/beeline"
        }
    
    async def start(self) -> None:
        """Démarre le moteur Hive."""
        logger.info("HiveEngine starting...")
        self._is_running = True
        
        # Connexion à Hive
        if not self.config["simulation_mode"]:
            await self._connect_to_hive()
        else:
            logger.info("Running in simulation mode")
        
        # Chargement des tables existantes
        await self._load_tables()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._metadata_updater())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("HiveEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur Hive."""
        logger.info("HiveEngine stopping...")
        self._is_running = False
        
        # Déconnexion de Hive
        if self._hive_connection:
            await self._disconnect_from_hive()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("HiveEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, table: HiveTable) -> bool:
        """Crée une table Hive."""
        with self._tables_lock:
            self._tables[table.table_id] = table
            self._stats["tables_created"] += 1
        
        try:
            # Construction de la requête de création
            create_sql = self._build_create_table_sql(table)
            
            # Exécution de la requête
            query = HiveQuery(
                query_type=HiveQueryType.CREATE,
                sql=create_sql,
                database=table.database,
                metadata={"table_name": table.name}
            )
            
            result = await self.execute_query(query)
            
            if result.status == "completed":
                logger.info(f"Table created: {table.database}.{table.name}")
                return True
            else:
                logger.error(f"Table creation failed: {result.error}")
                return False
            
        except Exception as e:
            logger.error(f"Table creation error: {e}")
            return False
    
    async def execute_query(self, query: HiveQuery) -> HiveQuery:
        """Exécute une requête Hive."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        with self._queries_lock:
            self._queries[query.query_id] = query
        
        try:
            # Mise à jour du statut
            query.status = "running"
            query.executed_at = datetime.now(timezone.utc)
            
            # Exécution de la requête
            if self.config["simulation_mode"]:
                result_data = await self._simulate_query_execution(query)
            else:
                result_data = await self._execute_hive_query(query)
            
            # Mise à jour du résultat
            query.status = "completed"
            query.completed_at = datetime.now(timezone.utc)
            query.execution_time = time.time() - start_time
            query.row_count = len(result_data) if result_data else 0
            query.result_data = result_data[:query.result_limit]
            
            self._stats["queries_completed"] += 1
            self._stats["rows_processed"] += query.row_count
            self._stats["avg_query_time"] = (
                self._stats["avg_query_time"] * 0.9 + query.execution_time * 0.1
            )
            
            # Stockage des résultats
            if self.data_manager:
                await self.data_manager.store(
                    f"hive:query:{query.query_id}",
                    query.to_dict(),
                    DataType.QUERY
                )
            
            logger.info(f"Query executed: {query.query_id} "
                       f"rows={query.row_count} time={query.execution_time:.2f}s")
            
            return query
            
        except Exception as e:
            query.status = "failed"
            query.error = str(e)
            query.completed_at = datetime.now(timezone.utc)
            query.execution_time = time.time() - start_time
            
            self._stats["queries_failed"] += 1
            
            logger.error(f"Query execution failed: {query.query_id} - {e}")
            return query
    
    async def get_table(self, table_name: str) -> Optional[HiveTable]:
        """Récupère une table Hive."""
        with self._tables_lock:
            for table in self._tables.values():
                if table.name == table_name:
                    return table
        
        # Vérification du cache
        cache_key = f"table:{table_name}"
        with self._cache_lock:
            if cache_key in self._metadata_cache:
                return self._metadata_cache[cache_key]
        
        # Récupération depuis Hive
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"hive:table:{table_name}",
                DataType.METADATA
            )
            if data:
                table = self._deserialize_table(data)
                if table:
                    with self._cache_lock:
                        self._metadata_cache[cache_key] = table
                    return table
        
        return None
    
    # ========== MÉTHODES PRIVÉES - SQL ==========
    
    def _build_create_table_sql(self, table: HiveTable) -> str:
        """Construit la requête de création de table."""
        sql_parts = []
        
        # CREATE TABLE
        sql_parts.append(f"CREATE {'EXTERNAL' if table.table_type == HiveTableType.EXTERNAL else ''} TABLE")
        sql_parts.append(f"{table.database}.{table.name}")
        
        # Colonnes
        if table.columns:
            cols = []
            for col in table.columns:
                cols.append(f"`{col['name']}` {col['type']}")
            sql_parts.append(f"({', '.join(cols)})")
        
        # Partitions
        if table.partitions:
            partition_cols = [f"`{p}` STRING" for p in table.partitions]
            sql_parts.append(f"PARTITIONED BY ({', '.join(partition_cols)})")
        
        # Bucketing
        if table.buckets > 0 and table.bucket_columns:
            sql_parts.append(f"CLUSTERED BY ({', '.join(table.bucket_columns)}) INTO {table.buckets} BUCKETS")
        
        # Format de stockage
        sql_parts.append(f"STORED AS {table.storage_format.value.upper()}")
        
        # Compression
        if table.compression != HiveCompression.NONE:
            sql_parts.append(f"TBLPROPERTIES ('orc.compress'='{table.compression.value.upper()}')")
        
        # Location
        if table.location:
            sql_parts.append(f"LOCATION '{table.location}'")
        
        return "\n".join(sql_parts)
    
    def _build_select_sql(self, query: HiveQuery) -> str:
        """Construit une requête SELECT."""
        # Parsing simplifié du SQL
        sql = query.sql
        
        # Limite du résultat
        if "limit" not in sql.lower():
            sql += f" LIMIT {query.result_limit}"
        
        return sql
    
    # ========== MÉTHODES PRIVÉES - EXÉCUTION ==========
    
    async def _simulate_query_execution(self, query: HiveQuery) -> List[Dict[str, Any]]:
        """Simule l'exécution d'une requête Hive."""
        # Simulation de temps d'exécution
        await asyncio.sleep(random.uniform(0.1, 1.0))
        
        # Détermination du type de requête
        sql_lower = query.sql.lower()
        
        if "select" in sql_lower:
            # Simulation de résultats SELECT
            return self._generate_simulated_results(query)
        elif "create" in sql_lower:
            return [{"status": "success", "message": "Table created"}]
        elif "insert" in sql_lower:
            return [{"status": "success", "message": "Data inserted"}]
        elif "drop" in sql_lower:
            return [{"status": "success", "message": "Table dropped"}]
        else:
            return [{"status": "success", "message": "Query executed"}]
    
    def _generate_simulated_results(self, query: HiveQuery) -> List[Dict[str, Any]]:
        """Génère des résultats simulés pour une requête SELECT."""
        # Analyse de la requête pour déterminer les colonnes
        sql_lower = query.sql.lower()
        columns = ["col1", "col2", "col3", "col4"]
        
        # Extraction des colonnes du SELECT
        if "select" in sql_lower:
            select_part = sql_lower.split("select")[1].split("from")[0]
            # Parsing simple
            if "*" in select_part:
                # Colonnes par défaut
                columns = ["id", "symbol", "price", "volume", "timestamp"]
            else:
                # Extraction des noms de colonnes
                raw_cols = select_part.split(",")
                columns = []
                for col in raw_cols:
                    col = col.strip()
                    if " as " in col:
                        col = col.split(" as ")[-1]
                    elif " " in col and not any(func in col for func in ["sum", "avg", "count", "max", "min"]):
                        col = col.split(" ")[-1]
                    columns.append(col)
        
        # Génération des données
        num_rows = min(random.randint(10, 100), query.result_limit)
        results = []
        
        for i in range(num_rows):
            row = {}
            for col in columns:
                if "id" in col.lower():
                    row[col] = i + 1
                elif "price" in col.lower() or "value" in col.lower():
                    row[col] = round(random.uniform(100, 1000), 2)
                elif "volume" in col.lower():
                    row[col] = random.randint(100, 10000)
                elif "timestamp" in col.lower() or "time" in col.lower():
                    row[col] = datetime.now(timezone.utc).isoformat()
                elif "symbol" in col.lower():
                    row[col] = random.choice(["BTC-USD", "ETH-USD", "AAPL", "SPX"])
                elif "status" in col.lower():
                    row[col] = random.choice(["active", "pending", "completed", "failed"])
                elif "type" in col.lower():
                    row[col] = random.choice(["buy", "sell", "hedge", "unwind"])
                else:
                    row[col] = random.choice(["A", "B", "C", "D"])
            results.append(row)
        
        return results
    
    async def _execute_hive_query(self, query: HiveQuery) -> List[Dict[str, Any]]:
        """Exécute une requête Hive réelle."""
        # Utilisation de beeline pour exécuter les requêtes
        # Dans un système réel, on utiliserait le client JDBC
        results = []
        
        try:
            # Construction de la commande
            cmd = [
                self.config["beeline_bin_path"],
                "-u", f"jdbc:hive2://{self.config['hive_host']}:{self.config['hive_port']}",
                "-n", self.config["hive_user"],
                "-e", query.sql,
                "--outputformat", "json"
            ]
            
            # Exécution
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parsing du résultat JSON
                output = stdout.decode()
                if output:
                    # Extraction des données JSON
                    try:
                        results = json.loads(output)
                    except:
                        # Fallback: parsing ligne par ligne
                        for line in output.split("\n"):
                            if line.strip():
                                try:
                                    results.append(json.loads(line))
                                except:
                                    pass
            else:
                error = stderr.decode()
                raise Exception(f"Hive query failed: {error}")
            
            return results
            
        except Exception as e:
            logger.error(f"Hive execution error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - CONNEXION ==========
    
    async def _connect_to_hive(self) -> None:
        """Connecte au serveur Hive."""
        # Dans un système réel, on établirait une connexion JDBC
        logger.info(f"Connecting to Hive at {self.config['hive_host']}:{self.config['hive_port']}")
        await asyncio.sleep(0.5)  # Simulation de connexion
        self._hive_connection = True
        logger.info("Connected to Hive")
    
    async def _disconnect_from_hive(self) -> None:
        """Déconnecte du serveur Hive."""
        if self._hive_connection:
            logger.info("Disconnecting from Hive")
            self._hive_connection = None
            await asyncio.sleep(0.2)
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _metadata_updater(self) -> None:
        """Met à jour les métadonnées des tables."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Mise à jour des métadonnées
                with self._tables_lock:
                    for table in self._tables.values():
                        # Mise à jour des statistiques
                        table.updated_at = datetime.now(timezone.utc)
                
                logger.debug("Table metadata updated")
                
            except Exception as e:
                logger.error(f"Metadata updater error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    # Nettoyage du cache
                    if len(self._metadata_cache) > 100:
                        keys = list(self._metadata_cache.keys())
                        for key in keys[:len(self._metadata_cache) - 100]:
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
                with self._queries_lock:
                    self._stats["total_queries"] = len(self._queries)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "hive:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _load_tables(self) -> None:
        """Charge les tables existantes."""
        try:
            if self.data_manager:
                tables_data = await self.data_manager.retrieve(
                    "hive:tables",
                    DataType.METADATA
                )
                
                if tables_data:
                    for table_dict in tables_data:
                        table = self._deserialize_table(table_dict)
                        if table:
                            with self._tables_lock:
                                self._tables[table.table_id] = table
            
            logger.info(f"Loaded {len(self._tables)} tables")
            
        except Exception as e:
            logger.error(f"Load tables error: {e}")
    
    # ========== MÉTHODES DE DÉSÉRIALISATION ==========
    
    def _deserialize_table(self, data: Dict) -> Optional[HiveTable]:
        """Désérialise une table Hive."""
        try:
            return HiveTable(
                table_id=data.get("table_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                database=data.get("database", "default"),
                table_type=HiveTableType(data.get("table_type", "managed")),
                storage_format=HiveStorageFormat(data.get("storage_format", "orc")),
                compression=HiveCompression(data.get("compression", "snappy")),
                columns=data.get("columns", []),
                partitions=data.get("partitions", []),
                buckets=data.get("buckets", 0),
                bucket_columns=data.get("bucket_columns", []),
                location=data.get("location"),
                properties=data.get("properties", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                row_count=data.get("row_count", 0),
                size_bytes=data.get("size_bytes", 0)
            )
        except Exception as e:
            logger.error(f"Error deserializing table: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_query(self, query_id: str) -> Optional[HiveQuery]:
        """Récupère une requête Hive."""
        with self._queries_lock:
            return self._queries.get(query_id)
    
    async def get_queries(self, status: Optional[str] = None) -> List[HiveQuery]:
        """Récupère les requêtes Hive."""
        with self._queries_lock:
            queries = list(self._queries.values())
            if status:
                queries = [q for q in queries if q.status == status]
            return sorted(queries, key=lambda q: q.created_at, reverse=True)
    
    async def get_tables(self, database: Optional[str] = None) -> List[HiveTable]:
        """Récupère les tables Hive."""
        with self._tables_lock:
            tables = list(self._tables.values())
            if database:
                tables = [t for t in tables if t.database == database]
            return tables
    
    async def get_table_schema(self, table_name: str) -> Optional[List[Dict[str, str]]]:
        """Récupère le schéma d'une table."""
        table = await self.get_table(table_name)
        if table:
            return table.columns
        return None
    
    async def get_partitions(self, table_name: str) -> List[HivePartition]:
        """Récupère les partitions d'une table."""
        with self._partitions_lock:
            return [
                p for p in self._partitions.values()
                if p.table_name == table_name
            ]
    
    async def analyze_table(self, table_name: str) -> Dict[str, Any]:
        """Analyse une table Hive."""
        # Construction de la requête ANALYZE
        analyze_sql = f"ANALYZE TABLE {table_name} COMPUTE STATISTICS"
        
        query = HiveQuery(
            query_type=HiveQueryType.ANALYZE,
            sql=analyze_sql,
            metadata={"table_name": table_name}
        )
        
        result = await self.execute_query(query)
        
        if result.status == "completed":
            # Mise à jour des statistiques
            table = await self.get_table(table_name)
            if table:
                table.updated_at = datetime.now(timezone.utc)
            
            return {
                "success": True,
                "message": "Table analyzed",
                "table": table_name,
                "row_count": result.row_count if result.row_count else 0
            }
        else:
            return {
                "success": False,
                "error": result.error
            }
    
    async def export_table(
        self,
        table_name: str,
        format: str = "csv",
        partition: Optional[str] = None
    ) -> str:
        """Exporte une table Hive."""
        # Construction de la requête d'export
        if partition:
            export_sql = f"SELECT * FROM {table_name} WHERE {partition}"
        else:
            export_sql = f"SELECT * FROM {table_name}"
        
        query = HiveQuery(
            query_type=HiveQueryType.SELECT,
            sql=export_sql,
            result_limit=100000,
            metadata={"export_format": format}
        )
        
        result = await self.execute_query(query)
        
        if result.status == "completed" and result.result_data:
            # Export en CSV
            if format == "csv":
                import csv
                import io
                output = io.StringIO()
                if result.result_data:
                    writer = csv.DictWriter(output, fieldnames=result.result_data[0].keys())
                    writer.writeheader()
                    writer.writerows(result.result_data)
                return output.getvalue()
            elif format == "json":
                return json.dumps(result.result_data, indent=2)
            else:
                return json.dumps(result.result_data)
        
        return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._tables_lock:
            self._stats["tables"] = len(self._tables)
        with self._queries_lock:
            self._stats["queries"] = len(self._queries)
        with self._cache_lock:
            self._stats["cache_size"] = len(self._metadata_cache)
        
        return self._stats.copy()


# ============== HIVE QUERY BUILDER ==============

class HiveQueryBuilder:
    """
    Constructeur de requêtes Hive.
    Facilite la création de requêtes Hive complexes.
    """
    
    def __init__(self):
        self._select = []
        self._from = ""
        self._where = []
        self._group_by = []
        self._having = []
        self._order_by = []
        self._limit = 0
        self._distinct = False
    
    def select(self, *columns: str) -> 'HiveQueryBuilder':
        """Ajoute une clause SELECT."""
        if self._distinct:
            self._select.append(f"DISTINCT {', '.join(columns)}")
        else:
            self._select.append(", ".join(columns))
        return self
    
    def select_distinct(self, *columns: str) -> 'HiveQueryBuilder':
        """Ajoute une clause SELECT DISTINCT."""
        self._distinct = True
        self._select.append(f"DISTINCT {', '.join(columns)}")
        return self
    
    def from_table(self, table: str) -> 'HiveQueryBuilder':
        """Ajoute une clause FROM."""
        self._from = table
        return self
    
    def where(self, condition: str) -> 'HiveQueryBuilder':
        """Ajoute une clause WHERE."""
        self._where.append(condition)
        return self
    
    def where_raw(self, condition: str) -> 'HiveQueryBuilder':
        """Ajoute une clause WHERE brute."""
        self._where.append(condition)
        return self
    
    def group_by(self, *columns: str) -> 'HiveQueryBuilder':
        """Ajoute une clause GROUP BY."""
        self._group_by.extend(columns)
        return self
    
    def having(self, condition: str) -> 'HiveQueryBuilder':
        """Ajoute une clause HAVING."""
        self._having.append(condition)
        return self
    
    def order_by(self, column: str, direction: str = "ASC") -> 'HiveQueryBuilder':
        """Ajoute une clause ORDER BY."""
        self._order_by.append(f"{column} {direction}")
        return self
    
    def limit(self, limit: int) -> 'HiveQueryBuilder':
        """Ajoute une clause LIMIT."""
        self._limit = limit
        return self
    
    def build(self) -> str:
        """Construit la requête SQL."""
        parts = []
        
        # SELECT
        if self._select:
            parts.append(f"SELECT {', '.join(self._select)}")
        else:
            parts.append("SELECT *")
        
        # FROM
        if self._from:
            parts.append(f"FROM {self._from}")
        else:
            raise ValueError("FROM clause is required")
        
        # WHERE
        if self._where:
            parts.append(f"WHERE {' AND '.join(self._where)}")
        
        # GROUP BY
        if self._group_by:
            parts.append(f"GROUP BY {', '.join(self._group_by)}")
        
        # HAVING
        if self._having:
            parts.append(f"HAVING {' AND '.join(self._having)}")
        
        # ORDER BY
        if self._order_by:
            parts.append(f"ORDER BY {', '.join(self._order_by)}")
        
        # LIMIT
        if self._limit > 0:
            parts.append(f"LIMIT {self._limit}")
        
        return "\n".join(parts)


# ============== FACTORY ==============

class HiveFactory:
    """Factory pour créer des composants Hive."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> HiveEngine:
        """Crée un moteur Hive."""
        engine = HiveEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_query_builder() -> HiveQueryBuilder:
        """Crée un constructeur de requêtes Hive."""
        return HiveQueryBuilder()


# ============== EXPORT ==============

__all__ = [
    "HiveTableType",
    "HiveStorageFormat",
    "HiveCompression",
    "HiveQueryType",
    "HiveTable",
    "HiveQuery",
    "HivePartition",
    "HiveEngineInterface",
    "HiveEngine",
    "HiveQueryBuilder",
    "HiveFactory"
]
