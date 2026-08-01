# trading/bots/hedge_bot/hedge_bot_data_postgresql.py
# Advanced PostgreSQL Integration & Relational Data Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot PostgreSQL Integration Module - Module d'intégration avancé avec PostgreSQL pour le Hedge Bot.
Gère le stockage relationnel, les schémas, les migrations, les index, les transactions,
et les requêtes SQL optimisées pour les données de hedging.
"""

import asyncio
import json
import time
import asyncpg
from asyncpg import Connection, Pool, Record
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_postgresql")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class IsolationLevel(Enum):
    """Niveaux d'isolation des transactions."""
    READ_UNCOMMITTED = "read_uncommitted"
    READ_COMMITTED = "read_committed"
    REPEATABLE_READ = "repeatable_read"
    SERIALIZABLE = "serializable"


class LockType(Enum):
    """Types de verrous PostgreSQL."""
    SHARE = "share"
    EXCLUSIVE = "exclusive"
    ROW_SHARE = "row_share"
    ROW_EXCLUSIVE = "row_exclusive"
    ACCESS_SHARE = "access_share"
    ACCESS_EXCLUSIVE = "access_exclusive"


# ============== DATA MODELS ==============

@dataclass
class TableSchema:
    """Schéma de table."""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    schema: str = "public"
    columns: List[Dict[str, Any]] = field(default_factory=list)
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    row_count: int = 0
    size_bytes: int = 0
    version: int = 1


@dataclass
class QueryResult:
    """Résultat de requête."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    columns: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Configuration de base de données."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    host: str = "localhost"
    port: int = 5432
    database: str = "nexus"
    user: str = "postgres"
    password: str = ""
    ssl_mode: str = "prefer"
    pool_size: int = 10
    max_overflow: int = 20
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


# ============== INTERFACES ==============

class PostgreSQLEngineInterface(ABC):
    """Interface abstraite pour le moteur PostgreSQL."""
    
    @abstractmethod
    async def create_table(self, schema: TableSchema) -> bool:
        """Crée une table."""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict] = None) -> QueryResult:
        """Exécute une requête SQL."""
        pass
    
    @abstractmethod
    async def transaction(self, queries: List[Tuple[str, Dict]]) -> List[QueryResult]:
        """Exécute des requêtes en transaction."""
        pass
    
    @abstractmethod
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Récupère les informations d'une table."""
        pass


# ============== IMPLÉMENTATION ==============

class PostgreSQLEngine(PostgreSQLEngineInterface):
    """
    Moteur PostgreSQL avancé pour le Hedge Bot.
    Gère le stockage relationnel, les transactions et les requêtes optimisées.
    """
    
    def __init__(
        self,
        config: DatabaseConfig,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config_override: Optional[Dict[str, Any]] = None
    ):
        self.config = config
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config_override = config_override or self._default_config()
        
        # Pool de connexions
        self._pool: Optional[Pool] = None
        self._pool_lock = threading.RLock()
        
        # Gestion des schémas
        self._schemas: Dict[str, TableSchema] = {}
        self._schemas_lock = threading.RLock()
        
        # Cache des requêtes
        self._query_cache: Dict[str, QueryResult] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "queries_executed": 0,
            "queries_cached": 0,
            "transactions_committed": 0,
            "transactions_rolled_back": 0,
            "tables_created": 0,
            "avg_query_time_ms": 0.0,
            "connections": 0,
            "errors": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config_override.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PostgreSQLEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "query_timeout": 30,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_prepared_statements": True,
            "max_query_size": 1024 * 1024,
            "batch_size": 1000,
            "statement_cache_size": 100,
            "enable_logging": True,
            "slow_query_threshold": 100
        }
    
    async def start(self) -> None:
        """Démarre le moteur PostgreSQL."""
        logger.info("PostgreSQLEngine starting...")
        self._is_running = True
        
        # Création du pool de connexions
        await self._create_pool()
        
        # Chargement des schémas
        await self._load_schemas()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._health_check_loop())
        
        logger.info("PostgreSQLEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur PostgreSQL."""
        logger.info("PostgreSQLEngine stopping...")
        self._is_running = False
        
        # Fermeture du pool
        if self._pool:
            await self._pool.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PostgreSQLEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_table(self, schema: TableSchema) -> bool:
        """Crée une table."""
        try:
            # Construction de la requête CREATE TABLE
            create_query = await self._build_create_table_query(schema)
            
            # Exécution de la requête
            result = await self.execute(create_query)
            
            if result.error:
                logger.error(f"Table creation failed: {result.error}")
                return False
            
            # Stockage du schéma
            with self._schemas_lock:
                self._schemas[schema.table_id] = schema
                self._stats["tables_created"] += 1
            
            logger.info(f"Table created: {schema.schema}.{schema.name}")
            return True
            
        except Exception as e:
            logger.error(f"Table creation error: {e}")
            return False
    
    async def execute(self, query: str, params: Optional[Dict] = None) -> QueryResult:
        """Exécute une requête SQL."""
        start_time = time.time()
        self._stats["queries_executed"] += 1
        
        # Vérification du cache
        cache_key = self._compute_cache_key(query, params)
        if self.config_override["enable_cache"] and cache_key in self._query_cache:
            self._stats["queries_cached"] += 1
            return self._query_cache[cache_key]
        
        try:
            # Exécution de la requête
            async with self._pool.acquire() as conn:
                # Préparation de la requête
                if self.config_override["enable_prepared_statements"]:
                    stmt = await conn.prepare(query)
                    result = await stmt.fetch(*(params.values() if params else ()))
                else:
                    result = await conn.fetch(query, *(params.values() if params else ()))
                
                # Construction du résultat
                query_result = QueryResult(
                    query=query,
                    rows=[dict(row) for row in result],
                    row_count=len(result),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    columns=list(result[0].keys()) if result else []
                )
                
                # Mise en cache
                if self.config_override["enable_cache"]:
                    with self._cache_lock:
                        if len(self._query_cache) < self.config_override["cache_size"]:
                            self._query_cache[cache_key] = query_result
                
                # Mise à jour des statistiques
                self._stats["avg_query_time_ms"] = (
                    self._stats["avg_query_time_ms"] * 0.9 + query_result.execution_time_ms * 0.1
                )
                
                # Log des requêtes lentes
                if query_result.execution_time_ms > self.config_override["slow_query_threshold"]:
                    logger.warning(f"Slow query: {query_result.execution_time_ms:.2f}ms - {query[:100]}...")
                
                return query_result
                
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query execution error: {e}")
            return QueryResult(
                query=query,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def transaction(self, queries: List[Tuple[str, Dict]]) -> List[QueryResult]:
        """Exécute des requêtes en transaction."""
        results = []
        
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    for query, params in queries:
                        result = await conn.fetch(query, *(params.values() if params else ()))
                        results.append(QueryResult(
                            query=query,
                            rows=[dict(row) for row in result],
                            row_count=len(result),
                            columns=list(result[0].keys()) if result else []
                        ))
                
                self._stats["transactions_committed"] += 1
                
        except Exception as e:
            self._stats["transactions_rolled_back"] += 1
            self._stats["errors"] += 1
            logger.error(f"Transaction error: {e}")
            
            # Ajout de l'erreur aux résultats
            results.append(QueryResult(
                query="",
                error=str(e)
            ))
        
        return results
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Récupère les informations d'une table."""
        try:
            # Récupération des colonnes
            columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = $1
                ORDER BY ordinal_position
            """
            columns_result = await self.execute(columns_query, {"table_name": table_name})
            
            # Récupération des contraintes
            constraints_query = """
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = $1
            """
            constraints_result = await self.execute(constraints_query, {"table_name": table_name})
            
            # Récupération des index
            indexes_query = """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = $1
            """
            indexes_result = await self.execute(indexes_query, {"table_name": table_name})
            
            return {
                "table_name": table_name,
                "columns": columns_result.rows,
                "constraints": constraints_result.rows,
                "indexes": indexes_result.rows
            }
            
        except Exception as e:
            logger.error(f"Table info error: {e}")
            return {"error": str(e)}
    
    # ========== MÉTHODES PRIVÉES - POOL ==========
    
    async def _create_pool(self) -> None:
        """Crée le pool de connexions."""
        try:
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                ssl=self.config.ssl_mode,
                min_size=1,
                max_size=self.config.pool_size,
                max_inactive_connection_lifetime=300,
                timeout=self.config.timeout,
                command_timeout=self.config.timeout
            )
            
            self._stats["connections"] = self.config.pool_size
            
            # Test de connexion
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"PostgreSQL connected: {version}")
                
        except Exception as e:
            logger.error(f"Pool creation error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - SCHÉMAS ==========
    
    async def _build_create_table_query(self, schema: TableSchema) -> str:
        """Construit une requête CREATE TABLE."""
        columns = []
        for col in schema.columns:
            col_def = f"{col['name']} {col['type']}"
            if col.get('nullable') == False:
                col_def += " NOT NULL"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            columns.append(col_def)
        
        query = f"CREATE TABLE IF NOT EXISTS {schema.schema}.{schema.name} (\n  " + ",\n  ".join(columns)
        
        if schema.primary_key:
            query += f",\n  PRIMARY KEY ({schema.primary_key})"
        
        query += "\n)"
        
        return query
    
    async def _load_schemas(self) -> None:
        """Charge les schémas existants."""
        try:
            # Récupération des tables
            tables_query = """
                SELECT table_name, table_schema
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """
            result = await self.execute(tables_query)
            
            for row in result.rows:
                table_name = row['table_name']
                table_schema = row['table_schema']
                
                # Récupération des colonnes
                columns_query = """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = $1 AND table_schema = $2
                    ORDER BY ordinal_position
                """
                columns_result = await self.execute(columns_query, {"table_name": table_name, "table_schema": table_schema})
                
                # Création du schéma
                schema = TableSchema(
                    name=table_name,
                    schema=table_schema,
                    columns=columns_result.rows
                )
                
                with self._schemas_lock:
                    self._schemas[schema.table_id] = schema
            
            logger.info(f"Loaded {len(self._schemas)} table schemas")
            
        except Exception as e:
            logger.error(f"Load schemas error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    def _compute_cache_key(self, query: str, params: Optional[Dict]) -> str:
        """Calcule une clé de cache."""
        key_data = {
            "query": query,
            "params": params
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._query_cache) > self.config_override["cache_size"]:
                        keys = list(self._query_cache.keys())
                        for key in keys[:len(self._query_cache) - self.config_override["cache_size"]]:
                            del self._query_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Vérification de la connexion
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self._stats["errors"] += 1
                
                # Tentative de reconnexion
                await self._reconnect()
    
    async def _reconnect(self) -> None:
        """Reconnecte la base de données."""
        try:
            if self._pool:
                await self._pool.close()
            
            await self._create_pool()
            logger.info("Reconnected to PostgreSQL")
            
        except Exception as e:
            logger.error(f"Reconnection error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Récupération des métriques PostgreSQL
                if self._pool:
                    async with self._pool.acquire() as conn:
                        # Taille de la base
                        size = await conn.fetchval("SELECT pg_database_size(current_database())")
                        
                        # Version
                        version = await conn.fetchval("SELECT version()")
                        
                        # Métriques système
                        stats = await conn.fetch("""
                            SELECT 
                                (SELECT count(*) FROM pg_stat_activity) as connections,
                                (SELECT count(*) FROM pg_stat_user_tables) as tables,
                                (SELECT sum(seq_scan) FROM pg_stat_user_tables) as seq_scans,
                                (SELECT sum(idx_scan) FROM pg_stat_user_tables) as idx_scans
                        """)
                        
                        if stats:
                            self._stats["db_size_mb"] = size / (1024 * 1024)
                            self._stats["db_connections"] = stats[0]["connections"]
                            self._stats["db_tables"] = stats[0]["tables"]
                            self._stats["seq_scans"] = stats[0]["seq_scans"]
                            self._stats["idx_scans"] = stats[0]["idx_scans"]
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "postgresql:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_schema(self, schema_id: str) -> Optional[TableSchema]:
        """Récupère un schéma."""
        with self._schemas_lock:
            return self._schemas.get(schema_id)
    
    async def get_schemas(self) -> List[TableSchema]:
        """Récupère les schémas."""
        with self._schemas_lock:
            return list(self._schemas.values())
    
    async def drop_table(self, table_name: str, schema: str = "public") -> bool:
        """Supprime une table."""
        try:
            query = f"DROP TABLE IF EXISTS {schema}.{table_name}"
            result = await self.execute(query)
            return not result.error
        except Exception as e:
            logger.error(f"Drop table error: {e}")
            return False
    
    async def vacuum(self, table_name: Optional[str] = None) -> bool:
        """Exécute VACUUM sur une table."""
        try:
            query = f"VACUUM {'ANALYZE' if table_name else ''} {table_name if table_name else ''}"
            result = await self.execute(query)
            return not result.error
        except Exception as e:
            logger.error(f"Vacuum error: {e}")
            return False
    
    async def analyze(self, table_name: Optional[str] = None) -> bool:
        """Exécute ANALYZE sur une table."""
        try:
            query = f"ANALYZE {table_name if table_name else ''}"
            result = await self.execute(query)
            return not result.error
        except Exception as e:
            logger.error(f"Analyze error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._query_cache)
        
        return self._stats.copy()


# ============== QUERY BUILDER ==============

class QueryBuilder:
    """
    Constructeur de requêtes SQL.
    Facilite la création de requêtes SQL complexes.
    """
    
    def __init__(self):
        self._select = []
        self._from = ""
        self._where = []
        self._group_by = []
        self._having = []
        self._order_by = []
        self._limit = 0
        self._offset = 0
        self._params = {}
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """Ajoute une clause SELECT."""
        self._select.extend(columns)
        return self
    
    def from_table(self, table: str, schema: str = "public") -> 'QueryBuilder':
        """Ajoute une clause FROM."""
        self._from = f"{schema}.{table}"
        return self
    
    def where(self, condition: str, params: Optional[Dict] = None) -> 'QueryBuilder':
        """Ajoute une clause WHERE."""
        self._where.append(condition)
        if params:
            self._params.update(params)
        return self
    
    def group_by(self, *columns: str) -> 'QueryBuilder':
        """Ajoute une clause GROUP BY."""
        self._group_by.extend(columns)
        return self
    
    def having(self, condition: str) -> 'QueryBuilder':
        """Ajoute une clause HAVING."""
        self._having.append(condition)
        return self
    
    def order_by(self, column: str, direction: str = "ASC") -> 'QueryBuilder':
        """Ajoute une clause ORDER BY."""
        self._order_by.append(f"{column} {direction}")
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """Ajoute une clause LIMIT."""
        self._limit = limit
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """Ajoute une clause OFFSET."""
        self._offset = offset
        return self
    
    def build(self) -> Tuple[str, Dict]:
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
        
        # OFFSET
        if self._offset > 0:
            parts.append(f"OFFSET {self._offset}")
        
        return "\n".join(parts), self._params


# ============== FACTORY ==============

class PostgreSQLFactory:
    """Factory pour créer des composants PostgreSQL."""
    
    @staticmethod
    async def create_engine(
        config: DatabaseConfig,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config_override: Optional[Dict[str, Any]] = None
    ) -> PostgreSQLEngine:
        """Crée un moteur PostgreSQL."""
        engine = PostgreSQLEngine(
            config=config,
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config_override=config_override
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_query_builder() -> QueryBuilder:
        """Crée un constructeur de requêtes."""
        return QueryBuilder()


# ============== EXPORT ==============

__all__ = [
    "IsolationLevel",
    "LockType",
    "TableSchema",
    "QueryResult",
    "DatabaseConfig",
    "PostgreSQLEngineInterface",
    "PostgreSQLEngine",
    "QueryBuilder",
    "PostgreSQLFactory"
]
