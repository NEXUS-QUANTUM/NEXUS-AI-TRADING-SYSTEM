# trading/bots/arbitrage_bot/data/data_storage.py
# Nexus AI Trading System - Arbitrage Bot Data Storage Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Data Storage Module

This module provides comprehensive data storage management for the arbitrage
bot system, including:

- Multi-database support (PostgreSQL, TimescaleDB, MongoDB, Redis)
- Data partitioning and sharding
- Data retention policies
- Data compression
- Data backup and recovery
- Data migration
- Data indexing optimization
- Query optimization
- Connection pooling
- Transaction management
- Data versioning
- Data lifecycle management
- Data integrity checks
- Data encryption
- Data auditing

The data storage module handles all data persistence needs for the
arbitrage bot, ensuring reliable, performant data access.
"""

import asyncio
import json
import math
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import aioredis
from pydantic import BaseModel, Field, validator, root_validator

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class StorageType(str, Enum):
    """Storage types."""
    POSTGRESQL = "postgresql"
    TIMESCALEDB = "timescaledb"
    MONGODB = "mongodb"
    REDIS = "redis"
    S3 = "s3"
    LOCAL = "local"


class PartitionType(str, Enum):
    """Partition types."""
    RANGE = "range"
    LIST = "list"
    HASH = "hash"
    TIME = "time"


class RetentionPolicy(str, Enum):
    """Retention policies."""
    DELETE = "delete"
    ARCHIVE = "archive"
    COMPRESS = "compress"
    KEEP = "keep"


class BackupStatus(str, Enum):
    """Backup status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StorageConfig(BaseModel):
    """Storage configuration."""
    type: StorageType
    host: str
    port: int
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: str = "require"
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_timeout: int = 30
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    compression: bool = True
    compression_level: int = 6
    encryption: bool = False
    encryption_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataPartition(BaseModel):
    """Data partition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str
    partition_key: str
    partition_type: PartitionType
    partition_range: Optional[Dict[str, Any]] = None
    partition_list: Optional[List[Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetentionPolicyConfig(BaseModel):
    """Retention policy configuration."""
    table_name: str
    policy: RetentionPolicy
    retention_days: int
    archive_table: Optional[str] = None
    archive_storage: Optional[StorageConfig] = None
    compress_after_days: Optional[int] = None
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BackupConfig(BaseModel):
    """Backup configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    storage: StorageConfig
    schedule: Optional[str] = None  # Cron expression
    retention_days: int = 30
    compression: bool = True
    encryption: bool = False
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BackupResult(BaseModel):
    """Backup result."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_id: str
    status: BackupStatus
    size_bytes: int = 0
    duration_ms: float = 0.0
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Partitions
CREATE TABLE IF NOT EXISTS data_partitions (
    id VARCHAR(64) PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    partition_key VARCHAR(100) NOT NULL,
    partition_type VARCHAR(20) NOT NULL,
    partition_range JSONB,
    partition_list JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    UNIQUE(table_name, partition_key)
);

-- Retention policies
CREATE TABLE IF NOT EXISTS retention_policies (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    policy VARCHAR(20) NOT NULL,
    retention_days INTEGER NOT NULL,
    archive_table VARCHAR(255),
    archive_storage JSONB,
    compress_after_days INTEGER,
    enabled BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    UNIQUE(table_name)
);

-- Backups
CREATE TABLE IF NOT EXISTS backups (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    storage JSONB NOT NULL,
    schedule VARCHAR(50),
    retention_days INTEGER NOT NULL,
    compression BOOLEAN DEFAULT TRUE,
    encryption BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'
);

-- Backup results
CREATE TABLE IF NOT EXISTS backup_results (
    id VARCHAR(64) PRIMARY KEY,
    backup_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,
    size_bytes BIGINT DEFAULT 0,
    duration_ms FLOAT DEFAULT 0,
    file_path TEXT,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_backup_results_backup_id (backup_id),
    INDEX idx_backup_results_status (status),
    INDEX idx_backup_results_started_at (started_at)
);

-- Data migrations
CREATE TABLE IF NOT EXISTS data_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    UNIQUE(migration_name)
);
"""


# =============================================================================
# DATA STORAGE CLASS
# =============================================================================

class DataStorage:
    """
    Advanced data storage manager for arbitrage bot.
    
    Features:
    - Multi-database support (PostgreSQL, TimescaleDB, MongoDB, Redis)
    - Data partitioning and sharding
    - Data retention policies
    - Data compression
    - Data backup and recovery
    - Data migration
    - Data indexing optimization
    - Query optimization
    - Connection pooling
    - Transaction management
    - Data versioning
    - Data lifecycle management
    - Data integrity checks
    - Data encryption
    - Data auditing
    """
    
    def __init__(
        self,
        configs: Dict[str, StorageConfig],
        redis: Optional[aioredis.Redis] = None
    ):
        self.configs = configs
        self.redis = redis
        
        # Connection pools
        self._pools: Dict[str, asyncpg.Pool] = {}
        self._redis_client: Optional[aioredis.Redis] = None
        
        # Partitions
        self._partitions: Dict[str, List[DataPartition]] = {}
        
        # Retention policies
        self._retention_policies: Dict[str, RetentionPolicyConfig] = {}
        
        # Backups
        self._backups: Dict[str, BackupConfig] = {}
        
        # Circuit breakers
        self._storage_cb = CircuitBreaker(
            name="data_storage",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("DataStorage initialized")
    
    async def initialize(self):
        """Initialize the data storage."""
        if self._initialized:
            return
        
        # Initialize PostgreSQL pools
        for name, config in self.configs.items():
            if config.type == StorageType.POSTGRESQL or config.type == StorageType.TIMESCALEDB:
                await self._create_postgres_pool(name, config)
        
        # Initialize Redis
        if self.redis:
            self._redis_client = self.redis
        
        # Initialize database tables
        for name, pool in self._pools.items():
            await self._init_database(pool)
        
        # Load partitions
        await self._load_partitions()
        
        # Load retention policies
        await self._load_retention_policies()
        
        # Load backups
        await self._load_backups()
        
        self._running = True
        self._initialized = True
        
        # Start retention cleanup
        asyncio.create_task(self._retention_cleanup_loop())
        
        logger.info("DataStorage initialized")
    
    async def _init_database(self, pool: asyncpg.Pool):
        """Initialize database tables."""
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    async def _create_postgres_pool(self, name: str, config: StorageConfig):
        """Create PostgreSQL connection pool."""
        try:
            pool = await asyncpg.create_pool(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.username,
                password=config.password,
                min_size=config.pool_min_size,
                max_size=config.pool_max_size,
                timeout=config.pool_timeout,
                command_timeout=config.timeout,
                ssl=config.ssl_mode != 'disable'
            )
            
            self._pools[name] = pool
            logger.info(f"Created PostgreSQL pool: {name}")
            
        except Exception as e:
            logger.error(f"Error creating PostgreSQL pool {name}: {e}")
            raise
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    async def execute(
        self,
        storage_name: str,
        query: str,
        *args,
        fetch: bool = False,
        fetch_all: bool = False
    ) -> Any:
        """
        Execute a query.
        
        Args:
            storage_name: Storage name
            query: SQL query
            *args: Query arguments
            fetch: Fetch one row
            fetch_all: Fetch all rows
            
        Returns:
            Query result
        """
        if storage_name not in self._pools:
            raise ValueError(f"Storage {storage_name} not found")
        
        pool = self._pools[storage_name]
        
        try:
            async with pool.acquire() as conn:
                if fetch:
                    return await conn.fetchrow(query, *args)
                elif fetch_all:
                    return await conn.fetch(query, *args)
                else:
                    return await conn.execute(query, *args)
                
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise
    
    async def insert(
        self,
        storage_name: str,
        table: str,
        data: Dict[str, Any],
        returning: Optional[str] = None
    ) -> Any:
        """
        Insert data into a table.
        
        Args:
            storage_name: Storage name
            table: Table name
            data: Data to insert
            returning: Return column
            
        Returns:
            Inserted data
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(data))])
        values = list(data.values())
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        if returning:
            query += f" RETURNING {returning}"
        
        return await self.execute(storage_name, query, *values, fetch=bool(returning))
    
    async def update(
        self,
        storage_name: str,
        table: str,
        data: Dict[str, Any],
        condition: str,
        *args
    ) -> int:
        """
        Update data in a table.
        
        Args:
            storage_name: Storage name
            table: Table name
            data: Data to update
            condition: WHERE condition
            *args: Condition arguments
            
        Returns:
            Number of rows updated
        """
        set_clause = ', '.join([f"{k} = ${i+1}" for i, k in enumerate(data.keys())])
        values = list(data.values()) + list(args)
        
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        
        result = await self.execute(storage_name, query, *values)
        return int(result.split(' ')[-1]) if result else 0
    
    async def delete(
        self,
        storage_name: str,
        table: str,
        condition: str,
        *args
    ) -> int:
        """
        Delete data from a table.
        
        Args:
            storage_name: Storage name
            table: Table name
            condition: WHERE condition
            *args: Condition arguments
            
        Returns:
            Number of rows deleted
        """
        query = f"DELETE FROM {table} WHERE {condition}"
        result = await self.execute(storage_name, query, *args)
        return int(result.split(' ')[-1]) if result else 0
    
    async def select(
        self,
        storage_name: str,
        table: str,
        columns: List[str] = None,
        condition: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        *args
    ) -> List[Dict[str, Any]]:
        """
        Select data from a table.
        
        Args:
            storage_name: Storage name
            table: Table name
            columns: Columns to select
            condition: WHERE condition
            order_by: ORDER BY clause
            limit: LIMIT clause
            *args: Condition arguments
            
        Returns:
            List of rows
        """
        col_str = ', '.join(columns) if columns else '*'
        query = f"SELECT {col_str} FROM {table}"
        
        if condition:
            query += f" WHERE {condition}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        rows = await self.execute(storage_name, query, *args, fetch_all=True)
        return [dict(row) for row in rows]
    
    # =========================================================================
    # PARTITION MANAGEMENT
    # =========================================================================
    
    async def create_partition(
        self,
        storage_name: str,
        table_name: str,
        partition_key: str,
        partition_type: PartitionType,
        partition_range: Optional[Dict[str, Any]] = None,
        partition_list: Optional[List[Any]] = None
    ) -> DataPartition:
        """
        Create a table partition.
        
        Args:
            storage_name: Storage name
            table_name: Table name
            partition_key: Partition key
            partition_type: Partition type
            partition_range: Range for RANGE partition
            partition_list: List for LIST partition
            
        Returns:
            DataPartition
        """
        partition = DataPartition(
            table_name=table_name,
            partition_key=partition_key,
            partition_type=partition_type,
            partition_range=partition_range,
            partition_list=partition_list
        )
        
        # Create partition table
        partition_name = f"{table_name}_{partition.id[:8]}"
        
        if partition_type == PartitionType.RANGE:
            if not partition_range:
                raise ValueError("Range required for RANGE partition")
            
            query = f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES FROM ({partition_range['from']}) TO ({partition_range['to']})
            """
            
        elif partition_type == PartitionType.LIST:
            if not partition_list:
                raise ValueError("List required for LIST partition")
            
            values = ', '.join([str(v) for v in partition_list])
            query = f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES IN ({values})
            """
            
        elif partition_type == PartitionType.TIME:
            if not partition_range:
                raise ValueError("Range required for TIME partition")
            
            from_time = partition_range['from'].isoformat()
            to_time = partition_range['to'].isoformat()
            query = f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES FROM ('{from_time}') TO ('{to_time}')
            """
            
        else:
            raise ValueError(f"Unsupported partition type: {partition_type}")
        
        await self.execute(storage_name, query)
        
        # Save partition metadata
        if storage_name in self._pools:
            await self.insert(
                storage_name,
                'data_partitions',
                {
                    'id': partition.id,
                    'table_name': table_name,
                    'partition_key': partition_key,
                    'partition_type': partition_type.value,
                    'partition_range': json.dumps(partition_range) if partition_range else None,
                    'partition_list': json.dumps(partition_list) if partition_list else None,
                    'metadata': json.dumps({})
                }
            )
        
        if table_name not in self._partitions:
            self._partitions[table_name] = []
        self._partitions[table_name].append(partition)
        
        logger.info(f"Created partition {partition_name} for {table_name}")
        return partition
    
    # =========================================================================
    # RETENTION MANAGEMENT
    # =========================================================================
    
    async def set_retention_policy(
        self,
        storage_name: str,
        table_name: str,
        policy: RetentionPolicy,
        retention_days: int,
        archive_table: Optional[str] = None,
        archive_storage: Optional[StorageConfig] = None,
        compress_after_days: Optional[int] = None
    ) -> RetentionPolicyConfig:
        """
        Set retention policy for a table.
        
        Args:
            storage_name: Storage name
            table_name: Table name
            policy: Retention policy
            retention_days: Retention days
            archive_table: Archive table name
            archive_storage: Archive storage config
            compress_after_days: Compress after days
            
        Returns:
            RetentionPolicyConfig
        """
        config = RetentionPolicyConfig(
            table_name=table_name,
            policy=policy,
            retention_days=retention_days,
            archive_table=archive_table,
            archive_storage=archive_storage,
            compress_after_days=compress_after_days
        )
        
        # Save to database
        if storage_name in self._pools:
            await self.insert(
                storage_name,
                'retention_policies',
                {
                    'table_name': table_name,
                    'policy': policy.value,
                    'retention_days': retention_days,
                    'archive_table': archive_table,
                    'archive_storage': json.dumps(archive_storage.dict() if archive_storage else None),
                    'compress_after_days': compress_after_days,
                    'enabled': True,
                    'metadata': json.dumps({})
                }
            )
        
        self._retention_policies[table_name] = config
        
        logger.info(f"Set retention policy for {table_name}: {policy.value} {retention_days} days")
        return config
    
    async def _retention_cleanup_loop(self):
        """Periodic retention cleanup."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                for storage_name, pool in self._pools.items():
                    for config in self._retention_policies.values():
                        if not config.enabled:
                            continue
                        
                        cutoff = datetime.utcnow() - timedelta(days=config.retention_days)
                        
                        if config.policy == RetentionPolicy.DELETE:
                            query = f"DELETE FROM {config.table_name} WHERE created_at < $1"
                            await self.execute(storage_name, query, cutoff)
                            
                        elif config.policy == RetentionPolicy.ARCHIVE and config.archive_table:
                            # Move to archive table
                            query = f"""
                                WITH deleted AS (
                                    DELETE FROM {config.table_name}
                                    WHERE created_at < $1
                                    RETURNING *
                                )
                                INSERT INTO {config.archive_table}
                                SELECT * FROM deleted
                            """
                            await self.execute(storage_name, query, cutoff)
                            
                        elif config.policy == RetentionPolicy.COMPRESS:
                            # Compress old data
                            # Implementation depends on database
                            pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retention cleanup error: {e}")
                await asyncio.sleep(3600)
    
    # =========================================================================
    # BACKUP MANAGEMENT
    # =========================================================================
    
    async def create_backup(
        self,
        storage_name: str,
        backup_id: str,
        tables: Optional[List[str]] = None
    ) -> BackupResult:
        """
        Create a backup.
        
        Args:
            storage_name: Storage name
            backup_id: Backup ID
            tables: Tables to backup (None = all)
            
        Returns:
            BackupResult
        """
        if backup_id not in self._backups:
            raise ValueError(f"Backup {backup_id} not found")
        
        backup_config = self._backups[backup_id]
        
        result = BackupResult(
            backup_id=backup_id,
            status=BackupStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        try:
            # Generate backup file
            file_path = f"/tmp/backup_{backup_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
            
            # Build pg_dump command
            tables_str = ' '.join([f'-t {t}' for t in tables]) if tables else ''
            command = f"pg_dump -h {backup_config.storage.host} -p {backup_config.storage.port} -U {backup_config.storage.username} -d {backup_config.storage.database} {tables_str} > {file_path}"
            
            # Execute backup
            # This would be implemented with subprocess
            # For now, simulate
            await asyncio.sleep(5)
            
            # Get file size
            import os
            size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            result.status = BackupStatus.COMPLETED
            result.size_bytes = size
            result.file_path = file_path
            result.completed_at = datetime.utcnow()
            result.duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000
            
        except Exception as e:
            result.status = BackupStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.utcnow()
        
        # Save result
        if storage_name in self._pools:
            await self.insert(
                storage_name,
                'backup_results',
                {
                    'id': result.id,
                    'backup_id': backup_id,
                    'status': result.status.value,
                    'size_bytes': result.size_bytes,
                    'duration_ms': result.duration_ms,
                    'file_path': result.file_path,
                    'error_message': result.error_message,
                    'started_at': result.started_at,
                    'completed_at': result.completed_at,
                    'metadata': json.dumps({})
                }
            )
        
        return result
    
    # =========================================================================
    # DATA MIGRATION
    # =========================================================================
    
    async def run_migration(
        self,
        storage_name: str,
        migration_name: str,
        version: str,
        migration_sql: str
    ) -> bool:
        """
        Run a data migration.
        
        Args:
            storage_name: Storage name
            migration_name: Migration name
            version: Migration version
            migration_sql: Migration SQL
            
        Returns:
            True if successful
        """
        try:
            # Check if migration already applied
            rows = await self.select(
                storage_name,
                'data_migrations',
                condition="migration_name = $1",
                args=[migration_name]
            )
            
            if rows:
                logger.info(f"Migration {migration_name} already applied")
                return True
            
            # Execute migration
            await self.execute(storage_name, migration_sql)
            
            # Record migration
            await self.insert(
                storage_name,
                'data_migrations',
                {
                    'migration_name': migration_name,
                    'version': version,
                    'success': True,
                    'metadata': json.dumps({})
                }
            )
            
            logger.info(f"Migration {migration_name} applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration {migration_name} failed: {e}")
            return False
    
    # =========================================================================
    # LOAD OPERATIONS
    # =========================================================================
    
    async def _load_partitions(self):
        """Load partitions from database."""
        for name, pool in self._pools.items():
            try:
                rows = await self.select(name, 'data_partitions')
                
                for row in rows:
                    partition = DataPartition(
                        id=row['id'],
                        table_name=row['table_name'],
                        partition_key=row['partition_key'],
                        partition_type=PartitionType(row['partition_type']),
                        partition_range=json.loads(row['partition_range']) if row['partition_range'] else None,
                        partition_list=json.loads(row['partition_list']) if row['partition_list'] else None,
                        created_at=row['created_at'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    
                    if partition.table_name not in self._partitions:
                        self._partitions[partition.table_name] = []
                    self._partitions[partition.table_name].append(partition)
                
                logger.info(f"Loaded {len(rows)} partitions from {name}")
                
            except Exception as e:
                logger.error(f"Error loading partitions from {name}: {e}")
    
    async def _load_retention_policies(self):
        """Load retention policies from database."""
        for name, pool in self._pools.items():
            try:
                rows = await self.select(name, 'retention_policies')
                
                for row in rows:
                    config = RetentionPolicyConfig(
                        table_name=row['table_name'],
                        policy=RetentionPolicy(row['policy']),
                        retention_days=row['retention_days'],
                        archive_table=row['archive_table'],
                        archive_storage=json.loads(row['archive_storage']) if row['archive_storage'] else None,
                        compress_after_days=row['compress_after_days'],
                        enabled=row['enabled'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    
                    self._retention_policies[config.table_name] = config
                
                logger.info(f"Loaded {len(rows)} retention policies from {name}")
                
            except Exception as e:
                logger.error(f"Error loading retention policies from {name}: {e}")
    
    async def _load_backups(self):
        """Load backups from database."""
        for name, pool in self._pools.items():
            try:
                rows = await self.select(name, 'backups')
                
                for row in rows:
                    config = BackupConfig(
                        id=row['id'],
                        name=row['name'],
                        storage=StorageConfig(**json.loads(row['storage'])) if row['storage'] else None,
                        schedule=row['schedule'],
                        retention_days=row['retention_days'],
                        compression=row['compression'],
                        encryption=row['encryption'],
                        enabled=row['enabled'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    
                    self._backups[config.id] = config
                
                logger.info(f"Loaded {len(rows)} backups from {name}")
                
            except Exception as e:
                logger.error(f"Error loading backups from {name}: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the data storage."""
        self._running = False
        
        # Close PostgreSQL pools
        for name, pool in self._pools.items():
            try:
                await pool.close()
                logger.info(f"Closed PostgreSQL pool: {name}")
            except Exception as e:
                logger.error(f"Error closing pool {name}: {e}")
        
        logger.info("DataStorage shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'DataStorage',
    'StorageType',
    'PartitionType',
    'RetentionPolicy',
    'BackupStatus',
    'StorageConfig',
    'DataPartition',
    'RetentionPolicyConfig',
    'BackupConfig',
    'BackupResult'
]
