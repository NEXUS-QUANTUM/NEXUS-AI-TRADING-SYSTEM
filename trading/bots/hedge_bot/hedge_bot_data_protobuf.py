# trading/bots/hedge_bot/hedge_bot_data_protobuf.py

import asyncio
import json
import logging
import time
import struct
import zlib
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd

try:
    import google.protobuf as pb
    from google.protobuf import (
        descriptor_pb2,
        descriptor_pool,
        message_factory,
        text_format,
        json_format,
        timestamp_pb2,
        duration_pb2,
        any_pb2,
        empty_pb2,
    )
    from google.protobuf.message import Message
    from google.protobuf.descriptor import FieldDescriptor
except ImportError:
    print("protobuf not installed. Please install: pip install protobuf")
    raise

logger = logging.getLogger(__name__)


class DataType(str, Enum):
    MARKET = "market"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    PERFORMANCE = "performance"
    SIGNAL = "signal"
    METRIC = "metric"
    ALERT = "alert"
    CONFIG = "config"
    STATE = "state"
    HISTORY = "history"
    BACKTEST = "backtest"
    ANALYTICS = "analytics"
    HEDGE = "hedge"
    BROKER = "broker"
    SYSTEM = "system"


class CompressionType(str, Enum):
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    LZ4 = "lz4"
    SNAPPY = "snappy"


class SerializationFormat(str, Enum):
    PROTOBUF = "protobuf"
    JSON = "json"
    BINARY = "binary"
    DELIMITED = "delimited"


@dataclass
class ProtobufSchema:
    name: str
    package: str = "nexus.trading"
    version: str = "1.0.0"
    messages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    enums: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ProtobufMessage:
    type: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    version: str = "1.0.0"
    correlation_id: str = ""
    source: str = "hedge_bot"
    destination: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    signature: bytes = b""


@dataclass
class ProtobufBatch:
    messages: List[ProtobufMessage]
    batch_id: str = ""
    timestamp: float = field(default_factory=time.time)
    total_size: int = 0
    compressed: bool = False
    compression_type: CompressionType = CompressionType.NONE


class ProtobufRegistry:
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._pool = descriptor_pool.DescriptorPool()
            self._factory = message_factory.MessageFactory(self._pool)
            self._messages: Dict[str, type] = {}
            self._schemas: Dict[str, ProtobufSchema] = {}
            self._descriptors: Dict[str, Any] = {}
            self._lock = asyncio.Lock()
            self._schema_version = "1.0.0"
            self._initialize_base_schemas()
    
    def _initialize_base_schemas(self) -> None:
        base_schema = ProtobufSchema(
            name="nexus_base",
            package="nexus.base",
            version="1.0.0",
            messages={
                "Timestamp": {
                    "fields": [
                        {"name": "seconds", "type": "int64", "number": 1},
                        {"name": "nanos", "type": "int32", "number": 2},
                    ]
                },
                "Decimal": {
                    "fields": [
                        {"name": "value", "type": "string", "number": 1},
                        {"name": "precision", "type": "int32", "number": 2},
                    ]
                },
                "Metadata": {
                    "fields": [
                        {"name": "key", "type": "string", "number": 1},
                        {"name": "value", "type": "string", "number": 2},
                    ]
                },
                "Price": {
                    "fields": [
                        {"name": "value", "type": "Decimal", "number": 1},
                        {"name": "currency", "type": "string", "number": 2},
                        {"name": "timestamp", "type": "Timestamp", "number": 3},
                    ]
                },
                "Amount": {
                    "fields": [
                        {"name": "value", "type": "Decimal", "number": 1},
                        {"name": "asset", "type": "string", "number": 2},
                        {"name": "timestamp", "type": "Timestamp", "number": 3},
                    ]
                },
            }
        )
        self.register_schema(base_schema)
        
        trading_schema = ProtobufSchema(
            name="nexus_trading",
            package="nexus.trading",
            version="1.0.0",
            messages={
                "MarketData": {
                    "fields": [
                        {"name": "symbol", "type": "string", "number": 1},
                        {"name": "price", "type": "Price", "number": 2},
                        {"name": "volume", "type": "Amount", "number": 3},
                        {"name": "bid", "type": "Price", "number": 4},
                        {"name": "ask", "type": "Price", "number": 5},
                        {"name": "high_24h", "type": "Price", "number": 6},
                        {"name": "low_24h", "type": "Price", "number": 7},
                        {"name": "change_24h", "type": "Decimal", "number": 8},
                        {"name": "timestamp", "type": "Timestamp", "number": 9},
                        {"name": "source", "type": "string", "number": 10},
                    ]
                },
                "Order": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "symbol", "type": "string", "number": 2},
                        {"name": "side", "type": "string", "number": 3},
                        {"name": "type", "type": "string", "number": 4},
                        {"name": "quantity", "type": "Amount", "number": 5},
                        {"name": "price", "type": "Price", "number": 6},
                        {"name": "stop_price", "type": "Price", "number": 7},
                        {"name": "status", "type": "string", "number": 8},
                        {"name": "created_at", "type": "Timestamp", "number": 9},
                        {"name": "updated_at", "type": "Timestamp", "number": 10},
                        {"name": "filled_quantity", "type": "Amount", "number": 11},
                        {"name": "filled_price", "type": "Price", "number": 12},
                        {"name": "fee", "type": "Amount", "number": 13},
                        {"name": "strategy", "type": "string", "number": 14},
                    ]
                },
                "Trade": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "order_id", "type": "string", "number": 2},
                        {"name": "symbol", "type": "string", "number": 3},
                        {"name": "side", "type": "string", "number": 4},
                        {"name": "quantity", "type": "Amount", "number": 5},
                        {"name": "price", "type": "Price", "number": 6},
                        {"name": "fee", "type": "Amount", "number": 7},
                        {"name": "pnl", "type": "Amount", "number": 8},
                        {"name": "timestamp", "type": "Timestamp", "number": 9},
                        {"name": "strategy", "type": "string", "number": 10},
                    ]
                },
                "Position": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "symbol", "type": "string", "number": 2},
                        {"name": "size", "type": "Amount", "number": 3},
                        {"name": "entry_price", "type": "Price", "number": 4},
                        {"name": "current_price", "type": "Price", "number": 5},
                        {"name": "unrealized_pnl", "type": "Amount", "number": 6},
                        {"name": "realized_pnl", "type": "Amount", "number": 7},
                        {"name": "liquidation_price", "type": "Price", "number": 8},
                        {"name": "margin", "type": "Amount", "number": 9},
                        {"name": "leverage", "type": "Decimal", "number": 10},
                        {"name": "direction", "type": "string", "number": 11},
                        {"name": "opened_at", "type": "Timestamp", "number": 12},
                        {"name": "updated_at", "type": "Timestamp", "number": 13},
                        {"name": "strategy", "type": "string", "number": 14},
                    ]
                },
                "Portfolio": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "total_value", "type": "Amount", "number": 2},
                        {"name": "available_balance", "type": "Amount", "number": 3},
                        {"name": "locked_balance", "type": "Amount", "number": 4},
                        {"name": "total_pnl", "type": "Amount", "number": 5},
                        {"name": "total_fees", "type": "Amount", "number": 6},
                        {"name": "positions", "type": "Position", "number": 7, "repeated": True},
                        {"name": "timestamp", "type": "Timestamp", "number": 8},
                    ]
                },
                "RiskMetrics": {
                    "fields": [
                        {"name": "var_95", "type": "Decimal", "number": 1},
                        {"name": "var_99", "type": "Decimal", "number": 2},
                        {"name": "cvar_95", "type": "Decimal", "number": 3},
                        {"name": "cvar_99", "type": "Decimal", "number": 4},
                        {"name": "sharpe_ratio", "type": "Decimal", "number": 5},
                        {"name": "sortino_ratio", "type": "Decimal", "number": 6},
                        {"name": "calmar_ratio", "type": "Decimal", "number": 7},
                        {"name": "max_drawdown", "type": "Decimal", "number": 8},
                        {"name": "current_drawdown", "type": "Decimal", "number": 9},
                        {"name": "volatility", "type": "Decimal", "number": 10},
                        {"name": "beta", "type": "Decimal", "number": 11},
                        {"name": "leverage", "type": "Decimal", "number": 12},
                        {"name": "margin_ratio", "type": "Decimal", "number": 13},
                        {"name": "timestamp", "type": "Timestamp", "number": 14},
                    ]
                },
                "PerformanceMetrics": {
                    "fields": [
                        {"name": "total_trades", "type": "int64", "number": 1},
                        {"name": "winning_trades", "type": "int64", "number": 2},
                        {"name": "losing_trades", "type": "int64", "number": 3},
                        {"name": "win_rate", "type": "Decimal", "number": 4},
                        {"name": "profit_factor", "type": "Decimal", "number": 5},
                        {"name": "avg_win", "type": "Amount", "number": 6},
                        {"name": "avg_loss", "type": "Amount", "number": 7},
                        {"name": "best_trade", "type": "Amount", "number": 8},
                        {"name": "worst_trade", "type": "Amount", "number": 9},
                        {"name": "total_pnl", "type": "Amount", "number": 10},
                        {"name": "total_fees", "type": "Amount", "number": 11},
                        {"name": "timestamp", "type": "Timestamp", "number": 12},
                    ]
                },
                "HedgeMetrics": {
                    "fields": [
                        {"name": "hedge_ratio", "type": "Decimal", "number": 1},
                        {"name": "hedge_effectiveness", "type": "Decimal", "number": 2},
                        {"name": "correlations", "type": "Correlation", "number": 3, "repeated": True},
                        {"name": "betas", "type": "Beta", "number": 4, "repeated": True},
                        {"name": "delta", "type": "Decimal", "number": 5},
                        {"name": "gamma", "type": "Decimal", "number": 6},
                        {"name": "vega", "type": "Decimal", "number": 7},
                        {"name": "theta", "type": "Decimal", "number": 8},
                        {"name": "timestamp", "type": "Timestamp", "number": 9},
                    ]
                },
                "Signal": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "symbol", "type": "string", "number": 2},
                        {"name": "direction", "type": "string", "number": 3},
                        {"name": "strength", "type": "Decimal", "number": 4},
                        {"name": "confidence", "type": "Decimal", "number": 5},
                        {"name": "entry_price", "type": "Price", "number": 6},
                        {"name": "stop_loss", "type": "Price", "number": 7},
                        {"name": "take_profit", "type": "Price", "number": 8},
                        {"name": "indicators", "type": "Indicator", "number": 9, "repeated": True},
                        {"name": "timestamp", "type": "Timestamp", "number": 10},
                        {"name": "strategy", "type": "string", "number": 11},
                        {"name": "expiry", "type": "Timestamp", "number": 12},
                    ]
                },
                "Indicator": {
                    "fields": [
                        {"name": "name", "type": "string", "number": 1},
                        {"name": "value", "type": "Decimal", "number": 2},
                        {"name": "parameters", "type": "Parameter", "number": 3, "repeated": True},
                    ]
                },
                "Parameter": {
                    "fields": [
                        {"name": "key", "type": "string", "number": 1},
                        {"name": "value", "type": "string", "number": 2},
                    ]
                },
                "Correlation": {
                    "fields": [
                        {"name": "asset1", "type": "string", "number": 1},
                        {"name": "asset2", "type": "string", "number": 2},
                        {"name": "value", "type": "Decimal", "number": 3},
                    ]
                },
                "Beta": {
                    "fields": [
                        {"name": "asset", "type": "string", "number": 1},
                        {"name": "benchmark", "type": "string", "number": 2},
                        {"name": "value", "type": "Decimal", "number": 3},
                    ]
                },
                "Alert": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "type", "type": "string", "number": 2},
                        {"name": "severity", "type": "string", "number": 3},
                        {"name": "message", "type": "string", "number": 4},
                        {"name": "data", "type": "google.protobuf.Any", "number": 5},
                        {"name": "timestamp", "type": "Timestamp", "number": 6},
                        {"name": "acknowledged", "type": "bool", "number": 7},
                        {"name": "resolved", "type": "bool", "number": 8},
                    ]
                },
                "Batch": {
                    "fields": [
                        {"name": "batch_id", "type": "string", "number": 1},
                        {"name": "messages", "type": "google.protobuf.Any", "number": 2, "repeated": True},
                        {"name": "timestamp", "type": "Timestamp", "number": 3},
                        {"name": "source", "type": "string", "number": 4},
                        {"name": "total_size", "type": "int64", "number": 5},
                        {"name": "compressed", "type": "bool", "number": 6},
                    ]
                },
                "Heartbeat": {
                    "fields": [
                        {"name": "service", "type": "string", "number": 1},
                        {"name": "status", "type": "string", "number": 2},
                        {"name": "timestamp", "type": "Timestamp", "number": 3},
                        {"name": "metrics", "type": "Metric", "number": 4, "repeated": True},
                    ]
                },
                "Metric": {
                    "fields": [
                        {"name": "name", "type": "string", "number": 1},
                        {"name": "value", "type": "Decimal", "number": 2},
                        {"name": "type", "type": "string", "number": 3},
                        {"name": "labels", "type": "Label", "number": 4, "repeated": True},
                    ]
                },
                "Label": {
                    "fields": [
                        {"name": "key", "type": "string", "number": 1},
                        {"name": "value", "type": "string", "number": 2},
                    ]
                },
                "Config": {
                    "fields": [
                        {"name": "key", "type": "string", "number": 1},
                        {"name": "value", "type": "string", "number": 2},
                        {"name": "type", "type": "string", "number": 3},
                        {"name": "version", "type": "string", "number": 4},
                        {"name": "updated_at", "type": "Timestamp", "number": 5},
                    ]
                },
                "BacktestResult": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "strategy", "type": "string", "number": 2},
                        {"name": "symbol", "type": "string", "number": 3},
                        {"name": "start_time", "type": "Timestamp", "number": 4},
                        {"name": "end_time", "type": "Timestamp", "number": 5},
                        {"name": "initial_balance", "type": "Amount", "number": 6},
                        {"name": "final_balance", "type": "Amount", "number": 7},
                        {"name": "total_pnl", "type": "Amount", "number": 8},
                        {"name": "total_trades", "type": "int64", "number": 9},
                        {"name": "win_rate", "type": "Decimal", "number": 10},
                        {"name": "sharpe_ratio", "type": "Decimal", "number": 11},
                        {"name": "max_drawdown", "type": "Decimal", "number": 12},
                        {"name": "trades", "type": "Trade", "number": 13, "repeated": True},
                        {"name": "metrics", "type": "PerformanceMetrics", "number": 14},
                    ]
                },
                "BrokerState": {
                    "fields": [
                        {"name": "connected", "type": "bool", "number": 1},
                        {"name": "account_id", "type": "string", "number": 2},
                        {"name": "balance", "type": "Amount", "number": 3},
                        {"name": "equity", "type": "Amount", "number": 4},
                        {"name": "margin", "type": "Amount", "number": 5},
                        {"name": "free_margin", "type": "Amount", "number": 6},
                        {"name": "leverage", "type": "Decimal", "number": 7},
                        {"name": "timestamp", "type": "Timestamp", "number": 8},
                    ]
                },
                "SystemState": {
                    "fields": [
                        {"name": "hostname", "type": "string", "number": 1},
                        {"name": "pid", "type": "int64", "number": 2},
                        {"name": "cpu_usage", "type": "Decimal", "number": 3},
                        {"name": "memory_usage", "type": "int64", "number": 4},
                        {"name": "memory_percent", "type": "Decimal", "number": 5},
                        {"name": "uptime", "type": "int64", "number": 6},
                        {"name": "connections", "type": "int64", "number": 7},
                        {"name": "timestamp", "type": "Timestamp", "number": 8},
                    ]
                },
            }
        )
        self.register_schema(trading_schema)
        
        hedge_schema = ProtobufSchema(
            name="nexus_hedge",
            package="nexus.hedge",
            version="1.0.0",
            messages={
                "HedgePosition": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "asset", "type": "string", "number": 2},
                        {"name": "hedge_asset", "type": "string", "number": 3},
                        {"name": "ratio", "type": "Decimal", "number": 4},
                        {"name": "size", "type": "Amount", "number": 5},
                        {"name": "entry_price", "type": "Price", "number": 6},
                        {"name": "current_price", "type": "Price", "number": 7},
                        {"name": "unrealized_pnl", "type": "Amount", "number": 8},
                        {"name": "correlation", "type": "Decimal", "number": 9},
                        {"name": "beta", "type": "Decimal", "number": 10},
                        {"name": "opened_at", "type": "Timestamp", "number": 11},
                        {"name": "strategy", "type": "string", "number": 12},
                    ]
                },
                "HedgePortfolio": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "positions", "type": "HedgePosition", "number": 2, "repeated": True},
                        {"name": "total_value", "type": "Amount", "number": 3},
                        {"name": "hedged_value", "type": "Amount", "number": 4},
                        {"name": "unhedged_value", "type": "Amount", "number": 5},
                        {"name": "hedge_ratio", "type": "Decimal", "number": 6},
                        {"name": "effectiveness", "type": "Decimal", "number": 7},
                        {"name": "timestamp", "type": "Timestamp", "number": 8},
                    ]
                },
                "HedgeSignal": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "asset", "type": "string", "number": 2},
                        {"name": "hedge_asset", "type": "string", "number": 3},
                        {"name": "action", "type": "string", "number": 4},
                        {"name": "ratio", "type": "Decimal", "number": 5},
                        {"name": "confidence", "type": "Decimal", "number": 6},
                        {"name": "correlation", "type": "Decimal", "number": 7},
                        {"name": "reason", "type": "string", "number": 8},
                        {"name": "timestamp", "type": "Timestamp", "number": 9},
                        {"name": "expiry", "type": "Timestamp", "number": 10},
                    ]
                },
                "HedgeMetrics": {
                    "fields": [
                        {"name": "total_hedge_ratio", "type": "Decimal", "number": 1},
                        {"name": "hedge_effectiveness", "type": "Decimal", "number": 2},
                        {"name": "correlations", "type": "Correlation", "number": 3, "repeated": True},
                        {"name": "betas", "type": "Beta", "number": 4, "repeated": True},
                        {"name": "delta", "type": "Decimal", "number": 5},
                        {"name": "gamma", "type": "Decimal", "number": 6},
                        {"name": "vega", "type": "Decimal", "number": 7},
                        {"name": "theta", "type": "Decimal", "number": 8},
                        {"name": "timestamp", "type": "Timestamp", "number": 9},
                    ]
                },
            }
        )
        self.register_schema(hedge_schema)
        
        analytics_schema = ProtobufSchema(
            name="nexus_analytics",
            package="nexus.analytics",
            version="1.0.0",
            messages={
                "AnalyticsEvent": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "type", "type": "string", "number": 2},
                        {"name": "category", "type": "string", "number": 3},
                        {"name": "data", "type": "google.protobuf.Any", "number": 4},
                        {"name": "timestamp", "type": "Timestamp", "number": 5},
                        {"name": "session_id", "type": "string", "number": 6},
                        {"name": "user_id", "type": "string", "number": 7},
                    ]
                },
                "AnalyticsAggregation": {
                    "fields": [
                        {"name": "metric", "type": "string", "number": 1},
                        {"name": "value", "type": "Decimal", "number": 2},
                        {"name": "count", "type": "int64", "number": 3},
                        {"name": "sum", "type": "Decimal", "number": 4},
                        {"name": "avg", "type": "Decimal", "number": 5},
                        {"name": "min", "type": "Decimal", "number": 6},
                        {"name": "max", "type": "Decimal", "number": 7},
                        {"name": "stddev", "type": "Decimal", "number": 8},
                        {"name": "percentiles", "type": "Percentile", "number": 9, "repeated": True},
                        {"name": "timestamp", "type": "Timestamp", "number": 10},
                        {"name": "group_by", "type": "string", "number": 11, "repeated": True},
                    ]
                },
                "Percentile": {
                    "fields": [
                        {"name": "p", "type": "int32", "number": 1},
                        {"name": "value", "type": "Decimal", "number": 2},
                    ]
                },
                "Report": {
                    "fields": [
                        {"name": "id", "type": "string", "number": 1},
                        {"name": "name", "type": "string", "number": 2},
                        {"name": "type", "type": "string", "number": 3},
                        {"name": "data", "type": "google.protobuf.Any", "number": 4},
                        {"name": "generated_at", "type": "Timestamp", "number": 5},
                        {"name": "period_start", "type": "Timestamp", "number": 6},
                        {"name": "period_end", "type": "Timestamp", "number": 7},
                        {"name": "filters", "type": "Filter", "number": 8, "repeated": True},
                    ]
                },
                "Filter": {
                    "fields": [
                        {"name": "field", "type": "string", "number": 1},
                        {"name": "operator", "type": "string", "number": 2},
                        {"name": "value", "type": "string", "number": 3},
                    ]
                },
            }
        )
        self.register_schema(analytics_schema)

    async def register_schema(self, schema: ProtobufSchema) -> None:
        async with self._lock:
            self._schemas[schema.name] = schema
            self._build_messages(schema)
            logger.info(f"Registered schema: {schema.name} v{schema.version}")

    def _build_messages(self, schema: ProtobufSchema) -> None:
        try:
            file_descriptor = self._create_file_descriptor(schema)
            self._pool.Add(file_descriptor)
            
            for message_name in schema.messages.keys():
                full_name = f"{schema.package}.{message_name}"
                try:
                    descriptor = self._pool.FindMessageTypeByName(full_name)
                    message_class = self._factory.GetPrototype(descriptor)
                    self._messages[full_name] = message_class
                    self._descriptors[full_name] = descriptor
                except Exception as e:
                    logger.warning(f"Could not build message {full_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error building messages for schema {schema.name}: {e}")

    def _create_file_descriptor(self, schema: ProtobufSchema) -> Any:
        file_desc = descriptor_pb2.FileDescriptorProto()
        file_desc.name = f"{schema.name}.proto"
        file_desc.package = schema.package
        
        for message_name, message_def in schema.messages.items():
            msg_desc = file_desc.message_type.add()
            msg_desc.name = message_name
            
            for field in message_def.get("fields", []):
                field_desc = msg_desc.field.add()
                field_desc.name = field["name"]
                field_desc.number = field["number"]
                field_desc.type = self._get_field_type(field["type"])
                field_desc.label = FieldDescriptor.LABEL_REPEATED if field.get("repeated", False) else FieldDescriptor.LABEL_OPTIONAL
                
        for enum_name, enum_def in schema.enums.items():
            enum_desc = file_desc.enum_type.add()
            enum_desc.name = enum_name
            for value_name, value_number in enum_def.items():
                value_desc = enum_desc.value.add()
                value_desc.name = value_name
                value_desc.number = value_number
        
        return file_desc

    def _get_field_type(self, type_name: str) -> int:
        type_map = {
            "double": FieldDescriptor.TYPE_DOUBLE,
            "float": FieldDescriptor.TYPE_FLOAT,
            "int32": FieldDescriptor.TYPE_INT32,
            "int64": FieldDescriptor.TYPE_INT64,
            "uint32": FieldDescriptor.TYPE_UINT32,
            "uint64": FieldDescriptor.TYPE_UINT64,
            "sint32": FieldDescriptor.TYPE_SINT32,
            "sint64": FieldDescriptor.TYPE_SINT64,
            "fixed32": FieldDescriptor.TYPE_FIXED32,
            "fixed64": FieldDescriptor.TYPE_FIXED64,
            "sfixed32": FieldDescriptor.TYPE_SFIXED32,
            "sfixed64": FieldDescriptor.TYPE_SFIXED64,
            "bool": FieldDescriptor.TYPE_BOOL,
            "string": FieldDescriptor.TYPE_STRING,
            "bytes": FieldDescriptor.TYPE_BYTES,
            "Decimal": FieldDescriptor.TYPE_STRING,
            "Price": FieldDescriptor.TYPE_MESSAGE,
            "Amount": FieldDescriptor.TYPE_MESSAGE,
            "Timestamp": FieldDescriptor.TYPE_MESSAGE,
            "Position": FieldDescriptor.TYPE_MESSAGE,
            "Trade": FieldDescriptor.TYPE_MESSAGE,
            "Order": FieldDescriptor.TYPE_MESSAGE,
            "Portfolio": FieldDescriptor.TYPE_MESSAGE,
            "RiskMetrics": FieldDescriptor.TYPE_MESSAGE,
            "PerformanceMetrics": FieldDescriptor.TYPE_MESSAGE,
            "HedgeMetrics": FieldDescriptor.TYPE_MESSAGE,
            "Signal": FieldDescriptor.TYPE_MESSAGE,
            "Indicator": FieldDescriptor.TYPE_MESSAGE,
            "Parameter": FieldDescriptor.TYPE_MESSAGE,
            "Correlation": FieldDescriptor.TYPE_MESSAGE,
            "Beta": FieldDescriptor.TYPE_MESSAGE,
            "Alert": FieldDescriptor.TYPE_MESSAGE,
            "Batch": FieldDescriptor.TYPE_MESSAGE,
            "Heartbeat": FieldDescriptor.TYPE_MESSAGE,
            "Metric": FieldDescriptor.TYPE_MESSAGE,
            "Label": FieldDescriptor.TYPE_MESSAGE,
            "Config": FieldDescriptor.TYPE_MESSAGE,
            "BacktestResult": FieldDescriptor.TYPE_MESSAGE,
            "BrokerState": FieldDescriptor.TYPE_MESSAGE,
            "SystemState": FieldDescriptor.TYPE_MESSAGE,
            "HedgePosition": FieldDescriptor.TYPE_MESSAGE,
            "HedgePortfolio": FieldDescriptor.TYPE_MESSAGE,
            "HedgeSignal": FieldDescriptor.TYPE_MESSAGE,
            "AnalyticsEvent": FieldDescriptor.TYPE_MESSAGE,
            "AnalyticsAggregation": FieldDescriptor.TYPE_MESSAGE,
            "Percentile": FieldDescriptor.TYPE_MESSAGE,
            "Report": FieldDescriptor.TYPE_MESSAGE,
            "Filter": FieldDescriptor.TYPE_MESSAGE,
            "Metadata": FieldDescriptor.TYPE_MESSAGE,
        }
        return type_map.get(type_name, FieldDescriptor.TYPE_STRING)

    def get_message_class(self, message_type: str) -> Optional[type]:
        return self._messages.get(message_type)

    def get_message_descriptor(self, message_type: str) -> Optional[Any]:
        return self._descriptors.get(message_type)

    def create_message(self, message_type: str, **kwargs) -> Optional[Message]:
        message_class = self.get_message_class(message_type)
        if message_class is None:
            return None
        return message_class(**kwargs)

    def parse_from_string(self, message_type: str, data: bytes) -> Optional[Message]:
        message_class = self.get_message_class(message_type)
        if message_class is None:
            return None
        try:
            message = message_class()
            message.ParseFromString(data)
            return message
        except Exception as e:
            logger.error(f"Error parsing message {message_type}: {e}")
            return None

    def serialize_to_string(self, message: Message) -> Optional[bytes]:
        try:
            return message.SerializeToString()
        except Exception as e:
            logger.error(f"Error serializing message: {e}")
            return None

    def to_json(self, message: Message) -> Optional[str]:
        try:
            return json_format.MessageToJson(message)
        except Exception as e:
            logger.error(f"Error converting message to JSON: {e}")
            return None

    def from_json(self, message_type: str, json_str: str) -> Optional[Message]:
        message_class = self.get_message_class(message_type)
        if message_class is None:
            return None
        try:
            message = message_class()
            json_format.Parse(json_str, message)
            return message
        except Exception as e:
            logger.error(f"Error parsing JSON to message: {e}")
            return None

    def to_dict(self, message: Message) -> Optional[Dict[str, Any]]:
        try:
            return json_format.MessageToDict(message)
        except Exception as e:
            logger.error(f"Error converting message to dict: {e}")
            return None

    def from_dict(self, message_type: str, data: Dict[str, Any]) -> Optional[Message]:
        message_class = self.get_message_class(message_type)
        if message_class is None:
            return None
        try:
            message = message_class()
            json_format.ParseDict(data, message)
            return message
        except Exception as e:
            logger.error(f"Error parsing dict to message: {e}")
            return None


class ProtobufCodec:
    
    def __init__(self):
        self.registry = ProtobufRegistry()
        self._lock = asyncio.Lock()
        self._compression = CompressionType.GZIP
        self._format = SerializationFormat.PROTOBUF
        self._version = "1.0.0"
        self._signing_key: Optional[bytes] = None
        self._message_count = 0
        self._total_bytes = 0
    
    def set_compression(self, compression: CompressionType) -> None:
        self._compression = compression
    
    def set_format(self, format: SerializationFormat) -> None:
        self._format = format
    
    def set_signing_key(self, key: bytes) -> None:
        self._signing_key = key
    
    async def encode(self, message: ProtobufMessage) -> bytes:
        async with self._lock:
            self._message_count += 1
            start_time = time.time()
            
            try:
                message_class = self.registry.get_message_class(message.type)
                if message_class is None:
                    raise ValueError(f"Unknown message type: {message.type}")
                
                pb_message = self._convert_to_protobuf(message, message_class)
                
                if self._format == SerializationFormat.PROTOBUF:
                    data = pb_message.SerializeToString()
                elif self._format == SerializationFormat.JSON:
                    data = json_format.MessageToJson(pb_message).encode('utf-8')
                elif self._format == SerializationFormat.DELIMITED:
                    data = self._encode_delimited(pb_message)
                else:
                    data = pb_message.SerializeToString()
                
                if self._signing_key:
                    signature = hashlib.sha256(self._signing_key + data).digest()
                    data = signature + data
                
                if self._compression != CompressionType.NONE:
                    data = self._compress_data(data)
                
                self._total_bytes += len(data)
                
                duration = time.time() - start_time
                logger.debug(f"Encoded {message.type} in {duration*1000:.2f}ms, size={len(data)}")
                
                return data
                
            except Exception as e:
                logger.error(f"Error encoding message: {e}")
                raise

    async def decode(self, data: bytes, expected_type: Optional[str] = None) -> ProtobufMessage:
        async with self._lock:
            start_time = time.time()
            
            try:
                if self._compression != CompressionType.NONE:
                    data = self._decompress_data(data)
                
                if self._signing_key:
                    signature = data[:32]
                    data = data[32:]
                    expected_sig = hashlib.sha256(self._signing_key + data).digest()
                    if signature != expected_sig:
                        raise ValueError("Invalid message signature")
                
                if self._format == SerializationFormat.PROTOBUF:
                    if expected_type is None:
                        message_type = self._detect_message_type(data)
                    else:
                        message_type = expected_type
                    
                    message_class = self.registry.get_message_class(message_type)
                    if message_class is None:
                        raise ValueError(f"Unknown message type: {message_type}")
                    
                    pb_message = message_class()
                    pb_message.ParseFromString(data)
                    
                elif self._format == SerializationFormat.JSON:
                    json_str = data.decode('utf-8')
                    if expected_type is None:
                        json_data = json.loads(json_str)
                        message_type = json_data.get("type", "nexus.trading.MarketData")
                    else:
                        message_type = expected_type
                    
                    pb_message = self.registry.from_json(message_type, json_str)
                    if pb_message is None:
                        raise ValueError(f"Failed to parse JSON to {message_type}")
                    
                elif self._format == SerializationFormat.DELIMITED:
                    pb_message, message_type = self._decode_delimited(data)
                    
                else:
                    raise ValueError(f"Unsupported format: {self._format}")
                
                result = self._convert_from_protobuf(pb_message, message_type)
                
                duration = time.time() - start_time
                logger.debug(f"Decoded {message_type} in {duration*1000:.2f}ms, size={len(data)}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error decoding message: {e}")
                raise

    async def encode_batch(self, batch: ProtobufBatch) -> bytes:
        async with self._lock:
            if not batch.batch_id:
                batch.batch_id = self._generate_batch_id()
            
            batch_data = []
            for message in batch.messages:
                encoded = await self.encode(message)
                batch_data.append(encoded)
            
            data = b''.join(batch_data)
            
            batch.total_size = len(data)
            batch.compressed = self._compression != CompressionType.NONE
            batch.compression_type = self._compression
            
            return data

    async def decode_batch(self, data: bytes) -> ProtobufBatch:
        async with self._lock:
            messages = []
            offset = 0
            
            while offset < len(data):
                try:
                    if self._format == SerializationFormat.DELIMITED:
                        if offset + 4 > len(data):
                            break
                        msg_len = struct.unpack('>I', data[offset:offset+4])[0]
                        offset += 4
                        msg_data = data[offset:offset+msg_len]
                        offset += msg_len
                    else:
                        msg_len = len(data) - offset
                        msg_data = data[offset:]
                        offset = len(data)
                    
                    if len(msg_data) > 0:
                        message = await self.decode(msg_data)
                        messages.append(message)
                        
                except Exception as e:
                    logger.error(f"Error decoding batch message at offset {offset}: {e}")
                    break
            
            return ProtobufBatch(
                messages=messages,
                timestamp=time.time(),
                total_size=len(data),
                compressed=self._compression != CompressionType.NONE,
                compression_type=self._compression
            )

    def _convert_to_protobuf(self, message: ProtobufMessage, message_class: type) -> Message:
        pb_message = message_class()
        
        if hasattr(pb_message, 'timestamp'):
            pb_message.timestamp.FromDatetime(datetime.fromtimestamp(message.timestamp))
        
        if hasattr(pb_message, 'version'):
            pb_message.version = message.version
        
        if hasattr(pb_message, 'correlation_id'):
            pb_message.correlation_id = message.correlation_id
        
        if hasattr(pb_message, 'source'):
            pb_message.source = message.source
        
        if hasattr(pb_message, 'destination'):
            pb_message.destination = message.destination
        
        for key, value in message.metadata.items():
            if hasattr(pb_message, 'metadata'):
                meta = pb_message.metadata.add()
                meta.key = key
                meta.value = str(value)
        
        if hasattr(pb_message, 'data') and isinstance(message.data, dict):
            any_msg = any_pb2.Any()
            if "type" in message.data:
                data_type = message.data["type"]
                data_msg = self.registry.create_message(data_type, **message.data.get("data", {}))
                if data_msg:
                    any_msg.Pack(data_msg)
                    pb_message.data.CopyFrom(any_msg)
        
        if isinstance(message.data, (dict, list, str, int, float, bool)):
            for key, value in message.data.items():
                if hasattr(pb_message, key):
                    setattr(pb_message, key, value)
        
        return pb_message

    def _convert_from_protobuf(self, pb_message: Message, message_type: str) -> ProtobufMessage:
        data = {}
        timestamp = time.time()
        version = "1.0.0"
        correlation_id = ""
        source = ""
        destination = ""
        metadata = {}
        
        for field in pb_message.DESCRIPTOR.fields:
            if field.name == 'timestamp' and hasattr(pb_message, 'timestamp'):
                ts = getattr(pb_message, 'timestamp')
                if hasattr(ts, 'ToDatetime'):
                    timestamp = ts.ToDatetime().timestamp()
                elif hasattr(ts, 'seconds'):
                    timestamp = ts.seconds + ts.nanos / 1e9
                continue
            
            if field.name == 'version':
                version = getattr(pb_message, 'version', '1.0.0')
                continue
            
            if field.name == 'correlation_id':
                correlation_id = getattr(pb_message, 'correlation_id', '')
                continue
            
            if field.name == 'source':
                source = getattr(pb_message, 'source', '')
                continue
            
            if field.name == 'destination':
                destination = getattr(pb_message, 'destination', '')
                continue
            
            if field.name == 'metadata':
                for meta in getattr(pb_message, 'metadata', []):
                    metadata[meta.key] = meta.value
                continue
            
            if field.name == 'data':
                any_msg = getattr(pb_message, 'data', None)
                if any_msg and any_msg.Is(any_msg.DESCRIPTOR):
                    inner_type = any_msg.TypeName()
                    inner_msg = any_msg.Unpack()
                    data["type"] = inner_type
                    data["data"] = self._protobuf_to_dict(inner_msg)
                continue
            
            if field.label == FieldDescriptor.LABEL_REPEATED:
                data[field.name] = [self._protobuf_to_dict(v) for v in getattr(pb_message, field.name, [])]
            else:
                value = getattr(pb_message, field.name, None)
                if value is not None:
                    if isinstance(value, Message):
                        data[field.name] = self._protobuf_to_dict(value)
                    elif isinstance(value, (timestamp_pb2.Timestamp, duration_pb2.Duration)):
                        if hasattr(value, 'ToDatetime'):
                            data[field.name] = value.ToDatetime().timestamp()
                        else:
                            data[field.name] = value.seconds + value.nanos / 1e9
                    else:
                        data[field.name] = value
        
        return ProtobufMessage(
            type=message_type,
            data=data,
            timestamp=timestamp,
            version=version,
            correlation_id=correlation_id,
            source=source,
            destination=destination,
            metadata=metadata
        )

    def _protobuf_to_dict(self, message: Message) -> Dict[str, Any]:
        try:
            return json_format.MessageToDict(message)
        except:
            result = {}
            for field in message.DESCRIPTOR.fields:
                value = getattr(message, field.name, None)
                if value is not None:
                    if isinstance(value, Message):
                        result[field.name] = self._protobuf_to_dict(value)
                    elif isinstance(value, (timestamp_pb2.Timestamp, duration_pb2.Duration)):
                        if hasattr(value, 'ToDatetime'):
                            result[field.name] = value.ToDatetime().timestamp()
                        else:
                            result[field.name] = value.seconds + value.nanos / 1e9
                    elif field.label == FieldDescriptor.LABEL_REPEATED:
                        result[field.name] = [
                            self._protobuf_to_dict(v) if isinstance(v, Message) else v
                            for v in value
                        ]
                    else:
                        result[field.name] = value
            return result

    def _encode_delimited(self, message: Message) -> bytes:
        data = message.SerializeToString()
        length_prefix = struct.pack('>I', len(data))
        return length_prefix + data

    def _decode_delimited(self, data: bytes) -> Tuple[Message, str]:
        if len(data) < 4:
            raise ValueError("Data too short for delimited format")
        
        msg_len = struct.unpack('>I', data[:4])[0]
        if len(data) < 4 + msg_len:
            raise ValueError("Incomplete delimited message")
        
        msg_data = data[4:4+msg_len]
        message_type = self._detect_message_type(msg_data)
        message_class = self.registry.get_message_class(message_type)
        
        if message_class is None:
            raise ValueError(f"Unknown message type: {message_type}")
        
        pb_message = message_class()
        pb_message.ParseFromString(msg_data)
        
        return pb_message, message_type

    def _detect_message_type(self, data: bytes) -> str:
        types_to_try = [
            "nexus.trading.MarketData",
            "nexus.trading.Order",
            "nexus.trading.Trade",
            "nexus.trading.Position",
            "nexus.trading.Portfolio",
            "nexus.trading.RiskMetrics",
            "nexus.trading.PerformanceMetrics",
            "nexus.trading.HedgeMetrics",
            "nexus.trading.Signal",
            "nexus.trading.Alert",
            "nexus.trading.Batch",
            "nexus.trading.Heartbeat",
            "nexus.trading.Config",
            "nexus.trading.BacktestResult",
            "nexus.trading.BrokerState",
            "nexus.trading.SystemState",
            "nexus.hedge.HedgePosition",
            "nexus.hedge.HedgePortfolio",
            "nexus.hedge.HedgeSignal",
            "nexus.hedge.HedgeMetrics",
            "nexus.analytics.AnalyticsEvent",
            "nexus.analytics.AnalyticsAggregation",
            "nexus.analytics.Report",
        ]
        
        for msg_type in types_to_try:
            try:
                message_class = self.registry.get_message_class(msg_type)
                if message_class is None:
                    continue
                
                test_msg = message_class()
                try:
                    test_msg.ParseFromString(data)
                    return msg_type
                except:
                    continue
            except:
                continue
        
        return "nexus.trading.MarketData"

    def _compress_data(self, data: bytes) -> bytes:
        if self._compression == CompressionType.GZIP:
            return zlib.compress(data, 9)
        elif self._compression == CompressionType.ZLIB:
            compressed = zlib.compress(data, 9)
            return b'\x78\x9c' + compressed[2:]
        else:
            return data

    def _decompress_data(self, data: bytes) -> bytes:
        if self._compression == CompressionType.GZIP:
            return zlib.decompress(data)
        elif self._compression == CompressionType.ZLIB:
            if data[:2] == b'\x78\x9c':
                return zlib.decompress(data)
            else:
                return zlib.decompress(b'\x78\x9c' + data)
        else:
            return data

    def _generate_batch_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "message_count": self._message_count,
            "total_bytes": self._total_bytes,
            "compression": self._compression.value,
            "format": self._format.value,
            "version": self._version,
            "signing_enabled": self._signing_key is not None,
        }


class HedgeBotProtobufHandler:
    
    def __init__(self):
        self.codec = ProtobufCodec()
        self.registry = ProtobufRegistry()
        self._lock = asyncio.Lock()
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        self._stats = defaultdict(int)

    def register_handler(self, message_type: str, handler: Callable) -> None:
        self._handlers[message_type].append(handler)
        logger.info(f"Registered handler for {message_type}")

    async def send_message(self, message: ProtobufMessage) -> bytes:
        encoded = await self.codec.encode(message)
        self._stats["sent"] += 1
        return encoded

    async def receive_message(self, data: bytes, expected_type: Optional[str] = None) -> ProtobufMessage:
        message = await self.codec.decode(data, expected_type)
        self._stats["received"] += 1
        return message

    async def process_message(self, data: bytes, expected_type: Optional[str] = None) -> Optional[Any]:
        try:
            message = await self.receive_message(data, expected_type)
            
            if message.type in self._handlers:
                results = []
                for handler in self._handlers[message.type]:
                    try:
                        result = await handler(message)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error in handler for {message.type}: {e}")
                        self._stats["handler_errors"] += 1
                
                self._stats["processed"] += 1
                return results
            else:
                self._stats["unhandled"] += 1
                logger.warning(f"No handler for message type: {message.type}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self._stats["errors"] += 1
            raise

    async def start_processor(self) -> None:
        if self._processing:
            return
        
        self._processing = True
        self._processor_task = asyncio.create_task(self._processor_loop())
        logger.info("Protobuf message processor started")

    async def stop_processor(self) -> None:
        self._processing = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        
        logger.info("Protobuf message processor stopped")

    async def _processor_loop(self) -> None:
        while self._processing:
            try:
                data = await self._message_queue.get()
                await self.process_message(data)
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in processor loop: {e}")
                await asyncio.sleep(0.1)

    async def queue_message(self, data: bytes) -> None:
        await self._message_queue.put(data)
        self._stats["queued"] += 1

    def get_stats(self) -> Dict[str, Any]:
        stats = self.codec.get_stats()
        stats.update({
            "queued": self._stats["queued"],
            "sent": self._stats["sent"],
            "received": self._stats["received"],
            "processed": self._stats["processed"],
            "unhandled": self._stats["unhandled"],
            "errors": self._stats["errors"],
            "handler_errors": self._stats["handler_errors"],
            "processing": self._processing,
            "queue_size": self._message_queue.qsize(),
            "registered_handlers": len(self._handlers),
        })
        return stats

    def clear_stats(self) -> None:
        self._stats.clear()
        self._stats = defaultdict(int)


class ProtobufMessageBuilder:
    
    @staticmethod
    def market_data(
        symbol: str,
        price: float,
        volume: float,
        bid: float = 0.0,
        ask: float = 0.0,
        high_24h: float = 0.0,
        low_24h: float = 0.0,
        change_24h: float = 0.0,
        source: str = "exchange"
    ) -> ProtobufMessage:
        data = {
            "symbol": symbol,
            "price": {"value": str(price), "currency": "USD"},
            "volume": {"value": str(volume), "asset": symbol.split('-')[0]},
            "bid": {"value": str(bid), "currency": "USD"},
            "ask": {"value": str(ask), "currency": "USD"},
            "high_24h": {"value": str(high_24h), "currency": "USD"},
            "low_24h": {"value": str(low_24h), "currency": "USD"},
            "change_24h": {"value": str(change_24h)},
            "source": source,
        }
        return ProtobufMessage(type="nexus.trading.MarketData", data=data)

    @staticmethod
    def trade(
        trade_id: str,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        pnl: float = 0.0,
        strategy: str = "hedge_bot"
    ) -> ProtobufMessage:
        data = {
            "id": trade_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": {"value": str(quantity), "asset": symbol.split('-')[0]},
            "price": {"value": str(price), "currency": "USD"},
            "fee": {"value": str(fee), "asset": "USD"},
            "pnl": {"value": str(pnl), "asset": "USD"},
            "strategy": strategy,
        }
        return ProtobufMessage(type="nexus.trading.Trade", data=data)

    @staticmethod
    def position(
        position_id: str,
        symbol: str,
        size: float,
        entry_price: float,
        current_price: float,
        direction: str = "long",
        leverage: float = 1.0,
        margin: float = 0.0,
        liquidation_price: float = 0.0,
        strategy: str = "hedge_bot"
    ) -> ProtobufMessage:
        asset = symbol.split('-')[0]
        data = {
            "id": position_id,
            "symbol": symbol,
            "size": {"value": str(size), "asset": asset},
            "entry_price": {"value": str(entry_price), "currency": "USD"},
            "current_price": {"value": str(current_price), "currency": "USD"},
            "direction": direction,
            "leverage": {"value": str(leverage)},
            "margin": {"value": str(margin), "asset": "USD"},
            "liquidation_price": {"value": str(liquidation_price), "currency": "USD"},
            "strategy": strategy,
        }
        return ProtobufMessage(type="nexus.trading.Position", data=data)

    @staticmethod
    def risk_metrics(
        var_95: float,
        var_99: float,
        cvar_95: float,
        cvar_99: float,
        sharpe_ratio: float,
        sortino_ratio: float,
        calmar_ratio: float,
        max_drawdown: float,
        current_drawdown: float,
        volatility: float,
        beta: float,
        leverage: float,
        margin_ratio: float
    ) -> ProtobufMessage:
        data = {
            "var_95": {"value": str(var_95)},
            "var_99": {"value": str(var_99)},
            "cvar_95": {"value": str(cvar_95)},
            "cvar_99": {"value": str(cvar_99)},
            "sharpe_ratio": {"value": str(sharpe_ratio)},
            "sortino_ratio": {"value": str(sortino_ratio)},
            "calmar_ratio": {"value": str(calmar_ratio)},
            "max_drawdown": {"value": str(max_drawdown)},
            "current_drawdown": {"value": str(current_drawdown)},
            "volatility": {"value": str(volatility)},
            "beta": {"value": str(beta)},
            "leverage": {"value": str(leverage)},
            "margin_ratio": {"value": str(margin_ratio)},
        }
        return ProtobufMessage(type="nexus.trading.RiskMetrics", data=data)

    @staticmethod
    def signal(
        signal_id: str,
        symbol: str,
        direction: str,
        strength: float,
        confidence: float,
        entry_price: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        strategy: str = "hedge_bot",
        indicators: List[Dict[str, Any]] = None
    ) -> ProtobufMessage:
        data = {
            "id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "strength": {"value": str(strength)},
            "confidence": {"value": str(confidence)},
            "entry_price": {"value": str(entry_price), "currency": "USD"},
            "stop_loss": {"value": str(stop_loss), "currency": "USD"},
            "take_profit": {"value": str(take_profit), "currency": "USD"},
            "strategy": strategy,
            "indicators": [
                {"name": ind["name"], "value": {"value": str(ind["value"])}}
                for ind in (indicators or [])
            ]
        }
        return ProtobufMessage(type="nexus.trading.Signal", data=data)

    @staticmethod
    def hedge_metrics(
        hedge_ratio: float,
        hedge_effectiveness: float,
        correlations: List[Dict[str, Any]],
        betas: List[Dict[str, Any]],
        delta: float = 0.0,
        gamma: float = 0.0,
        vega: float = 0.0,
        theta: float = 0.0
    ) -> ProtobufMessage:
        data = {
            "hedge_ratio": {"value": str(hedge_ratio)},
            "hedge_effectiveness": {"value": str(hedge_effectiveness)},
            "correlations": [
                {"asset1": c["asset1"], "asset2": c["asset2"], "value": {"value": str(c["value"])}}
                for c in correlations
            ],
            "betas": [
                {"asset": b["asset"], "benchmark": b["benchmark"], "value": {"value": str(b["value"])}}
                for b in betas
            ],
            "delta": {"value": str(delta)},
            "gamma": {"value": str(gamma)},
            "vega": {"value": str(vega)},
            "theta": {"value": str(theta)},
        }
        return ProtobufMessage(type="nexus.hedge.HedgeMetrics", data=data)

    @staticmethod
    def alert(
        alert_id: str,
        alert_type: str,
        severity: str,
        message: str,
        data: Dict[str, Any] = None
    ) -> ProtobufMessage:
        msg_data = {
            "id": alert_id,
            "type": alert_type,
            "severity": severity,
            "message": message,
            "acknowledged": False,
            "resolved": False,
        }
        if data:
            msg_data["data"] = {"type": "nexus.trading.AlertData", "data": data}
        return ProtobufMessage(type="nexus.trading.Alert", data=msg_data)

    @staticmethod
    def heartbeat(service: str, status: str, metrics: List[Dict[str, Any]] = None) -> ProtobufMessage:
        data = {
            "service": service,
            "status": status,
            "metrics": [
                {"name": m["name"], "value": {"value": str(m["value"])}, "type": m.get("type", "gauge")}
                for m in (metrics or [])
            ]
        }
        return ProtobufMessage(type="nexus.trading.Heartbeat", data=data)

    @staticmethod
    def config(key: str, value: str, config_type: str = "string", version: str = "1.0.0") -> ProtobufMessage:
        data = {
            "key": key,
            "value": value,
            "type": config_type,
            "version": version,
        }
        return ProtobufMessage(type="nexus.trading.Config", data=data)


class ProtobufFileHandler:
    
    def __init__(self, filepath: str, codec: Optional[ProtobufCodec] = None):
        self.filepath = filepath
        self.codec = codec or ProtobufCodec()
        self._lock = asyncio.Lock()
        self._file: Optional[BinaryIO] = None
        self._open = False

    async def open(self, mode: str = 'rb') -> None:
        async with self._lock:
            if self._open:
                return
            self._file = open(self.filepath, mode)
            self._open = True

    async def close(self) -> None:
        async with self._lock:
            if self._file:
                self._file.close()
                self._file = None
                self._open = False

    async def write_message(self, message: ProtobufMessage) -> None:
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            data = await self.codec.encode(message)
            length = struct.pack('>I', len(data))
            self._file.write(length)
            self._file.write(data)
            self._file.flush()

    async def write_batch(self, batch: ProtobufBatch) -> None:
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            data = await self.codec.encode_batch(batch)
            length = struct.pack('>I', len(data))
            self._file.write(length)
            self._file.write(data)
            self._file.flush()

    async def read_message(self, expected_type: Optional[str] = None) -> Optional[ProtobufMessage]:
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            length_bytes = self._file.read(4)
            if not length_bytes:
                return None
            
            length = struct.unpack('>I', length_bytes)[0]
            data = self._file.read(length)
            if len(data) < length:
                return None
            
            return await self.codec.decode(data, expected_type)

    async def read_batch(self) -> Optional[ProtobufBatch]:
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            length_bytes = self._file.read(4)
            if not length_bytes:
                return None
            
            length = struct.unpack('>I', length_bytes)[0]
            data = self._file.read(length)
            if len(data) < length:
                return None
            
            return await self.codec.decode_batch(data)

    async def read_all(self) -> List[ProtobufMessage]:
        messages = []
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            self._file.seek(0)
            while True:
                length_bytes = self._file.read(4)
                if not length_bytes:
                    break
                
                length = struct.unpack('>I', length_bytes)[0]
                data = self._file.read(length)
                if len(data) < length:
                    break
                
                try:
                    message = await self.codec.decode(data)
                    messages.append(message)
                except Exception as e:
                    logger.error(f"Error reading message: {e}")
                    break
        
        return messages

    async def read_all_batches(self) -> List[ProtobufBatch]:
        batches = []
        async with self._lock:
            if not self._open:
                raise RuntimeError("File not open")
            
            self._file.seek(0)
            while True:
                length_bytes = self._file.read(4)
                if not length_bytes:
                    break
                
                length = struct.unpack('>I', length_bytes)[0]
                data = self._file.read(length)
                if len(data) < length:
                    break
                
                try:
                    batch = await self.codec.decode_batch(data)
                    batches.append(batch)
                except Exception as e:
                    logger.error(f"Error reading batch: {e}")
                    break
        
        return batches

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


__all__ = [
    "DataType",
    "CompressionType",
    "SerializationFormat",
    "ProtobufSchema",
    "ProtobufMessage",
    "ProtobufBatch",
    "ProtobufRegistry",
    "ProtobufCodec",
    "HedgeBotProtobufHandler",
    "ProtobufMessageBuilder",
    "ProtobufFileHandler",
]
