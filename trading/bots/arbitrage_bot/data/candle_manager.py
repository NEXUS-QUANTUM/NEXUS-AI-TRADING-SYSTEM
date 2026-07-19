# trading/bots/arbitrage_bot/data/candle_manager.py
# Nexus AI Trading System - Arbitrage Bot Candle Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Candle Manager Module

This module provides comprehensive candlestick (OHLC) data management
for the arbitrage bot system, including:

- Multi-exchange candle data aggregation
- Real-time candle updates via WebSocket
- Historical candle data management
- Candle data normalization and validation
- Candle data caching and persistence
- Multi-timeframe support
- Candle data interpolation and resampling
- Technical indicator calculation
- Candle pattern detection
- Candle data quality monitoring
- Candle data export and reporting

Supported timeframes:
- 1m, 3m, 5m, 15m, 30m
- 1h, 2h, 4h, 6h, 8h, 12h
- 1d, 2d, 3d, 1w, 1M

Supported exchanges:
- Binance
- OKX
- Kraken
- Coinbase
- Bybit
- Bitget
- KuCoin
- Huobi
- Gate.io
- MEXC
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketDataSource, MarketDataStatus
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class CandleInterval(str, Enum):
    """Candle intervals."""
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    DAY_2 = "2d"
    DAY_3 = "3d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class CandleStatus(str, Enum):
    """Candle status."""
    OPEN = "open"          # Currently forming
    CLOSED = "closed"      # Completed
    UPDATED = "updated"    # Updated (overwritten)
    INVALID = "invalid"    # Invalid data
    PENDING = "pending"    # Waiting for data


class CandlePattern(str, Enum):
    """Candle patterns."""
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING_BULLISH = "engulfing_bullish"
    ENGULFING_BEARISH = "engulfing_bearish"
    HARAMI_BULLISH = "harami_bullish"
    HARAMI_BEARISH = "harami_bearish"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"
    PIERCING_LINE = "piercing_line"
    DARK_CLOUD_COVER = "dark_cloud_cover"
    NONE = "none"


class CandleQuality(str, Enum):
    """Candle data quality."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


# =============================================================================
# INTERVAL CONSTANTS
# =============================================================================

INTERVAL_SECONDS = {
    CandleInterval.MINUTE_1: 60,
    CandleInterval.MINUTE_3: 180,
    CandleInterval.MINUTE_5: 300,
    CandleInterval.MINUTE_15: 900,
    CandleInterval.MINUTE_30: 1800,
    CandleInterval.HOUR_1: 3600,
    CandleInterval.HOUR_2: 7200,
    CandleInterval.HOUR_4: 14400,
    CandleInterval.HOUR_6: 21600,
    CandleInterval.HOUR_8: 28800,
    CandleInterval.HOUR_12: 43200,
    CandleInterval.DAY_1: 86400,
    CandleInterval.DAY_2: 172800,
    CandleInterval.DAY_3: 259200,
    CandleInterval.WEEK_1: 604800,
    CandleInterval.MONTH_1: 2592000,
}

INTERVAL_DISPLAY = {
    CandleInterval.MINUTE_1: "1m",
    CandleInterval.MINUTE_3: "3m",
    CandleInterval.MINUTE_5: "5m",
    CandleInterval.MINUTE_15: "15m",
    CandleInterval.MINUTE_30: "30m",
    CandleInterval.HOUR_1: "1h",
    CandleInterval.HOUR_2: "2h",
    CandleInterval.HOUR_4: "4h",
    CandleInterval.HOUR_6: "6h",
    CandleInterval.HOUR_8: "8h",
    CandleInterval.HOUR_12: "12h",
    CandleInterval.DAY_1: "1d",
    CandleInterval.DAY_2: "2d",
    CandleInterval.DAY_3: "3d",
    CandleInterval.WEEK_1: "1w",
    CandleInterval.MONTH_1: "1M",
}

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class Candle(BaseModel):
    """Candlestick data."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    interval: CandleInterval
    timestamp: int  # Unix timestamp (seconds)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Optional[Decimal] = None
    trade_count: Optional[int] = None
    status: CandleStatus = CandleStatus.CLOSED
    source: MarketDataSource = MarketDataSource.REST
    quality: CandleQuality = CandleQuality.GOOD
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('open', 'high', 'low', 'close', 'volume')
    def validate_prices(cls, v):
        if v < 0:
            raise ValueError("Price/volume cannot be negative")
        return v

    @root_validator
    def validate_ohlc(cls, values):
        """Validate OHLC consistency."""
        open_price = values.get('open')
        high = values.get('high')
        low = values.get('low')
        close = values.get('close')
        
        if open_price is not None and high is not None and low is not None:
            if high < open_price or high < close:
                values['high'] = max(open_price, close, high)
            if low > open_price or low > close:
                values['low'] = min(open_price, close, low)
        
        return values

    @property
    def datetime(self) -> datetime:
        """Get datetime from timestamp."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def body(self) -> Decimal:
        """Get candle body size."""
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> Decimal:
        """Get upper wick size."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> Decimal:
        """Get lower wick size."""
        return min(self.open, self.close) - self.low

    @property
    def range(self) -> Decimal:
        """Get price range."""
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        """Check if candle is bullish."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """Check if candle is bearish."""
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        """Check if candle is doji."""
        if self.range == 0:
            return True
        return self.body / self.range < Decimal('0.1')

    @property
    def change_percent(self) -> Decimal:
        """Calculate percent change."""
        if self.open == 0:
            return Decimal('0')
        return (self.close - self.open) / self.open * 100

    @property
    def vwap(self) -> Optional[Decimal]:
        """Calculate volume-weighted average price."""
        if self.volume == 0:
            return None
        typical_price = (self.high + self.low + self.close) / 3
        return typical_price

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'interval': self.interval.value,
            'timestamp': self.timestamp,
            'open': float(self.open),
            'high': float(self.high),
            'low': float(self.low),
            'close': float(self.close),
            'volume': float(self.volume),
            'quote_volume': float(self.quote_volume) if self.quote_volume else None,
            'trade_count': self.trade_count,
            'status': self.status.value,
            'quality': self.quality.value
        }


class CandlePatternResult(BaseModel):
    """Candle pattern detection result."""
    pattern: CandlePattern
    confidence: Decimal = Decimal('0')
    bullish: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CandleStatistics(BaseModel):
    """Candle statistics."""
    exchange: str
    symbol: str
    interval: CandleInterval
    count: int = 0
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    high: Decimal = Decimal('0')
    low: Decimal = Decimal('0')
    average_high: Decimal = Decimal('0')
    average_low: Decimal = Decimal('0')
    average_close: Decimal = Decimal('0')
    average_volume: Decimal = Decimal('0')
    volatility: Decimal = Decimal('0')
    total_volume: Decimal = Decimal('0')
    bullish_count: int = 0
    bearish_count: int = 0
    doji_count: int = 0
    max_body: Decimal = Decimal('0')
    avg_body: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Candles
CREATE TABLE IF NOT EXISTS arbitrage_candles (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(32, 16) NOT NULL,
    high DECIMAL(32, 16) NOT NULL,
    low DECIMAL(32, 16) NOT NULL,
    close DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    quote_volume DECIMAL(32, 16),
    trade_count INTEGER,
    status VARCHAR(20) NOT NULL,
    source VARCHAR(20) NOT NULL,
    quality VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    UNIQUE(exchange, symbol, interval, timestamp)
);

-- Candle statistics
CREATE TABLE IF NOT EXISTS candle_statistics (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    count INTEGER NOT NULL,
    open_time TIMESTAMP,
    close_time TIMESTAMP,
    high DECIMAL(32, 16) NOT NULL,
    low DECIMAL(32, 16) NOT NULL,
    average_high DECIMAL(32, 16) NOT NULL,
    average_low DECIMAL(32, 16) NOT NULL,
    average_close DECIMAL(32, 16) NOT NULL,
    average_volume DECIMAL(32, 16) NOT NULL,
    volatility DECIMAL(32, 16) NOT NULL,
    total_volume DECIMAL(32, 16) NOT NULL,
    bullish_count INTEGER NOT NULL,
    bearish_count INTEGER NOT NULL,
    doji_count INTEGER NOT NULL,
    max_body DECIMAL(32, 16) NOT NULL,
    avg_body DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, symbol, interval)
);

-- Candle patterns
CREATE TABLE IF NOT EXISTS candle_patterns (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    pattern VARCHAR(30) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    bullish BOOLEAN NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_candle_patterns_exchange (exchange),
    INDEX idx_candle_patterns_symbol (symbol),
    INDEX idx_candle_patterns_pattern (pattern),
    INDEX idx_candle_patterns_timestamp (timestamp)
);

-- Candle quality
CREATE TABLE IF NOT EXISTS candle_quality (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    quality VARCHAR(20) NOT NULL,
    missing_count INTEGER DEFAULT 0,
    invalid_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    total_count INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, symbol, interval)
);
"""


# =============================================================================
# CANDLE MANAGER CLASS
# =============================================================================

class CandleManager:
    """
    Advanced candle manager for arbitrage bot.
    
    Features:
    - Multi-exchange candle data aggregation
    - Real-time candle updates via WebSocket
    - Historical candle data management
    - Candle data normalization and validation
    - Candle data caching and persistence
    - Multi-timeframe support
    - Candle data interpolation and resampling
    - Technical indicator calculation
    - Candle pattern detection
    - Candle data quality monitoring
    - Candle data export and reporting
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.market_data = market_data
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Candle cache
        self._candles: Dict[str, Dict[str, Dict[str, List[Candle]]]] = {}
        # exchange -> symbol -> interval -> [Candle]
        
        # Latest candles
        self._latest: Dict[str, Dict[str, Dict[str, Candle]]] = {}
        # exchange -> symbol -> interval -> Candle
        
        # Patterns
        self._patterns: Dict[str, List[CandlePatternResult]] = {}
        
        # Quality metrics
        self._quality: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        
        # Circuit breakers
        self._candle_cb = CircuitBreaker(
            name="candle_manager",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Subscription handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Update tasks
        self._update_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("CandleManager initialized")
    
    async def initialize(self):
        """Initialize the candle manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load candles
        if self.pool:
            await self._load_candles()
        
        # Start update loop
        self._running = True
        asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("CandleManager initialized")
    
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
    # CANDLE DATA RETRIEVAL
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_candles(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        refresh: bool = False
    ) -> List[Candle]:
        """
        Get candles for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of candles
            refresh: Force refresh from API
            
        Returns:
            List of Candle
        """
        if self._candle_cb.is_open():
            raise CircuitBreakerOpenError("Candle manager circuit breaker is open")
        
        try:
            # Check cache
            if not refresh:
                cache_key = f"{exchange}:{symbol}:{interval.value}"
                if cache_key in self._candles:
                    candles = self._candles[cache_key]
                    if start_time is not None:
                        candles = [c for c in candles if c.timestamp >= start_time]
                    if end_time is not None:
                        candles = [c for c in candles if c.timestamp <= end_time]
                    
                    if len(candles) >= limit or (start_time is not None and end_time is not None):
                        return candles[:limit]
            
            # Get from exchange
            candles = await self._fetch_candles(exchange, symbol, interval, start_time, end_time, limit)
            
            # Update cache
            async with self._lock:
                cache_key = f"{exchange}:{symbol}:{interval.value}"
                if cache_key not in self._candles:
                    self._candles[cache_key] = []
                
                # Merge and deduplicate
                existing_timestamps = {c.timestamp for c in self._candles[cache_key]}
                new_candles = [c for c in candles if c.timestamp not in existing_timestamps]
                self._candles[cache_key].extend(new_candles)
                self._candles[cache_key].sort(key=lambda c: c.timestamp)
                
                # Update latest candle
                if candles:
                    self._update_latest_candle(candles[-1])
            
            # Save to database
            if self.pool and candles:
                await self._save_candles(candles)
            
            # Record success
            self._candle_cb.record_success()
            
            return candles
            
        except Exception as e:
            self._candle_cb.record_failure()
            logger.error(f"Error getting candles: {e}")
            
            # Return cached candles if available
            cache_key = f"{exchange}:{symbol}:{interval.value}"
            if cache_key in self._candles:
                return self._candles[cache_key][:limit]
            
            raise
    
    async def get_latest_candle(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        refresh: bool = False
    ) -> Optional[Candle]:
        """
        Get the latest candle for a symbol.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            refresh: Force refresh
            
        Returns:
            Latest Candle or None
        """
        if not refresh:
            cache_key = f"{exchange}:{symbol}:{interval.value}"
            if cache_key in self._latest:
                return self._latest[cache_key]
        
        # Get candles
        candles = await self.get_candles(exchange, symbol, interval, limit=1, refresh=refresh)
        
        if candles:
            return candles[-1]
        
        return None
    
    async def get_candles_dataframe(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
        refresh: bool = False
    ) -> pd.DataFrame:
        """
        Get candles as pandas DataFrame.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of candles
            refresh: Force refresh
            
        Returns:
            pandas DataFrame with candle data
        """
        candles = await self.get_candles(exchange, symbol, interval, start_time, end_time, limit, refresh)
        
        if not candles:
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
                'quote_volume': float(c.quote_volume) if c.quote_volume else None,
                'trade_count': c.trade_count
            }
            for c in candles
        ])
        
        df.set_index('datetime', inplace=True)
        return df
    
    # =========================================================================
    # CANDLE FETCHING
    # =========================================================================
    
    async def _fetch_candles(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> List[Candle]:
        """
        Fetch candles from exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of candles
            
        Returns:
            List of Candle
        """
        # Use market data manager to get candles
        try:
            bars = await self.market_data.get_klines(exchange, symbol, interval.value, limit)
            
            candles = []
            for bar in bars:
                candle = Candle(
                    exchange=exchange,
                    symbol=symbol,
                    interval=interval,
                    timestamp=int(bar.get('timestamp', 0)) if 'timestamp' in bar else int(bar.get('t', 0)),
                    open=Decimal(str(bar.get('open', 0))),
                    high=Decimal(str(bar.get('high', 0))),
                    low=Decimal(str(bar.get('low', 0))),
                    close=Decimal(str(bar.get('close', 0))),
                    volume=Decimal(str(bar.get('volume', 0))),
                    quote_volume=Decimal(str(bar.get('quote_volume', 0))) if bar.get('quote_volume') else None,
                    trade_count=bar.get('trade_count'),
                    source=MarketDataSource.REST,
                    status=CandleStatus.CLOSED
                )
                candles.append(candle)
            
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching candles from {exchange}: {e}")
            raise
    
    # =========================================================================
    # REAL-TIME UPDATES
    # =========================================================================
    
    async def update_candle(self, candle: Candle):
        """
        Update a candle in real-time.
        
        Args:
            candle: Candle data
        """
        async with self._lock:
            cache_key = f"{candle.exchange}:{candle.symbol}:{candle.interval.value}"
            
            if cache_key not in self._candles:
                self._candles[cache_key] = []
            
            # Check if candle exists
            existing_idx = None
            for i, c in enumerate(self._candles[cache_key]):
                if c.timestamp == candle.timestamp:
                    existing_idx = i
                    break
            
            if existing_idx is not None:
                # Update existing candle
                self._candles[cache_key][existing_idx] = candle
                candle.status = CandleStatus.UPDATED
            else:
                # Add new candle
                self._candles[cache_key].append(candle)
                self._candles[cache_key].sort(key=lambda c: c.timestamp)
            
            # Update latest candle
            self._update_latest_candle(candle)
        
        # Save to database
        if self.pool:
            await self._save_candle(candle)
        
        # Trigger handlers
        await self._trigger_handlers(candle)
    
    def _update_latest_candle(self, candle: Candle):
        """Update the latest candle cache."""
        cache_key = f"{candle.exchange}:{candle.symbol}:{candle.interval.value}"
        if cache_key not in self._latest:
            self._latest[cache_key] = candle
        elif self._latest[cache_key].timestamp <= candle.timestamp:
            self._latest[cache_key] = candle
    
    # =========================================================================
    # CANDLE PATTERN DETECTION
    # =========================================================================
    
    async def detect_patterns(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        lookback: int = 50
    ) -> List[CandlePatternResult]:
        """
        Detect candle patterns.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            lookback: Number of candles to look back
            
        Returns:
            List of CandlePatternResult
        """
        candles = await self.get_candles(exchange, symbol, interval, limit=lookback)
        
        if len(candles) < 3:
            return []
        
        patterns = []
        
        # Convert to list for easier access
        c = candles
        
        # Check for patterns
        for i in range(len(c) - 2, -1, -1):
            # Doji
            if self._is_doji(c[i]):
                patterns.append(CandlePatternResult(
                    pattern=CandlePattern.DOJI,
                    confidence=Decimal('0.8'),
                    bullish=self._is_bullish_doji(c[i])
                ))
            
            # Hammer
            if self._is_hammer(c[i]):
                patterns.append(CandlePatternResult(
                    pattern=CandlePattern.HAMMER,
                    confidence=Decimal('0.7'),
                    bullish=True
                ))
            
            # Shooting Star
            if self._is_shooting_star(c[i]):
                patterns.append(CandlePatternResult(
                    pattern=CandlePattern.SHOOTING_STAR,
                    confidence=Decimal('0.7'),
                    bullish=False
                ))
            
            # Engulfing
            if i > 0:
                if self._is_bullish_engulfing(c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.ENGULFING_BULLISH,
                        confidence=Decimal('0.8'),
                        bullish=True
                    ))
                elif self._is_bearish_engulfing(c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.ENGULFING_BEARISH,
                        confidence=Decimal('0.8'),
                        bullish=False
                    ))
            
            # Morning Star
            if i > 1:
                if self._is_morning_star(c[i-2], c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.MORNING_STAR,
                        confidence=Decimal('0.7'),
                        bullish=True
                    ))
            
            # Evening Star
            if i > 1:
                if self._is_evening_star(c[i-2], c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.EVENING_STAR,
                        confidence=Decimal('0.7'),
                        bullish=False
                    ))
            
            # Three White Soldiers
            if i > 2:
                if self._is_three_white_soldiers(c[i-3], c[i-2], c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.THREE_WHITE_SOLDIERS,
                        confidence=Decimal('0.8'),
                        bullish=True
                    ))
            
            # Three Black Crows
            if i > 2:
                if self._is_three_black_crows(c[i-3], c[i-2], c[i-1], c[i]):
                    patterns.append(CandlePatternResult(
                        pattern=CandlePattern.THREE_BLACK_CROWS,
                        confidence=Decimal('0.8'),
                        bullish=False
                    ))
        
        # Save patterns
        key = f"{exchange}:{symbol}:{interval.value}"
        if key not in self._patterns:
            self._patterns[key] = []
        self._patterns[key].extend(patterns)
        
        return patterns
    
    # =========================================================================
    # PATTERN DETECTION HELPERS
    # =========================================================================
    
    def _is_doji(self, candle: Candle) -> bool:
        """Check if candle is doji."""
        return candle.is_doji
    
    def _is_bullish_doji(self, candle: Candle) -> bool:
        """Check if doji is bullish."""
        return candle.close >= candle.open
    
    def _is_hammer(self, candle: Candle) -> bool:
        """Check if candle is hammer."""
        if candle.range == 0:
            return False
        lower_wick = candle.lower_wick
        upper_wick = candle.upper_wick
        body = candle.body
        
        return (lower_wick >= body * 2 and 
                upper_wick <= body * 0.3 and
                body > 0)
    
    def _is_shooting_star(self, candle: Candle) -> bool:
        """Check if candle is shooting star."""
        if candle.range == 0:
            return False
        lower_wick = candle.lower_wick
        upper_wick = candle.upper_wick
        body = candle.body
        
        return (upper_wick >= body * 2 and 
                lower_wick <= body * 0.3 and
                body > 0)
    
    def _is_bullish_engulfing(self, prev: Candle, curr: Candle) -> bool:
        """Check if bullish engulfing."""
        return (prev.is_bearish and 
                curr.is_bullish and 
                curr.open < prev.close and 
                curr.close > prev.open)
    
    def _is_bearish_engulfing(self, prev: Candle, curr: Candle) -> bool:
        """Check if bearish engulfing."""
        return (prev.is_bullish and 
                curr.is_bearish and 
                curr.open > prev.close and 
                curr.close < prev.open)
    
    def _is_morning_star(self, c1: Candle, c2: Candle, c3: Candle) -> bool:
        """Check if morning star pattern."""
        return (c1.is_bearish and
                c2.is_doji and
                c3.is_bullish and
                c2.low < c1.close and
                c3.close > (c1.open + c1.close) / 2)
    
    def _is_evening_star(self, c1: Candle, c2: Candle, c3: Candle) -> bool:
        """Check if evening star pattern."""
        return (c1.is_bullish and
                c2.is_doji and
                c3.is_bearish and
                c2.high > c1.close and
                c3.close < (c1.open + c1.close) / 2)
    
    def _is_three_white_soldiers(self, c1: Candle, c2: Candle, c3: Candle, c4: Candle) -> bool:
        """Check if three white soldiers pattern."""
        return (c1.is_bullish and
                c2.is_bullish and
                c3.is_bullish and
                c2.open > c1.open and
                c2.close > c1.close and
                c3.open > c2.open and
                c3.close > c2.close)
    
    def _is_three_black_crows(self, c1: Candle, c2: Candle, c3: Candle, c4: Candle) -> bool:
        """Check if three black crows pattern."""
        return (c1.is_bearish and
                c2.is_bearish and
                c3.is_bearish and
                c2.open < c1.open and
                c2.close < c1.close and
                c3.open < c2.open and
                c3.close < c2.close)
    
    # =========================================================================
    # TECHNICAL INDICATORS
    # =========================================================================
    
    async def calculate_sma(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        period: int,
        limit: int = 100
    ) -> List[Tuple[datetime, Decimal]]:
        """
        Calculate Simple Moving Average.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            period: SMA period
            limit: Number of candles
            
        Returns:
            List of (timestamp, sma_value)
        """
        df = await self.get_candles_dataframe(exchange, symbol, interval, limit=limit)
        
        if df.empty:
            return []
        
        sma = df['close'].rolling(window=period).mean()
        
        return [(idx, Decimal(str(val))) for idx, val in sma.items() if not pd.isna(val)]
    
    async def calculate_ema(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        period: int,
        limit: int = 100
    ) -> List[Tuple[datetime, Decimal]]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            period: EMA period
            limit: Number of candles
            
        Returns:
            List of (timestamp, ema_value)
        """
        df = await self.get_candles_dataframe(exchange, symbol, interval, limit=limit)
        
        if df.empty:
            return []
        
        ema = df['close'].ewm(span=period, adjust=False).mean()
        
        return [(idx, Decimal(str(val))) for idx, val in ema.items() if not pd.isna(val)]
    
    async def calculate_rsi(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        period: int = 14,
        limit: int = 100
    ) -> List[Tuple[datetime, Decimal]]:
        """
        Calculate Relative Strength Index.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            period: RSI period
            limit: Number of candles
            
        Returns:
            List of (timestamp, rsi_value)
        """
        df = await self.get_candles_dataframe(exchange, symbol, interval, limit=limit)
        
        if df.empty:
            return []
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return [(idx, Decimal(str(val))) for idx, val in rsi.items() if not pd.isna(val)]
    
    async def calculate_macd(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        limit: int = 100
    ) -> Dict[str, List[Tuple[datetime, Decimal]]]:
        """
        Calculate MACD.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            limit: Number of candles
            
        Returns:
            Dict with 'macd', 'signal', and 'histogram' lists
        """
        df = await self.get_candles_dataframe(exchange, symbol, interval, limit=limit)
        
        if df.empty:
            return {'macd': [], 'signal': [], 'histogram': []}
        
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': [(idx, Decimal(str(val))) for idx, val in macd_line.items() if not pd.isna(val)],
            'signal': [(idx, Decimal(str(val))) for idx, val in signal_line.items() if not pd.isna(val)],
            'histogram': [(idx, Decimal(str(val))) for idx, val in histogram.items() if not pd.isna(val)]
        }
    
    async def calculate_bollinger_bands(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        period: int = 20,
        std_dev: float = 2.0,
        limit: int = 100
    ) -> Dict[str, List[Tuple[datetime, Decimal]]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            period: Moving average period
            std_dev: Standard deviation multiplier
            limit: Number of candles
            
        Returns:
            Dict with 'upper', 'middle', and 'lower' lists
        """
        df = await self.get_candles_dataframe(exchange, symbol, interval, limit=limit)
        
        if df.empty:
            return {'upper': [], 'middle': [], 'lower': []}
        
        middle = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        
        return {
            'upper': [(idx, Decimal(str(val))) for idx, val in upper.items() if not pd.isna(val)],
            'middle': [(idx, Decimal(str(val))) for idx, val in middle.items() if not pd.isna(val)],
            'lower': [(idx, Decimal(str(val))) for idx, val in lower.items() if not pd.isna(val)]
        }
    
    # =========================================================================
    # CANDLE STATISTICS
    # =========================================================================
    
    async def calculate_statistics(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        limit: int = 100
    ) -> CandleStatistics:
        """
        Calculate statistics for candles.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            limit: Number of candles
            
        Returns:
            CandleStatistics
        """
        candles = await self.get_candles(exchange, symbol, interval, limit=limit)
        
        if not candles:
            return CandleStatistics(
                exchange=exchange,
                symbol=symbol,
                interval=interval
            )
        
        high = max(c.high for c in candles)
        low = min(c.low for c in candles)
        total_volume = sum(c.volume for c in candles)
        avg_high = sum(c.high for c in candles) / len(candles)
        avg_low = sum(c.low for c in candles) / len(candles)
        avg_close = sum(c.close for c in candles) / len(candles)
        avg_volume = total_volume / len(candles)
        
        # Calculate volatility
        returns = [float((c.close - c.open) / c.open) for c in candles if c.open > 0]
        volatility = np.std(returns) if returns else 0
        
        bullish = sum(1 for c in candles if c.is_bullish)
        bearish = sum(1 for c in candles if c.is_bearish)
        doji = sum(1 for c in candles if c.is_doji)
        
        bodies = [c.body for c in candles]
        max_body = max(bodies) if bodies else Decimal('0')
        avg_body = sum(bodies) / len(bodies) if bodies else Decimal('0')
        
        return CandleStatistics(
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            count=len(candles),
            open_time=candles[0].datetime if candles else None,
            close_time=candles[-1].datetime if candles else None,
            high=high,
            low=low,
            average_high=avg_high.quantize(Decimal('0.0001')),
            average_low=avg_low.quantize(Decimal('0.0001')),
            average_close=avg_close.quantize(Decimal('0.0001')),
            average_volume=avg_volume.quantize(Decimal('0.0001')),
            volatility=Decimal(str(volatility)).quantize(Decimal('0.0001')),
            total_volume=total_volume.quantize(Decimal('0.0001')),
            bullish_count=bullish,
            bearish_count=bearish,
            doji_count=doji,
            max_body=max_body.quantize(Decimal('0.0001')),
            avg_body=avg_body.quantize(Decimal('0.0001'))
        )
    
    # =========================================================================
    # CANDLE QUALITY
    # =========================================================================
    
    async def check_quality(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval
    ) -> CandleQuality:
        """
        Check candle data quality.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            
        Returns:
            CandleQuality
        """
        key = f"{exchange}:{symbol}:{interval.value}"
        
        if key not in self._quality:
            return CandleQuality.UNKNOWN
        
        quality_data = self._quality[key]
        quality_score = quality_data.get('quality_score', 0)
        
        if quality_score >= 90:
            return CandleQuality.EXCELLENT
        elif quality_score >= 75:
            return CandleQuality.GOOD
        elif quality_score >= 50:
            return CandleQuality.FAIR
        else:
            return CandleQuality.POOR
    
    async def update_quality(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        candles: List[Candle]
    ):
        """
        Update candle quality metrics.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            interval: Candle interval
            candles: List of candles
        """
        if not candles:
            return
        
        key = f"{exchange}:{symbol}:{interval.value}"
        
        if key not in self._quality:
            self._quality[key] = {
                'total_count': 0,
                'missing_count': 0,
                'invalid_count': 0,
                'duplicate_count': 0,
                'quality_score': 100
            }
        
        quality = self._quality[key]
        
        # Check for duplicates
        timestamps = [c.timestamp for c in candles]
        duplicate_count = len(timestamps) - len(set(timestamps))
        
        # Check for invalid candles
        invalid_count = sum(1 for c in candles if c.status == CandleStatus.INVALID)
        
        # Calculate quality score
        total = len(candles)
        quality['total_count'] += total
        quality['invalid_count'] += invalid_count
        quality['duplicate_count'] += duplicate_count
        
        # Calculate missing count (expected vs actual)
        if total > 1:
            interval_seconds = INTERVAL_SECONDS[interval]
            expected = int((candles[-1].timestamp - candles[0].timestamp) / interval_seconds) + 1
            missing = expected - len(set(timestamps))
            quality['missing_count'] += max(0, missing)
        
        # Quality score (100% - deductions)
        quality_score = 100
        quality_score -= (quality['invalid_count'] / max(1, quality['total_count'])) * 20
        quality_score -= (quality['duplicate_count'] / max(1, quality['total_count'])) * 10
        quality_score -= (quality['missing_count'] / max(1, quality['total_count'])) * 30
        quality['quality_score'] = max(0, min(100, quality_score))
        
        # Save to database
        if self.pool:
            await self._save_quality(exchange, symbol, interval, quality)
    
    # =========================================================================
    # CANDLE RESAMPLING
    # =========================================================================
    
    async def resample_candles(
        self,
        exchange: str,
        symbol: str,
        from_interval: CandleInterval,
        to_interval: CandleInterval,
        limit: int = 100
    ) -> List[Candle]:
        """
        Resample candles to a higher timeframe.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            from_interval: Source interval
            to_interval: Target interval
            limit: Number of candles
            
        Returns:
            List of resampled Candle
        """
        # Get source candles
        candles = await self.get_candles(exchange, symbol, from_interval, limit=limit * 10)
        
        if not candles:
            return []
        
        # Convert to DataFrame
        df = await self.get_candles_dataframe(exchange, symbol, from_interval, limit=limit * 10)
        
        if df.empty:
            return []
        
        # Resample to target interval
        interval_seconds = INTERVAL_SECONDS[to_interval]
        resampled = df.resample(f'{interval_seconds}S').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Convert back to candles
        result = []
        for idx, row in resampled.iterrows():
            candle = Candle(
                exchange=exchange,
                symbol=symbol,
                interval=to_interval,
                timestamp=int(idx.timestamp()),
                open=Decimal(str(row['open'])),
                high=Decimal(str(row['high'])),
                low=Decimal(str(row['low'])),
                close=Decimal(str(row['close'])),
                volume=Decimal(str(row['volume'])),
                source=MarketDataSource.AGGREGATED,
                status=CandleStatus.CLOSED
            )
            result.append(candle)
        
        return result
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_candle_update(self, handler: Callable):
        """Register a candle update handler."""
        key = "candle_update"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
    
    async def _trigger_handlers(self, candle: Candle):
        """Trigger candle update handlers."""
        key = "candle_update"
        if key in self._handlers:
            for handler in self._handlers[key]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(candle)
                    else:
                        handler(candle)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
    
    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    
    async def _update_loop(self):
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Update quality metrics
                for cache_key, candles in self._candles.items():
                    if candles:
                        parts = cache_key.split(':')
                        exchange, symbol, interval_str = parts[0], parts[1], parts[2]
                        interval = CandleInterval(interval_str)
                        await self.update_quality(exchange, symbol, interval, candles)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_candles(self):
        """Load candles from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM arbitrage_candles 
                    ORDER BY timestamp DESC LIMIT 10000
                    """
                )
                
                for row in rows:
                    candle = Candle(
                        id=row['id'],
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        interval=CandleInterval(row['interval']),
                        timestamp=row['timestamp'],
                        open=row['open'],
                        high=row['high'],
                        low=row['low'],
                        close=row['close'],
                        volume=row['volume'],
                        quote_volume=row['quote_volume'],
                        trade_count=row['trade_count'],
                        status=CandleStatus(row['status']),
                        source=MarketDataSource(row['source']),
                        quality=CandleQuality(row['quality']),
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        metadata=row['metadata'] or {}
                    )
                    
                    cache_key = f"{candle.exchange}:{candle.symbol}:{candle.interval.value}"
                    if cache_key not in self._candles:
                        self._candles[cache_key] = []
                    self._candles[cache_key].append(candle)
                    
                    # Update latest
                    self._update_latest_candle(candle)
                
                logger.info(f"Loaded {len(self._candles)} candles")
                
        except Exception as e:
            logger.error(f"Error loading candles: {e}")
    
    async def _save_candle(self, candle: Candle):
        """Save candle to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_candles (
                        id, exchange, symbol, interval, timestamp,
                        open, high, low, close, volume,
                        quote_volume, trade_count, status,
                        source, quality, created_at, updated_at,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14, $15,
                              $16, $17, $18)
                    ON CONFLICT (exchange, symbol, interval, timestamp) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        quote_volume = EXCLUDED.quote_volume,
                        trade_count = EXCLUDED.trade_count,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    candle.id,
                    candle.exchange,
                    candle.symbol,
                    candle.interval.value,
                    candle.timestamp,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.quote_volume,
                    candle.trade_count,
                    candle.status.value,
                    candle.source.value,
                    candle.quality.value,
                    candle.created_at,
                    candle.updated_at,
                    json.dumps(candle.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving candle: {e}")
    
    async def _save_candles(self, candles: List[Candle]):
        """Save multiple candles to database."""
        for candle in candles:
            await self._save_candle(candle)
    
    async def _save_quality(
        self,
        exchange: str,
        symbol: str,
        interval: CandleInterval,
        quality: Dict[str, Any]
    ):
        """Save quality metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO candle_quality (
                        exchange, symbol, interval,
                        quality, missing_count, invalid_count,
                        duplicate_count, total_count, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (exchange, symbol, interval) DO UPDATE SET
                        quality = EXCLUDED.quality,
                        missing_count = EXCLUDED.missing_count,
                        invalid_count = EXCLUDED.invalid_count,
                        duplicate_count = EXCLUDED.duplicate_count,
                        total_count = EXCLUDED.total_count,
                        timestamp = EXCLUDED.timestamp
                    """,
                    exchange,
                    symbol,
                    interval.value,
                    quality['quality_score'],
                    quality['missing_count'],
                    quality['invalid_count'],
                    quality['duplicate_count'],
                    quality['total_count'],
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving quality: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the candle manager."""
        self._running = False
        logger.info("CandleManager shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CandleManager',
    'CandleInterval',
    'CandleStatus',
    'CandlePattern',
    'CandleQuality',
    'Candle',
    'CandlePatternResult',
    'CandleStatistics',
    'INTERVAL_SECONDS',
    'INTERVAL_DISPLAY',
    'CircuitBreakerOpenError'
]
