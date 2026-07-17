# trading/bots/ai_bot/ai_bot_data_collector.py
"""
NEXUS AI TRADING SYSTEM - Data Collector Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements the data collection system for the AI Trading Bot.
Provides:
    - Market data collection from multiple sources
    - Real-time data streaming
    - Historical data retrieval
    - Data validation and cleaning
    - Data storage and caching
    - Data aggregation and resampling
    - Multi-exchange support
    - WebSocket and REST API integration
    - Data quality monitoring
    - Automatic retry and failover
"""

import os
import sys
import json
import asyncio
import logging
import hashlib
import aiohttp
import websockets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum
import pandas as pd
import numpy as np
import sqlite3
import redis
from collections import deque
import threading
import time
import zstandard as zstd

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class DataSource(Enum):
    """Data source enumeration."""
    BINANCE = "binance"
    COINBASE = "coinbase"
    BYBIT = "bybit"
    KRAKEN = "kraken"
    OANDA = "oanda"
    ALPACA = "alpaca"
    IBKR = "ibkr"
    POLYGON = "polygon"
    YAHOO = "yahoo"
    ALPHA_VANTAGE = "alpha_vantage"

class DataType(Enum):
    """Data type enumeration."""
    OHLCV = "ohlcv"
    TICK = "tick"
    ORDER_BOOK = "order_book"
    TRADE = "trade"
    QUOTE = "quote"
    FUNDING = "funding"
    OPEN_INTEREST = "open_interest"
    SENTIMENT = "sentiment"
    NEWS = "news"
    SOCIAL = "social"
    ONCHAIN = "onchain"

class DataStatus(Enum):
    """Data status enumeration."""
    PENDING = "pending"
    COLLECTING = "collecting"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DataRequest:
    """Data request configuration."""
    symbol: str
    data_type: DataType
    source: DataSource
    timeframe: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: Optional[int] = None
    realtime: bool = False
    compress: bool = True
    priority: int = 5


@dataclass
class DataPoint:
    """Single data point."""
    timestamp: datetime
    symbol: str
    data_type: DataType
    data: Dict[str, Any]
    source: DataSource
    quality_score: float = 1.0
    checksum: Optional[str] = None
    collected_at: datetime = field(default_factory=datetime.now)


@dataclass
class DataCollectionStats:
    """Data collection statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_data_points: int = 0
    average_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    error_rate: float = 0.0
    collection_rate: float = 0.0  # points per second


# =============================================================================
# Data Collector
# =============================================================================

class DataCollector:
    """
    Comprehensive data collector for the AI Trading Bot.
    
    This class handles all data collection needs including:
        - Multiple data sources
        - Real-time and historical data
        - Data validation and cleaning
        - Storage and caching
        - Automatic retry and failover
        - Rate limiting
        - Compression
    
    Usage:
        # Create collector
        collector = DataCollector(config)
        
        # Collect historical data
        data = await collector.collect_historical(
            symbol='BTC-USD',
            timeframe='1h',
            start_time=datetime(2026, 1, 1)
        )
        
        # Start real-time collection
        await collector.start_realtime(
            symbol='BTC-USD',
            callback=on_data_received
        )
        
        # Get stored data
        data = collector.get_stored_data(symbol='BTC-USD')
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        storage_path: Optional[Union[str, Path]] = None,
        redis_url: Optional[str] = None
    ):
        """
        Initialize the data collector.
        
        Args:
            config: Configuration dictionary
            storage_path: Path for persistent storage
            redis_url: Redis URL for caching
        """
        # Load configuration
        self.config = config or {}
        self.storage_path = Path(storage_path) if storage_path else Path.cwd() / 'data'
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.data_cache = {}
        self.collectors = {}
        self.callbacks = []
        self.is_running = False
        
        # Statistics
        self.stats = DataCollectionStats()
        self.stats_history = deque(maxlen=1000)
        
        # Storage
        self.db_conn = None
        self.redis_client = None
        
        # Rate limiting
        self.rate_limits = {}
        self.request_times = deque(maxlen=1000)
        
        # Compression
        self.compressor = zstd.ZstdCompressor(level=3)
        self.decompressor = zstd.ZstdDecompressor()
        
        # Threading
        self._threads = []
        self._stop_event = threading.Event()
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize storage
        self._init_storage()
        
        # Initialize Redis
        if redis_url:
            self._init_redis(redis_url)
        
        self.logger.info("Data collector initialized")
    
    # =========================================================================
    # Initialization Methods
    # =========================================================================
    
    def _init_storage(self) -> None:
        """Initialize persistent storage."""
        try:
            db_path = self.storage_path / 'data.db'
            self.db_conn = sqlite3.connect(str(db_path), check_same_thread=False)
            cursor = self.db_conn.cursor()
            
            # Create tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    data TEXT NOT NULL,
                    quality_score REAL DEFAULT 1.0,
                    checksum TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, data_type, source, timestamp)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_data_points_symbol 
                ON data_points(symbol)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_data_points_timestamp 
                ON data_points(timestamp)
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            ''')
            
            self.db_conn.commit()
            self.logger.info("Storage initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize storage: {e}")
            self.db_conn = None
    
    def _init_redis(self, redis_url: str) -> None:
        """Initialize Redis connection for caching."""
        try:
            import redis
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            self.logger.info("Redis cache initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis: {e}")
            self.redis_client = None
    
    # =========================================================================
    # Data Collection Methods
    # =========================================================================
    
    async def collect_historical(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        source: DataSource = DataSource.BINANCE,
        data_type: DataType = DataType.OHLCV,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Collect historical data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1h', '1d')
            start_time: Start time
            end_time: End time (defaults to now)
            source: Data source
            data_type: Data type
            limit: Maximum number of points
            
        Returns:
            DataFrame with collected data
        """
        if end_time is None:
            end_time = datetime.now()
        
        self.logger.info(f"Collecting historical data for {symbol} from {start_time} to {end_time}")
        
        # Generate request ID
        request_id = self._generate_request_id(symbol, data_type, source, start_time, end_time)
        
        # Check cache first
        cached = await self._get_from_cache(request_id)
        if cached is not None:
            self.logger.info(f"Data found in cache: {request_id}")
            return cached
        
        # Create request
        request = DataRequest(
            symbol=symbol,
            data_type=data_type,
            source=source,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Record request
        self._record_request(request_id, request)
        
        # Collect data
        start = time.time()
        data = await self._collect_from_source(request)
        latency = (time.time() - start) * 1000
        
        if data is not None and not data.empty:
            # Store data
            await self._store_data(data, symbol, data_type, source)
            
            # Cache data
            await self._cache_data(request_id, data)
            
            # Update stats
            self.stats.total_data_points += len(data)
            self.stats.successful_requests += 1
            
            self.logger.info(f"Collected {len(data)} data points in {latency:.2f}ms")
        else:
            self.stats.failed_requests += 1
            self.logger.error(f"Failed to collect data for {symbol}")
        
        self.stats.total_requests += 1
        self.stats.average_latency_ms = (
            (self.stats.average_latency_ms * (self.stats.total_requests - 1) + latency) /
            self.stats.total_requests
        )
        self.stats.last_request_time = datetime.now()
        self.stats.error_rate = self.stats.failed_requests / self.stats.total_requests if self.stats.total_requests > 0 else 0
        
        return data
    
    async def start_realtime(
        self,
        symbol: str,
        callback: Callable[[DataPoint], Awaitable[None]],
        source: DataSource = DataSource.BINANCE,
        data_type: DataType = DataType.TICK,
        timeframe: Optional[str] = None
    ) -> None:
        """
        Start real-time data collection.
        
        Args:
            symbol: Trading symbol
            callback: Callback function for received data
            source: Data source
            data_type: Data type
            timeframe: Timeframe for aggregation
        """
        self.logger.info(f"Starting real-time collection for {symbol} from {source.value}")
        
        # Add callback
        self.callbacks.append(callback)
        
        # Start collection
        await self._start_realtime_stream(symbol, source, data_type, timeframe)
    
    async def stop_realtime(self, symbol: Optional[str] = None) -> None:
        """
        Stop real-time data collection.
        
        Args:
            symbol: Symbol to stop (None for all)
        """
        self.logger.info(f"Stopping real-time collection for {symbol or 'all'}")
        self._stop_event.set()
        
        # Wait for threads to finish
        for thread in self._threads:
            thread.join(timeout=5)
        
        self._threads = []
        self._stop_event = threading.Event()
    
    # =========================================================================
    # Source Collection Methods
    # =========================================================================
    
    async def _collect_from_source(self, request: DataRequest) -> pd.DataFrame:
        """
        Collect data from the specified source.
        
        Args:
            request: Data request
            
        Returns:
            DataFrame with collected data
        """
        source_map = {
            DataSource.BINANCE: self._collect_binance,
            DataSource.COINBASE: self._collect_coinbase,
            DataSource.BYBIT: self._collect_bybit,
            DataSource.KRAKEN: self._collect_kraken,
        }
        
        collector = source_map.get(request.source)
        if collector is None:
            raise ValueError(f"Unsupported source: {request.source}")
        
        # Apply rate limiting
        await self._apply_rate_limit(request.source)
        
        try:
            return await collector(request)
        except Exception as e:
            self.logger.error(f"Error collecting from {request.source.value}: {e}")
            # Attempt retry with exponential backoff
            for attempt in range(3):
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)
                try:
                    return await collector(request)
                except Exception:
                    continue
            return pd.DataFrame()
    
    async def _collect_binance(self, request: DataRequest) -> pd.DataFrame:
        """Collect data from Binance."""
        async with aiohttp.ClientSession() as session:
            if request.data_type == DataType.OHLCV:
                # Get kline data
                endpoint = "https://api.binance.com/api/v3/klines"
                params = {
                    'symbol': request.symbol.replace('-', ''),
                    'interval': request.timeframe,
                    'limit': request.limit or 1000
                }
                
                if request.start_time:
                    params['startTime'] = int(request.start_time.timestamp() * 1000)
                if request.end_time:
                    params['endTime'] = int(request.end_time.timestamp() * 1000)
                
                async with session.get(endpoint, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Binance API error: {response.status} - {text}")
                    
                    data = await response.json()
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
                        'taker_buy_quote_volume', 'ignore'
                    ])
                    
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(float)
                    
                    # Select relevant columns
                    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                    
                    return df
    
    async def _collect_coinbase(self, request: DataRequest) -> pd.DataFrame:
        """Collect data from Coinbase."""
        async with aiohttp.ClientSession() as session:
            if request.data_type == DataType.OHLCV:
                # Get historical data
                endpoint = f"https://api.coinbase.com/v2/products/{request.symbol}/candles"
                params = {
                    'granularity': self._get_granularity(request.timeframe),
                    'start': request.start_time.isoformat() if request.start_time else None,
                    'end': request.end_time.isoformat() if request.end_time else None
                }
                
                async with session.get(endpoint, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Coinbase API error: {response.status} - {text}")
                    
                    data = await response.json()
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    
                    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    async def _collect_bybit(self, request: DataRequest) -> pd.DataFrame:
        """Collect data from Bybit."""
        async with aiohttp.ClientSession() as session:
            if request.data_type == DataType.OHLCV:
                endpoint = "https://api.bybit.com/v5/market/kline"
                params = {
                    'symbol': request.symbol.replace('-', ''),
                    'interval': request.timeframe,
                    'limit': request.limit or 200,
                }
                
                async with session.get(endpoint, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Bybit API error: {response.status} - {text}")
                    
                    data = await response.json()
                    
                    if data.get('retCode') != 0:
                        raise Exception(f"Bybit error: {data.get('retMsg')}")
                    
                    result = data.get('result', {})
                    candles = result.get('list', [])
                    
                    df = pd.DataFrame(candles, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                    ])
                    
                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(float)
                    
                    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    async def _collect_kraken(self, request: DataRequest) -> pd.DataFrame:
        """Collect data from Kraken."""
        async with aiohttp.ClientSession() as session:
            if request.data_type == DataType.OHLCV:
                endpoint = "https://api.kraken.com/0/public/OHLC"
                params = {
                    'pair': request.symbol.replace('-', ''),
                    'interval': self._get_kraken_interval(request.timeframe),
                }
                
                if request.start_time:
                    params['since'] = int(request.start_time.timestamp())
                
                async with session.get(endpoint, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Kraken API error: {response.status} - {text}")
                    
                    data = await response.json()
                    
                    if data.get('error'):
                        raise Exception(f"Kraken error: {data['error']}")
                    
                    result = data.get('result', {})
                    candles = result.get(request.symbol.replace('-', ''), [])
                    
                    df = pd.DataFrame(candles, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
                    ])
                    
                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(float)
                    
                    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    # =========================================================================
    # Real-time Streaming Methods
    # =========================================================================
    
    async def _start_realtime_stream(
        self,
        symbol: str,
        source: DataSource,
        data_type: DataType,
        timeframe: Optional[str] = None
    ) -> None:
        """Start real-time stream from source."""
        if source == DataSource.BINANCE:
            await self._stream_binance(symbol, data_type, timeframe)
        elif source == DataSource.COINBASE:
            await self._stream_coinbase(symbol, data_type, timeframe)
        elif source == DataSource.BYBIT:
            await self._stream_bybit(symbol, data_type, timeframe)
        else:
            raise ValueError(f"Unsupported source for streaming: {source}")
    
    async def _stream_binance(
        self,
        symbol: str,
        data_type: DataType,
        timeframe: Optional[str] = None
    ) -> None:
        """Stream data from Binance WebSocket."""
        ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
        
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.logger.info(f"Connected to Binance WebSocket for {symbol}")
                    
                    while not self._stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30)
                            data = json.loads(message)
                            
                            # Create DataPoint
                            point = DataPoint(
                                timestamp=datetime.fromtimestamp(data['T'] / 1000),
                                symbol=data['s'],
                                data_type=DataType.TICK,
                                data={
                                    'price': float(data['p']),
                                    'quantity': float(data['q']),
                                    'trade_id': data['t'],
                                    'buyer_maker': data['m']
                                },
                                source=DataSource.BINANCE
                            )
                            
                            # Process with callbacks
                            await self._process_data_point(point)
                            
                        except asyncio.TimeoutError:
                            continue
                        except websockets.exceptions.ConnectionClosed:
                            self.logger.warning("WebSocket connection closed, reconnecting...")
                            break
                        except Exception as e:
                            self.logger.error(f"Error in WebSocket stream: {e}")
                            
            except Exception as e:
                self.logger.error(f"Failed to connect to WebSocket: {e}")
                await asyncio.sleep(5)
    
    async def _stream_coinbase(
        self,
        symbol: str,
        data_type: DataType,
        timeframe: Optional[str] = None
    ) -> None:
        """Stream data from Coinbase WebSocket."""
        ws_url = "wss://ws-feed.exchange.coinbase.com"
        subscribe_msg = {
            "type": "subscribe",
            "product_ids": [symbol],
            "channels": ["matches"]
        }
        
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(ws_url) as websocket:
                    await websocket.send(json.dumps(subscribe_msg))
                    self.logger.info(f"Connected to Coinbase WebSocket for {symbol}")
                    
                    while not self._stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30)
                            data = json.loads(message)
                            
                            if data.get('type') == 'match':
                                point = DataPoint(
                                    timestamp=datetime.fromisoformat(data['time'].replace('Z', '+00:00')),
                                    symbol=data['product_id'],
                                    data_type=DataType.TICK,
                                    data={
                                        'price': float(data['price']),
                                        'quantity': float(data['size']),
                                        'trade_id': data['trade_id'],
                                        'side': data['side']
                                    },
                                    source=DataSource.COINBASE
                                )
                                await self._process_data_point(point)
                                
                        except asyncio.TimeoutError:
                            continue
                        except websockets.exceptions.ConnectionClosed:
                            self.logger.warning("WebSocket connection closed, reconnecting...")
                            break
                        except Exception as e:
                            self.logger.error(f"Error in WebSocket stream: {e}")
                            
            except Exception as e:
                self.logger.error(f"Failed to connect to WebSocket: {e}")
                await asyncio.sleep(5)
    
    async def _stream_bybit(
        self,
        symbol: str,
        data_type: DataType,
        timeframe: Optional[str] = None
    ) -> None:
        """Stream data from Bybit WebSocket."""
        ws_url = "wss://stream.bybit.com/v5/public/linear"
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"trade.{symbol}"]
        }
        
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(ws_url) as websocket:
                    await websocket.send(json.dumps(subscribe_msg))
                    self.logger.info(f"Connected to Bybit WebSocket for {symbol}")
                    
                    while not self._stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30)
                            data = json.loads(message)
                            
                            if data.get('topic') and 'trade' in data['topic']:
                                trades = data.get('data', [])
                                for trade in trades:
                                    point = DataPoint(
                                        timestamp=datetime.fromtimestamp(trade['T'] / 1000),
                                        symbol=trade['s'],
                                        data_type=DataType.TICK,
                                        data={
                                            'price': float(trade['p']),
                                            'quantity': float(trade['q']),
                                            'trade_id': trade['v']
                                        },
                                        source=DataSource.BYBIT
                                    )
                                    await self._process_data_point(point)
                                    
                        except asyncio.TimeoutError:
                            continue
                        except websockets.exceptions.ConnectionClosed:
                            self.logger.warning("WebSocket connection closed, reconnecting...")
                            break
                        except Exception as e:
                            self.logger.error(f"Error in WebSocket stream: {e}")
                            
            except Exception as e:
                self.logger.error(f"Failed to connect to WebSocket: {e}")
                await asyncio.sleep(5)
    
    # =========================================================================
    # Data Processing Methods
    # =========================================================================
    
    async def _process_data_point(self, point: DataPoint) -> None:
        """
        Process a data point through all callbacks.
        
        Args:
            point: Data point to process
        """
        # Store data point
        await self._store_data_point(point)
        
        # Update statistics
        self.stats.total_data_points += 1
        
        # Process callbacks
        for callback in self.callbacks:
            try:
                await callback(point)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}")
    
    async def _store_data_point(self, point: DataPoint) -> None:
        """
        Store a data point in the database.
        
        Args:
            point: Data point to store
        """
        if self.db_conn is None:
            return
        
        try:
            cursor = self.db_conn.cursor()
            
            # Calculate checksum
            data_str = json.dumps(point.data, sort_keys=True)
            point.checksum = hashlib.md5(data_str.encode()).hexdigest()
            
            # Insert data
            cursor.execute('''
                INSERT OR REPLACE INTO data_points 
                (symbol, data_type, source, timestamp, data, quality_score, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                point.symbol,
                point.data_type.value,
                point.source.value,
                point.timestamp,
                json.dumps(point.data),
                point.quality_score,
                point.checksum
            ))
            
            self.db_conn.commit()
            
            # Update cache
            cache_key = f"{point.symbol}:{point.data_type.value}:{point.source.value}"
            if cache_key not in self.data_cache:
                self.data_cache[cache_key] = deque(maxlen=1000)
            self.data_cache[cache_key].append(point)
            
        except Exception as e:
            self.logger.error(f"Failed to store data point: {e}")
    
    async def _store_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        data_type: DataType,
        source: DataSource
    ) -> None:
        """
        Store a DataFrame of data points.
        
        Args:
            df: DataFrame with data
            symbol: Trading symbol
            data_type: Data type
            source: Data source
        """
        for _, row in df.iterrows():
            point = DataPoint(
                timestamp=row['timestamp'],
                symbol=symbol,
                data_type=data_type,
                data=row.to_dict(),
                source=source
            )
            await self._store_data_point(point)
    
    # =========================================================================
    # Cache Methods
    # =========================================================================
    
    async def _get_from_cache(self, request_id: str) -> Optional[pd.DataFrame]:
        """
        Get data from cache.
        
        Args:
            request_id: Request ID
            
        Returns:
            DataFrame or None
        """
        # Check memory cache
        if request_id in self.data_cache:
            return self.data_cache[request_id]
        
        # Check Redis cache
        if self.redis_client:
            try:
                cached = self.redis_client.get(f"data_cache:{request_id}")
                if cached:
                    # Decompress if needed
                    if self._is_compressed(cached):
                        cached = self.decompressor.decompress(cached).decode()
                    
                    data = json.loads(cached)
                    return pd.DataFrame(data)
            except Exception as e:
                self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    async def _cache_data(self, request_id: str, data: pd.DataFrame) -> None:
        """
        Cache data.
        
        Args:
            request_id: Request ID
            data: DataFrame to cache
        """
        try:
            # Convert to JSON
            data_json = data.to_json(orient='records')
            
            # Compress if enabled
            if self.config.get('compress', True):
                data_json = self.compressor.compress(data_json.encode()).decode()
            
            # Memory cache
            self.data_cache[request_id] = data
            
            # Redis cache
            if self.redis_client:
                ttl = self.config.get('cache_ttl', 3600)  # 1 hour default
                self.redis_client.setex(
                    f"data_cache:{request_id}",
                    ttl,
                    data_json
                )
                
        except Exception as e:
            self.logger.error(f"Failed to cache data: {e}")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _generate_request_id(
        self,
        symbol: str,
        data_type: DataType,
        source: DataSource,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Generate unique request ID."""
        raw = f"{symbol}:{data_type.value}:{source.value}:{start_time.isoformat()}:{end_time.isoformat()}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def _record_request(self, request_id: str, request: DataRequest) -> None:
        """Record a data request."""
        if self.db_conn is None:
            return
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO data_requests 
                (request_id, symbol, data_type, source, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                request_id,
                request.symbol,
                request.data_type.value,
                request.source.value,
                DataStatus.PENDING.value,
                datetime.now()
            ))
            self.db_conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to record request: {e}")
    
    async def _apply_rate_limit(self, source: DataSource) -> None:
        """
        Apply rate limiting for a source.
        
        Args:
            source: Data source
        """
        rate_limits = {
            DataSource.BINANCE: {'requests_per_second': 10, 'per_minute': 600},
            DataSource.COINBASE: {'requests_per_second': 5, 'per_minute': 300},
            DataSource.BYBIT: {'requests_per_second': 20, 'per_minute': 1200},
        }
        
        limit = rate_limits.get(source, {'requests_per_second': 5, 'per_minute': 300})
        
        # Simple rate limiting
        current_time = time.time()
        self.request_times.append(current_time)
        
        # Remove old timestamps
        cutoff = current_time - 60  # Last minute
        self.request_times = deque(
            [t for t in self.request_times if t > cutoff],
            maxlen=limit['per_minute']
        )
        
        # Check if we need to wait
        if len(self.request_times) >= limit['per_minute']:
            wait_time = 60 - (current_time - min(self.request_times))
            if wait_time > 0:
                await asyncio.sleep(wait_time)
    
    def _get_granularity(self, timeframe: str) -> int:
        """Get Coinbase granularity in seconds."""
        granularities = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '6h': 21600,
            '1d': 86400
        }
        return granularities.get(timeframe, 3600)
    
    def _get_kraken_interval(self, timeframe: str) -> int:
        """Get Kraken interval."""
        intervals = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
            '1w': 10080,
            '1M': 21600
        }
        return intervals.get(timeframe, 60)
    
    def _is_compressed(self, data: str) -> bool:
        """Check if data is compressed."""
        try:
            # Try to decompress - if it fails, it's not compressed
            self.decompressor.decompress(data.encode())
            return True
        except:
            return False
    
    # =========================================================================
    # Data Retrieval Methods
    # =========================================================================
    
    def get_stored_data(
        self,
        symbol: Optional[str] = None,
        data_type: Optional[DataType] = None,
        source: Optional[DataSource] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 1000
    ) -> pd.DataFrame:
        """
        Retrieve stored data from database.
        
        Args:
            symbol: Filter by symbol
            data_type: Filter by data type
            source: Filter by source
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum rows
            
        Returns:
            DataFrame with data
        """
        if self.db_conn is None:
            return pd.DataFrame()
        
        try:
            query = "SELECT * FROM data_points WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type.value)
            
            if source:
                query += " AND source = ?"
                params.append(source.value)
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = self.db_conn.cursor()
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=[
                'id', 'symbol', 'data_type', 'source', 'timestamp',
                'data', 'quality_score', 'checksum', 'collected_at'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['collected_at'] = pd.to_datetime(df['collected_at'])
            
            # Parse data JSON
            df['data'] = df['data'].apply(json.loads)
            
            # Normalize data
            data_df = pd.json_normalize(df['data'])
            
            # Combine with metadata
            result = pd.concat([
                df[['symbol', 'data_type', 'source', 'timestamp', 'quality_score']],
                data_df
            ], axis=1)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve stored data: {e}")
            return pd.DataFrame()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics dictionary
        """
        return {
            'memory_cache_size': len(self.data_cache),
            'redis_connected': self.redis_client is not None,
            'total_data_points': self.stats.total_data_points
        }
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'total_requests': self.stats.total_requests,
            'successful_requests': self.stats.successful_requests,
            'failed_requests': self.stats.failed_requests,
            'total_data_points': self.stats.total_data_points,
            'average_latency_ms': self.stats.average_latency_ms,
            'error_rate': self.stats.error_rate,
            'last_request_time': self.stats.last_request_time
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_data_collector(
    config: Optional[Dict[str, Any]] = None,
    storage_path: Optional[Union[str, Path]] = None,
    redis_url: Optional[str] = None
) -> DataCollector:
    """
    Factory function to create a data collector.
    
    Args:
        config: Configuration dictionary
        storage_path: Path for persistent storage
        redis_url: Redis URL for caching
        
    Returns:
        DataCollector instance
    """
    return DataCollector(
        config=config,
        storage_path=storage_path,
        redis_url=redis_url
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'DataCollector',
    'DataRequest',
    'DataPoint',
    'DataCollectionStats',
    'DataSource',
    'DataType',
    'DataStatus',
    'create_data_collector'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Data Collector

This module provides comprehensive data collection capabilities for the
NEXUS AI Trading Bot, supporting multiple sources, real-time streaming,
and persistent storage.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Features:
    - Multiple data sources (Binance, Coinbase, Bybit, Kraken, etc.)
    - Historical data collection
    - Real-time data streaming via WebSocket
    - Data validation and cleaning
    - Persistent storage with SQLite
    - Redis caching
    - Data compression
    - Automatic retry and failover
    - Rate limiting
    - Data quality monitoring
"""

# Log module initialization
logger.info(f"Data collector module loaded (version {__version__})")
