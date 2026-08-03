# trading/bots/hedge_bot/hedge_bot_data_timescaledb.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

try:
    import asyncpg
    from asyncpg import Connection, Pool, Record
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)


class TimescaleDBChunking(str, Enum):
    TIME = "time"
    HASH = "hash"
    RANGE = "range"
    HYBRID = "hybrid"


class TimescaleDBCompression(str, Enum):
    NONE = "none"
    LZ4 = "lz4"
    ZSTD = "zstd"
    DELTA = "delta"
    DELTA_LZ4 = "delta_lz4"
    DELTA_ZSTD = "delta_zstd"


@dataclass
class TimescaleDBConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "nexus_tsdb"
    user: str = "nexus"
    password: str = ""
    ssl: bool = False
    min_pool_size: int = 1
    max_pool_size: int = 10
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HypertableConfig:
    name: str
    time_column: str
    chunk_interval: str = "1 day"
    partition_column: Optional[str] = None
    partitions: int = 1
    compression: TimescaleDBCompression = TimescaleDBCompression.NONE
    retention: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimescaleDBQuery:
    id: str
    query: str
    parameters: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TimescaleDBManager:
    
    def __init__(self, config: Optional[TimescaleDBConfig] = None):
        self.config = config or TimescaleDBConfig()
        self._lock = asyncio.Lock()
        self._pool: Optional[Pool] = None
        self._hypertables: Dict[str, HypertableConfig] = {}
        self._queries: Dict[str, TimescaleDBQuery] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._connected = False
        
        self._initialize_default_hypertables()

    def _initialize_default_hypertables(self) -> None:
        default_hypertables = [
            HypertableConfig(
                name="market_data",
                time_column="timestamp",
                chunk_interval="1 hour",
                compression=TimescaleDBCompression.ZSTD,
                retention="30 days"
            ),
            HypertableConfig(
                name="trades",
                time_column="timestamp",
                chunk_interval="1 day",
                compression=TimescaleDBCompression.DELTA_ZSTD,
                retention="90 days"
            ),
            HypertableConfig(
                name="orders",
                time_column="created_at",
                chunk_interval="1 day",
                compression=TimescaleDBCompression.LZ4,
                retention="180 days"
            ),
            HypertableConfig(
                name="positions",
                time_column="created_at",
                chunk_interval="1 week",
                compression=TimescaleDBCompression.ZSTD,
                retention="365 days"
            ),
            HypertableConfig(
                name="metrics",
                time_column="timestamp",
                chunk_interval="1 hour",
                compression=TimescaleDBCompression.DELTA_LZ4,
                retention="30 days"
            )
        ]
        
        for ht in default_hypertables:
            self._hypertables[ht.name] = ht

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def connect(self) -> None:
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg not available")
        
        async with self._lock:
            if self._connected:
                return
            
            try:
                self._pool = await asyncpg.create_pool(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                    ssl=self.config.ssl,
                    min_size=self.config.min_pool_size,
                    max_size=self.config.max_pool_size,
                    timeout=self.config.timeout
                )
                
                await self._init_extensions()
                self._connected = True
                logger.info(f"Connected to TimescaleDB: {self.config.database}")
                
            except Exception as e:
                logger.error(f"Failed to connect to TimescaleDB: {e}")
                raise

    async def _init_extensions(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
            logger.info("TimescaleDB extension initialized")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False
            logger.info("Disconnected from TimescaleDB")

    async def create_hypertable(self, config: HypertableConfig) -> bool:
        async with self._lock:
            if not self._connected:
                await self.connect()
            
            try:
                async with self._pool.acquire() as conn:
                    # Create table if not exists
                    create_table = f"""
                    CREATE TABLE IF NOT EXISTS {config.name} (
                        time TIMESTAMPTZ NOT NULL,
                        {config.time_column} TIMESTAMPTZ NOT NULL,
                        data JSONB DEFAULT '{{}}'::jsonb,
                        metadata JSONB DEFAULT '{{}}'::jsonb,
                        PRIMARY KEY ({config.time_column})
                    );
                    """
                    await conn.execute(create_table)
                    
                    # Convert to hypertable
                    create_hypertable = f"""
                    SELECT create_hypertable('{config.name}', '{config.time_column}', 
                        chunk_time_interval => INTERVAL '{config.chunk_interval}');
                    """
                    await conn.execute(create_hypertable)
                    
                    # Set compression
                    if config.compression != TimescaleDBCompression.NONE:
                        compress = f"""
                        ALTER TABLE {config.name} SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = '{config.time_column}',
                            timescaledb.compress_orderby = '{config.time_column} DESC'
                        );
                        """
                        await conn.execute(compress)
                    
                    # Set retention
                    if config.retention:
                        retention = f"""
                        SELECT add_retention_policy('{config.name}', INTERVAL '{config.retention}');
                        """
                        await conn.execute(retention)
                    
                    self._hypertables[config.name] = config
                    logger.info(f"Hypertable created: {config.name}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error creating hypertable: {e}")
                return False

    async def insert_data(
        self,
        table_name: str,
        timestamp: float,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        async with self._lock:
            if not self._connected:
                await self.connect()
            
            if table_name not in self._hypertables:
                return False
            
            try:
                async with self._pool.acquire() as conn:
                    query = f"""
                    INSERT INTO {table_name} ({table_name}.time, {table_name}.data, {table_name}.metadata)
                    VALUES ($1, $2, $3)
                    """
                    await conn.execute(
                        query,
                        datetime.fromtimestamp(timestamp),
                        json.dumps(data),
                        json.dumps(metadata or {})
                    )
                    return True
                    
            except Exception as e:
                logger.error(f"Error inserting data: {e}")
                return False

    async def insert_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]]
    ) -> int:
        async with self._lock:
            if not self._connected:
                await self.connect()
            
            if table_name not in self._hypertables:
                return 0
            
            try:
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        for record in records:
                            query = f"""
                            INSERT INTO {table_name} ({table_name}.time, {table_name}.data, {table_name}.metadata)
                            VALUES ($1, $2, $3)
                            """
                            await conn.execute(
                                query,
                                datetime.fromtimestamp(record["timestamp"]),
                                json.dumps(record.get("data", {})),
                                json.dumps(record.get("metadata", {}))
                            )
                    return len(records)
                    
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")
                return 0

    async def query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Optional[TimescaleDBQuery]:
        async with self._lock:
            if not self._connected:
                await self.connect()
            
            query_id = hashlib.md5(f"{query}_{time.time()}".encode()).hexdigest()
            
            ts_query = TimescaleDBQuery(
                id=query_id,
                query=query,
                parameters=parameters or {}
            )
            
            try:
                start_time = time.time()
                
                async with self._pool.acquire() as conn:
                    result = await conn.fetch(query, *parameters.values())
                    
                ts_query.execution_time = time.time() - start_time
                ts_query.result = result
                
                self._queries[query_id] = ts_query
                await self._notify_observers("query_completed", ts_query)
                return ts_query
                
            except asyncio.TimeoutError:
                logger.error(f"Query timeout: {query}")
                return None
            except Exception as e:
                logger.error(f"Query error: {e}")
                return None

    async def get_data(
        self,
        table_name: str,
        start_time: float,
        end_time: float,
        columns: Optional[List[str]] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        if table_name not in self._hypertables:
            return []
        
        columns_str = "*" if not columns else ", ".join(columns)
        
        query = f"""
        SELECT {columns_str}
        FROM {table_name}
        WHERE time >= $1 AND time <= $2
        ORDER BY time DESC
        LIMIT $3
        """
        
        result = await self.query(
            query,
            {
                "start_time": datetime.fromtimestamp(start_time),
                "end_time": datetime.fromtimestamp(end_time),
                "limit": limit
            }
        )
        
        if result and result.result:
            return [dict(row) for row in result.result]
        
        return []

    async def aggregate(
        self,
        table_name: str,
        start_time: float,
        end_time: float,
        interval: str,
        aggregation_type: str = "avg",
        column: str = "data"
    ) -> List[Dict[str, Any]]:
        if table_name not in self._hypertables:
            return []
        
        query = f"""
        SELECT 
            time_bucket(INTERVAL '{interval}', time) AS bucket,
            {aggregation_type}({column}) AS value
        FROM {table_name}
        WHERE time >= $1 AND time <= $2
        GROUP BY bucket
        ORDER BY bucket ASC
        """
        
        result = await self.query(
            query,
            {
                "start_time": datetime.fromtimestamp(start_time),
                "end_time": datetime.fromtimestamp(end_time)
            }
        )
        
        if result and result.result:
            return [{"timestamp": row["bucket"].timestamp(), "value": row["value"]} for row in result.result]
        
        return []

    async def continuous_aggregate(
        self,
        table_name: str,
        view_name: str,
        interval: str,
        aggregation_type: str = "avg",
        column: str = "data"
    ) -> bool:
        try:
            async with self._pool.acquire() as conn:
                query = f"""
                CREATE MATERIALIZED VIEW {view_name}
                WITH (timescaledb.continuous) AS
                SELECT 
                    time_bucket(INTERVAL '{interval}', time) AS bucket,
                    {aggregation_type}({column}) AS value
                FROM {table_name}
                GROUP BY bucket;
                """
                await conn.execute(query)
                
                refresh = f"""
                SELECT add_continuous_aggregate_policy('{view_name}',
                    start_offset => INTERVAL '1 day',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '1 hour');
                """
                await conn.execute(refresh)
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating continuous aggregate: {e}")
            return False

    async def compress_chunks(self, table_name: str, older_than: str = "7 days") -> bool:
        try:
            async with self._pool.acquire() as conn:
                query = f"""
                SELECT compress_chunk(i)
                FROM show_chunks('{table_name}', older_than => INTERVAL '{older_than}') i;
                """
                await conn.execute(query)
                return True
                
        except Exception as e:
            logger.error(f"Error compressing chunks: {e}")
            return False

    async def get_chunk_info(self, table_name: str) -> List[Dict[str, Any]]:
        try:
            async with self._pool.acquire() as conn:
                query = f"""
                SELECT 
                    chunk_name,
                    range_start,
                    range_end,
                    is_compressed
                FROM chunk_info
                WHERE hypertable_name = '{table_name}';
                """
                result = await conn.fetch(query)
                return [dict(row) for row in result]
                
        except Exception as e:
            logger.error(f"Error getting chunk info: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        stats = {
            "connected": self._connected,
            "hypertables": len(self._hypertables),
            "queries": len(self._queries),
            "pool_size": self._pool.get_max_size() if self._pool else 0
        }
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetch("SELECT * FROM timescaledb_information.license")
                stats["license"] = dict(result[0]) if result else {}
                
                result = await conn.fetch("SELECT * FROM timescaledb_information.hypertable")
                stats["hypertables_info"] = [dict(row) for row in result]
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
        
        return stats

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")


__all__ = [
    "TimescaleDBChunking",
    "TimescaleDBCompression",
    "TimescaleDBConfig",
    "HypertableConfig",
    "TimescaleDBQuery",
    "TimescaleDBManager"
]
