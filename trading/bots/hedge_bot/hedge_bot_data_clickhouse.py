# trading/bots/hedge_bot/hedge_bot_data_clickhouse.py
# NEXUS AI TRADING SYSTEM - Hedge Bot ClickHouse Integration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot ClickHouse Integration Module

This module provides comprehensive ClickHouse database integration for the
NEXUS Hedge Bot system. It handles data storage, querying, and analytics
using ClickHouse as the time-series database.

The module covers:
- ClickHouse Connection Management
- Table Management
- Data Insertion
- Data Querying
- Time-Series Analytics
- Aggregation Queries
- Materialized Views
- Data Partitioning
- Performance Optimization
"""

import os
import sys
import json
import logging
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

# Try to import ClickHouse driver
try:
    from clickhouse_driver import Client
    HAS_CLICKHOUSE = True
except ImportError:
    HAS_CLICKHOUSE = False

logger = logging.getLogger(__name__)


# ============================================================
# CLICKHOUSE ENUMS
# ============================================================

class TableEngine(Enum):
    """ClickHouse table engines"""
    MERGE_TREE = "MergeTree"
    REPLICATED_MERGE_TREE = "ReplicatedMergeTree"
    AGGREGATING_MERGE_TREE = "AggregatingMergeTree"
    SUMMING_MERGE_TREE = "SummingMergeTree"
    DISTRIBUTED = "Distributed"


class OrderByType(Enum):
    """Order by types"""
    TIMESTAMP = "timestamp"
    SYMBOL = "symbol"
    COMPOSITE = "composite"


@dataclass
class ClickHouseConfig:
    """ClickHouse configuration"""
    host: str = "localhost"
    port: int = 9000
    user: str = "default"
    password: str = ""
    database: str = "nexus_trading"
    secure: bool = False
    timeout: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "secure": self.secure,
            "timeout": self.timeout,
        }


@dataclass
class TableSchema:
    """Table schema definition"""
    name: str
    engine: TableEngine
    columns: List[Dict[str, str]]
    order_by: List[str]
    partition_by: Optional[str] = None
    sample_by: Optional[str] = None
    ttl: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "engine": self.engine.value,
            "columns": self.columns,
            "order_by": self.order_by,
            "partition_by": self.partition_by,
            "sample_by": self.sample_by,
            "ttl": self.ttl,
        }


# ============================================================
# CLICKHOUSE ENGINE
# ============================================================

class ClickHouseEngine:
    """
    Comprehensive ClickHouse integration engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ClickHouse engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_CLICKHOUSE:
            logger.warning("ClickHouse driver not installed")
        
        # Load configuration
        self.clickhouse_config = ClickHouseConfig(
            host=self.config.get("host", "localhost"),
            port=self.config.get("port", 9000),
            user=self.config.get("user", "default"),
            password=self.config.get("password", ""),
            database=self.config.get("database", "nexus_trading"),
            secure=self.config.get("secure", False),
            timeout=self.config.get("timeout", 30),
        )
        
        # Client
        self.client = None
        
        # Connect
        self._connect()
        
        # Initialize tables
        self._init_tables()
        
        logger.info("ClickHouse engine initialized")
    
    # ============================================================
    # CONNECTION MANAGEMENT
    # ============================================================
    
    def _connect(self) -> None:
        """Connect to ClickHouse"""
        if not HAS_CLICKHOUSE:
            return
        
        try:
            self.client = Client(
                host=self.clickhouse_config.host,
                port=self.clickhouse_config.port,
                user=self.clickhouse_config.user,
                password=self.clickhouse_config.password,
                database=self.clickhouse_config.database,
                secure=self.clickhouse_config.secure,
                connect_timeout=self.clickhouse_config.timeout,
            )
            self.client.execute("SELECT 1")
            logger.info("Connected to ClickHouse")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check connection status"""
        if not self.client:
            return False
        try:
            self.client.execute("SELECT 1")
            return True
        except:
            return False
    
    def reconnect(self) -> bool:
        """Reconnect to ClickHouse"""
        self._connect()
        return self.is_connected()
    
    # ============================================================
    # TABLE MANAGEMENT
    # ============================================================
    
    def _init_tables(self) -> None:
        """Initialize default tables"""
        if not self.is_connected():
            return
        
        # Create database if not exists
        self.client.execute(f"CREATE DATABASE IF NOT EXISTS {self.clickhouse_config.database}")
        
        # Trades table
        trades_schema = TableSchema(
            name="trades",
            engine=TableEngine.MERGE_TREE,
            columns=[
                {"name": "trade_id", "type": "String"},
                {"name": "symbol", "type": "String"},
                {"name": "side", "type": "String"},
                {"name": "quantity", "type": "Float64"},
                {"name": "price", "type": "Float64"},
                {"name": "fee", "type": "Float64"},
                {"name": "pnl", "type": "Float64"},
                {"name": "timestamp", "type": "DateTime64(3)"},
            ],
            order_by=["timestamp", "symbol"],
            partition_by="toYYYYMM(timestamp)",
        )
        self.create_table(trades_schema)
        
        # Market data table
        market_data_schema = TableSchema(
            name="market_data",
            engine=TableEngine.MERGE_TREE,
            columns=[
                {"name": "symbol", "type": "String"},
                {"name": "open", "type": "Float64"},
                {"name": "high", "type": "Float64"},
                {"name": "low", "type": "Float64"},
                {"name": "close", "type": "Float64"},
                {"name": "volume", "type": "Float64"},
                {"name": "timestamp", "type": "DateTime64(3)"},
            ],
            order_by=["timestamp", "symbol"],
            partition_by="toYYYYMM(timestamp)",
        )
        self.create_table(market_data_schema)
        
        # Positions table
        positions_schema = TableSchema(
            name="positions",
            engine=TableEngine.MERGE_TREE,
            columns=[
                {"name": "position_id", "type": "String"},
                {"name": "symbol", "type": "String"},
                {"name": "side", "type": "String"},
                {"name": "quantity", "type": "Float64"},
                {"name": "entry_price", "type": "Float64"},
                {"name": "current_price", "type": "Float64"},
                {"name": "unrealized_pnl", "type": "Float64"},
                {"name": "status", "type": "String"},
                {"name": "timestamp", "type": "DateTime64(3)"},
            ],
            order_by=["timestamp", "symbol"],
            partition_by="toYYYYMM(timestamp)",
        )
        self.create_table(positions_schema)
        
        logger.info("Tables initialized")
    
    def create_table(self, schema: TableSchema) -> bool:
        """
        Create a table
        
        Args:
            schema: Table schema
            
        Returns:
            True if created
        """
        if not self.is_connected():
            return False
        
        try:
            # Build column definitions
            columns = [f"{col['name']} {col['type']}" for col in schema.columns]
            
            # Build CREATE TABLE statement
            query = f"""
            CREATE TABLE IF NOT EXISTS {schema.name} (
                {', '.join(columns)}
            ) ENGINE = {schema.engine.value}
            ORDER BY ({', '.join(schema.order_by)})
            """
            
            if schema.partition_by:
                query += f" PARTITION BY {schema.partition_by}"
            
            if schema.ttl:
                query += f" TTL {schema.ttl}"
            
            self.client.execute(query)
            logger.info(f"Table created: {schema.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            return False
    
    def drop_table(self, table_name: str) -> bool:
        """
        Drop a table
        
        Args:
            table_name: Table name
            
        Returns:
            True if dropped
        """
        if not self.is_connected():
            return False
        
        try:
            self.client.execute(f"DROP TABLE IF EXISTS {table_name}")
            logger.info(f"Table dropped: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop table: {e}")
            return False
    
    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get table information
        
        Args:
            table_name: Table name
            
        Returns:
            Table info or None
        """
        if not self.is_connected():
            return None
        
        try:
            result = self.client.execute(f"DESCRIBE TABLE {table_name}")
            return {
                "columns": [{"name": r[0], "type": r[1]} for r in result],
                "table_name": table_name,
            }
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return None
    
    # ============================================================
    # DATA OPERATIONS
    # ============================================================
    
    def insert_data(
        self,
        table_name: str,
        data: pd.DataFrame,
        batch_size: int = 10000
    ) -> int:
        """
        Insert data into table
        
        Args:
            table_name: Table name
            data: DataFrame to insert
            batch_size: Batch size
            
        Returns:
            Number of rows inserted
        """
        if not self.is_connected():
            return 0
        
        if data.empty:
            return 0
        
        try:
            # Convert to list of tuples
            rows = data.values.tolist()
            columns = data.columns.tolist()
            
            # Insert in batches
            total_inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                self.client.execute(
                    f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES",
                    batch,
                    types_check=True,
                )
                total_inserted += len(batch)
            
            logger.info(f"Inserted {total_inserted} rows into {table_name}")
            return total_inserted
            
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            return 0
    
    def query_data(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Query data
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            DataFrame with results
        """
        if not self.is_connected():
            return pd.DataFrame()
        
        try:
            result = self.client.execute(query, params or {})
            if not result:
                return pd.DataFrame()
            
            # Get column names from query
            # Parse column names
            import re
            columns = re.findall(r'SELECT (.+?) FROM', query, re.IGNORECASE)
            if columns:
                col_names = [c.strip().split(' as ')[-1].split()[-1] for c in columns[0].split(',')]
            else:
                # Try to get from result
                col_names = [f"col_{i}" for i in range(len(result[0]))]
            
            return pd.DataFrame(result, columns=col_names)
            
        except Exception as e:
            logger.error(f"Failed to query data: {e}")
            return pd.DataFrame()
    
    def execute_query(self, query: str) -> bool:
        """
        Execute a query
        
        Args:
            query: SQL query
            
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        try:
            self.client.execute(query)
            return True
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return False
    
    # ============================================================
    # TIME-SERIES ANALYTICS
    # ============================================================
    
    def get_time_series(
        self,
        table_name: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        fields: List[str],
        interval: str = "1h"
    ) -> pd.DataFrame:
        """
        Get time-series data
        
        Args:
            table_name: Table name
            symbol: Symbol to query
            start_time: Start time
            end_time: End time
            fields: Fields to select
            interval: Time interval
            
        Returns:
            DataFrame with time-series data
        """
        query = f"""
        SELECT 
            toStartOfInterval(timestamp, INTERVAL {interval}) as time,
            {', '.join([f'avg({f}) as {f}' for f in fields])}
        FROM {table_name}
        WHERE symbol = '{symbol}'
            AND timestamp >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
            AND timestamp <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
        GROUP BY time
        ORDER BY time
        """
        
        return self.query_data(query)
    
    def get_aggregated_data(
        self,
        table_name: str,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        aggregations: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Get aggregated data
        
        Args:
            table_name: Table name
            symbol: Symbol to query
            start_time: Start time
            end_time: End time
            aggregations: Aggregation functions
            
        Returns:
            Aggregated results
        """
        agg_parts = [f"{func}({field}) as {field}_{func}" for field, func in aggregations.items()]
        
        query = f"""
        SELECT 
            {', '.join(agg_parts)}
        FROM {table_name}
        WHERE symbol = '{symbol}'
            AND timestamp >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
            AND timestamp <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
        """
        
        result = self.query_data(query)
        if result.empty:
            return {}
        
        return result.iloc[0].to_dict()
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get ClickHouse statistics
        
        Returns:
            Statistics dictionary
        """
        if not self.is_connected():
            return {"connected": False}
        
        try:
            tables = self.client.execute("SHOW TABLES")
            table_count = len(tables)
            
            return {
                "connected": True,
                "database": self.clickhouse_config.database,
                "table_count": table_count,
                "tables": [t[0] for t in tables],
                "host": self.clickhouse_config.host,
                "port": self.clickhouse_config.port,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "TableEngine",
    "OrderByType",
    
    # Dataclasses
    "ClickHouseConfig",
    "TableSchema",
    
    # Classes
    "ClickHouseEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
