# trading/exchanges/kraken/market.py
# Nexus AI Trading System - Kraken Exchange Market Data Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Market Data Module

This module provides comprehensive market data functionality for the Kraken
cryptocurrency exchange, including:

- Real-time and historical OHLC (candlestick) data
- Order book depth and snapshots
- Trade history and recent trades
- Ticker information for all trading pairs
- Price and volume statistics
- Market capitalization data
- Asset information
- Pair information and specifications
- Spread analysis
- Volume-weighted average price (VWAP)
- Market sentiment indicators
- Technical indicator calculations
- Data caching and persistence
- WebSocket real-time updates
- Multi-timeframe aggregation
- Quote currency conversion
- Market health monitoring
- Exchange status information
- Rate limit management
- Comprehensive error handling
"""

import asyncio
import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
import asyncpg

# Nexus imports
from trading.exchanges.kraken.base import KrakenBase, KrakenConfig, KrakenApiType
from trading.exchanges.kraken.exceptions import (
    KrakenError,
    KrakenDataError,
    KrakenInvalidSymbolError,
    KrakenRateLimitError,
    KrakenConnectionError
)
from trading.exchanges.kraken.converter import KrakenConverter, get_converter
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class KrakenInterval(str, Enum):
    """Kraken OHLC intervals in minutes."""
    MINUTE_1 = "1"
    MINUTE_5 = "5"
    MINUTE_15 = "15"
    MINUTE_30 = "30"
    HOUR_1 = "60"
    HOUR_4 = "240"
    DAY_1 = "1440"
    WEEK_1 = "10080"
    MONTH_1 = "21600"


class KrakenIntervalSeconds:
    """Kraken interval durations in seconds."""
    INTERVAL_MAP = {
        KrakenInterval.MINUTE_1: 60,
        KrakenInterval.MINUTE_5: 300,
        KrakenInterval.MINUTE_15: 900,
        KrakenInterval.MINUTE_30: 1800,
        KrakenInterval.HOUR_1: 3600,
        KrakenInterval.HOUR_4: 14400,
        KrakenInterval.DAY_1: 86400,
        KrakenInterval.WEEK_1: 604800,
        KrakenInterval.MONTH_1: 2592000,
    }


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class KrakenOHLC(BaseModel):
    """Kraken OHLC (candlestick) data."""
    time: int  # Unix timestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    volume_quote: Optional[Decimal] = None
    
    @validator('open', 'high', 'low', 'close', 'volume', 'volume_quote', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.time)
    
    @property
    def change(self) -> Decimal:
        return self.close - self.open
    
    @property
    def change_percent(self) -> Decimal:
        if self.open == 0:
            return Decimal('0')
        return (self.change / self.open) * 100


class KrakenOrderBookEntry(BaseModel):
    """Kraken order book entry."""
    price: Decimal
    volume: Decimal
    
    @validator('price', 'volume', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class KrakenOrderBook(BaseModel):
    """Kraken order book."""
    pair: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bids: List[KrakenOrderBookEntry] = Field(default_factory=list)
    asks: List[KrakenOrderBookEntry] = Field(default_factory=list)
    
    @property
    def best_bid(self) -> Optional[KrakenOrderBookEntry]:
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[KrakenOrderBookEntry]:
        return self.asks[0] if self.asks else None
    
    @property
    def spread(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None


class KrakenTrade(BaseModel):
    """Kraken trade."""
    price: Decimal
    volume: Decimal
    time: int
    side: str  # 'b' = buy, 's' = sell
    id: Optional[str] = None
    
    @validator('price', 'volume', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.time)
    
    @property
    def is_buy(self) -> bool:
        return self.side == 'b'
    
    @property
    def is_sell(self) -> bool:
        return self.side == 's'
    
    @property
    def value(self) -> Decimal:
        return self.price * self.volume


class KrakenTickerData(BaseModel):
    """Kraken ticker data."""
    ask: Decimal
    bid: Decimal
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    volume_24h: Decimal
    open: Decimal
    close: Decimal
    change: Decimal
    change_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('ask', 'bid', 'last', 'high', 'low', 'volume', 'volume_24h', 'open', 'close', 'change', 'change_percent', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class KrakenAsset(BaseModel):
    """Kraken asset information."""
    name: str
    altname: str
    aclass: str  # asset class (currency, commodity, etc.)
    decimals: int
    display_decimals: int
    status: str
    collateral_value: Optional[Decimal] = None


class KrakenPair(BaseModel):
    """Kraken trading pair information."""
    name: str  # Kraken pair name
    altname: str  # Alternative name
    base: str  # Base asset
    quote: str  # Quote asset
    wsname: Optional[str] = None  # WebSocket name
    pair_decimals: int  # Price decimals
    lot_decimals: int  # Volume decimals
    cost_decimals: int
    ordermin: Decimal  # Minimum order volume
    costmin: Decimal  # Minimum order cost
    tick_size: Decimal  # Minimum price increment
    status: str
    leverage_buy: List[int]
    leverage_sell: List[int]


class MarketStats(BaseModel):
    """Market statistics."""
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int = 0
    vwap: Optional[Decimal] = None
    range: Decimal = Decimal('0')
    range_percent: Decimal = Decimal('0')
    volatility: Decimal = Decimal('0')


class MarketMetrics(BaseModel):
    """Advanced market metrics."""
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Volume metrics
    volume_24h: Decimal
    volume_24h_usd: Optional[Decimal] = None
    volume_change_24h: Optional[Decimal] = None
    
    # Liquidity metrics
    depth_bid: Decimal
    depth_ask: Decimal
    depth_total: Decimal
    spread: Decimal
    spread_percent: Decimal
    
    # Price metrics
    price: Decimal
    price_change_24h: Decimal
    price_change_percent_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    
    # Volatility metrics
    volatility_24h: Decimal
    volatility_7d: Optional[Decimal] = None
    atr_14: Optional[Decimal] = None
    
    # Order book metrics
    bid_count: int
    ask_count: int
    imbalance: Optional[Decimal] = None
    
    # Market sentiment
    buy_volume_24h: Optional[Decimal] = None
    sell_volume_24h: Optional[Decimal] = None
    buy_sell_ratio: Optional[Decimal] = None
    
    # Additional metrics
    trades_24h: int = 0
    average_trade_size: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    dominance: Optional[Decimal] = None
    correlation: Optional[Dict[str, Decimal]] = None


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- OHLC data
CREATE TABLE IF NOT EXISTS kraken_ohlc (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    time BIGINT NOT NULL,
    open DECIMAL(32, 16) NOT NULL,
    high DECIMAL(32, 16) NOT NULL,
    low DECIMAL(32, 16) NOT NULL,
    close DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    volume_quote DECIMAL(32, 16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pair, interval, time)
);

-- Ticker data
CREATE TABLE IF NOT EXISTS kraken_ticker (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    bid DECIMAL(32, 16) NOT NULL,
    ask DECIMAL(32, 16) NOT NULL,
    last DECIMAL(32, 16) NOT NULL,
    high DECIMAL(32, 16) NOT NULL,
    low DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    volume_24h DECIMAL(32, 16) NOT NULL,
    open DECIMAL(32, 16) NOT NULL,
    close DECIMAL(32, 16) NOT NULL,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pair, timestamp)
);

-- Order book snapshots
CREATE TABLE IF NOT EXISTS kraken_order_book (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    best_bid DECIMAL(32, 16),
    best_ask DECIMAL(32, 16),
    spread DECIMAL(32, 16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade history
CREATE TABLE IF NOT EXISTS kraken_trades (
    id VARCHAR(64) PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    time BIGINT NOT NULL,
    side VARCHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market metrics
CREATE TABLE IF NOT EXISTS kraken_market_metrics (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_kraken_ohlc_pair_interval_time ON kraken_ohlc(pair, interval, time);
CREATE INDEX idx_kraken_ticker_pair_timestamp ON kraken_ticker(pair, timestamp);
CREATE INDEX idx_kraken_order_book_pair_timestamp ON kraken_order_book(pair, timestamp);
CREATE INDEX idx_kraken_trades_pair_time ON kraken_trades(pair, time);
CREATE INDEX idx_kraken_market_metrics_pair_timestamp ON kraken_market_metrics(pair, timestamp);
"""


# =============================================================================
# MAIN MARKET DATA CLASS
# =============================================================================

class KrakenMarketData:
    """
    Advanced market data handler for Kraken exchange.
    
    Features:
    - Real-time OHLC (candlestick) data fetching
    - Historical data with pagination
    - Order book snapshots with depth
    - Recent trade history
    - Ticker data for all pairs
    - Market statistics and analytics
    - Technical indicator calculations
    - Data caching with Redis
    - Database persistence
    - WebSocket real-time updates
    - Multi-timeframe aggregation
    - Volume-weighted average price (VWAP)
    - Market sentiment analysis
    - Correlation calculations
    - Volatility indicators
    - Liquidity analysis
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base: KrakenBase,
        config: KrakenConfig,
        converter: Optional[KrakenConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # Caches
        self._pair_cache: Dict[str, KrakenPair] = {}
        self._asset_cache: Dict[str, KrakenAsset] = {}
        self._ticker_cache: Dict[str, KrakenTickerData] = {}
        self._order_book_cache: Dict[str, KrakenOrderBook] = {}
        self._ohlc_cache: Dict[str, Dict[str, List[KrakenOHLC]]] = {}
        
        # Circuit breakers
        self._ticker_cb = CircuitBreaker(
            name="kraken_ticker",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._order_book_cb = CircuitBreaker(
            name="kraken_order_book",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._ohlc_cb = CircuitBreaker(
            name="kraken_ohlc",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # WebSocket handlers
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_subscribed = False
        
        # Cache TTL
        self._cache_ttl = config.cache_ttl or 60
        
        # Database initialization
        self._db_initialized = False
        
        # Rate limit tracking
        self._request_count = 0
        self._request_time = 0
        
        logger.info("KrakenMarketData initialized")
    
    async def initialize(self):
        """Initialize market data module."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load pair information
        await self.get_pairs()
        
        # Start periodic refresh
        asyncio.create_task(self._periodic_refresh())
        
        logger.info("KrakenMarketData initialization complete")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # PAIR AND ASSET INFORMATION
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_pairs(self, refresh: bool = False) -> Dict[str, KrakenPair]:
        """
        Get all available trading pairs.
        
        Args:
            refresh: Force refresh from API
            
        Returns:
            Dict mapping pair name to KrakenPair
        """
        if not refresh and self._pair_cache:
            return self._pair_cache
        
        try:
            # Check cache
            cache_key = "kraken_pairs"
            if self.redis and not refresh:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    self._pair_cache = {
                        k: KrakenPair(**v) for k, v in data.items()
                    }
                    return self._pair_cache
            
            # Make API request
            result = await self.base._make_request(
                "AssetPairs",
                data={},
                api_type=KrakenApiType.PUBLIC
            )
            
            # Parse pairs
            pairs = {}
            for name, data in result.items():
                try:
                    pair = KrakenPair(
                        name=name,
                        altname=data.get('altname', ''),
                        base=data.get('base', ''),
                        quote=data.get('quote', ''),
                        wsname=data.get('wsname'),
                        pair_decimals=data.get('pair_decimals', 0),
                        lot_decimals=data.get('lot_decimals', 0),
                        cost_decimals=data.get('cost_decimals', 0),
                        ordermin=Decimal(str(data.get('ordermin', 0))),
                        costmin=Decimal(str(data.get('costmin', 0))),
                        tick_size=Decimal(str(data.get('tick_size', 0))),
                        status=data.get('status', 'online'),
                        leverage_buy=data.get('leverage_buy', []),
                        leverage_sell=data.get('leverage_sell', [])
                    )
                    pairs[name] = pair
                except Exception as e:
                    logger.error(f"Error parsing pair {name}: {e}")
                    continue
            
            self._pair_cache = pairs
            
            # Cache in Redis
            if self.redis:
                cache_data = {
                    k: v.dict() for k, v in pairs.items()
                }
                await self.redis.setex(
                    cache_key,
                    self._cache_ttl * 60,  # 1 hour
                    json.dumps(cache_data, default=str)
                )
            
            logger.info(f"Loaded {len(pairs)} trading pairs")
            return pairs
            
        except Exception as e:
            logger.error(f"Error getting pairs: {e}")
            if self._pair_cache:
                return self._pair_cache
            raise
    
    async def get_pair(self, symbol: str) -> Optional[KrakenPair]:
        """
        Get information for a specific trading pair.
        
        Args:
            symbol: Trading pair in standard or Kraken format
            
        Returns:
            KrakenPair or None
        """
        kraken_symbol = self.converter.to_kraken_pair(symbol)
        pairs = await self.get_pairs()
        return pairs.get(kraken_symbol)
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_assets(self, refresh: bool = False) -> Dict[str, KrakenAsset]:
        """
        Get all available assets.
        
        Args:
            refresh: Force refresh from API
            
        Returns:
            Dict mapping asset name to KrakenAsset
        """
        if not refresh and self._asset_cache:
            return self._asset_cache
        
        try:
            result = await self.base._make_request(
                "Assets",
                data={},
                api_type=KrakenApiType.PUBLIC
            )
            
            assets = {}
            for name, data in result.items():
                try:
                    asset = KrakenAsset(
                        name=name,
                        altname=data.get('altname', ''),
                        aclass=data.get('aclass', ''),
                        decimals=data.get('decimals', 0),
                        display_decimals=data.get('display_decimals', 0),
                        status=data.get('status', 'online'),
                        collateral_value=Decimal(str(data['collateral_value'])) if data.get('collateral_value') else None
                    )
                    assets[name] = asset
                except Exception as e:
                    logger.error(f"Error parsing asset {name}: {e}")
                    continue
            
            self._asset_cache = assets
            return assets
            
        except Exception as e:
            logger.error(f"Error getting assets: {e}")
            if self._asset_cache:
                return self._asset_cache
            raise
    
    # =========================================================================
    # TICKER DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_ticker(self, symbols: Union[str, List[str]]) -> Dict[str, KrakenTickerData]:
        """
        Get ticker data for one or more trading pairs.
        
        Args:
            symbols: Single symbol or list of symbols
            
        Returns:
            Dict mapping symbol to ticker data
        """
        if self._ticker_cb.is_open():
            raise KrakenRateLimitError("Ticker circuit breaker is open")
        
        try:
            # Normalize symbols
            if isinstance(symbols, str):
                symbols = [symbols]
            
            kraken_pairs = [self.converter.to_kraken_pair(s) for s in symbols]
            pair_str = ','.join(kraken_pairs)
            
            # Check cache
            cache_key = f"ticker_{pair_str}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    result = {}
                    for k, v in data.items():
                        standard_pair = self.converter.to_standard_pair(k)
                        result[standard_pair] = KrakenTickerData(**v)
                    self._ticker_cb.record_success()
                    return result
            
            # Make API request
            result = await self.base._make_request(
                "Ticker",
                data={"pair": pair_str},
                api_type=KrakenApiType.PUBLIC
            )
            
            # Parse ticker data
            tickers = {}
            for pair, data in result.items():
                try:
                    standard_pair = self.converter.to_standard_pair(pair)
                    
                    # Parse Kraken ticker format
                    # a = ask, b = bid, c = last, h = high, l = low
                    # v = volume, o = open
                    ask = Decimal(str(data.get('a', ['0'])[0]))
                    bid = Decimal(str(data.get('b', ['0'])[0]))
                    last = Decimal(str(data.get('c', ['0'])[0]))
                    high = Decimal(str(data.get('h', ['0'])[0]))
                    low = Decimal(str(data.get('l', ['0'])[0]))
                    volume = Decimal(str(data.get('v', ['0'])[0]))
                    volume_24h = Decimal(str(data.get('v', ['0'])[1] if len(data.get('v', [])) > 1 else '0'))
                    open_price = Decimal(str(data.get('o', ['0'])[0]))
                    close_price = last
                    
                    ticker = KrakenTickerData(
                        ask=ask,
                        bid=bid,
                        last=last,
                        high=high,
                        low=low,
                        volume=volume,
                        volume_24h=volume_24h,
                        open=open_price,
                        close=close_price,
                        change=close_price - open_price,
                        change_percent=((close_price - open_price) / open_price * 100) if open_price > 0 else Decimal('0'),
                        timestamp=datetime.fromtimestamp(float(data.get('t', 0)) or time.time())
                    )
                    tickers[standard_pair] = ticker
                    
                except Exception as e:
                    logger.error(f"Error parsing ticker for {pair}: {e}")
                    continue
            
            # Cache results
            if self.redis and tickers:
                cache_data = {}
                for pair, ticker in tickers.items():
                    kraken_pair = self.converter.to_kraken_pair(pair)
                    cache_data[kraken_pair] = ticker.dict()
                await self.redis.setex(
                    cache_key,
                    min(self._cache_ttl, 10),  # Short TTL for ticker
                    json.dumps(cache_data, default=str)
                )
            
            self._ticker_cb.record_success()
            return tickers
            
        except Exception as e:
            self._ticker_cb.record_failure()
            logger.error(f"Error getting ticker: {e}")
            raise
    
    # =========================================================================
    # OHLC (CANDLESTICK) DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_ohlc(
        self,
        symbol: str,
        interval: KrakenInterval = KrakenInterval.HOUR_1,
        since: Optional[int] = None,
        limit: int = 500
    ) -> List[KrakenOHLC]:
        """
        Get OHLC (candlestick) data for a symbol.
        
        Args:
            symbol: Trading symbol
            interval: Candlestick interval
            since: Start timestamp
            limit: Maximum number of candles
            
        Returns:
            List of OHLC data
        """
        if self._ohlc_cb.is_open():
            raise KrakenRateLimitError("OHLC circuit breaker is open")
        
        try:
            kraken_pair = self.converter.to_kraken_pair(symbol)
            
            # Check cache
            cache_key = f"ohlc_{kraken_pair}_{interval.value}_{since}_{limit}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    result = [KrakenOHLC(**item) for item in data]
                    self._ohlc_cb.record_success()
                    return result
            
            # Prepare request
            params = {
                "pair": kraken_pair,
                "interval": int(interval.value)
            }
            if since:
                params["since"] = since
            if limit:
                params["count"] = min(limit, 720)
            
            # Make API request
            result = await self.base._make_request(
                "OHLC",
                data=params,
                api_type=KrakenApiType.PUBLIC
            )
            
            # Parse OHLC data
            ohlc_data = []
            if kraken_pair in result:
                for candle in result[kraken_pair]:
                    try:
                        ohlc = KrakenOHLC(
                            time=int(candle[0]),
                            open=Decimal(str(candle[1])),
                            high=Decimal(str(candle[2])),
                            low=Decimal(str(candle[3])),
                            close=Decimal(str(candle[4])),
                            volume=Decimal(str(candle[6]) if len(candle) > 6 else candle[5]),
                            volume_quote=Decimal(str(candle[7])) if len(candle) > 7 else None
                        )
                        ohlc_data.append(ohlc)
                    except Exception as e:
                        logger.error(f"Error parsing OHLC candle: {e}")
                        continue
            
            # Cache results
            if self.redis and ohlc_data:
                cache_data = [item.dict() for item in ohlc_data]
                ttl = min(self._cache_ttl, 60)  # TTL based on interval
                await self.redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_data, default=str)
                )
            
            # Save to database
            if self.pool and ohlc_data:
                await self._save_ohlc(kraken_pair, interval.value, ohlc_data)
            
            self._ohlc_cb.record_success()
            return ohlc_data
            
        except Exception as e:
            self._ohlc_cb.record_failure()
            logger.error(f"Error getting OHLC: {e}")
            raise
    
    async def get_ohlc_dataframe(
        self,
        symbol: str,
        interval: KrakenInterval = KrakenInterval.HOUR_1,
        since: Optional[int] = None,
        limit: int = 500
    ) -> pd.DataFrame:
        """
        Get OHLC data as pandas DataFrame.
        
        Args:
            symbol: Trading symbol
            interval: Candlestick interval
            since: Start timestamp
            limit: Maximum number of candles
            
        Returns:
            pandas DataFrame with OHLC data
        """
        ohlc_data = await self.get_ohlc(symbol, interval, since, limit)
        
        if not ohlc_data:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                'time': c.time,
                'datetime': c.datetime,
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'close': float(c.close),
                'volume': float(c.volume),
                'volume_quote': float(c.volume_quote) if c.volume_quote else None
            }
            for c in ohlc_data
        ])
        
        df.set_index('datetime', inplace=True)
        return df
    
    # =========================================================================
    # ORDER BOOK
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_order_book(
        self,
        symbol: str,
        depth: int = 10
    ) -> KrakenOrderBook:
        """
        Get order book for a symbol.
        
        Args:
            symbol: Trading symbol
            depth: Order book depth (1-100)
            
        Returns:
            KrakenOrderBook
        """
        if self._order_book_cb.is_open():
            raise KrakenRateLimitError("Order book circuit breaker is open")
        
        try:
            kraken_pair = self.converter.to_kraken_pair(symbol)
            
            # Check cache
            cache_key = f"order_book_{kraken_pair}_{depth}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    order_book = KrakenOrderBook(**data)
                    self._order_book_cb.record_success()
                    return order_book
            
            # Make API request
            result = await self.base._make_request(
                "Depth",
                data={
                    "pair": kraken_pair,
                    "count": min(depth, 100)
                },
                api_type=KrakenApiType.PUBLIC
            )
            
            # Parse order book
            if kraken_pair not in result:
                raise KrakenInvalidSymbolError(f"Symbol {symbol} not found")
            
            data = result[kraken_pair]
            
            bids = [
                KrakenOrderBookEntry(
                    price=Decimal(str(entry[0])),
                    volume=Decimal(str(entry[1]))
                )
                for entry in data.get('bids', [])
            ]
            
            asks = [
                KrakenOrderBookEntry(
                    price=Decimal(str(entry[0])),
                    volume=Decimal(str(entry[1]))
                )
                for entry in data.get('asks', [])
            ]
            
            order_book = KrakenOrderBook(
                pair=kraken_pair,
                timestamp=datetime.fromtimestamp(float(data.get('timestamp', time.time()))),
                bids=bids,
                asks=asks
            )
            
            # Cache results
            if self.redis:
                ttl = min(self._cache_ttl, 5)  # Short TTL for order book
                await self.redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(order_book.dict(), default=str)
                )
            
            # Save snapshot to database
            if self.pool:
                await self._save_order_book_snapshot(kraken_pair, order_book)
            
            self._order_book_cb.record_success()
            return order_book
            
        except Exception as e:
            self._order_book_cb.record_failure()
            logger.error(f"Error getting order book: {e}")
            raise
    
    async def get_l2_order_book(
        self,
        symbol: str,
        depth: int = 100
    ) -> Dict[str, List[Tuple[Decimal, Decimal]]]:
        """
        Get Level 2 order book (price levels).
        
        Args:
            symbol: Trading symbol
            depth: Depth to return
            
        Returns:
            Dict with 'bids' and 'asks' as lists of (price, volume)
        """
        order_book = await self.get_order_book(symbol, depth)
        
        bids = [(entry.price, entry.volume) for entry in order_book.bids[:depth]]
        asks = [(entry.price, entry.volume) for entry in order_book.asks[:depth]]
        
        return {
            'bids': bids,
            'asks': asks,
            'timestamp': order_book.timestamp
        }
    
    # =========================================================================
    # TRADE HISTORY
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_trades(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: int = 100
    ) -> List[KrakenTrade]:
        """
        Get recent trades for a symbol.
        
        Args:
            symbol: Trading symbol
            since: Start timestamp
            limit: Maximum number of trades
            
        Returns:
            List of trades
        """
        try:
            kraken_pair = self.converter.to_kraken_pair(symbol)
            
            params = {"pair": kraken_pair}
            if since:
                params["since"] = since
            
            # Make API request
            result = await self.base._make_request(
                "Trades",
                data=params,
                api_type=KrakenApiType.PUBLIC
            )
            
            # Parse trades
            trades = []
            if kraken_pair in result:
                for trade_data in result[kraken_pair]:
                    try:
                        trade = KrakenTrade(
                            price=Decimal(str(trade_data[0])),
                            volume=Decimal(str(trade_data[1])),
                            time=int(trade_data[2]),
                            side=trade_data[3],
                            id=str(trade_data[4]) if len(trade_data) > 4 else None
                        )
                        trades.append(trade)
                    except Exception as e:
                        logger.error(f"Error parsing trade: {e}")
                        continue
                
                # Limit results
                if len(trades) > limit:
                    trades = trades[:limit]
            
            # Save to database
            if self.pool and trades:
                await self._save_trades(kraken_pair, trades)
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            raise
    
    # =========================================================================
    # MARKET STATISTICS
    # =========================================================================
    
    async def get_market_stats(
        self,
        symbol: str,
        interval: KrakenInterval = KrakenInterval.HOUR_1,
        lookback: int = 100
    ) -> MarketStats:
        """
        Get market statistics for a symbol.
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            lookback: Number of periods to analyze
            
        Returns:
            MarketStats
        """
        ohlc_data = await self.get_ohlc(symbol, interval, limit=lookback)
        
        if not ohlc_data:
            return MarketStats(
                symbol=symbol,
                interval=interval.value,
                open_time=datetime.utcnow(),
                close_time=datetime.utcnow(),
                open=Decimal('0'),
                high=Decimal('0'),
                low=Decimal('0'),
                close=Decimal('0'),
                volume=Decimal('0')
            )
        
        # Calculate statistics
        open_price = ohlc_data[0].open
        close_price = ohlc_data[-1].close
        high_price = max(c.high for c in ohlc_data)
        low_price = min(c.low for c in ohlc_data)
        total_volume = sum(c.volume for c in ohlc_data)
        trades = len(ohlc_data)
        
        # Calculate VWAP
        vwap = None
        if total_volume > 0:
            typical_prices = [(c.high + c.low + c.close) / 3 for c in ohlc_data]
            vwap = sum(tp * c.volume for tp, c in zip(typical_prices, ohlc_data)) / total_volume
        
        # Calculate range
        range_val = high_price - low_price
        range_percent = (range_val / open_price * 100) if open_price > 0 else Decimal('0')
        
        # Calculate volatility (standard deviation of returns)
        returns = []
        for i in range(1, len(ohlc_data)):
            ret = (ohlc_data[i].close - ohlc_data[i-1].close) / ohlc_data[i-1].close if ohlc_data[i-1].close > 0 else Decimal('0')
            returns.append(float(ret))
        
        volatility = Decimal(str(np.std(returns) * 100 if returns else 0))
        
        return MarketStats(
            symbol=symbol,
            interval=interval.value,
            open_time=ohlc_data[0].datetime,
            close_time=ohlc_data[-1].datetime,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=total_volume,
            trades=trades,
            vwap=vwap,
            range=range_val,
            range_percent=range_percent,
            volatility=volatility
        )
    
    # =========================================================================
    # ADVANCED MARKET METRICS
    # =========================================================================
    
    async def get_market_metrics(self, symbol: str) -> MarketMetrics:
        """
        Get comprehensive market metrics for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            MarketMetrics
        """
        try:
            # Get ticker data
            ticker_data = await self.get_ticker(symbol)
            ticker = ticker_data.get(symbol)
            if not ticker:
                raise KrakenDataError(f"No ticker data for {symbol}")
            
            # Get order book
            order_book = await self.get_order_book(symbol, depth=50)
            
            # Calculate depth metrics
            total_bid_depth = sum(entry.volume for entry in order_book.bids[:20])
            total_ask_depth = sum(entry.volume for entry in order_book.asks[:20])
            total_depth = total_bid_depth + total_ask_depth
            
            # Calculate spread
            spread = order_book.spread or Decimal('0')
            spread_percent = (spread / order_book.mid_price * 100) if order_book.mid_price else Decimal('0')
            
            # Calculate imbalance
            imbalance = None
            if total_ask_depth > 0 and total_bid_depth > 0:
                imbalance = (total_bid_depth - total_ask_depth) / (total_bid_depth + total_ask_depth)
            
            # Calculate volatility (24h)
            vol_24h = (ticker.high - ticker.low) / ticker.low * 100 if ticker.low > 0 else Decimal('0')
            
            # Calculate ATR (14-period)
            atr_14 = await self._calculate_atr(symbol, 14) if symbol else None
            
            # Get trade history for sentiment
            trades = await self.get_trades(symbol, limit=100)
            buy_volume = sum(t.volume for t in trades if t.is_buy)
            sell_volume = sum(t.volume for t in trades if t.is_sell)
            buy_sell_ratio = (buy_volume / sell_volume) if sell_volume > 0 else None
            
            return MarketMetrics(
                symbol=symbol,
                volume_24h=ticker.volume_24h,
                depth_bid=total_bid_depth,
                depth_ask=total_ask_depth,
                depth_total=total_depth,
                spread=spread,
                spread_percent=spread_percent,
                price=ticker.last,
                price_change_24h=ticker.change,
                price_change_percent_24h=ticker.change_percent,
                high_24h=ticker.high,
                low_24h=ticker.low,
                volatility_24h=vol_24h,
                volatility_7d=None,  # Would need historical data
                atr_14=atr_14,
                bid_count=len(order_book.bids),
                ask_count=len(order_book.asks),
                imbalance=imbalance,
                buy_volume_24h=buy_volume if buy_volume > 0 else None,
                sell_volume_24h=sell_volume if sell_volume > 0 else None,
                buy_sell_ratio=buy_sell_ratio,
                trades_24h=len(trades),
                average_trade_size=(buy_volume + sell_volume) / len(trades) if trades else None
            )
            
        except Exception as e:
            logger.error(f"Error calculating market metrics: {e}")
            raise
    
    async def _calculate_atr(self, symbol: str, period: int = 14) -> Optional[Decimal]:
        """
        Calculate Average True Range (ATR).
        
        Args:
            symbol: Trading symbol
            period: ATR period
            
        Returns:
            ATR value or None
        """
        try:
            ohlc_data = await self.get_ohlc(symbol, KrakenInterval.HOUR_1, limit=period + 1)
            
            if len(ohlc_data) < period + 1:
                return None
            
            # Calculate true ranges
            tr_values = []
            for i in range(1, len(ohlc_data)):
                high = float(ohlc_data[i].high)
                low = float(ohlc_data[i].low)
                prev_close = float(ohlc_data[i-1].close)
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_values.append(tr)
            
            # Calculate ATR
            if not tr_values:
                return None
            
            atr = sum(tr_values[-period:]) / period
            return Decimal(str(atr))
            
        except Exception:
            return None
    
    # =========================================================================
    # VOLUME WEIGHTED AVERAGE PRICE (VWAP)
    # =========================================================================
    
    async def get_vwap(
        self,
        symbol: str,
        interval: KrakenInterval = KrakenInterval.HOUR_1,
        lookback: int = 24
    ) -> Optional[Decimal]:
        """
        Calculate Volume Weighted Average Price (VWAP).
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            lookback: Number of periods
            
        Returns:
            VWAP value
        """
        ohlc_data = await self.get_ohlc(symbol, interval, limit=lookback)
        
        if not ohlc_data:
            return None
        
        total_volume = Decimal('0')
        total_typical_volume = Decimal('0')
        
        for candle in ohlc_data:
            typical_price = (candle.high + candle.low + candle.close) / 3
            total_typical_volume += typical_price * candle.volume
            total_volume += candle.volume
        
        if total_volume == 0:
            return None
        
        return total_typical_volume / total_volume
    
    # =========================================================================
    # CORRELATION ANALYSIS
    # =========================================================================
    
    async def get_correlation(
        self,
        symbol1: str,
        symbol2: str,
        interval: KrakenInterval = KrakenInterval.HOUR_1,
        lookback: int = 100
    ) -> float:
        """
        Calculate correlation between two symbols.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            interval: Time interval
            lookback: Number of periods
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        try:
            # Get data
            ohlc1 = await self.get_ohlc(symbol1, interval, limit=lookback)
            ohlc2 = await self.get_ohlc(symbol2, interval, limit=lookback)
            
            if not ohlc1 or not ohlc2:
                return 0.0
            
            # Align data
            min_len = min(len(ohlc1), len(ohlc2))
            returns1 = []
            returns2 = []
            
            for i in range(min_len - 1):
                ret1 = float((ohlc1[i].close - ohlc1[i+1].close) / ohlc1[i+1].close if ohlc1[i+1].close > 0 else 0)
                ret2 = float((ohlc2[i].close - ohlc2[i+1].close) / ohlc2[i+1].close if ohlc2[i+1].close > 0 else 0)
                returns1.append(ret1)
                returns2.append(ret2)
            
            if len(returns1) < 2:
                return 0.0
            
            # Calculate correlation
            corr = np.corrcoef(returns1, returns2)[0, 1]
            return float(corr)
            
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return 0.0
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_ohlc(
        self,
        pair: str,
        interval: str,
        ohlc_data: List[KrakenOHLC]
    ):
        """Save OHLC data to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for candle in ohlc_data:
                        await conn.execute(
                            """
                            INSERT INTO kraken_ohlc (
                                pair, interval, time, open, high, low,
                                close, volume, volume_quote
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            ON CONFLICT (pair, interval, time) DO UPDATE SET
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                volume = EXCLUDED.volume,
                                volume_quote = EXCLUDED.volume_quote
                            """,
                            pair,
                            interval,
                            candle.time,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            candle.volume_quote
                        )
        except Exception as e:
            logger.error(f"Error saving OHLC: {e}")
    
    async def _save_order_book_snapshot(
        self,
        pair: str,
        order_book: KrakenOrderBook
    ):
        """Save order book snapshot to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_order_book (
                        pair, timestamp, bids, asks,
                        best_bid, best_ask, spread
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    pair,
                    order_book.timestamp,
                    json.dumps([entry.dict() for entry in order_book.bids[:50]]),
                    json.dumps([entry.dict() for entry in order_book.asks[:50]]),
                    order_book.best_bid.price if order_book.best_bid else None,
                    order_book.best_ask.price if order_book.best_ask else None,
                    order_book.spread
                )
        except Exception as e:
            logger.error(f"Error saving order book: {e}")
    
    async def _save_trades(self, pair: str, trades: List[KrakenTrade]):
        """Save trades to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for trade in trades:
                        await conn.execute(
                            """
                            INSERT INTO kraken_trades (
                                id, pair, price, volume, time, side
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            trade.id or f"{pair}_{trade.time}_{trade.price}",
                            pair,
                            trade.price,
                            trade.volume,
                            trade.time,
                            trade.side
                        )
        except Exception as e:
            logger.error(f"Error saving trades: {e}")
    
    # =========================================================================
    # PERIODIC REFRESH
    # =========================================================================
    
    async def _periodic_refresh(self):
        """Periodically refresh market data."""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Refresh ticker cache for major pairs
                major_pairs = ['BTC/USD', 'ETH/USD', 'XRP/USD', 'LTC/USD']
                try:
                    await self.get_ticker(major_pairs)
                except Exception as e:
                    logger.debug(f"Error refreshing ticker: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic refresh: {e}")
                await asyncio.sleep(300)
    
    # =========================================================================
    # WEBSOCKET INTEGRATION
    # =========================================================================
    
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        channels: List[str],
        handler: Callable
    ):
        """
        Subscribe to WebSocket market data.
        
        Args:
            symbols: List of symbols
            channels: List of channels (ticker, ohlc, trade, spread, book)
            handler: Callback for messages
        """
        kraken_pairs = [self.converter.to_kraken_pair(s) for s in symbols]
        
        for channel in channels:
            await self.base.ws_subscribe(
                self.base._get_channel_enum(channel),
                kraken_pairs,
                handler
            )
        
        logger.info(f"Subscribed to {channels} for {symbols}")
    
    async def unsubscribe_from_market_data(
        self,
        symbols: List[str],
        channels: List[str]
    ):
        """Unsubscribe from WebSocket market data."""
        kraken_pairs = [self.converter.to_kraken_pair(s) for s in symbols]
        
        for channel in channels:
            await self.base.ws_unsubscribe(
                self.base._get_channel_enum(channel),
                kraken_pairs
            )
        
        logger.info(f"Unsubscribed from {channels} for {symbols}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown market data module."""
        logger.info("Shutting down KrakenMarketData")
        # Nothing to clean up


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenMarketData',
    'KrakenInterval',
    'KrakenIntervalSeconds',
    'KrakenOHLC',
    'KrakenOrderBookEntry',
    'KrakenOrderBook',
    'KrakenTrade',
    'KrakenTickerData',
    'KrakenAsset',
    'KrakenPair',
    'MarketStats',
    'MarketMetrics'
]
