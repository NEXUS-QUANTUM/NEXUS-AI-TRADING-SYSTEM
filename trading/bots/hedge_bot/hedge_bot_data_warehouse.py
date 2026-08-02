# trading/bots/hedge_bot/hedge_bot_data_warehouse.py

import asyncio
import logging
import time
import json
import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import pandas as pd
import numpy as np

try:
    import sqlalchemy
    from sqlalchemy import create_engine, Table, Column, MetaData, Integer, String, Float, DateTime, Boolean, Text, inspect
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

logger = logging.getLogger(__name__)


class WarehouseType(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    DUCKDB = "duckdb"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    CLICKHOUSE = "clickhouse"
    TIMESCALE = "timescale"


class StorageType(str, Enum):
    ROW = "row"
    COLUMN = "column"
    HYBRID = "hybrid"
    IN_MEMORY = "in_memory"


class CompressionType(str, Enum):
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    LZ4 = "lz4"
    ZSTD = "zstd"
    DELTA = "delta"


@dataclass
class WarehouseConfig:
    id: str
    name: str
    type: WarehouseType
    connection_string: str
    storage_type: StorageType = StorageType.ROW
    compression: CompressionType = CompressionType.NONE
    max_connections: int = 10
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WarehouseTable:
    id: str
    warehouse_id: str
    name: str
    schema: Dict[str, str]
    row_count: int
    size: int
    created_at: float
    updated_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WarehouseQuery:
    id: str
    warehouse_id: str
    query: str
    parameters: Dict[str, Any]
    result: Optional[pd.DataFrame] = None
    execution_time: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WarehouseJob:
    id: str
    name: str
    warehouse_id: str
    query_ids: List[str]
    status: str
    created_at: float
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataWarehouseManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._warehouses: Dict[str, WarehouseConfig] = {}
        self._tables: Dict[str, Dict[str, WarehouseTable]] = defaultdict(dict)
        self._queries: Dict[str, WarehouseQuery] = {}
        self._jobs: Dict[str, WarehouseJob] = {}
        self._engines: Dict[str, Any] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_warehouses()

    def _initialize_default_warehouses(self) -> None:
        default_warehouses = [
            WarehouseConfig(
                id="default",
                name="Default SQLite",
                type=WarehouseType.SQLITE,
                connection_string="sqlite:///nexus_warehouse.db",
                storage_type=StorageType.ROW
            )
        ]
        
        for warehouse in default_warehouses:
            self._warehouses[warehouse.id] = warehouse
            self._connect_warehouse(warehouse)

    def _connect_warehouse(self, config: WarehouseConfig) -> None:
        if not SQLALCHEMY_AVAILABLE:
            return
        
        try:
            engine = create_engine(config.connection_string, pool_size=config.max_connections)
            self._engines[config.id] = engine
            logger.info(f"Connected to warehouse: {config.name}")
        except Exception as e:
            logger.error(f"Failed to connect to warehouse {config.name}: {e}")

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_warehouse(
        self,
        name: str,
        type: WarehouseType,
        connection_string: str,
        storage_type: StorageType = StorageType.ROW,
        compression: CompressionType = CompressionType.NONE,
        max_connections: int = 10,
        timeout: int = 30,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WarehouseConfig:
        async with self._lock:
            warehouse_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = WarehouseConfig(
                id=warehouse_id,
                name=name,
                type=type,
                connection_string=connection_string,
                storage_type=storage_type,
                compression=compression,
                max_connections=max_connections,
                timeout=timeout,
                metadata=metadata or {}
            )
            
            self._warehouses[warehouse_id] = config
            self._connect_warehouse(config)
            await self._notify_observers("warehouse_added", config)
            return config

    async def create_table(
        self,
        warehouse_id: str,
        table_name: str,
        schema: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[WarehouseTable]:
        async with self._lock:
            if warehouse_id not in self._warehouses:
                return None
            
            if warehouse_id not in self._engines:
                return None
            
            engine = self._engines[warehouse_id]
            metadata_obj = MetaData()
            
            columns = []
            for col_name, col_type in schema.items():
                col_type_map = {
                    "int": Integer,
                    "float": Float,
                    "string": String,
                    "text": Text,
                    "datetime": DateTime,
                    "bool": Boolean
                }
                sql_type = col_type_map.get(col_type, String)
                columns.append(Column(col_name, sql_type))
            
            table = Table(table_name, metadata_obj, *columns)
            
            try:
                table.create(engine, checkfirst=True)
            except Exception as e:
                logger.error(f"Error creating table: {e}")
                return None
            
            table_id = hashlib.md5(f"{warehouse_id}_{table_name}_{time.time()}".encode()).hexdigest()
            
            warehouse_table = WarehouseTable(
                id=table_id,
                warehouse_id=warehouse_id,
                name=table_name,
                schema=schema,
                row_count=0,
                size=0,
                created_at=time.time(),
                updated_at=time.time(),
                metadata=metadata or {}
            )
            
            self._tables[warehouse_id][table_name] = warehouse_table
            await self._notify_observers("table_created", warehouse_table)
            return warehouse_table

    async def insert_data(
        self,
        warehouse_id: str,
        table_name: str,
        data: Union[pd.DataFrame, List[Dict], Dict]
    ) -> Optional[int]:
        async with self._lock:
            if warehouse_id not in self._warehouses:
                return None
            
            if warehouse_id not in self._engines:
                return None
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                df = data
            else:
                return None
            
            engine = self._engines[warehouse_id]
            
            try:
                df.to_sql(table_name, engine, if_exists='append', index=False)
                
                if table_name in self._tables[warehouse_id]:
                    self._tables[warehouse_id][table_name].row_count += len(df)
                    self._tables[warehouse_id][table_name].updated_at = time.time()
                
                await self._notify_observers("data_inserted", warehouse_id, table_name, len(df))
                return len(df)
                
            except Exception as e:
                logger.error(f"Error inserting data: {e}")
                return None

    async def query(
        self,
        warehouse_id: str,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[WarehouseQuery]:
        async with self._lock:
            if warehouse_id not in self._warehouses:
                return None
            
            if warehouse_id not in self._engines:
                return None
            
            engine = self._engines[warehouse_id]
            
            query_id = hashlib.md5(f"{warehouse_id}_{query}_{time.time()}".encode()).hexdigest()
            
            warehouse_query = WarehouseQuery(
                id=query_id,
                warehouse_id=warehouse_id,
                query=query,
                parameters=parameters or {}
            )
            
            start_time = time.time()
            
            try:
                result = pd.read_sql(query, engine, params=parameters)
                warehouse_query.result = result
                warehouse_query.execution_time = time.time() - start_time
                
                self._queries[query_id] = warehouse_query
                await self._notify_observers("query_completed", warehouse_query)
                return warehouse_query
                
            except Exception as e:
                logger.error(f"Error executing query: {e}")
                return None

    async def execute_batch(
        self,
        warehouse_id: str,
        queries: List[str],
        parameters: Optional[List[Dict[str, Any]]] = None
    ) -> List[WarehouseQuery]:
        results = []
        
        for i, query in enumerate(queries):
            params = parameters[i] if parameters and i < len(parameters) else {}
            result = await self.query(warehouse_id, query, params)
            if result:
                results.append(result)
        
        return results

    async def create_job(
        self,
        name: str,
        warehouse_id: str,
        query_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> WarehouseJob:
        async with self._lock:
            job_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            job = WarehouseJob(
                id=job_id,
                name=name,
                warehouse_id=warehouse_id,
                query_ids=query_ids,
                status="pending",
                created_at=time.time(),
                metadata=metadata or {}
            )
            
            self._jobs[job_id] = job
            await self._notify_observers("job_created", job)
            return job

    async def execute_job(self, job_id: str) -> Optional[WarehouseJob]:
        async with self._lock:
            if job_id not in self._jobs:
                return None
            
            job = self._jobs[job_id]
            job.status = "running"
            
            try:
                for query_id in job.query_ids:
                    if query_id in self._queries:
                        await self.query(job.warehouse_id, self._queries[query_id].query)
                
                job.status = "completed"
                job.completed_at = time.time()
                await self._notify_observers("job_completed", job)
                
            except Exception as e:
                job.status = "failed"
                job.metadata["error"] = str(e)
                await self._notify_observers("job_failed", job)
            
            return job

    async def get_table(
        self,
        warehouse_id: str,
        table_name: str
    ) -> Optional[WarehouseTable]:
        if warehouse_id in self._tables:
            return self._tables[warehouse_id].get(table_name)
        return None

    async def get_tables(self, warehouse_id: str) -> List[WarehouseTable]:
        if warehouse_id in self._tables:
            return list(self._tables[warehouse_id].values())
        return []

    async def get_all_tables(self) -> Dict[str, List[WarehouseTable]]:
        result = {}
        for warehouse_id, tables in self._tables.items():
            result[warehouse_id] = list(tables.values())
        return result

    async def get_query(self, query_id: str) -> Optional[WarehouseQuery]:
        return self._queries.get(query_id)

    async def get_queries(
        self,
        warehouse_id: Optional[str] = None,
        limit: int = 100
    ) -> List[WarehouseQuery]:
        queries = list(self._queries.values())
        
        if warehouse_id:
            queries = [q for q in queries if q.warehouse_id == warehouse_id]
        
        queries.sort(key=lambda q: q.created_at, reverse=True)
        return queries[:limit]

    async def get_job(self, job_id: str) -> Optional[WarehouseJob]:
        return self._jobs.get(job_id)

    async def get_jobs(
        self,
        warehouse_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[WarehouseJob]:
        jobs = list(self._jobs.values())
        
        if warehouse_id:
            jobs = [j for j in jobs if j.warehouse_id == warehouse_id]
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def delete_table(
        self,
        warehouse_id: str,
        table_name: str
    ) -> bool:
        async with self._lock:
            if warehouse_id not in self._engines:
                return False
            
            engine = self._engines[warehouse_id]
            
            try:
                table = Table(table_name, MetaData(), autoload_with=engine)
                table.drop(engine)
                
                if warehouse_id in self._tables:
                    self._tables[warehouse_id].pop(table_name, None)
                
                return True
                
            except Exception as e:
                logger.error(f"Error deleting table: {e}")
                return False

    async def vacuum(self, warehouse_id: str) -> bool:
        async with self._lock:
            if warehouse_id not in self._engines:
                return False
            
            engine = self._engines[warehouse_id]
            
            try:
                if warehouse_id in self._warehouses:
                    warehouse = self._warehouses[warehouse_id]
                    if warehouse.type == WarehouseType.SQLITE:
                        with engine.connect() as conn:
                            conn.execute("VACUUM")
                    elif warehouse.type == WarehouseType.POSTGRES:
                        with engine.connect() as conn:
                            conn.execute("VACUUM ANALYZE")
                    elif warehouse.type == WarehouseType.MYSQL:
                        with engine.connect() as conn:
                            conn.execute("OPTIMIZE TABLE")
                
                return True
                
            except Exception as e:
                logger.error(f"Error vacuuming warehouse: {e}")
                return False

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        total_tables = sum(len(tables) for tables in self._tables.values())
        total_queries = len(self._queries)
        total_jobs = len(self._jobs)
        
        return {
            "warehouses": len(self._warehouses),
            "tables": total_tables,
            "queries": total_queries,
            "jobs": total_jobs,
            "running": self._running
        }


__all__ = [
    "WarehouseType",
    "StorageType",
    "CompressionType",
    "WarehouseConfig",
    "WarehouseTable",
    "WarehouseQuery",
    "WarehouseJob",
    "DataWarehouseManager"
]
