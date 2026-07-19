# trading/bots/arbitrage_bot/core/market_data.py
# Nexus AI Trading System - Arbitrage Bot Market Data Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Market Data Module

This module provides comprehensive market data management for the arbitrage
bot system, including:

- Real-time price data aggregation
- Multi-exchange price synchronization
- Order book management
- Trade history tracking
- Price feed normalization
- Data caching and persistence
- WebSocket integration
- Price spread analysis
- Volume analysis
- Liquidity analysis
- Market depth analysis
- Price volatility tracking
- Data quality monitoring
- Historical data management

The market data module ensures the arbitrage bot has access to accurate,
up-to-date market data across all exchanges for opportunity detection.
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
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeConnector, ExchangePrice, ExchangeOrderBook
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class MarketDataSource(str, Enum):
    """Market data source types."""
    REST = "rest"
    WEBSOCKET = "websocket"
    CACHE = "cache"
    DATABASE = "database"
    AGGREGATED = "aggregated"


class MarketDataStatus(str, Enum):
    """Market data status."""
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class SpreadType(str, Enum):
    """Spread types."""
    BID_ASK = "bid_ask"
    EXCHANGE = "exchange"
    CROSS_EXCHANGE = "cross_exchange"
    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class MarketDataConfig(BaseModel):
    """Market data configuration."""
    enabled: bool = True
    cache_ttl: int = 5  # seconds
    stale_threshold: int = 10  # seconds
    expire_threshold: int = 30  # seconds
    max_depth: int = 100
    max_history: int = 10000
    persist_data: bool = True
    websocket_reconnect: bool = True
    websocket_timeout: int = 30
    rest_timeout: int = 10
    rate_limit: int = 100  # requests per second
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketPrice(BaseModel):
    """Market price data."""
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    mid: Decimal
    spread: Decimal
    spread_percent: Decimal
    volume_24h: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    source: MarketDataSource = MarketDataSource.REST
    status: MarketDataStatus = MarketDataStatus.FRESH
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('bid', 'ask', 'last')
    def validate_prices(cls, v):
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @property
    def is_valid(self) -> bool:
        """Check if price data is valid."""
        return self.bid > 0 and self.ask > 0 and self.ask >= self.bid

    @property
    def age_seconds(self) -> float:
        """Get age of data in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()


class MarketDepth(BaseModel):
    """Market depth data."""
    exchange: str
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # (price, volume)
    asks: List[Tuple[Decimal, Decimal]]  # (price, volume)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: MarketDataSource = MarketDataSource.REST
    status: MarketDataStatus = MarketDataStatus.FRESH
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_bid_volume(self) -> Decimal:
        """Get total bid volume."""
        return sum(volume for _, volume in self.bids)

    @property
    def total_ask_volume(self) -> Decimal:
        """Get total ask volume."""
        return sum(volume for _, volume in self.asks)

    @property
    def best_bid(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get best bid (price, volume)."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Get best ask (price, volume)."""
        return self.asks[0] if self.asks else None


class MarketTrade(BaseModel):
    """Market trade data."""
    id: str
    exchange: str
    symbol: str
    price: Decimal
    volume: Decimal
    side: str  # 'buy' or 'sell'
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketSpread(BaseModel):
    """Market spread data."""
    exchange: str
    symbol: str
    spread_type: SpreadType
    value: Decimal
    value_percent: Decimal
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketSummary(BaseModel):
    """Market summary data."""
    exchange: str
    symbol: str
    price: Decimal
    volume_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    open_24h: Decimal
    close_24h: Decimal
    change_24h: Decimal
    change_percent_24h: Decimal
    bid: Decimal
    ask: Decimal
    spread: Decimal
    spread_percent: Decimal
    depth_bid: Decimal
    depth_ask: Decimal
    trade_count_24h: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Market prices
CREATE TABLE IF NOT EXISTS market_prices (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    bid DECIMAL(32, 16) NOT NULL,
    ask DECIMAL(32, 16) NOT NULL,
    last DECIMAL(32, 16) NOT NULL,
    mid DECIMAL(32, 16) NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    spread_percent DECIMAL(32, 16) NOT NULL,
    volume_24h DECIMAL(32, 16),
    high_24h DECIMAL(32, 16),
    low_24h DECIMAL(32, 16),
    source VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_market_prices_exchange (exchange),
    INDEX idx_market_prices_symbol (symbol),
    INDEX idx_market_prices_timestamp (timestamp)
);

-- Market depth snapshots
CREATE TABLE IF NOT EXISTS market_depth (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    source VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_market_depth_exchange (exchange),
    INDEX idx_market_depth_symbol (symbol),
    INDEX idx_market_depth_timestamp (timestamp)
);

-- Market trades
CREATE TABLE IF NOT EXISTS market_trades (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    side VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_market_trades_exchange (exchange),
    INDEX idx_market_trades_symbol (symbol),
    INDEX idx_market_trades_timestamp (timestamp)
);

-- Market summary
CREATE TABLE IF NOT EXISTS market_summary (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume_24h DECIMAL(32, 16) NOT NULL,
    high_24h DECIMAL(32, 16) NOT NULL,
    low_24h DECIMAL(32, 16) NOT NULL,
    open_24h DECIMAL(32, 16) NOT NULL,
    close_24h DECIMAL(32, 16) NOT NULL,
    change_24h DECIMAL(32, 16) NOT NULL,
    change_percent_24h DECIMAL(32, 16) NOT NULL,
    bid DECIMAL(32, 16) NOT NULL,
    ask DECIMAL(32, 16) NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    spread_percent DECIMAL(32, 16) NOT NULL,
    depth_bid DECIMAL(32, 16) NOT NULL,
    depth_ask DECIMAL(32, 16) NOT NULL,
    trade_count_24h INTEGER DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    UNIQUE(exchange, symbol)
);
"""


# =============================================================================
# MARKET DATA MANAGER
# =============================================================================

class MarketDataManager:
    """
    Advanced market data manager for arbitrage bot.
    
    Features:
    - Real-time price data aggregation
    - Multi-exchange price synchronization
    - Order book management
    - Trade history tracking
    - Price feed normalization
    - Data caching and persistence
    - WebSocket integration
    - Price spread analysis
    - Volume analysis
    - Liquidity analysis
    - Market depth analysis
    - Price volatility tracking
    - Data quality monitoring
    - Historical data management
    """
    
    def __init__(
        self,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[MarketDataConfig] = None
    ):
        self.redis = redis
        self.pool = pool
        self.config = config or MarketDataConfig()
        
        # Price cache
        self._prices: Dict[str, Dict[str, MarketPrice]] = {}  # exchange -> symbol -> price
        self._depth: Dict[str, Dict[str, MarketDepth]] = {}  # exchange -> symbol -> depth
        self._trades: Dict[str, List[MarketTrade]] = {}  # exchange -> trades
        self._summary: Dict[str, Dict[str, MarketSummary]] = {}  # exchange -> symbol -> summary
        
        # Exchange connectors
        self._connectors: Dict[str, ExchangeConnector] = {}
        
        # Circuit breakers
        self._market_cb = CircuitBreaker(
            name="market_data",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Update tasks
        self._update_tasks: Dict[str, asyncio.Task] = {}
        
        # Subscription handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        logger.info("MarketDataManager initialized")
    
    async def initialize(self):
        """Initialize the market data manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load cached data
        if self.redis:
            await self._load_cached_data()
        
        self._running = True
        
        # Start periodic update
        asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("MarketDataManager initialized")
    
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
    # CONNECTOR MANAGEMENT
    # =========================================================================
    
    def register_connector(self, connector: ExchangeConnector):
        """
        Register an exchange connector.
        
        Args:
            connector: Exchange connector instance
        """
        self._connectors[connector.config.exchange] = connector
        
        # Initialize data structures
        exchange = connector.config.exchange
        if exchange not in self._prices:
            self._prices[exchange] = {}
        if exchange not in self._depth:
            self._depth[exchange] = {}
        if exchange not in self._trades:
            self._trades[exchange] = []
        if exchange not in self._summary:
            self._summary[exchange] = {}
        
        logger.info(f"Registered connector for {exchange}")
    
    async def connect_all(self):
        """Connect all registered connectors."""
        for exchange, connector in self._connectors.items():
            try:
                await connector.connect()
                logger.info(f"Connected to {exchange}")
            except Exception as e:
                logger.error(f"Error connecting to {exchange}: {e}")
    
    async def disconnect_all(self):
        """Disconnect all registered connectors."""
        for exchange, connector in self._connectors.items():
            try:
                await connector.disconnect()
                logger.info(f"Disconnected from {exchange}")
            except Exception as e:
                logger.error(f"Error disconnecting from {exchange}: {e}")
    
    # =========================================================================
    # PRICE DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def get_price(
        self,
        exchange: str,
        symbol: str,
        refresh: bool = False
    ) -> MarketPrice:
        """
        Get current price for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            refresh: Force refresh
            
        Returns:
            MarketPrice
        """
        exchange = exchange.lower()
        symbol = symbol.upper()
        
        # Check cache
        if not refresh:
            async with self._lock:
                if exchange in self._prices and symbol in self._prices[exchange]:
                    price = self._prices[exchange][symbol]
                    if price.age_seconds < self.config.cache_ttl:
                        return price
        
        # Get from connector
        connector = self._connectors.get(exchange)
        if not connector:
            raise ValueError(f"No connector for {exchange}")
        
        try:
            # Get price from connector
            exchange_price = await connector.get_price(symbol)
            
            # Convert to MarketPrice
            market_price = MarketPrice(
                exchange=exchange,
                symbol=symbol,
                bid=exchange_price.bid,
                ask=exchange_price.ask,
                last=exchange_price.last,
                mid=exchange_price.mid,
                spread=exchange_price.spread,
                spread_percent=exchange_price.spread_percent,
                volume_24h=exchange_price.volume_24h,
                high_24h=exchange_price.high_24h,
                low_24h=exchange_price.low_24h,
                source=MarketDataSource.REST,
                status=MarketDataStatus.FRESH,
                timestamp=exchange_price.timestamp,
                metadata=exchange_price.metadata
            )
            
            # Update cache
            async with self._lock:
                if exchange not in self._prices:
                    self._prices[exchange] = {}
                self._prices[exchange][symbol] = market_price
            
            # Cache in Redis
            if self.redis:
                await self._cache_price(market_price)
            
            # Save to database
            if self.pool:
                await self._save_price(market_price)
            
            return market_price
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol} on {exchange}: {e}")
            
            # Return cached price if available
            async with self._lock:
                if exchange in self._prices and symbol in self._prices[exchange]:
                    return self._prices[exchange][symbol]
            
            raise
    
    async def get_prices(
        self,
        exchanges: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        refresh: bool = False
    ) -> Dict[str, Dict[str, MarketPrice]]:
        """
        Get prices for multiple exchanges and symbols.
        
        Args:
            exchanges: List of exchanges (None = all)
            symbols: List of symbols (None = all)
            refresh: Force refresh
            
        Returns:
            Dict mapping exchange -> symbol -> price
        """
        if exchanges is None:
            exchanges = list(self._connectors.keys())
        
        result = {}
        tasks = []
        
        for exchange in exchanges:
            if symbols is None:
                # Get all symbols from connector
                connector = self._connectors.get(exchange)
                if connector:
                    # This would need a method to get supported symbols
                    pass
            
            for symbol in (symbols or []):
                tasks.append(self.get_price(exchange, symbol, refresh))
        
        if tasks:
            prices = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, price in enumerate(prices):
                if isinstance(price, Exception):
                    logger.error(f"Error getting price: {price}")
                    continue
                
                exchange = price.exchange
                symbol = price.symbol
                
                if exchange not in result:
                    result[exchange] = {}
                result[exchange][symbol] = price
        
        return result
    
    # =========================================================================
    # ORDER BOOK DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def get_depth(
        self,
        exchange: str,
        symbol: str,
        depth: int = 10,
        refresh: bool = False
    ) -> MarketDepth:
        """
        Get order book depth for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            depth: Depth level
            refresh: Force refresh
            
        Returns:
            MarketDepth
        """
        exchange = exchange.lower()
        symbol = symbol.upper()
        
        # Check cache
        if not refresh:
            async with self._lock:
                if exchange in self._depth and symbol in self._depth[exchange]:
                    depth_data = self._depth[exchange][symbol]
                    if depth_data.age_seconds < self.config.cache_ttl:
                        return depth_data
        
        # Get from connector
        connector = self._connectors.get(exchange)
        if not connector:
            raise ValueError(f"No connector for {exchange}")
        
        try:
            # Get depth from connector
            exchange_depth = await connector.get_order_book(symbol, depth)
            
            # Convert to MarketDepth
            market_depth = MarketDepth(
                exchange=exchange,
                symbol=symbol,
                bids=exchange_depth.bids[:depth],
                asks=exchange_depth.asks[:depth],
                timestamp=exchange_depth.timestamp,
                source=MarketDataSource.REST,
                status=MarketDataStatus.FRESH,
                metadata=exchange_depth.metadata
            )
            
            # Update cache
            async with self._lock:
                if exchange not in self._depth:
                    self._depth[exchange] = {}
                self._depth[exchange][symbol] = market_depth
            
            # Cache in Redis
            if self.redis:
                await self._cache_depth(market_depth)
            
            return market_depth
            
        except Exception as e:
            logger.error(f"Error getting depth for {symbol} on {exchange}: {e}")
            
            # Return cached depth if available
            async with self._lock:
                if exchange in self._depth and symbol in self._depth[exchange]:
                    return self._depth[exchange][symbol]
            
            raise
    
    # =========================================================================
    # SPREAD ANALYSIS
    # =========================================================================
    
    async def get_spread(
        self,
        exchange: str,
        symbol: str,
        spread_type: SpreadType = SpreadType.BID_ASK
    ) -> MarketSpread:
        """
        Get spread for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            spread_type: Type of spread
            
        Returns:
            MarketSpread
        """
        price = await self.get_price(exchange, symbol)
        
        if spread_type == SpreadType.BID_ASK:
            value = price.spread
            value_percent = price.spread_percent
        elif spread_type == SpreadType.EXCHANGE:
            # Compare to average across exchanges
            all_prices = await self.get_prices(refresh=False)
            avg_mid = sum(p.mid for _, prices in all_prices.items() 
                         for _, p in prices.items() if p.symbol == symbol) / len(all_prices)
            value = abs(price.mid - avg_mid)
            value_percent = value / avg_mid * 100
        else:
            value = price.spread
            value_percent = price.spread_percent
        
        return MarketSpread(
            exchange=exchange,
            symbol=symbol,
            spread_type=spread_type,
            value=value,
            value_percent=value_percent,
            bid_price=price.bid,
            ask_price=price.ask,
            timestamp=datetime.utcnow()
        )
    
    async def get_cross_exchange_spread(
        self,
        exchanges: List[str],
        symbol: str
    ) -> Dict[str, MarketSpread]:
        """
        Get cross-exchange spreads for a symbol.
        
        Args:
            exchanges: List of exchanges
            symbol: Trading symbol
            
        Returns:
            Dict mapping exchange to MarketSpread
        """
        result = {}
        
        for exchange in exchanges:
            try:
                spread = await self.get_spread(
                    exchange,
                    symbol,
                    SpreadType.EXCHANGE
                )
                result[exchange] = spread
            except Exception as e:
                logger.error(f"Error getting spread for {exchange}: {e}")
        
        return result
    
    # =========================================================================
    # DATA AGGREGATION
    # =========================================================================
    
    async def get_best_price(
        self,
        symbol: str,
        side: str = "buy"
    ) -> Tuple[str, MarketPrice]:
        """
        Get best price across all exchanges.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            
        Returns:
            Tuple of (exchange, MarketPrice)
        """
        prices = await self.get_prices(symbols=[symbol])
        
        best_exchange = None
        best_price = None
        
        for exchange, exchange_prices in prices.items():
            if symbol not in exchange_prices:
                continue
            
            price = exchange_prices[symbol]
            
            if side == "buy":
                # Best buy price is lowest ask
                if best_price is None or price.ask < best_price.ask:
                    best_exchange = exchange
                    best_price = price
            else:
                # Best sell price is highest bid
                if best_price is None or price.bid > best_price.bid:
                    best_exchange = exchange
                    best_price = price
        
        if best_exchange is None:
            raise ValueError(f"No price found for {symbol}")
        
        return best_exchange, best_price
    
    async def get_market_summary(
        self,
        exchange: str,
        symbol: str
    ) -> MarketSummary:
        """
        Get market summary for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            
        Returns:
            MarketSummary
        """
        price = await self.get_price(exchange, symbol)
        depth = await self.get_depth(exchange, symbol, depth=10)
        
        # Calculate 24h change
        change_24h = price.last - (price.open_24h or price.last)
        change_percent_24h = change_24h / price.last * 100 if price.last > 0 else Decimal('0')
        
        return MarketSummary(
            exchange=exchange,
            symbol=symbol,
            price=price.last,
            volume_24h=price.volume_24h or Decimal('0'),
            high_24h=price.high_24h or price.last,
            low_24h=price.low_24h or price.last,
            open_24h=price.open_24h or price.last,
            close_24h=price.last,
            change_24h=change_24h,
            change_percent_24h=change_percent_24h,
            bid=price.bid,
            ask=price.ask,
            spread=price.spread,
            spread_percent=price.spread_percent,
            depth_bid=depth.total_bid_volume,
            depth_ask=depth.total_ask_volume,
            timestamp=datetime.utcnow()
        )
    
    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    
    async def _update_loop(self):
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(1)  # Check every second
                
                # Update all prices
                for exchange in self._connectors.keys():
                    try:
                        await self._update_exchange_prices(exchange)
                    except Exception as e:
                        logger.error(f"Error updating prices for {exchange}: {e}")
                
                # Update depth for active symbols
                # This would be triggered by WebSocket updates
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(5)
    
    async def _update_exchange_prices(self, exchange: str):
        """
        Update prices for an exchange.
        
        Args:
            exchange: Exchange name
        """
        connector = self._connectors.get(exchange)
        if not connector:
            return
        
        # Get active symbols (from config or database)
        symbols = self.config.get('symbols', {}).get(exchange, [])
        if not symbols:
            return
        
        for symbol in symbols:
            try:
                await self.get_price(exchange, symbol, refresh=True)
            except Exception as e:
                logger.error(f"Error updating price for {symbol} on {exchange}: {e}")
    
    # =========================================================================
    # WEBSOCKET INTEGRATION
    # =========================================================================
    
    async def subscribe_to_prices(
        self,
        exchange: str,
        symbols: List[str],
        handler: Callable
    ):
        """
        Subscribe to price updates via WebSocket.
        
        Args:
            exchange: Exchange name
            symbols: List of symbols
            handler: Callback function
        """
        connector = self._connectors.get(exchange)
        if not connector:
            raise ValueError(f"No connector for {exchange}")
        
        # Register handler
        key = f"{exchange}:prices"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
        
        # Subscribe via connector
        await connector.subscribe_to_ticker(symbols, self._handle_price_update)
    
    async def _handle_price_update(self, data: Dict[str, Any]):
        """
        Handle price update from WebSocket.
        
        Args:
            data: Price update data
        """
        try:
            # Parse data
            exchange = data.get('exchange')
            symbol = data.get('symbol')
            price = data.get('price')
            
            if not all([exchange, symbol, price]):
                return
            
            # Update cache
            market_price = MarketPrice(
                exchange=exchange,
                symbol=symbol,
                bid=Decimal(str(price.get('bid', 0))),
                ask=Decimal(str(price.get('ask', 0))),
                last=Decimal(str(price.get('last', 0))),
                mid=Decimal(str(price.get('mid', 0))),
                spread=Decimal(str(price.get('spread', 0))),
                spread_percent=Decimal(str(price.get('spread_percent', 0))),
                source=MarketDataSource.WEBSOCKET,
                status=MarketDataStatus.FRESH,
                timestamp=datetime.utcnow()
            )
            
            async with self._lock:
                if exchange not in self._prices:
                    self._prices[exchange] = {}
                self._prices[exchange][symbol] = market_price
            
            # Notify handlers
            key = f"{exchange}:prices"
            if key in self._handlers:
                for handler in self._handlers[key]:
                    try:
                        await handler(market_price)
                    except Exception as e:
                        logger.error(f"Handler error: {e}")
            
        except Exception as e:
            logger.error(f"Error handling price update: {e}")
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_price(self, price: MarketPrice):
        """Cache price in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"market:price:{price.exchange}:{price.symbol}"
            await self.redis.setex(
                key,
                self.config.cache_ttl,
                json.dumps(price.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Error caching price: {e}")
    
    async def _cache_depth(self, depth: MarketDepth):
        """Cache depth in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"market:depth:{depth.exchange}:{depth.symbol}"
            await self.redis.setex(
                key,
                self.config.cache_ttl,
                json.dumps(depth.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Error caching depth: {e}")
    
    async def _load_cached_data(self):
        """Load cached data from Redis."""
        if not self.redis:
            return
        
        try:
            # Load prices
            keys = await self.redis.keys("market:price:*")
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    price_data = json.loads(data)
                    price = MarketPrice(**price_data)
                    
                    exchange = price.exchange
                    symbol = price.symbol
                    
                    if exchange not in self._prices:
                        self._prices[exchange] = {}
                    self._prices[exchange][symbol] = price
            
            # Load depth
            keys = await self.redis.keys("market:depth:*")
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    depth_data = json.loads(data)
                    depth = MarketDepth(**depth_data)
                    
                    exchange = depth.exchange
                    symbol = depth.symbol
                    
                    if exchange not in self._depth:
                        self._depth[exchange] = {}
                    self._depth[exchange][symbol] = depth
            
            logger.info(f"Loaded cached data for {len(self._prices)} exchanges")
            
        except Exception as e:
            logger.error(f"Error loading cached data: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_price(self, price: MarketPrice):
        """Save price to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO market_prices (
                        exchange, symbol, bid, ask, last, mid,
                        spread, spread_percent, volume_24h,
                        high_24h, low_24h, source, status,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15)
                    """,
                    price.exchange,
                    price.symbol,
                    price.bid,
                    price.ask,
                    price.last,
                    price.mid,
                    price.spread,
                    price.spread_percent,
                    price.volume_24h,
                    price.high_24h,
                    price.low_24h,
                    price.source.value,
                    price.status.value,
                    price.timestamp,
                    json.dumps(price.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving price: {e}")
    
    async def _save_depth(self, depth: MarketDepth):
        """Save depth to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO market_depth (
                        exchange, symbol, bids, asks,
                        source, status, timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    depth.exchange,
                    depth.symbol,
                    json.dumps([(float(p), float(v)) for p, v in depth.bids]),
                    json.dumps([(float(p), float(v)) for p, v in depth.asks]),
                    depth.source.value,
                    depth.status.value,
                    depth.timestamp,
                    json.dumps(depth.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving depth: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the market data manager."""
        self._running = False
        
        await self.disconnect_all()
        
        logger.info("MarketDataManager shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MarketDataManager',
    'MarketDataSource',
    'MarketDataStatus',
    'SpreadType',
    'MarketDataConfig',
    'MarketPrice',
    'MarketDepth',
    'MarketTrade',
    'MarketSpread',
    'MarketSummary'
]
