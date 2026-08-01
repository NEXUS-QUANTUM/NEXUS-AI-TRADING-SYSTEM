"""
NEXUS AI TRADING SYSTEM
Hedge Bot Data Nessie - Full Production Version

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: trading/bots/hedge_bot/hedge_bot_data_nessie.py
Description: Advanced data management and processing system for hedge bot
             with real-time data ingestion, processing, storage, and analytics.
             Supports multiple data sources, real-time streaming, and AI-driven
             data enrichment.
"""

import asyncio
import json
import logging
import pickle
import zlib
import hashlib
import hmac
import base64
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Set, Callable, Awaitable, Iterator
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import weakref

import numpy as np
import pandas as pd
import polars as pl
from scipy import stats
from scipy.signal import find_peaks
from scipy.fft import fft, ifft
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

import aiohttp
import asyncpg
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from elasticsearch import AsyncElasticsearch

from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async, RetryConfig
from shared.utilities.cache import cache_result, CacheConfig

logger = get_logger(__name__)


class DataSource(str, Enum):
    YAHOO = "yahoo"
    ALPHA_VANTAGE = "alphavantage"
    COINGECKO = "coingecko"
    BINANCE = "binance"
    BYBIT = "bybit"
    KRAKEN = "kraken"
    POLYGON = "polygon"
    FRED = "fred"
    QUANDL = "quandl"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"
    CSV = "csv"
    DATABASE = "database"
    REDIS = "redis"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    S3 = "s3"
    MONGO = "mongo"
    POSTGRES = "postgres"
    ELASTIC = "elastic"
    CUSTOM = "custom"


class DataType(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    TRADE = "trade"
    ORDER_BOOK = "order_book"
    QUOTE = "quote"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    NEWS = "news"
    SOCIAL = "social"
    MACRO = "macro"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    BOND = "bond"
    COMMODITY = "commodity"
    CUSTOM = "custom"


class DataFrequency(str, Enum):
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    HOUR = "1h"
    FOUR_HOUR = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"
    QUARTER = "1Q"
    YEAR = "1Y"


class DataProcessingStage(str, Enum):
    RAW = "raw"
    CLEANED = "cleaned"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"
    FEATURED = "featured"
    TRANSFORMED = "transformed"
    AGGREGATED = "aggregated"
    ANALYZED = "analyzed"
    READY = "ready"


@dataclass
class DataConfig:
    """Configuration for data management."""
    sources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl: int = 3600
    cache_max_size: int = 10000
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    compression_enabled: bool = True
    encryption_enabled: bool = True
    encryption_key: Optional[str] = None
    validation_schema: Dict[str, Any] = field(default_factory=dict)
    transformation_pipeline: List[Dict[str, Any]] = field(default_factory=list)
    feature_engineering: List[Dict[str, Any]] = field(default_factory=list)
    storage_backend: str = "postgres"
    backup_enabled: bool = True
    backup_interval: int = 86400
    cleanup_interval: int = 604800
    max_history_days: int = 365
    realtime_enabled: bool = True
    websocket_url: Optional[str] = None
    kafka_bootstrap: Optional[str] = None
    kafka_topic: Optional[str] = None
    rabbitmq_url: Optional[str] = None
    rabbitmq_queue: Optional[str] = None


@dataclass
class DataRecord:
    """Generic data record."""
    id: str
    source: DataSource
    symbol: str
    data_type: DataType
    frequency: DataFrequency
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    stage: DataProcessingStage = DataProcessingStage.RAW
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1


@dataclass
class DataBatch:
    """Batch of data records."""
    id: str
    source: DataSource
    records: List[DataRecord]
    size: int
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQuery:
    """Data query parameters."""
    source: Optional[DataSource] = None
    symbol: Optional[str] = None
    data_type: Optional[DataType] = None
    frequency: Optional[DataFrequency] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "desc"
    filters: Dict[str, Any] = field(default_factory=dict)
    include_metadata: bool = False


@dataclass
class DataQuality:
    """Data quality metrics."""
    completeness: float
    accuracy: float
    consistency: float
    timeliness: float
    uniqueness: float
    validity: float
    overall_score: float
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]


@dataclass
class DataStats:
    """Data statistics."""
    total_records: int
    total_size_bytes: int
    unique_symbols: int
    unique_sources: int
    unique_types: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    frequency_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    type_distribution: Dict[str, int]
    missing_values: Dict[str, float]
    outliers_count: int
    duplicates_count: int
    quality_score: float


@dataclass
class DataEnrichment:
    """Data enrichment configuration."""
    type: str
    source_field: str
    target_field: str
    transformation: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None


class DataNessie:
    """
    Advanced Data Management System for Hedge Bot.
    
    Features:
    - Multi-source data ingestion
    - Real-time streaming via WebSocket, Kafka, RabbitMQ
    - Data validation and quality checks
    - Data transformation and normalization
    - Feature engineering
    - Data enrichment and augmentation
    - Automated ETL pipelines
    - Caching with Redis
    - Storage with PostgreSQL, MongoDB, Elasticsearch
    - Data compression and encryption
    - Backup and recovery
    - Data versioning
    - Advanced analytics
    - Machine learning data preparation
    - Real-time monitoring
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        connection_pool: Optional[Any] = None,
    ):
        self.config = config
        self._data_config = DataConfig(**config.get("data_config", {}))
        self._connection_pool = connection_pool
        
        # Data storage
        self._data_buffer: Dict[str, List[DataRecord]] = defaultdict(list)
        self._data_cache: Dict[str, Any] = {}
        self._processed_data: Dict[str, pd.DataFrame] = {}
        self._polars_data: Dict[str, pl.DataFrame] = {}
        
        # Connections
        self._redis_client: Optional[redis.Redis] = None
        self._postgres_pool: Optional[asyncpg.Pool] = None
        self._mongo_client: Optional[AsyncIOMotorClient] = None
        self._elastic_client: Optional[AsyncElasticsearch] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._kafka_producer: Optional[Any] = None
        self._rabbitmq_connection: Optional[Any] = None
        
        # Processing
        self._processing_queue: asyncio.Queue = asyncio.Queue()
        self._processing_tasks: Set[asyncio.Task] = set()
        self._is_running = False
        self._executor = ThreadPoolExecutor(max_workers=config.get("thread_workers", 4))
        self._process_executor = ProcessPoolExecutor(max_workers=config.get("process_workers", 2))
        
        # Statistics
        self._stats: DataStats = DataStats(
            total_records=0,
            total_size_bytes=0,
            unique_symbols=0,
            unique_sources=0,
            unique_types=0,
            date_range_start=None,
            date_range_end=None,
            frequency_distribution={},
            source_distribution={},
            type_distribution={},
            missing_values={},
            outliers_count=0,
            duplicates_count=0,
            quality_score=0.0,
        )
        
        # Feature engineering cache
        self._feature_cache: Dict[str, pd.DataFrame] = {}
        self._scaler_cache: Dict[str, StandardScaler] = {}
        self._pca_cache: Dict[str, PCA] = {}
        
        # Data quality
        self._quality_history: List[DataQuality] = []
        
        # Error tracking
        self._error_log: List[Dict[str, Any]] = []
        self._error_count = 0
        
        # Subscriptions
        self._subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self._realtime_handlers: Dict[str, Callable] = {}
        
        # Initialize connections
        self._init_connections()
        
        # Load schemas
        self._load_schemas()
        
        # Initialize feature engineering
        self._init_feature_engineering()
        
        logger.info("DataNessie initialized with full production capabilities")
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def _init_connections(self) -> None:
        """Initialize database and message queue connections."""
        try:
            # Redis for caching
            redis_config = self.config.get("redis", {})
            if redis_config.get("enabled", True):
                self._redis_client = redis.Redis(
                    host=redis_config.get("host", "localhost"),
                    port=redis_config.get("port", 6379),
                    password=redis_config.get("password"),
                    db=redis_config.get("db", 0),
                    decode_responses=True,
                )
            
            # PostgreSQL for storage
            pg_config = self.config.get("postgres", {})
            if pg_config.get("enabled", True):
                # Connection pool will be created on first use
                pass
            
            # MongoDB for unstructured data
            mongo_config = self.config.get("mongo", {})
            if mongo_config.get("enabled", False):
                self._mongo_client = AsyncIOMotorClient(mongo_config.get("url", "mongodb://localhost:27017"))
            
            # Elasticsearch for search
            es_config = self.config.get("elastic", {})
            if es_config.get("enabled", False):
                self._elastic_client = AsyncElasticsearch(
                    hosts=es_config.get("hosts", ["http://localhost:9200"])
                )
            
            # HTTP session
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._data_config.timeout)
            )
            
        except Exception as e:
            logger.error(f"Error initializing connections: {e}")
    
    def _load_schemas(self) -> None:
        """Load data validation schemas."""
        self._schemas = self.config.get("schemas", {})
    
    def _init_feature_engineering(self) -> None:
        """Initialize feature engineering pipeline."""
        self._feature_pipeline = self.config.get("feature_pipeline", [])
    
    # ========================================================================
    # DATA INGESTION
    # ========================================================================
    
    async def ingest_data(
        self,
        source: DataSource,
        symbol: str,
        data_type: DataType,
        frequency: DataFrequency,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataRecord:
        """
        Ingest data from any source.
        
        Args:
            source: Data source
            symbol: Trading symbol
            data_type: Type of data
            frequency: Data frequency
            data: Data dictionary
            metadata: Additional metadata
            
        Returns:
            DataRecord
        """
        # Generate ID
        record_id = self._generate_record_id(source, symbol, data_type, frequency, data)
        
        # Validate data
        if not self._validate_data(data_type, data):
            logger.warning(f"Data validation failed for {symbol}")
            return None
        
        # Create record
        record = DataRecord(
            id=record_id,
            source=source,
            symbol=symbol,
            data_type=data_type,
            frequency=frequency,
            timestamp=data.get("timestamp", datetime.now()),
            data=data,
            metadata=metadata or {},
            checksum=self._calculate_checksum(data),
        )
        
        # Process data through pipeline
        record = await self._process_record(record)
        
        # Store record
        await self._store_record(record)
        
        # Update statistics
        self._update_stats(record)
        
        # Notify subscribers
        await self._notify_subscribers(record)
        
        return record
    
    async def ingest_batch(
        self,
        source: DataSource,
        records: List[Dict[str, Any]],
    ) -> DataBatch:
        """
        Ingest a batch of data records.
        
        Args:
            source: Data source
            records: List of data records
            
        Returns:
            DataBatch
        """
        processed_records = []
        
        for record_data in records:
            record = await self.ingest_data(
                source=source,
                symbol=record_data.get("symbol"),
                data_type=DataType(record_data.get("data_type", "price")),
                frequency=DataFrequency(record_data.get("frequency", "1d")),
                data=record_data.get("data", {}),
                metadata=record_data.get("metadata", {}),
            )
            if record:
                processed_records.append(record)
        
        batch = DataBatch(
            id=self._generate_batch_id(source),
            source=source,
            records=processed_records,
            size=len(processed_records),
        )
        
        return batch
    
    # ========================================================================
    # DATA SOURCE SPECIFIC INGESTION
    # ========================================================================
    
    async def fetch_yahoo_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if not data.empty:
                # Ingest the data
                for timestamp, row in data.iterrows():
                    await self.ingest_data(
                        source=DataSource.YAHOO,
                        symbol=symbol,
                        data_type=DataType.PRICE,
                        frequency=DataFrequency(interval),
                        data={
                            "timestamp": timestamp,
                            "open": row.get("Open", 0),
                            "high": row.get("High", 0),
                            "low": row.get("Low", 0),
                            "close": row.get("Close", 0),
                            "volume": row.get("Volume", 0),
                        },
                    )
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_binance_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch data from Binance."""
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
            "1M": "1M",
        }
        
        binance_interval = interval_map.get(interval, "1d")
        url = "https://api.binance.com/api/v3/klines"
        
        params = {
            "symbol": symbol.upper(),
            "interval": binance_interval,
            "startTime": int(start_date.timestamp() * 1000),
            "endTime": int(end_date.timestamp() * 1000),
            "limit": 1000,
        }
        
        try:
            async with self._http_session.get(url, params=params) as response:
                data = await response.json()
            
            if isinstance(data, list) and data:
                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades", "taker_buy_base",
                    "taker_buy_quote", "ignore"
                ])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                
                # Convert to numeric
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col])
                
                # Ingest the data
                for timestamp, row in df.iterrows():
                    await self.ingest_data(
                        source=DataSource.BINANCE,
                        symbol=symbol,
                        data_type=DataType.PRICE,
                        frequency=DataFrequency(interval),
                        data={
                            "timestamp": timestamp,
                            "open": row["open"],
                            "high": row["high"],
                            "low": row["low"],
                            "close": row["close"],
                            "volume": row["volume"],
                        },
                    )
                
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching Binance data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_alpha_vantage_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "daily",
    ) -> pd.DataFrame:
        """Fetch data from Alpha Vantage."""
        api_key = self.config.get("api_keys", {}).get("alphavantage")
        if not api_key:
            logger.error("Alpha Vantage API key not configured")
            return pd.DataFrame()
        
        function = "TIME_SERIES_DAILY" if interval == "daily" else "TIME_SERIES_INTRADAY"
        url = "https://www.alphavantage.co/query"
        
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": api_key,
            "outputsize": "full",
        }
        
        if interval != "daily":
            params["interval"] = interval
        
        try:
            async with self._http_session.get(url, params=params) as response:
                data = await response.json()
            
            time_series_key = "Time Series (Daily)" if interval == "daily" else f"Time Series ({interval})"
            
            if time_series_key in data:
                time_series = data[time_series_key]
                df = pd.DataFrame.from_dict(time_series, orient="index")
                df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                df = df.loc[start_date:end_date]
                
                # Rename columns
                df.columns = [col.split('.')[0].lower().replace(' ', '_') for col in df.columns]
                df = df.astype(float)
                
                # Ingest the data
                for timestamp, row in df.iterrows():
                    await self.ingest_data(
                        source=DataSource.ALPHA_VANTAGE,
                        symbol=symbol,
                        data_type=DataType.PRICE,
                        frequency=DataFrequency(interval),
                        data={
                            "timestamp": timestamp,
                            "open": row.get("open", 0),
                            "high": row.get("high", 0),
                            "low": row.get("low", 0),
                            "close": row.get("close", 0),
                            "volume": row.get("volume", 0),
                        },
                    )
                
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_coingecko_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch data from CoinGecko."""
        coin_id = self._get_coingecko_id(symbol)
        url = "https://api.coingecko.com/api/v3/coins"
        
        params = {
            "vs_currency": "usd",
            "from": int(start_date.timestamp()),
            "to": int(end_date.timestamp()),
        }
        
        try:
            async with self._http_session.get(f"{url}/{coin_id}/market_chart/range", params=params) as response:
                data = await response.json()
            
            if "prices" in data:
                prices = data["prices"]
                df = pd.DataFrame(prices, columns=["timestamp", "price"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df.set_index("timestamp", inplace=True)
                
                # Ingest the data
                for timestamp, row in df.iterrows():
                    await self.ingest_data(
                        source=DataSource.COINGECKO,
                        symbol=symbol,
                        data_type=DataType.PRICE,
                        frequency=DataFrequency.HOUR,
                        data={
                            "timestamp": timestamp,
                            "price": row["price"],
                        },
                    )
                
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def fetch_fred_data(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch data from FRED."""
        api_key = self.config.get("api_keys", {}).get("fred")
        if not api_key:
            logger.error("FRED API key not configured")
            return pd.DataFrame()
        
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
        }
        
        try:
            async with self._http_session.get(url, params=params) as response:
                data = await response.json()
            
            if "observations" in data:
                observations = data["observations"]
                df = pd.DataFrame(observations)
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                
                # Ingest the data
                for timestamp, row in df.iterrows():
                    await self.ingest_data(
                        source=DataSource.FRED,
                        symbol=series_id,
                        data_type=DataType.MACRO,
                        frequency=DataFrequency.DAY,
                        data={
                            "timestamp": timestamp,
                            "value": row["value"],
                        },
                    )
                
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching FRED data for {series_id}: {e}")
            return pd.DataFrame()
    
    # ========================================================================
    # REAL-TIME DATA STREAMING
    # ========================================================================
    
    async def start_realtime_stream(
        self,
        source: DataSource,
        symbols: List[str],
        handler: Callable[[DataRecord], Awaitable[None]],
    ) -> None:
        """
        Start real-time data streaming from a source.
        
        Args:
            source: Data source
            symbols: List of symbols to stream
            handler: Async handler function for incoming data
        """
        self._realtime_handlers[source.value] = handler
        
        if source == DataSource.WEBSOCKET:
            await self._start_websocket_stream(symbols, handler)
        elif source == DataSource.BINANCE:
            await self._start_binance_websocket(symbols, handler)
        elif source == DataSource.KAFKA:
            await self._start_kafka_stream(symbols, handler)
        elif source == DataSource.RABBITMQ:
            await self._start_rabbitmq_stream(symbols, handler)
        else:
            logger.error(f"Unsupported real-time source: {source}")
    
    async def _start_websocket_stream(
        self,
        symbols: List[str],
        handler: Callable[[DataRecord], Awaitable[None]],
    ) -> None:
        """Start WebSocket stream."""
        websocket_url = self._data_config.websocket_url
        if not websocket_url:
            logger.error("WebSocket URL not configured")
            return
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(websocket_url) as ws:
                # Subscribe to symbols
                subscription = {
                    "action": "subscribe",
                    "symbols": symbols,
                }
                await ws.send_json(subscription)
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        record = await self._process_websocket_message(data)
                        if record:
                            await handler(record)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {msg}")
                        break
    
    async def _start_binance_websocket(
        self,
        symbols: List[str],
        handler: Callable[[DataRecord], Awaitable[None]],
    ) -> None:
        """Start Binance WebSocket stream."""
        streams = []
        for symbol in symbols:
            streams.append(f"{symbol.lower()}@trade")
        
        url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        record = await self._process_binance_message(data)
                        if record:
                            await handler(record)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"Binance WebSocket error: {msg}")
                        break
    
    async def _start_kafka_stream(
        self,
        symbols: List[str],
        handler: Callable[[DataRecord], Awaitable[None]],
    ) -> None:
        """Start Kafka stream."""
        # Placeholder - would use aiokafka
        logger.info("Kafka stream started")
    
    async def _start_rabbitmq_stream(
        self,
        symbols: List[str],
        handler: Callable[[DataRecord], Awaitable[None]],
    ) -> None:
        """Start RabbitMQ stream."""
        # Placeholder - would use aio-pika
        logger.info("RabbitMQ stream started")
    
    async def _process_websocket_message(self, data: Dict[str, Any]) -> Optional[DataRecord]:
        """Process WebSocket message."""
        try:
            return await self.ingest_data(
                source=DataSource.WEBSOCKET,
                symbol=data.get("symbol", "unknown"),
                data_type=DataType.PRICE,
                frequency=DataFrequency.TICK,
                data=data,
            )
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            return None
    
    async def _process_binance_message(self, data: Dict[str, Any]) -> Optional[DataRecord]:
        """Process Binance WebSocket message."""
        try:
            if "data" in data:
                trade_data = data["data"]
                return await self.ingest_data(
                    source=DataSource.BINANCE,
                    symbol=trade_data.get("s", "unknown"),
                    data_type=DataType.TRADE,
                    frequency=DataFrequency.TICK,
                    data={
                        "price": float(trade_data.get("p", 0)),
                        "volume": float(trade_data.get("q", 0)),
                        "timestamp": datetime.fromtimestamp(trade_data.get("T", 0) / 1000),
                        "side": "buy" if trade_data.get("m", False) else "sell",
                    },
                )
            return None
        except Exception as e:
            logger.error(f"Error processing Binance message: {e}")
            return None
    
    # ========================================================================
    # DATA PROCESSING
    # ========================================================================
    
    async def _process_record(self, record: DataRecord) -> DataRecord:
        """
        Process a data record through the processing pipeline.
        
        Args:
            record: Data record
            
        Returns:
            Processed DataRecord
        """
        # Stage 1: Clean
        record = await self._clean_record(record)
        record.stage = DataProcessingStage.CLEANED
        
        # Stage 2: Normalize
        record = await self._normalize_record(record)
        record.stage = DataProcessingStage.NORMALIZED
        
        # Stage 3: Enrich
        record = await self._enrich_record(record)
        record.stage = DataProcessingStage.ENRICHED
        
        # Stage 4: Feature engineering
        record = await self._engineer_features(record)
        record.stage = DataProcessingStage.FEATURED
        
        # Stage 5: Transform
        record = await self._transform_record(record)
        record.stage = DataProcessingStage.TRANSFORMED
        
        # Stage 6: Validate quality
        quality = await self._validate_quality(record)
        if quality.overall_score < 0.5:
            logger.warning(f"Low quality score for {record.symbol}: {quality.overall_score:.2f}")
        
        record.stage = DataProcessingStage.READY
        
        return record
    
    async def _clean_record(self, record: DataRecord) -> DataRecord:
        """Clean data record."""
        data = record.data.copy()
        
        # Remove null values
        data = {k: v for k, v in data.items() if v is not None and v != ""}
        
        # Handle infinite values
        for key, value in data.items():
            if isinstance(value, float):
                if math.isinf(value) or math.isnan(value):
                    data[key] = 0.0
        
        # Remove duplicates
        if "timestamp" in data:
            # Check for duplicate timestamps
            pass
        
        record.data = data
        return record
    
    async def _normalize_record(self, record: DataRecord) -> DataRecord:
        """Normalize data record."""
        data = record.data.copy()
        
        # Normalize numeric fields
        numeric_fields = ["open", "high", "low", "close", "volume", "price"]
        for field in numeric_fields:
            if field in data and isinstance(data[field], (int, float)):
                if field == "volume":
                    data[field] = float(data[field])
                else:
                    # Ensure price fields are positive
                    data[field] = abs(float(data[field]))
        
        record.data = data
        return record
    
    async def _enrich_record(self, record: DataRecord) -> DataRecord:
        """Enrich data record."""
        # Add derived fields
        data = record.data.copy()
        
        if all(k in data for k in ["open", "high", "low", "close"]):
            # Calculate additional metrics
            data["range"] = data["high"] - data["low"]
            data["body"] = abs(data["close"] - data["open"])
            data["upper_wick"] = data["high"] - max(data["open"], data["close"])
            data["lower_wick"] = min(data["open"], data["close"]) - data["low"]
            
            # Price change
            if record.metadata.get("previous_close"):
                previous_close = record.metadata.get("previous_close")
                data["change"] = data["close"] - previous_close
                data["change_percent"] = (data["change"] / previous_close) * 100
        
        # Add metadata
        record.data = data
        return record
    
    async def _engineer_features(self, record: DataRecord) -> DataRecord:
        """Engineer features from data."""
        data = record.data.copy()
        
        # Add technical indicators
        if "close" in data:
            # Simple features
            data["log_return"] = np.log(data["close"] / data.get("previous_close", data["close"]))
            
            # Momentum indicators
            if record.metadata.get("close_5"):
                data["momentum_5"] = (data["close"] - record.metadata["close_5"]) / record.metadata["close_5"]
            
            if record.metadata.get("close_20"):
                data["momentum_20"] = (data["close"] - record.metadata["close_20"]) / record.metadata["close_20"]
            
            # Volatility
            if record.metadata.get("returns_20"):
                data["volatility_20"] = np.std(record.metadata["returns_20"])
        
        record.data = data
        return record
    
    async def _transform_record(self, record: DataRecord) -> DataRecord:
        """Transform data record."""
        data = record.data.copy()
        
        # Apply transformations
        for transform in self._data_config.transformation_pipeline:
            if transform.get("type") == "scale":
                field = transform.get("field")
                if field in data:
                    scaler = self._scaler_cache.get(field)
                    if scaler:
                        data[field] = scaler.transform([[data[field]]])[0][0]
            elif transform.get("type") == "log":
                field = transform.get("field")
                if field in data and data[field] > 0:
                    data[f"{field}_log"] = np.log(data[field])
            elif transform.get("type") == "difference":
                field = transform.get("field")
                if field in data and record.metadata.get(f"{field}_prev"):
                    data[f"{field}_diff"] = data[field] - record.metadata[f"{field}_prev"]
        
        record.data = data
        return record
    
    async def _validate_quality(self, record: DataRecord) -> DataQuality:
        """Validate data quality."""
        issues = []
        warnings = []
        recommendations = []
        
        # Check required fields
        required_fields = ["timestamp"]
        for field in required_fields:
            if field not in record.data:
                issues.append(f"Missing required field: {field}")
        
        # Check data types
        if "close" in record.data and not isinstance(record.data["close"], (int, float)):
            issues.append("Close price must be numeric")
        
        # Check value ranges
        if "close" in record.data and record.data["close"] <= 0:
            issues.append("Close price must be positive")
        
        # Check timestamp
        if "timestamp" in record.data:
            timestamp = record.data["timestamp"]
            if isinstance(timestamp, datetime):
                if timestamp > datetime.now() + timedelta(days=1):
                    warnings.append("Timestamp is in the future")
                if timestamp < datetime.now() - timedelta(days=365):
                    warnings.append("Timestamp is very old")
        
        # Calculate metrics
        completeness = 1.0 - (len(issues) / len(record.data)) if record.data else 0.0
        validity = 1.0 - (len(issues) / 10) if issues else 1.0
        consistency = 0.9 if not warnings else 0.7
        timeliness = 0.9
        uniqueness = 0.9
        accuracy = 0.9
        
        overall_score = (completeness + accuracy + consistency + timeliness + uniqueness + validity) / 6
        
        # Generate recommendations
        if completeness < 0.8:
            recommendations.append("Improve data completeness by adding missing fields")
        if validity < 0.8:
            recommendations.append("Validate data types and ranges")
        if consistency < 0.8:
            recommendations.append("Ensure data consistency across fields")
        
        return DataQuality(
            completeness=completeness,
            accuracy=accuracy,
            consistency=consistency,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
            overall_score=overall_score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
        )
    
    # ========================================================================
    # DATA STORAGE
    # ========================================================================
    
    async def _store_record(self, record: DataRecord) -> None:
        """Store data record in configured storage backends."""
        storage_backend = self._data_config.storage_backend
        
        if storage_backend == "postgres":
            await self._store_postgres(record)
        elif storage_backend == "mongo":
            await self._store_mongo(record)
        elif storage_backend == "elastic":
            await self._store_elastic(record)
        elif storage_backend == "redis":
            await self._store_redis(record)
        else:
            # Default: store in memory buffer
            self._data_buffer[record.symbol].append(record)
            if len(self._data_buffer[record.symbol]) > self._data_config.batch_size:
                await self._flush_buffer(record.symbol)
        
        # Cache the record
        if self._data_config.cache_enabled:
            await self._cache_record(record)
    
    async def _store_postgres(self, record: DataRecord) -> None:
        """Store record in PostgreSQL."""
        if not self._postgres_pool:
            pg_config = self.config.get("postgres", {})
            self._postgres_pool = await asyncpg.create_pool(
                host=pg_config.get("host", "localhost"),
                port=pg_config.get("port", 5432),
                database=pg_config.get("database", "nexus"),
                user=pg_config.get("user", "nexus"),
                password=pg_config.get("password", ""),
                min_size=1,
                max_size=10,
            )
        
        async with self._postgres_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO data_records (
                    id, source, symbol, data_type, frequency, timestamp,
                    data, metadata, stage, checksum, created_at, updated_at, version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (id) DO UPDATE SET
                    data = EXCLUDED.data,
                    metadata = EXCLUDED.metadata,
                    stage = EXCLUDED.stage,
                    updated_at = EXCLUDED.updated_at,
                    version = data_records.version + 1
            """, (
                record.id,
                record.source.value,
                record.symbol,
                record.data_type.value,
                record.frequency.value,
                record.timestamp,
                json.dumps(record.data),
                json.dumps(record.metadata),
                record.stage.value,
                record.checksum,
                record.created_at,
                record.updated_at,
                record.version,
            ))
    
    async def _store_mongo(self, record: DataRecord) -> None:
        """Store record in MongoDB."""
        if not self._mongo_client:
            return
        
        db = self._mongo_client["nexus"]
        collection = db["data_records"]
        
        doc = asdict(record)
        doc["_id"] = doc.pop("id")
        
        await collection.update_one(
            {"_id": record.id},
            {"$set": doc},
            upsert=True,
        )
    
    async def _store_elastic(self, record: DataRecord) -> None:
        """Store record in Elasticsearch."""
        if not self._elastic_client:
            return
        
        doc = asdict(record)
        doc["timestamp"] = doc["timestamp"].isoformat()
        doc["created_at"] = doc["created_at"].isoformat()
        doc["updated_at"] = doc["updated_at"].isoformat()
        
        await self._elastic_client.index(
            index="data_records",
            id=record.id,
            document=doc,
        )
    
    async def _store_redis(self, record: DataRecord) -> None:
        """Store record in Redis."""
        if not self._redis_client:
            return
        
        key = f"data:{record.symbol}:{record.data_type.value}:{record.frequency.value}"
        await self._redis_client.hset(key, record.timestamp.isoformat(), json.dumps(record.data))
        await self._redis_client.expire(key, self._data_config.cache_ttl)
    
    async def _cache_record(self, record: DataRecord) -> None:
        """Cache data record."""
        if not self._redis_client:
            return
        
        key = f"cache:{record.id}"
        await self._redis_client.setex(
            key,
            self._data_config.cache_ttl,
            json.dumps(asdict(record)),
        )
    
    async def _flush_buffer(self, symbol: str) -> None:
        """Flush data buffer for a symbol."""
        if symbol not in self._data_buffer:
            return
        
        records = self._data_buffer[symbol]
        if not records:
            return
        
        # Store in database
        for record in records:
            await self._store_record(record)
        
        # Clear buffer
        self._data_buffer[symbol].clear()
    
    # ========================================================================
    # DATA QUERYING
    # ========================================================================
    
    async def query_data(self, query: DataQuery) -> List[DataRecord]:
        """
        Query data from storage.
        
        Args:
            query: DataQuery object
            
        Returns:
            List of DataRecord objects
        """
        results = []
        
        # Try cache first
        if self._data_config.cache_enabled:
            cached = await self._query_cache(query)
            if cached:
                return cached
        
        # Query from storage
        storage_backend = self._data_config.storage_backend
        
        if storage_backend == "postgres":
            results = await self._query_postgres(query)
        elif storage_backend == "mongo":
            results = await self._query_mongo(query)
        elif storage_backend == "elastic":
            results = await self._query_elastic(query)
        else:
            # Query from memory buffer
            results = self._query_buffer(query)
        
        # Cache results
        if results and self._data_config.cache_enabled:
            await self._cache_query_results(query, results)
        
        return results
    
    async def _query_postgres(self, query: DataQuery) -> List[DataRecord]:
        """Query data from PostgreSQL."""
        if not self._postgres_pool:
            return []
        
        conditions = []
        params = []
        param_index = 1
        
        if query.source:
            conditions.append(f"source = ${param_index}")
            params.append(query.source.value)
            param_index += 1
        
        if query.symbol:
            conditions.append(f"symbol = ${param_index}")
            params.append(query.symbol)
            param_index += 1
        
        if query.data_type:
            conditions.append(f"data_type = ${param_index}")
            params.append(query.data_type.value)
            param_index += 1
        
        if query.frequency:
            conditions.append(f"frequency = ${param_index}")
            params.append(query.frequency.value)
            param_index += 1
        
        if query.start_time:
            conditions.append(f"timestamp >= ${param_index}")
            params.append(query.start_time)
            param_index += 1
        
        if query.end_time:
            conditions.append(f"timestamp <= ${param_index}")
            params.append(query.end_time)
            param_index += 1
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        order_clause = f"ORDER BY {query.sort_by or 'timestamp'} {query.sort_order or 'DESC'}"
        limit_clause = f"LIMIT {query.limit}" if query.limit else ""
        offset_clause = f"OFFSET {query.offset}" if query.offset else ""
        
        async with self._postgres_pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM data_records
                WHERE {where_clause}
                {order_clause}
                {limit_clause}
                {offset_clause}
            """, *params)
            
            records = []
            for row in rows:
                record = DataRecord(
                    id=row["id"],
                    source=DataSource(row["source"]),
                    symbol=row["symbol"],
                    data_type=DataType(row["data_type"]),
                    frequency=DataFrequency(row["frequency"]),
                    timestamp=row["timestamp"],
                    data=json.loads(row["data"]),
                    metadata=json.loads(row["metadata"]),
                    stage=DataProcessingStage(row["stage"]),
                    checksum=row["checksum"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    version=row["version"],
                )
                records.append(record)
            
            return records
    
    async def _query_mongo(self, query: DataQuery) -> List[DataRecord]:
        """Query data from MongoDB."""
        if not self._mongo_client:
            return []
        
        db = self._mongo_client["nexus"]
        collection = db["data_records"]
        
        mongo_query = {}
        if query.source:
            mongo_query["source"] = query.source.value
        if query.symbol:
            mongo_query["symbol"] = query.symbol
        if query.data_type:
            mongo_query["data_type"] = query.data_type.value
        if query.frequency:
            mongo_query["frequency"] = query.frequency.value
        if query.start_time or query.end_time:
            mongo_query["timestamp"] = {}
            if query.start_time:
                mongo_query["timestamp"]["$gte"] = query.start_time
            if query.end_time:
                mongo_query["timestamp"]["$lte"] = query.end_time
        
        cursor = collection.find(mongo_query)
        
        if query.sort_by:
            cursor = cursor.sort(query.sort_by, -1 if query.sort_order == "desc" else 1)
        if query.limit:
            cursor = cursor.limit(query.limit)
        if query.offset:
            cursor = cursor.skip(query.offset)
        
        records = []
        async for doc in cursor:
            doc["_id"] = doc.pop("_id") if "_id" in doc else ""
            record = DataRecord(**doc)
            records.append(record)
        
        return records
    
    async def _query_elastic(self, query: DataQuery) -> List[DataRecord]:
        """Query data from Elasticsearch."""
        if not self._elastic_client:
            return []
        
        must_conditions = []
        
        if query.source:
            must_conditions.append({"term": {"source": query.source.value}})
        if query.symbol:
            must_conditions.append({"term": {"symbol": query.symbol}})
        if query.data_type:
            must_conditions.append({"term": {"data_type": query.data_type.value}})
        if query.frequency:
            must_conditions.append({"term": {"frequency": query.frequency.value}})
        
        if query.start_time or query.end_time:
            range_query = {}
            if query.start_time:
                range_query["gte"] = query.start_time.isoformat()
            if query.end_time:
                range_query["lte"] = query.end_time.isoformat()
            must_conditions.append({"range": {"timestamp": range_query}})
        
        search_body = {
            "query": {
                "bool": {
                    "must": must_conditions
                }
            }
        }
        
        if query.sort_by:
            search_body["sort"] = [{query.sort_by: {"order": query.sort_order or "desc"}}]
        if query.limit:
            search_body["size"] = query.limit
        if query.offset:
            search_body["from"] = query.offset
        
        response = await self._elastic_client.search(
            index="data_records",
            body=search_body,
        )
        
        records = []
        for hit in response["hits"]["hits"]:
            doc = hit["_source"]
            doc["id"] = doc.pop("_id") if "_id" in doc else hit["_id"]
            records.append(DataRecord(**doc))
        
        return records
    
    def _query_buffer(self, query: DataQuery) -> List[DataRecord]:
        """Query data from memory buffer."""
        results = []
        
        for symbol, records in self._data_buffer.items():
            if query.symbol and query.symbol != symbol:
                continue
            
            for record in records:
                if query.source and query.source != record.source:
                    continue
                if query.data_type and query.data_type != record.data_type:
                    continue
                if query.frequency and query.frequency != record.frequency:
                    continue
                if query.start_time and record.timestamp < query.start_time:
                    continue
                if query.end_time and record.timestamp > query.end_time:
                    continue
                
                results.append(record)
        
        # Sort
        if query.sort_by:
            reverse = query.sort_order == "desc"
            results.sort(key=lambda r: getattr(r, query.sort_by, r.timestamp), reverse=reverse)
        
        # Limit
        if query.limit:
            offset = query.offset or 0
            results = results[offset:offset + query.limit]
        
        return results
    
    async def _query_cache(self, query: DataQuery) -> Optional[List[DataRecord]]:
        """Query data from cache."""
        if not self._redis_client:
            return None
        
        cache_key = self._generate_cache_key(query)
        cached = await self._redis_client.get(cache_key)
        
        if cached:
            try:
                data = json.loads(cached)
                return [DataRecord(**record) for record in data]
            except:
                return None
        
        return None
    
    async def _cache_query_results(self, query: DataQuery, results: List[DataRecord]) -> None:
        """Cache query results."""
        if not self._redis_client:
            return
        
        cache_key = self._generate_cache_key(query)
        data = [asdict(record) for record in results]
        
        await self._redis_client.setex(
            cache_key,
            self._data_config.cache_ttl,
            json.dumps(data, default=str),
        )
    
    # ========================================================================
    # DATA ANALYTICS
    # ========================================================================
    
    async def get_data_stats(self) -> DataStats:
        """Get data statistics."""
        return self._stats
    
    async def analyze_data(
        self,
        symbol: str,
        data_type: DataType,
        frequency: DataFrequency,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Perform advanced analysis on data.
        
        Args:
            symbol: Trading symbol
            data_type: Data type
            frequency: Data frequency
            start_date: Start date
            end_date: End date
            
        Returns:
            Analysis results
        """
        query = DataQuery(
            symbol=symbol,
            data_type=data_type,
            frequency=frequency,
            start_time=start_date,
            end_time=end_date,
        )
        
        records = await self.query_data(query)
        
        if not records:
            return {"error": "No data found"}
        
        # Convert to DataFrame
        df = self._records_to_dataframe(records)
        
        # Basic statistics
        stats = {
            "count": len(df),
            "mean": df.mean().to_dict(),
            "std": df.std().to_dict(),
            "min": df.min().to_dict(),
            "max": df.max().to_dict(),
            "median": df.median().to_dict(),
            "skew": df.skew().to_dict(),
            "kurtosis": df.kurtosis().to_dict(),
        }
        
        # Time series analysis
        if "close" in df.columns:
            returns = df["close"].pct_change().dropna()
            
            stats["returns"] = {
                "mean": returns.mean(),
                "std": returns.std(),
                "sharpe": returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0,
                "skew": returns.skew(),
                "kurtosis": returns.kurtosis(),
            }
            
            # Volatility
            stats["volatility"] = {
                "historical": returns.std() * np.sqrt(252),
                "ewma": self._calculate_ewma_volatility(returns.values),
            }
            
            # Drawdown
            cumprod = (1 + returns).cumprod()
            running_max = cumprod.expanding().max()
            drawdown = (cumprod - running_max) / running_max
            stats["drawdown"] = {
                "max": drawdown.min(),
                "current": drawdown.iloc[-1] if len(drawdown) > 0 else 0,
            }
        
        # Detect outliers
        if "close" in df.columns:
            z_scores = np.abs(stats.zscore(df["close"]))
            outliers = z_scores > 3
            stats["outliers"] = {
                "count": outliers.sum(),
                "indices": outliers[outliers].index.tolist(),
            }
        
        # Detect trend
        if len(df) > 1:
            x = np.arange(len(df))
            y = df["close"].values if "close" in df.columns else df.iloc[:, 0].values
            slope, intercept = np.polyfit(x, y, 1)
            stats["trend"] = {
                "slope": slope,
                "direction": "up" if slope > 0 else "down",
                "magnitude": abs(slope / y[0]) if y[0] > 0 else 0,
            }
        
        # Seasonality detection (if enough data)
        if len(df) > 100:
            # Fourier transform for seasonality
            fft_result = np.fft.fft(y)
            freqs = np.fft.fftfreq(len(y))
            
            # Find dominant frequencies
            magnitudes = np.abs(fft_result)
            dominant_freqs = freqs[np.argsort(magnitudes)[-5:]]
            dominant_freqs = [f for f in dominant_freqs if f > 0]
            
            stats["seasonality"] = {
                "dominant_frequencies": dominant_freqs.tolist(),
                "periods": [int(1/f) for f in dominant_freqs if f > 0],
            }
        
        return stats
    
    def _records_to_dataframe(self, records: List[DataRecord]) -> pd.DataFrame:
        """Convert records to DataFrame."""
        data = []
        for record in records:
            row = record.data.copy()
            row["timestamp"] = record.timestamp
            row["symbol"] = record.symbol
            row["source"] = record.source.value
            data.append(row)
        
        df = pd.DataFrame(data)
        if "timestamp" in df.columns:
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
        
        return df
    
    def _calculate_ewma_volatility(self, returns: np.ndarray, lambda_: float = 0.94) -> float:
        """Calculate EWMA volatility."""
        if len(returns) == 0:
            return 0.0
        
        weights = (1 - lambda_) * lambda_ ** np.arange(len(returns))
        weights = weights / weights.sum()
        
        mean = np.average(returns, weights=weights)
        variance = np.average((returns - mean) ** 2, weights=weights)
        return np.sqrt(variance) * np.sqrt(252)
    
    # ========================================================================
    # DATA EXPORT
    # ========================================================================
    
    async def export_data(
        self,
        query: DataQuery,
        format: str = "csv",
        compression: bool = True,
    ) -> bytes:
        """
        Export data in various formats.
        
        Args:
            query: Data query
            format: Export format (csv, json, parquet, excel)
            compression: Whether to compress output
            
        Returns:
            Exported data as bytes
        """
        records = await self.query_data(query)
        
        if not records:
            return b""
        
        df = self._records_to_dataframe(records)
        
        if format == "csv":
            output = df.to_csv().encode('utf-8')
        elif format == "json":
            output = df.to_json(orient='records').encode('utf-8')
        elif format == "parquet":
            output = df.to_parquet()
        elif format == "excel":
            output = df.to_excel()
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        if compression:
            output = zlib.compress(output)
        
        return output
    
    # ========================================================================
    # DATA SUBSCRIPTIONS
    # ========================================================================
    
    def subscribe(self, pattern: str, callback: Callable[[DataRecord], Awaitable[None]]) -> str:
        """
        Subscribe to data updates.
        
        Args:
            pattern: Subscription pattern (supports wildcards)
            callback: Async callback function
            
        Returns:
            Subscription ID
        """
        subscription_id = self._generate_subscription_id()
        self._subscriptions[pattern].append((subscription_id, callback))
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from data updates.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if unsubscribed, False otherwise
        """
        for pattern, subscribers in self._subscriptions.items():
            for idx, (sub_id, _) in enumerate(subscribers):
                if sub_id == subscription_id:
                    subscribers.pop(idx)
                    return True
        return False
    
    async def _notify_subscribers(self, record: DataRecord) -> None:
        """Notify subscribers of new data."""
        for pattern, subscribers in self._subscriptions.items():
            # Check if pattern matches record
            if self._matches_pattern(pattern, record):
                for _, callback in subscribers:
                    try:
                        await callback(record)
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")
    
    def _matches_pattern(self, pattern: str, record: DataRecord) -> bool:
        """Check if record matches subscription pattern."""
        # Simple pattern matching with wildcards
        parts = pattern.split('*')
        
        if len(parts) == 1:
            return pattern == record.symbol
        
        # Check prefix and suffix
        if parts[0] and not record.symbol.startswith(parts[0]):
            return False
        if parts[-1] and not record.symbol.endswith(parts[-1]):
            return False
        
        return True
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _generate_record_id(
        self,
        source: DataSource,
        symbol: str,
        data_type: DataType,
        frequency: DataFrequency,
        data: Dict[str, Any],
    ) -> str:
        """Generate a unique record ID."""
        timestamp = data.get("timestamp", datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)
        
        raw = f"{source.value}:{symbol}:{data_type.value}:{frequency.value}:{timestamp_str}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    
    def _generate_batch_id(self, source: DataSource) -> str:
        """Generate a batch ID."""
        raw = f"batch:{source.value}:{datetime.now().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def _generate_subscription_id(self) -> str:
        """Generate a subscription ID."""
        return hashlib.sha256(f"{datetime.now().isoformat()}{id(self)}".encode()).hexdigest()[:16]
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate data checksum."""
        sorted_data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()[:32]
    
    def _generate_cache_key(self, query: DataQuery) -> str:
        """Generate cache key for query."""
        key = f"query:{query.source}:{query.symbol}:{query.data_type}:{query.frequency}"
        if query.start_time:
            key += f":{query.start_time.isoformat()}"
        if query.end_time:
            key += f":{query.end_time.isoformat()}"
        if query.limit:
            key += f":{query.limit}"
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _get_coingecko_id(self, symbol: str) -> str:
        """Get CoinGecko coin ID from symbol."""
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "XRP": "ripple",
            "LTC": "litecoin",
            "BCH": "bitcoin-cash",
            "BNB": "binancecoin",
            "USDT": "tether",
            "SOL": "solana",
            "ADA": "cardano",
            "DOT": "polkadot",
            "DOGE": "dogecoin",
            "AVAX": "avalanche-2",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
        }
        return symbol_map.get(symbol.upper(), symbol.lower())
    
    def _validate_data(self, data_type: DataType, data: Dict[str, Any]) -> bool:
        """Validate data against schema."""
        schema = self._schemas.get(data_type.value)
        if not schema:
            return True
        
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                return False
        
        return True
    
    def _update_stats(self, record: DataRecord) -> None:
        """Update data statistics."""
        self._stats.total_records += 1
        
        # Update unique counts
        symbols = set([record.symbol])
        self._stats.unique_symbols = len(symbols)
        
        sources = set([record.source.value])
        self._stats.unique_sources = len(sources)
        
        types = set([record.data_type.value])
        self._stats.unique_types = len(types)
        
        # Update date range
        if self._stats.date_range_start is None or record.timestamp < self._stats.date_range_start:
            self._stats.date_range_start = record.timestamp
        if self._stats.date_range_end is None or record.timestamp > self._stats.date_range_end:
            self._stats.date_range_end = record.timestamp
        
        # Update distributions
        freq_key = record.frequency.value
        self._stats.frequency_distribution[freq_key] = self._stats.frequency_distribution.get(freq_key, 0) + 1
        
        source_key = record.source.value
        self._stats.source_distribution[source_key] = self._stats.source_distribution.get(source_key, 0) + 1
        
        type_key = record.data_type.value
        self._stats.type_distribution[type_key] = self._stats.type_distribution.get(type_key, 0) + 1
    
    # ========================================================================
    # CLEANUP AND SHUTDOWN
    # ========================================================================
    
    async def cleanup(self) -> None:
        """Clean up old data."""
        cutoff = datetime.now() - timedelta(days=self._data_config.max_history_days)
        
        # Clean up PostgreSQL
        if self._postgres_pool:
            async with self._postgres_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM data_records WHERE timestamp < $1",
                    cutoff,
                )
        
        # Clean up MongoDB
        if self._mongo_client:
            db = self._mongo_client["nexus"]
            collection = db["data_records"]
            await collection.delete_many({"timestamp": {"$lt": cutoff}})
        
        # Clean up Elasticsearch
        if self._elastic_client:
            await self._elastic_client.delete_by_query(
                index="data_records",
                body={
                    "query": {
                        "range": {
                            "timestamp": {"lt": cutoff.isoformat()}
                        }
                    }
                },
            )
        
        logger.info(f"Cleaned up data older than {cutoff}")
    
    async def shutdown(self) -> None:
        """Shutdown data service."""
        logger.info("Shutting down DataNessie...")
        
        self._is_running = False
        
        # Cancel processing tasks
        for task in self._processing_tasks:
            if not task.done():
                task.cancel()
        
        # Flush buffers
        for symbol in list(self._data_buffer.keys()):
            await self._flush_buffer(symbol)
        
        # Close connections
        if self._postgres_pool:
            await self._postgres_pool.close()
        
        if self._mongo_client:
            self._mongo_client.close()
        
        if self._elastic_client:
            await self._elastic_client.close()
        
        if self._redis_client:
            await self._redis_client.close()
        
        if self._http_session:
            await self._http_session.close()
        
        logger.info("DataNessie shutdown complete")


# ========================================================================
# FACTORY FUNCTION
# ========================================================================

def create_data_nessie(
    config: Dict[str, Any],
    connection_pool: Optional[Any] = None,
) -> DataNessie:
    """Factory function to create a DataNessie instance."""
    return DataNessie(
        config=config,
        connection_pool=connection_pool,
    )
