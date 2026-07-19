# trading/exchanges/okx/market.py
# Nexus AI Trading System - OKX Exchange Market Data Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Market Data Module

This module provides comprehensive market data functionality for the OKX
cryptocurrency exchange, including:

- Real-time and historical OHLC (candlestick) data
- Order book depth and snapshots
- Trade history and recent trades
- Ticker information for all instruments
- Price and volume statistics
- Market capitalization data
- Instrument information and specifications
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
- Data normalization and validation
- Historical data backfilling
- Correlation analysis
- Volatility metrics
- Liquidity analysis

The market data module provides a unified interface for accessing all
OKX market data with advanced analytics and caching capabilities.
"""

import asyncio
import json
import math
import time
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
from trading.exchanges.okx.base import OKXBase, OKXConfig, OKXApiType
from trading.exchanges.okx.exceptions import (
    OKXError,
    OKXMarketDataError,
    OKXInvalidSymbolError,
    OKXRateLimitError,
    OKXConnectionError
)
from trading.exchanges.okx.converter import OKXConverter, get_converter
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OKXInterval(str, Enum):
    """OKX OHLC intervals."""
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1H"
    HOUR_2 = "2H"
    HOUR_4 = "4H"
    HOUR_6 = "6H"
    HOUR_12 = "12H"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"


class OKXIntervalSeconds:
    """OKX interval durations in seconds."""
    INTERVAL_MAP = {
        OKXInterval.MINUTE_1: 60,
        OKXInterval.MINUTE_3: 180,
        OKXInterval.MINUTE_5: 300,
        OKXInterval.MINUTE_15: 900,
        OKXInterval.MINUTE_30: 1800,
        OKXInterval.HOUR_1: 3600,
        OKXInterval.HOUR_2: 7200,
        OKXInterval.HOUR_4: 14400,
        OKXInterval.HOUR_6: 21600,
        OKXInterval.HOUR_12: 43200,
        OKXInterval.DAY_1: 86400,
        OKXInterval.WEEK_1: 604800,
        OKXInterval.MONTH_1: 2592000,
    }


class OKXInstrumentType(str, Enum):
    """OKX instrument types."""
    SPOT = "SPOT"
    FUTURES = "FUTURES"
    OPTION = "OPTION"
    SWAP = "SWAP"
    PERPETUAL = "PERPETUAL"


class OKXMarketStatus(str, Enum):
    """Market status."""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    SUSPENDED = "suspended"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OKXOHLC(BaseModel):
    """OKX OHLC (candlestick) data."""
    timestamp: int  # Unix timestamp in milliseconds
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    volume_quote: Optional[Decimal] = None
    volume_quote_ccy: Optional[Decimal] = None

    @validator('open', 'high', 'low', 'close', 'volume', 'volume_quote', 'volume_quote_ccy', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def change(self) -> Decimal:
        return self.close - self.open

    @property
    def change_percent(self) -> Decimal:
        if self.open == 0:
            return Decimal('0')
        return (self.change / self.open) * 100


class OKXOrderBookEntry(BaseModel):
    """OKX order book entry."""
    price: Decimal
    volume: Decimal
    orders: Optional[int] = None

    @validator('price', 'volume', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class OKXOrderBook(BaseModel):
    """OKX order book."""
    instrument_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bids: List[OKXOrderBookEntry] = Field(default_factory=list)
    asks: List[OKXOrderBookEntry] = Field(default_factory=list)
    checksum: Optional[int] = None

    @property
    def best_bid(self) -> Optional[OKXOrderBookEntry]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OKXOrderBookEntry]:
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


class OKXTicker(BaseModel):
    """OKX ticker data."""
    instrument_id: str
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    last: Decimal = Decimal('0')
    high_24h: Decimal = Decimal('0')
    low_24h: Decimal = Decimal('0')
    volume_24h: Decimal = Decimal('0')
    volume_24h_usd: Optional[Decimal] = None
    open_24h: Decimal = Decimal('0')
    close: Decimal = Decimal('0')
    change: Decimal = Decimal('0')
    change_percent: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator('bid', 'ask', 'last', 'high_24h', 'low_24h', 'volume_24h', 
                'open_24h', 'close', 'change', 'change_percent', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class OKXInstrument(BaseModel):
    """OKX instrument information."""
    instrument_id: str
    instrument_type: OKXInstrumentType
    base_currency: str
    quote_currency: str
    settle_currency: Optional[str] = None
    contract_size: Optional[Decimal] = None
    tick_size: Decimal
    lot_size: Decimal
    min_volume: Decimal
    max_volume: Optional[Decimal] = None
    leverage_min: Optional[Decimal] = None
    leverage_max: Optional[Decimal] = None
    margin_rate: Optional[Decimal] = None
    maintenance_rate: Optional[Decimal] = None
    expiry: Optional[datetime] = None
    delivery_time: Optional[datetime] = None
    status: OKXMarketStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    volume_usd: Optional[Decimal] = None


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
CREATE TABLE IF NOT EXISTS okx_ohlc (
    id SERIAL PRIMARY KEY,
    instrument_id VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(32, 16) NOT NULL,
    high DECIMAL(32, 16) NOT NULL,
    low DECIMAL(32, 16) NOT NULL,
    close DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    volume_quote DECIMAL(32, 16),
    volume_quote_ccy DECIMAL(32, 16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, interval, timestamp)
);

-- Ticker data
CREATE TABLE IF NOT EXISTS okx_ticker (
    id SERIAL PRIMARY KEY,
    instrument_id VARCHAR(50) NOT NULL,
    bid DECIMAL(32, 16) NOT NULL,
    ask DECIMAL(32, 16) NOT NULL,
    last DECIMAL(32, 16) NOT NULL,
    high_24h DECIMAL(32, 16) NOT NULL,
    low_24h DECIMAL(32, 16) NOT NULL,
    volume_24h DECIMAL(32, 16) NOT NULL,
    volume_24h_usd DECIMAL(32, 16),
    open_24h DECIMAL(32, 16) NOT NULL,
    close DECIMAL(32, 16) NOT NULL,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(instrument_id, timestamp)
);

-- Order book snapshots
CREATE TABLE IF NOT EXISTS okx_order_book (
    id SERIAL PRIMARY KEY,
    instrument_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    best_bid DECIMAL(32, 16),
    best_ask DECIMAL(32, 16),
    spread DECIMAL(32, 16),
    checksum INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade history
CREATE TABLE IF NOT EXISTS okx_trades (
    id VARCHAR(64) PRIMARY KEY,
    instrument_id VARCHAR(50) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    timestamp BIGINT NOT NULL,
    side VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market metrics
CREATE TABLE IF NOT EXISTS okx_market_metrics (
    id SERIAL PRIMARY KEY,
    instrument_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Instruments cache
CREATE TABLE IF NOT EXISTS okx_instruments (
    instrument_id VARCHAR(50) PRIMARY KEY,
    instrument_type VARCHAR(20) NOT NULL,
    base_currency VARCHAR(10) NOT NULL,
    quote_currency VARCHAR(10) NOT NULL,
    settle_currency VARCHAR(10),
    contract_size DECIMAL(32, 16),
    tick_size DECIMAL(32, 16) NOT NULL,
    lot_size DECIMAL(32, 16) NOT NULL,
    min_volume DECIMAL(32, 16) NOT NULL,
    max_volume DECIMAL(32, 16),
    leverage_min DECIMAL(32, 16),
    leverage_max DECIMAL(32, 16),
    margin_rate DECIMAL(32, 16),
    maintenance_rate DECIMAL(32, 16),
    expiry TIMESTAMP,
    delivery_time TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_okx_ohlc_instrument_interval_time ON okx_ohlc(instrument_id, interval, timestamp);
CREATE INDEX idx_okx_ticker_instrument_timestamp ON okx_ticker(instrument_id, timestamp);
CREATE INDEX idx_okx_order_book_instrument_timestamp ON okx_order_book(instrument_id, timestamp);
CREATE INDEX idx_okx_trades_instrument_time ON okx_trades(instrument_id, timestamp);
CREATE INDEX idx_okx_market_metrics_instrument_timestamp ON okx_market_metrics(instrument_id, timestamp);
"""


# =============================================================================
# MAIN MARKET DATA CLASS
# =============================================================================

class OKXMarketData:
    """
    Advanced market data handler for OKX exchange.
    
    Features:
    - Real-time OHLC (candlestick) data fetching
    - Historical data with pagination
    - Order book snapshots with depth
    - Recent trade history
    - Ticker data for all instruments
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
    - Instrument management
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base: OKXBase,
        config: OKXConfig,
        converter: Optional[OKXConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # Caches
        self._instrument_cache: Dict[str, OKXInstrument] = {}
        self._ticker_cache: Dict[str, OKXTicker] = {}
        self._order_book_cache: Dict[str, OKXOrderBook] = {}
        self._ohlc_cache: Dict[str, Dict[str, List[OKXOHLC]]] = {}
        
        # Circuit breakers
        self._ticker_cb = CircuitBreaker(
            name="okx_ticker",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._order_book_cb = CircuitBreaker(
            name="okx_order_book",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._ohlc_cb = CircuitBreaker(
            name="okx_ohlc",
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
        
        logger.info("OKXMarketData initialized")
    
    async def initialize(self):
        """Initialize market data module."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load instruments
        await self.get_instruments()
        
        # Start periodic refresh
        asyncio.create_task(self._periodic_refresh())
        
        logger.info("OKXMarketData initialization complete")
    
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
    # INSTRUMENT MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_instruments(
        self,
        instrument_type: Optional[OKXInstrumentType] = None,
        refresh: bool = False
    ) -> Dict[str, OKXInstrument]:
        """
        Get all available instruments.
        
        Args:
            instrument_type: Filter by instrument type
            refresh: Force refresh from API
            
        Returns:
            Dict mapping instrument_id to OKXInstrument
        """
        if not refresh and self._instrument_cache:
            return self._instrument_cache
        
        try:
            # Check cache
            cache_key = f"okx_instruments_{instrument_type.value if instrument_type else 'all'}"
            if self.redis and not refresh:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    instruments = {}
                    for k, v in data.items():
                        v['instrument_type'] = OKXInstrumentType(v['instrument_type'])
                        v['status'] = OKXMarketStatus(v['status'])
                        if v.get('expiry'):
                            v['expiry'] = datetime.fromisoformat(v['expiry'])
                        if v.get('delivery_time'):
                            v['delivery_time'] = datetime.fromisoformat(v['delivery_time'])
                        instruments[k] = OKXInstrument(**v)
                    self._instrument_cache = instruments
                    return instruments
            
            # Build request
            params = {'instType': instrument_type.value} if instrument_type else {}
            
            # Make API request
            result = await self.base._public_request('public/instruments', params)
            
            # Parse instruments
            instruments = {}
            for item in result:
                try:
                    instrument = self._parse_instrument(item)
                    instruments[instrument.instrument_id] = instrument
                except Exception as e:
                    logger.error(f"Error parsing instrument {item.get('instId')}: {e}")
                    continue
            
            self._instrument_cache = instruments
            
            # Cache in Redis
            if self.redis:
                cache_data = {}
                for k, v in instruments.items():
                    v_dict = v.dict()
                    v_dict['instrument_type'] = v_dict['instrument_type'].value
                    v_dict['status'] = v_dict['status'].value
                    if v_dict.get('expiry'):
                        v_dict['expiry'] = v_dict['expiry'].isoformat()
                    if v_dict.get('delivery_time'):
                        v_dict['delivery_time'] = v_dict['delivery_time'].isoformat()
                    cache_data[k] = v_dict
                await self.redis.setex(
                    cache_key,
                    self._cache_ttl * 60,  # 1 hour
                    json.dumps(cache_data, default=str)
                )
            
            logger.info(f"Loaded {len(instruments)} instruments")
            return instruments
            
        except Exception as e:
            logger.error(f"Error getting instruments: {e}")
            if self._instrument_cache:
                return self._instrument_cache
            raise
    
    async def get_instrument(self, symbol: str) -> Optional[OKXInstrument]:
        """
        Get instrument information for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            OKXInstrument or None
        """
        okx_instrument = self.converter.to_okx_instrument(symbol)
        instruments = await self.get_instruments()
        return instruments.get(okx_instrument)
    
    def _parse_instrument(self, data: Dict[str, Any]) -> OKXInstrument:
        """Parse instrument data from API response."""
        instrument_type = data.get('instType', 'SPOT')
        
        # Parse timestamps
        expiry = None
        if data.get('expTime'):
            try:
                expiry = datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000)
            except (ValueError, TypeError):
                pass
        
        delivery_time = None
        if data.get('deliveryTime'):
            try:
                delivery_time = datetime.fromtimestamp(int(data.get('deliveryTime', 0)) / 1000)
            except (ValueError, TypeError):
                pass
        
        return OKXInstrument(
            instrument_id=data.get('instId', ''),
            instrument_type=OKXInstrumentType(instrument_type),
            base_currency=data.get('baseCcy', ''),
            quote_currency=data.get('quoteCcy', ''),
            settle_currency=data.get('settleCcy'),
            contract_size=Decimal(str(data.get('ctVal', 1))) if data.get('ctVal') else None,
            tick_size=Decimal(str(data.get('tickSz', 0.01))),
            lot_size=Decimal(str(data.get('lotSz', 0.001))),
            min_volume=Decimal(str(data.get('minSz', 0))),
            max_volume=Decimal(str(data.get('maxSz', 0))) if data.get('maxSz') else None,
            leverage_min=Decimal(str(data.get('lever', 1))) if data.get('lever') else None,
            leverage_max=Decimal(str(data.get('maxLever', 100))) if data.get('maxLever') else None,
            margin_rate=Decimal(str(data.get('marginRate', 0.01))) if data.get('marginRate') else None,
            maintenance_rate=Decimal(str(data.get('maintenanceRate', 0.005))) if data.get('maintenanceRate') else None,
            expiry=expiry,
            delivery_time=delivery_time,
            status=OKXMarketStatus(data.get('state', 'online')),
            metadata=data
        )
    
    # =========================================================================
    # TICKER DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_ticker(self, instrument_id: str) -> OKXTicker:
        """
        Get ticker data for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            
        Returns:
            OKXTicker object
        """
        if self._ticker_cb.is_open():
            raise OKXRateLimitError("Ticker circuit breaker is open")
        
        try:
            # Check cache
            cache_key = f"ticker_{instrument_id}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    ticker = OKXTicker(**data)
                    self._ticker_cb.record_success()
                    return ticker
            
            # Make API request
            result = await self.base._public_request(
                'market/ticker',
                {'instId': instrument_id}
            )
            
            if not result:
                raise OKXInvalidSymbolError(f"Instrument {instrument_id} not found")
            
            item = result[0]
            
            # Parse ticker
            ticker = OKXTicker(
                instrument_id=item.get('instId', ''),
                bid=Decimal(str(item.get('bidPx', 0))),
                ask=Decimal(str(item.get('askPx', 0))),
                last=Decimal(str(item.get('last', 0))),
                high_24h=Decimal(str(item.get('high24h', 0))),
                low_24h=Decimal(str(item.get('low24h', 0))),
                volume_24h=Decimal(str(item.get('vol24h', 0))),
                open_24h=Decimal(str(item.get('open24h', 0))),
                close=Decimal(str(item.get('last', 0))),
                change=Decimal(str(item.get('last', 0))) - Decimal(str(item.get('open24h', 0))),
                change_percent=Decimal(str(item.get('last', 0))) / Decimal(str(item.get('open24h', 0))) * 100 if item.get('open24h') else Decimal('0'),
                timestamp=datetime.fromtimestamp(int(item.get('ts', 0)) / 1000)
            )
            
            # Cache
            if self.redis:
                await self.redis.setex(
                    cache_key,
                    min(self._cache_ttl, 10),  # Short TTL for ticker
                    json.dumps(ticker.dict(), default=str)
                )
            
            self._ticker_cb.record_success()
            return ticker
            
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
        instrument_id: str,
        interval: OKXInterval = OKXInterval.HOUR_1,
        after: Optional[int] = None,
        before: Optional[int] = None,
        limit: int = 100
    ) -> List[OKXOHLC]:
        """
        Get OHLC (candlestick) data for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            interval: Candlestick interval
            after: Start timestamp in milliseconds
            before: End timestamp in milliseconds
            limit: Maximum number of candles
            
        Returns:
            List of OHLC data
        """
        if self._ohlc_cb.is_open():
            raise OKXRateLimitError("OHLC circuit breaker is open")
        
        try:
            # Check cache
            cache_key = f"ohlc_{instrument_id}_{interval.value}_{after}_{before}_{limit}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    result = [OKXOHLC(**item) for item in data]
                    self._ohlc_cb.record_success()
                    return result
            
            # Build request
            params = {
                'instId': instrument_id,
                'bar': interval.value,
                'limit': min(limit, 300)
            }
            if after:
                params['after'] = after
            if before:
                params['before'] = before
            
            # Make API request
            result = await self.base._public_request('market/candles', params)
            
            # Parse OHLC data
            ohlc_data = []
            for item in result:
                try:
                    ohlc = OKXOHLC(
                        timestamp=int(item[0]),
                        open=Decimal(str(item[1])),
                        high=Decimal(str(item[2])),
                        low=Decimal(str(item[3])),
                        close=Decimal(str(item[4])),
                        volume=Decimal(str(item[5])),
                        volume_quote=Decimal(str(item[6])) if len(item) > 6 else None,
                        volume_quote_ccy=Decimal(str(item[7])) if len(item) > 7 else None
                    )
                    ohlc_data.append(ohlc)
                except Exception as e:
                    logger.error(f"Error parsing OHLC candle: {e}")
                    continue
            
            # Cache
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
                await self._save_ohlc(instrument_id, interval.value, ohlc_data)
            
            self._ohlc_cb.record_success()
            return ohlc_data
            
        except Exception as e:
            self._ohlc_cb.record_failure()
            logger.error(f"Error getting OHLC: {e}")
            raise
    
    async def get_ohlc_dataframe(
        self,
        instrument_id: str,
        interval: OKXInterval = OKXInterval.HOUR_1,
        after: Optional[int] = None,
        before: Optional[int] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get OHLC data as pandas DataFrame.
        
        Args:
            instrument_id: OKX instrument ID
            interval: Candlestick interval
            after: Start timestamp
            before: End timestamp
            limit: Maximum number of candles
            
        Returns:
            pandas DataFrame with OHLC data
        """
        ohlc_data = await self.get_ohlc(instrument_id, interval, after, before, limit)
        
        if not ohlc_data:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                'timestamp': c.timestamp,
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
        instrument_id: str,
        depth: int = 10
    ) -> OKXOrderBook:
        """
        Get order book for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            depth: Order book depth (1-400)
            
        Returns:
            OKXOrderBook
        """
        if self._order_book_cb.is_open():
            raise OKXRateLimitError("Order book circuit breaker is open")
        
        try:
            # Check cache
            cache_key = f"orderbook_{instrument_id}_{depth}"
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    order_book = OKXOrderBook(**data)
                    self._order_book_cb.record_success()
                    return order_book
            
            # Make API request
            result = await self.base._public_request(
                'market/books',
                {
                    'instId': instrument_id,
                    'sz': min(depth, 400)
                }
            )
            
            if not result:
                raise OKXInvalidSymbolError(f"Instrument {instrument_id} not found")
            
            data = result[0]
            
            # Parse order book
            bids = [
                OKXOrderBookEntry(
                    price=Decimal(str(entry[0])),
                    volume=Decimal(str(entry[1])),
                    orders=int(entry[2]) if len(entry) > 2 else None
                )
                for entry in data.get('bids', [])
            ]
            
            asks = [
                OKXOrderBookEntry(
                    price=Decimal(str(entry[0])),
                    volume=Decimal(str(entry[1])),
                    orders=int(entry[2]) if len(entry) > 2 else None
                )
                for entry in data.get('asks', [])
            ]
            
            order_book = OKXOrderBook(
                instrument_id=instrument_id,
                timestamp=datetime.fromtimestamp(int(data.get('ts', 0)) / 1000),
                bids=bids,
                asks=asks,
                checksum=data.get('checksum')
            )
            
            # Cache
            if self.redis:
                ttl = min(self._cache_ttl, 5)  # Short TTL for order book
                await self.redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(order_book.dict(), default=str)
                )
            
            # Save snapshot to database
            if self.pool:
                await self._save_order_book_snapshot(instrument_id, order_book)
            
            self._order_book_cb.record_success()
            return order_book
            
        except Exception as e:
            self._order_book_cb.record_failure()
            logger.error(f"Error getting order book: {e}")
            raise
    
    # =========================================================================
    # TRADE HISTORY
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_trades(
        self,
        instrument_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            limit: Number of trades
            
        Returns:
            List of trades
        """
        try:
            result = await self.base._public_request(
                'market/trades',
                {
                    'instId': instrument_id,
                    'limit': min(limit, 500)
                }
            )
            
            # Save to database
            if self.pool and result:
                await self._save_trades(instrument_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            raise
    
    # =========================================================================
    # MARKET STATISTICS
    # =========================================================================
    
    async def get_market_stats(
        self,
        instrument_id: str,
        interval: OKXInterval = OKXInterval.HOUR_1,
        lookback: int = 100
    ) -> MarketStats:
        """
        Get market statistics for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            interval: Time interval
            lookback: Number of periods to analyze
            
        Returns:
            MarketStats
        """
        ohlc_data = await self.get_ohlc(instrument_id, interval, limit=lookback)
        
        if not ohlc_data:
            return MarketStats(
                symbol=instrument_id,
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
        
        # Calculate USD volume
        volume_usd = None
        if instrument_id.endswith('-USDT'):
            volume_usd = total_volume
        elif not instrument_id.endswith('-USDC'):
            # Try to get price in USD
            try:
                ticker = await self.get_ticker(instrument_id)
                if ticker.last > 0:
                    volume_usd = total_volume * ticker.last
            except Exception:
                pass
        
        return MarketStats(
            symbol=instrument_id,
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
            volatility=volatility,
            volume_usd=volume_usd
        )
    
    # =========================================================================
    # ADVANCED MARKET METRICS
    # =========================================================================
    
    async def get_market_metrics(self, instrument_id: str) -> MarketMetrics:
        """
        Get comprehensive market metrics for an instrument.
        
        Args:
            instrument_id: OKX instrument ID
            
        Returns:
            MarketMetrics
        """
        try:
            # Get ticker data
            ticker = await self.get_ticker(instrument_id)
            
            # Get order book
            order_book = await self.get_order_book(instrument_id, depth=50)
            
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
            vol_24h = (ticker.high_24h - ticker.low_24h) / ticker.low_24h * 100 if ticker.low_24h > 0 else Decimal('0')
            
            # Calculate ATR (14-period)
            atr_14 = await self._calculate_atr(instrument_id, 14) if instrument_id else None
            
            # Get trade history for sentiment
            trades = await self.get_trades(instrument_id, limit=100)
            buy_volume = sum(Decimal(str(t.get('vol', 0))) for t in trades if t.get('side') == 'buy')
            sell_volume = sum(Decimal(str(t.get('vol', 0))) for t in trades if t.get('side') == 'sell')
            buy_sell_ratio = (buy_volume / sell_volume) if sell_volume > 0 else None
            
            return MarketMetrics(
                symbol=instrument_id,
                volume_24h=ticker.volume_24h,
                depth_bid=total_bid_depth,
                depth_ask=total_ask_depth,
                depth_total=total_depth,
                spread=spread,
                spread_percent=spread_percent,
                price=ticker.last,
                price_change_24h=ticker.change,
                price_change_percent_24h=ticker.change_percent,
                high_24h=ticker.high_24h,
                low_24h=ticker.low_24h,
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
    
    async def _calculate_atr(self, instrument_id: str, period: int = 14) -> Optional[Decimal]:
        """
        Calculate Average True Range (ATR).
        
        Args:
            instrument_id: OKX instrument ID
            period: ATR period
            
        Returns:
            ATR value or None
        """
        try:
            ohlc_data = await self.get_ohlc(instrument_id, OKXInterval.HOUR_1, limit=period + 1)
            
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
    # CORRELATION ANALYSIS
    # =========================================================================
    
    async def get_correlation(
        self,
        instrument1: str,
        instrument2: str,
        interval: OKXInterval = OKXInterval.HOUR_1,
        lookback: int = 100
    ) -> float:
        """
        Calculate correlation between two instruments.
        
        Args:
            instrument1: First instrument
            instrument2: Second instrument
            interval: Time interval
            lookback: Number of periods
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        try:
            # Get data
            ohlc1 = await self.get_ohlc(instrument1, interval, limit=lookback)
            ohlc2 = await self.get_ohlc(instrument2, interval, limit=lookback)
            
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
        instrument_id: str,
        interval: str,
        ohlc_data: List[OKXOHLC]
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
                            INSERT INTO okx_ohlc (
                                instrument_id, interval, timestamp,
                                open, high, low, close,
                                volume, volume_quote, volume_quote_ccy
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (instrument_id, interval, timestamp) DO UPDATE SET
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                volume = EXCLUDED.volume,
                                volume_quote = EXCLUDED.volume_quote,
                                volume_quote_ccy = EXCLUDED.volume_quote_ccy
                            """,
                            instrument_id,
                            interval,
                            candle.timestamp,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            candle.volume_quote,
                            candle.volume_quote_ccy
                        )
        except Exception as e:
            logger.error(f"Error saving OHLC: {e}")
    
    async def _save_order_book_snapshot(
        self,
        instrument_id: str,
        order_book: OKXOrderBook
    ):
        """Save order book snapshot to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_order_book (
                        instrument_id, timestamp, bids, asks,
                        best_bid, best_ask, spread, checksum
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    instrument_id,
                    order_book.timestamp,
                    json.dumps([entry.dict() for entry in order_book.bids[:50]]),
                    json.dumps([entry.dict() for entry in order_book.asks[:50]]),
                    order_book.best_bid.price if order_book.best_bid else None,
                    order_book.best_ask.price if order_book.best_ask else None,
                    order_book.spread,
                    order_book.checksum
                )
        except Exception as e:
            logger.error(f"Error saving order book: {e}")
    
    async def _save_trades(self, instrument_id: str, trades: List[Dict[str, Any]]):
        """Save trades to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for trade in trades:
                        await conn.execute(
                            """
                            INSERT INTO okx_trades (
                                id, instrument_id, price, volume,
                                timestamp, side
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            trade.get('tradeId', f"{instrument_id}_{trade.get('ts', 0)}"),
                            instrument_id,
                            Decimal(str(trade.get('px', 0))),
                            Decimal(str(trade.get('sz', 0))),
                            int(trade.get('ts', 0)),
                            trade.get('side', 'buy')
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
                
                # Refresh instruments
                await self.get_instruments(refresh=True)
                
                # Refresh major tickers
                major_pairs = ['BTC-USDT', 'ETH-USDT', 'XRP-USDT', 'ADA-USDT']
                for pair in major_pairs:
                    try:
                        await self.get_ticker(pair)
                    except Exception as e:
                        logger.debug(f"Error refreshing ticker {pair}: {e}")
                
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
        instruments: List[str],
        channels: List[str],
        handler: Callable
    ):
        """
        Subscribe to WebSocket market data.
        
        Args:
            instruments: List of instruments
            channels: List of channels (ticker, candle, trades, books)
            handler: Callback for messages
        """
        for channel in channels:
            for instrument in instruments:
                await self.base.ws_subscribe(
                    channel,
                    [instrument],
                    handler
                )
        
        logger.info(f"Subscribed to {channels} for {instruments}")
    
    async def unsubscribe_from_market_data(
        self,
        instruments: List[str],
        channels: List[str]
    ):
        """Unsubscribe from WebSocket market data."""
        for channel in channels:
            for instrument in instruments:
                await self.base.ws_unsubscribe(channel, [instrument])
        
        logger.info(f"Unsubscribed from {channels} for {instruments}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown market data module."""
        logger.info("Shutting down OKXMarketData")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXMarketData',
    'OKXInterval',
    'OKXIntervalSeconds',
    'OKXInstrumentType',
    'OKXMarketStatus',
    'OKXOHLC',
    'OKXOrderBookEntry',
    'OKXOrderBook',
    'OKXTicker',
    'OKXInstrument',
    'MarketStats',
    'MarketMetrics'
]
