# trading/bots/hedge_bot/hedge_bot_historical_data.py

import asyncio
import logging
import time
import json
import hashlib
import pickle
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import numpy as np
import pandas as pd
import aiofiles
import os

logger = logging.getLogger(__name__)


class TimeFrame(str, Enum):
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


class DataType(str, Enum):
    OHLCV = "ohlcv"
    TRADES = "trades"
    ORDER_BOOK = "order_book"
    TICKER = "ticker"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LIQUIDATIONS = "liquidations"
    SOCIAL = "social"
    NEWS = "news"
    ONCHAIN = "onchain"
    METRICS = "metrics"


class StorageFormat(str, Enum):
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    HDF5 = "hdf5"
    PICKLE = "pickle"
    FEATHER = "feather"
    ORC = "orc"


@dataclass
class HistoricalDataConfig:
    symbol: str
    timeframe: TimeFrame
    data_type: DataType
    start_date: datetime
    end_date: datetime
    exchange: str = "binance"
    storage_format: StorageFormat = StorageFormat.PARQUET
    compression: bool = True
    max_records: Optional[int] = None
    fields: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HistoricalData:
    id: str
    symbol: str
    timeframe: TimeFrame
    data_type: DataType
    exchange: str
    data: pd.DataFrame
    start_date: datetime
    end_date: datetime
    record_count: int
    storage_format: StorageFormat
    size: int
    hash: str
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSource:
    id: str
    name: str
    exchange: str
    priority: int = 1
    rate_limit: float = 1.0
    max_retries: int = 3
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataRequest:
    id: str
    config: HistoricalDataConfig
    source: Optional[str] = None
    status: str = "pending"
    progress: float = 0.0
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class DataAggregation:
    id: str
    source_id: str
    timeframe: TimeFrame
    window: int
    method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class HistoricalDataManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._data: Dict[str, HistoricalData] = {}
        self._requests: Dict[str, DataRequest] = {}
        self._sources: Dict[str, DataSource] = {}
        self._aggregations: Dict[str, DataAggregation] = {}
        self._cache: Dict[str, Any] = {}
        self._handlers: Dict[DataType, List[Callable]] = defaultdict(list)
        self._observers: List[Callable] = []
        self._running = False
        self._storage_path = self.config.get("storage_path", "./data/historical")
        self._max_cache_size = self.config.get("max_cache_size", 100)
        self._default_source = None
        
        os.makedirs(self._storage_path, exist_ok=True)
        self._initialize_default_sources()

    def _initialize_default_sources(self) -> None:
        default_sources = [
            DataSource(
                id="binance",
                name="Binance API",
                exchange="binance",
                priority=1,
                rate_limit=1200,
                max_retries=3,
                timeout=30
            ),
            DataSource(
                id="bybit",
                name="Bybit API",
                exchange="bybit",
                priority=2,
                rate_limit=600,
                max_retries=3,
                timeout=30
            ),
            DataSource(
                id="kraken",
                name="Kraken API",
                exchange="kraken",
                priority=3,
                rate_limit=600,
                max_retries=3,
                timeout=30
            ),
            DataSource(
                id="coinbase",
                name="Coinbase API",
                exchange="coinbase",
                priority=4,
                rate_limit=300,
                max_retries=3,
                timeout=30
            ),
            DataSource(
                id="file",
                name="Local File",
                exchange="local",
                priority=0,
                rate_limit=0,
                max_retries=1,
                timeout=5
            )
        ]
        
        for source in default_sources:
            self._sources[source.id] = source
        
        self._default_source = "binance"

    def register_source(self, source: DataSource) -> None:
        self._sources[source.id] = source

    def register_handler(self, data_type: DataType, handler: Callable) -> None:
        self._handlers[data_type].append(handler)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def fetch_historical_data(
        self,
        config: HistoricalDataConfig,
        source_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Optional[HistoricalData]:
        async with self._lock:
            data_id = self._generate_data_id(config)
            
            if not force_refresh and data_id in self._data:
                return self._data[data_id]
            
            if not force_refresh and data_id in self._cache:
                cached = self._cache[data_id]
                if self._is_cache_valid(cached):
                    return cached
            
            request = DataRequest(
                id=hashlib.md5(f"{data_id}_{time.time()}".encode()).hexdigest(),
                config=config,
                source=source_id,
                status="pending"
            )
            
            self._requests[request.id] = request
            
            await self._notify_observers("request_started", request)
            
            try:
                data = await self._fetch_from_source(config, source_id)
                
                if data is not None:
                    historical_data = await self._process_data(data, config)
                    
                    self._data[data_id] = historical_data
                    self._update_cache(data_id, historical_data)
                    
                    await self._save_to_storage(historical_data)
                    
                    request.status = "completed"
                    request.completed_at = time.time()
                    
                    for handler in self._handlers.get(config.data_type, []):
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(historical_data)
                            else:
                                handler(historical_data)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
                    
                    await self._notify_observers("data_fetched", historical_data)
                    return historical_data
                else:
                    request.status = "failed"
                    request.error = "No data returned from source"
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching historical data: {e}")
                request.status = "failed"
                request.error = str(e)
                await self._notify_observers("request_failed", request)
                return None

    async def _fetch_from_source(
        self,
        config: HistoricalDataConfig,
        source_id: Optional[str]
    ) -> Optional[pd.DataFrame]:
        source = None
        
        if source_id and source_id in self._sources:
            source = self._sources[source_id]
        elif self._default_source and self._default_source in self._sources:
            source = self._sources[self._default_source]
        else:
            source = next(iter(self._sources.values()))
        
        if source.id == "file":
            return await self._load_from_file(config)
        
        try:
            return await self._fetch_from_api(source, config)
        except Exception as e:
            logger.error(f"Error fetching from {source.name}: {e}")
            return None

    async def _fetch_from_api(
        self,
        source: DataSource,
        config: HistoricalDataConfig
    ) -> Optional[pd.DataFrame]:
        exchange = source.exchange
        
        if exchange == "binance":
            return await self._fetch_binance(config)
        elif exchange == "bybit":
            return await self._fetch_bybit(config)
        elif exchange == "kraken":
            return await self._fetch_kraken(config)
        elif exchange == "coinbase":
            return await self._fetch_coinbase(config)
        else:
            logger.warning(f"Unsupported exchange: {exchange}")
            return None

    async def _fetch_binance(self, config: HistoricalDataConfig) -> Optional[pd.DataFrame]:
        import ccxt
        
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        timeframe = config.timeframe.value
        symbol = config.symbol.replace('/', '').replace('-', '')
        
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=int(config.start_date.timestamp() * 1000),
                limit=1000
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Binance API error: {e}")
            return None

    async def _fetch_bybit(self, config: HistoricalDataConfig) -> Optional[pd.DataFrame]:
        import ccxt
        
        exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        timeframe = config.timeframe.value
        symbol = config.symbol.replace('/', '').replace('-', '')
        
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=int(config.start_date.timestamp() * 1000),
                limit=1000
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Bybit API error: {e}")
            return None

    async def _fetch_kraken(self, config: HistoricalDataConfig) -> Optional[pd.DataFrame]:
        import ccxt
        
        exchange = ccxt.kraken({
            'enableRateLimit': True
        })
        
        timeframe = config.timeframe.value
        symbol = config.symbol.replace('/', '').replace('-', '')
        
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=int(config.start_date.timestamp() * 1000),
                limit=1000
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Kraken API error: {e}")
            return None

    async def _fetch_coinbase(self, config: HistoricalDataConfig) -> Optional[pd.DataFrame]:
        import ccxt
        
        exchange = ccxt.coinbase({
            'enableRateLimit': True
        })
        
        timeframe = config.timeframe.value
        symbol = config.symbol.replace('/', '').replace('-', '')
        
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=int(config.start_date.timestamp() * 1000),
                limit=1000
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Coinbase API error: {e}")
            return None

    async def _load_from_file(self, config: HistoricalDataConfig) -> Optional[pd.DataFrame]:
        storage_format = config.storage_format or StorageFormat.PARQUET
        file_path = self._get_file_path(config)
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None
        
        try:
            if storage_format == StorageFormat.PARQUET:
                df = pd.read_parquet(file_path)
            elif storage_format == StorageFormat.CSV:
                df = pd.read_csv(file_path, parse_dates=True, index_col=0)
            elif storage_format == StorageFormat.JSON:
                df = pd.read_json(file_path)
            elif storage_format == StorageFormat.HDF5:
                df = pd.read_hdf(file_path)
            elif storage_format == StorageFormat.PICKLE:
                df = pd.read_pickle(file_path)
            else:
                return None
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            return None

    async def _process_data(
        self,
        data: pd.DataFrame,
        config: HistoricalDataConfig
    ) -> HistoricalData:
        data_id = self._generate_data_id(config)
        
        if config.max_records and len(data) > config.max_records:
            data = data.iloc[-config.max_records:]
        
        if config.fields:
            existing_fields = [f for f in config.fields if f in data.columns]
            if existing_fields:
                data = data[existing_fields]
        
        if config.data_type == DataType.OHLCV:
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in data.columns:
                    data[col] = np.nan
        
        data = data.sort_index()
        
        serialized = pickle.dumps(data)
        compressed = zlib.compress(serialized) if config.compression else serialized
        
        historical_data = HistoricalData(
            id=data_id,
            symbol=config.symbol,
            timeframe=config.timeframe,
            data_type=config.data_type,
            exchange=config.exchange,
            data=data,
            start_date=data.index.min() if not data.empty else config.start_date,
            end_date=data.index.max() if not data.empty else config.end_date,
            record_count=len(data),
            storage_format=config.storage_format,
            size=len(compressed),
            hash=hashlib.sha256(serialized).hexdigest()
        )
        
        return historical_data

    async def _save_to_storage(self, historical_data: HistoricalData) -> None:
        file_path = self._get_file_path_from_data(historical_data)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        storage_format = historical_data.storage_format
        
        try:
            if storage_format == StorageFormat.PARQUET:
                historical_data.data.to_parquet(file_path)
            elif storage_format == StorageFormat.CSV:
                historical_data.data.to_csv(file_path)
            elif storage_format == StorageFormat.JSON:
                historical_data.data.to_json(file_path)
            elif storage_format == StorageFormat.HDF5:
                historical_data.data.to_hdf(file_path, key='data')
            elif storage_format == StorageFormat.PICKLE:
                historical_data.data.to_pickle(file_path)
            else:
                historical_data.data.to_parquet(f"{file_path}.parquet")
                
        except Exception as e:
            logger.error(f"Error saving to storage: {e}")

    async def load_historical_data(
        self,
        config: HistoricalDataConfig,
        source_id: Optional[str] = None
    ) -> Optional[HistoricalData]:
        data_id = self._generate_data_id(config)
        
        if data_id in self._data:
            return self._data[data_id]
        
        if data_id in self._cache:
            cached = self._cache[data_id]
            if self._is_cache_valid(cached):
                return cached
        
        file_path = self._get_file_path(config)
        
        if os.path.exists(file_path):
            df = await self._load_from_file(config)
            if df is not None:
                return await self._process_data(df, config)
        
        return await self.fetch_historical_data(config, source_id)

    def _generate_data_id(self, config: HistoricalDataConfig) -> str:
        base = f"{config.exchange}_{config.symbol}_{config.timeframe.value}_{config.data_type.value}_{config.start_date.timestamp()}_{config.end_date.timestamp()}"
        return hashlib.md5(base.encode()).hexdigest()

    def _get_file_path(self, config: HistoricalDataConfig) -> str:
        storage_format = config.storage_format or StorageFormat.PARQUET
        ext = {
            StorageFormat.PARQUET: 'parquet',
            StorageFormat.CSV: 'csv',
            StorageFormat.JSON: 'json',
            StorageFormat.HDF5: 'h5',
            StorageFormat.PICKLE: 'pkl',
            StorageFormat.FEATHER: 'feather'
        }.get(storage_format, 'parquet')
        
        data_id = self._generate_data_id(config)
        return os.path.join(
            self._storage_path,
            config.exchange,
            config.symbol,
            config.timeframe.value,
            f"{data_id}.{ext}"
        )

    def _get_file_path_from_data(self, historical_data: HistoricalData) -> str:
        ext = {
            StorageFormat.PARQUET: 'parquet',
            StorageFormat.CSV: 'csv',
            StorageFormat.JSON: 'json',
            StorageFormat.HDF5: 'h5',
            StorageFormat.PICKLE: 'pkl',
            StorageFormat.FEATHER: 'feather'
        }.get(historical_data.storage_format, 'parquet')
        
        return os.path.join(
            self._storage_path,
            historical_data.exchange,
            historical_data.symbol,
            historical_data.timeframe.value,
            f"{historical_data.id}.{ext}"
        )

    async def aggregate_data(
        self,
        data: pd.DataFrame,
        timeframe: TimeFrame,
        method: str = "ohlcv"
    ) -> pd.DataFrame:
        if data.empty:
            return data
        
        if method == "ohlcv":
            resampled = data.resample(timeframe.value)
            df = pd.DataFrame({
                'open': resampled['open'].first(),
                'high': resampled['high'].max(),
                'low': resampled['low'].min(),
                'close': resampled['close'].last(),
                'volume': resampled['volume'].sum()
            })
        elif method == "average":
            df = data.resample(timeframe.value).mean()
        elif method == "sum":
            df = data.resample(timeframe.value).sum()
        elif method == "max":
            df = data.resample(timeframe.value).max()
        elif method == "min":
            df = data.resample(timeframe.value).min()
        else:
            raise ValueError(f"Unsupported aggregation method: {method}")
        
        return df.dropna()

    def _update_cache(self, data_id: str, historical_data: HistoricalData) -> None:
        self._cache[data_id] = historical_data
        
        if len(self._cache) > self._max_cache_size:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
            del self._cache[oldest]

    def _is_cache_valid(self, cached_data: HistoricalData) -> bool:
        return time.time() - cached_data.created_at < self.config.get("cache_ttl", 3600)

    async def clear_cache(self) -> None:
        self._cache.clear()

    async def get_data(self, data_id: str) -> Optional[HistoricalData]:
        return self._data.get(data_id)

    async def get_data_by_symbol(
        self,
        symbol: str,
        timeframe: Optional[TimeFrame] = None,
        data_type: Optional[DataType] = None
    ) -> List[HistoricalData]:
        results = []
        for data in self._data.values():
            if data.symbol == symbol:
                if timeframe and data.timeframe != timeframe:
                    continue
                if data_type and data.data_type != data_type:
                    continue
                results.append(data)
        return results

    async def delete_data(self, data_id: str) -> bool:
        if data_id in self._data:
            data = self._data[data_id]
            file_path = self._get_file_path_from_data(data)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            del self._data[data_id]
            if data_id in self._cache:
                del self._cache[data_id]
            return True
        
        return False

    async def get_request_status(self, request_id: str) -> Optional[DataRequest]:
        return self._requests.get(request_id)

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
        return {
            "total_data": len(self._data),
            "total_requests": len(self._requests),
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size,
            "sources": len(self._sources),
            "handlers": sum(len(h) for h in self._handlers.values()),
            "storage_path": self._storage_path
        }


__all__ = [
    "TimeFrame",
    "DataType",
    "StorageFormat",
    "HistoricalDataConfig",
    "HistoricalData",
    "DataSource",
    "DataRequest",
    "DataAggregation",
    "HistoricalDataManager"
]
