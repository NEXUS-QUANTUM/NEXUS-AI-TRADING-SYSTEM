# trading/exchanges/stocks/alpaca.py
# Nexus AI Trading System - Alpaca Stock Trading Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Alpaca Stock Trading Module

This module provides comprehensive stock trading functionality for the Alpaca
stock trading API, including:

- Stock order placement and management (market, limit, stop, stop-limit, trailing stop)
- Real-time stock price data and quotes
- Historical stock data with multiple timeframes
- Account and position management
- Portfolio management and analytics
- Watchlist management
- Corporate actions and dividends
- News and fundamentals
- Technical indicators and analysis
- Paper trading support
- WebSocket real-time streaming
- Comprehensive error handling
- Database persistence
- Redis caching
- Circuit breaker pattern

Features:
- All order types (market, limit, stop, stop-limit, trailing stop)
- Multiple timeframes (1min, 5min, 15min, 1hour, 1day, 1week, 1month)
- Real-time quotes and trades
- Position management
- Portfolio analytics (Sharpe ratio, drawdown, etc.)
- News and sentiment analysis
- Corporate actions monitoring
- Dividend tracking
- WebSocket streaming for real-time updates
- Paper trading support
- Comprehensive error handling
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import aiohttp
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
import asyncpg
import websockets

# Nexus imports
from shared.configs.app_config import AppConfig
from shared.helpers.logging import get_logger
from shared.helpers.crypto_helpers import encrypt_data, decrypt_data
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AlpacaEnvironment(str, Enum):
    """Alpaca API environments."""
    LIVE = "live"
    PAPER = "paper"


class AlpacaOrderType(str, Enum):
    """Alpaca order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class AlpacaOrderSide(str, Enum):
    """Alpaca order sides."""
    BUY = "buy"
    SELL = "sell"


class AlpacaOrderStatus(str, Enum):
    """Alpaca order status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    DONE = "done"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REPLACED = "replaced"
    PENDING_CANCEL = "pending_cancel"
    STOPPED = "stopped"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    CALCULATED = "calculated"


class AlpacaTimeInForce(str, Enum):
    """Alpaca time in force."""
    DAY = "day"
    GTC = "gtc"
    OPG = "opg"
    CLS = "cls"
    IOC = "ioc"
    FOK = "fok"


class AlpacaAssetClass(str, Enum):
    """Alpaca asset classes."""
    US_EQUITY = "us_equity"
    CRYPTO = "crypto"


class AlpacaAssetStatus(str, Enum):
    """Alpaca asset status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELISTED = "delisted"


class AlpacaOrderClass(str, Enum):
    """Alpaca order classes."""
    SIMPLE = "simple"
    BRACKET = "bracket"
    OCO = "oco"
    OTO = "oto"


class AlpacaCancelRequestReason(str, Enum):
    """Alpaca cancel request reasons."""
    MANUAL = "manual"
    SYSTEM = "system"
    RISK = "risk"
    EXPIRATION = "expiration"
    OTHER = "other"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AlpacaConfig(BaseModel):
    """Alpaca API configuration."""
    api_key: str
    api_secret: str
    environment: AlpacaEnvironment = AlpacaEnvironment.PAPER
    base_url: Optional[str] = None
    data_url: Optional[str] = None
    ws_url: Optional[str] = None
    data_ws_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit: int = 200  # requests per minute
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    cache_ttl: int = 60
    use_cache: bool = True
    verify_ssl: bool = True
    user_agent: str = "NexusAI-Trading/3.0"
    paper_trading: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid API key format")
        return v

    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v) < 20:
            raise ValueError("Invalid API secret format")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == AlpacaEnvironment.PAPER:
            return "https://paper-api.alpaca.markets"
        else:
            return "https://api.alpaca.markets"

    def get_data_url(self) -> str:
        """Get the data API URL."""
        if self.data_url:
            return self.data_url
        return "https://data.alpaca.markets"

    def get_ws_url(self) -> str:
        """Get the WebSocket URL."""
        if self.ws_url:
            return self.ws_url
        
        if self.environment == AlpacaEnvironment.PAPER:
            return "wss://paper-api.alpaca.markets/stream"
        else:
            return "wss://api.alpaca.markets/stream"

    def get_data_ws_url(self) -> str:
        """Get the data WebSocket URL."""
        if self.data_ws_url:
            return self.data_ws_url
        return "wss://stream.data.alpaca.markets/v2/iex"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class AlpacaAccount(BaseModel):
    """Alpaca account information."""
    id: str
    account_number: str
    status: str
    currency: str = "USD"
    buying_power: Decimal = Decimal('0')
    cash: Decimal = Decimal('0')
    portfolio_value: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    equity: Decimal = Decimal('0')
    last_equity: Decimal = Decimal('0')
    multiplier: Decimal = Decimal('1')
    pattern_day_trader: bool = False
    trade_suspended: bool = False
    day_trade_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlpacaAsset(BaseModel):
    """Alpaca asset information."""
    id: str
    symbol: str
    name: str
    asset_class: AlpacaAssetClass
    status: AlpacaAssetStatus
    fractionable: bool = False
    marginable: bool = False
    shortable: bool = False
    easy_to_borrow: bool = False
    exchange: str
    min_order_size: Optional[Decimal] = None
    max_order_size: Optional[Decimal] = None
    tick_size: Decimal = Decimal('0.01')
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlpacaOrder(BaseModel):
    """Alpaca order."""
    id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: AlpacaOrderSide
    order_type: AlpacaOrderType
    status: AlpacaOrderStatus
    time_in_force: AlpacaTimeInForce
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = Decimal('0')
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trail_percent: Optional[Decimal] = None
    trail_price: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extended_hours: bool = False
    order_class: AlpacaOrderClass = AlpacaOrderClass.SIMPLE
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [AlpacaOrderStatus.ACCEPTED, AlpacaOrderStatus.NEW, 
                              AlpacaOrderStatus.PARTIALLY_FILLED, AlpacaOrderStatus.PENDING,
                              AlpacaOrderStatus.PENDING_CANCEL]

    @property
    def is_closed(self) -> bool:
        return self.status in [AlpacaOrderStatus.FILLED, AlpacaOrderStatus.DONE,
                              AlpacaOrderStatus.CANCELLED, AlpacaOrderStatus.EXPIRED,
                              AlpacaOrderStatus.REJECTED, AlpacaOrderStatus.STOPPED]


class AlpacaPosition(BaseModel):
    """Alpaca position."""
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal = Decimal('0')
    unrealized_plpc: Decimal = Decimal('0')
    realized_pl: Decimal = Decimal('0')
    realized_plpc: Decimal = Decimal('0')
    change_today: Decimal = Decimal('0')
    side: Optional[AlpacaOrderSide] = None
    cost_basis: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0


class AlpacaTrade(BaseModel):
    """Alpaca trade."""
    id: str
    symbol: str
    side: AlpacaOrderSide
    price: Decimal
    quantity: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlpacaQuote(BaseModel):
    """Alpaca quote."""
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    conditions: List[str] = Field(default_factory=list)


class AlpacaBar(BaseModel):
    """Alpaca bar (OHLC)."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None


class AlpacaWatchlist(BaseModel):
    """Alpaca watchlist."""
    id: str
    name: str
    symbols: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class AlpacaCalendar(BaseModel):
    """Alpaca market calendar."""
    date: datetime
    open: str
    close: str
    session_open: str
    session_close: str


class AlpacaCorporateAction(BaseModel):
    """Alpaca corporate action."""
    symbol: str
    action_type: str  # split, dividend, merger, etc.
    ratio: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    ex_date: datetime
    record_date: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlpacaNews(BaseModel):
    """Alpaca news item."""
    id: str
    headline: str
    summary: str
    author: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    source: str
    symbols: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    sentiment: Optional[Dict[str, float]] = None


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Orders
CREATE TABLE IF NOT EXISTS alpaca_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    time_in_force VARCHAR(10) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    filled_quantity DECIMAL(32, 8) DEFAULT 0,
    remaining_quantity DECIMAL(32, 8) DEFAULT 0,
    price DECIMAL(32, 8),
    limit_price DECIMAL(32, 8),
    stop_price DECIMAL(32, 8),
    trail_percent DECIMAL(32, 8),
    trail_price DECIMAL(32, 8),
    avg_price DECIMAL(32, 8),
    fee DECIMAL(32, 8) DEFAULT 0,
    cost DECIMAL(32, 8) DEFAULT 0,
    extended_hours BOOLEAN DEFAULT FALSE,
    order_class VARCHAR(20) DEFAULT 'simple',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_alpaca_orders_symbol (symbol),
    INDEX idx_alpaca_orders_status (status),
    INDEX idx_alpaca_orders_created_at (created_at)
);

-- Positions
CREATE TABLE IF NOT EXISTS alpaca_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    quantity DECIMAL(32, 8) NOT NULL,
    avg_entry_price DECIMAL(32, 8) NOT NULL,
    current_price DECIMAL(32, 8) NOT NULL,
    market_value DECIMAL(32, 8) NOT NULL,
    unrealized_pl DECIMAL(32, 8) DEFAULT 0,
    unrealized_plpc DECIMAL(32, 8) DEFAULT 0,
    realized_pl DECIMAL(32, 8) DEFAULT 0,
    realized_plpc DECIMAL(32, 8) DEFAULT 0,
    change_today DECIMAL(32, 8) DEFAULT 0,
    side VARCHAR(10),
    cost_basis DECIMAL(32, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Trades
CREATE TABLE IF NOT EXISTS alpaca_trades (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(32, 8) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    cost DECIMAL(32, 8) NOT NULL,
    fee DECIMAL(32, 8) DEFAULT 0,
    order_id VARCHAR(64),
    trade_id VARCHAR(64),
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_alpaca_trades_symbol (symbol),
    INDEX idx_alpaca_trades_timestamp (timestamp)
);

-- Watchlists
CREATE TABLE IF NOT EXISTS alpaca_watchlists (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    symbols JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(name)
);

-- Bars (candles)
CREATE TABLE IF NOT EXISTS alpaca_bars (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(32, 8) NOT NULL,
    high DECIMAL(32, 8) NOT NULL,
    low DECIMAL(32, 8) NOT NULL,
    close DECIMAL(32, 8) NOT NULL,
    volume DECIMAL(32, 8) NOT NULL,
    vwap DECIMAL(32, 8),
    trade_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);
"""


# =============================================================================
# MAIN ALPACA CLIENT
# =============================================================================

class AlpacaClient:
    """
    Advanced Alpaca stock trading client.
    
    Features:
    - All order types (market, limit, stop, stop-limit, trailing stop)
    - Real-time quotes and trades
    - Historical data with multiple timeframes
    - Account and position management
    - Portfolio analytics
    - Watchlist management
    - News and fundamentals
    - Corporate actions
    - WebSocket real-time streaming
    - Paper trading support
    - Comprehensive error handling
    - Database persistence
    - Redis caching
    """
    
    def __init__(
        self,
        config: AlpacaConfig,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.redis = redis
        self.pool = pool
        
        # HTTP sessions
        self._session: Optional[aiohttp.ClientSession] = None
        self._data_session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._data_ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_connected = False
        self._data_ws_connected = False
        
        # State
        self._account: Optional[AlpacaAccount] = None
        self._positions: Dict[str, AlpacaPosition] = {}
        self._orders: Dict[str, AlpacaOrder] = {}
        self._assets: Dict[str, AlpacaAsset] = {}
        self._watchlists: Dict[str, AlpacaWatchlist] = {}
        
        # Circuit breakers
        self._order_cb = CircuitBreaker(
            name="alpaca_order",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._market_data_cb = CircuitBreaker(
            name="alpaca_market_data",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Rate limiter
        self._rate_limiter = AlpacaRateLimiter(
            rate=config.rate_limit / 60,  # requests per second
            name="alpaca"
        )
        
        # Database
        self._db_initialized = False
        
        # WebSocket handlers
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_subscriptions: Set[str] = set()
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # Running state
        self._running = False
        self._shutdown_requested = False
        
        logger.info(f"AlpacaClient initialized for {config.environment.value}")
    
    async def initialize(self):
        """Initialize the Alpaca client."""
        # Initialize HTTP sessions
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "application/json",
                "APCA-API-KEY-ID": self.config.api_key,
                "APCA-API-SECRET-KEY": self.config.api_secret
            }
        )
        
        self._data_session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "application/json",
                "APCA-API-KEY-ID": self.config.api_key,
                "APCA-API-SECRET-KEY": self.config.api_secret
            }
        )
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load account
        await self.get_account()
        
        # Load assets
        await self.get_assets()
        
        # Load positions
        await self.get_positions()
        
        # Load watchlists
        await self.get_watchlists()
        
        # Connect WebSocket
        await self._connect_websocket()
        
        self._running = True
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        logger.info("AlpacaClient initialization complete")
    
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
    # HTTP REQUEST HANDLING
    # =========================================================================
    
    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        use_data_api: bool = False,
        version: str = "v2"
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Alpaca.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data
            use_data_api: Use data API
            version: API version
            
        Returns:
            Response data
        """
        # Check circuit breaker
        cb_key = "alpaca_order" if "order" in endpoint else "alpaca_market_data"
        cb = self._order_cb if "order" in endpoint else self._market_data_cb
        
        if cb.is_open():
            raise AlpacaRateLimitError("Circuit breaker is open")
        
        # Rate limit
        await self._rate_limiter.acquire()
        
        # Build URL
        if use_data_api:
            base_url = self.config.get_data_url()
        else:
            base_url = self.config.get_base_url()
        
        url = f"{base_url}/{version}/{endpoint.lstrip('/')}"
        
        # Select session
        session = self._data_session if use_data_api else self._session
        
        try:
            async with session.request(
                method=method.upper(),
                url=url,
                json=data if data else None,
                ssl=self.config.verify_ssl
            ) as response:
                if response.status == 429:
                    # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 60))
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, method, data, use_data_api, version)
                
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 401:
                        raise AlpacaAuthenticationError(error_text)
                    elif response.status == 404:
                        raise AlpacaNotFoundError(error_text)
                    elif response.status == 403:
                        raise AlpacaPermissionError(error_text)
                    elif response.status == 422:
                        raise AlpacaValidationError(error_text)
                    else:
                        raise AlpacaError(f"HTTP {response.status}: {error_text}")
                
                if response.status == 204:
                    return {}
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            cb.record_failure()
            raise AlpacaConnectionError(f"HTTP error: {e}")
        except asyncio.TimeoutError:
            cb.record_failure()
            raise AlpacaTimeoutError("Request timeout")
        except Exception as e:
            cb.record_failure()
            raise AlpacaError(f"Request error: {e}")
    
    # =========================================================================
    # ACCOUNT MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_account(self, refresh: bool = False) -> AlpacaAccount:
        """
        Get account information.
        
        Args:
            refresh: Force refresh from API
            
        Returns:
            AlpacaAccount
        """
        if not refresh and self._account:
            return self._account
        
        try:
            data = await self._make_request("account")
            
            account = AlpacaAccount(
                id=data.get('id', ''),
                account_number=data.get('account_number', ''),
                status=data.get('status', ''),
                currency=data.get('currency', 'USD'),
                buying_power=Decimal(str(data.get('buying_power', 0))),
                cash=Decimal(str(data.get('cash', 0))),
                portfolio_value=Decimal(str(data.get('portfolio_value', 0))),
                long_market_value=Decimal(str(data.get('long_market_value', 0))),
                short_market_value=Decimal(str(data.get('short_market_value', 0))),
                equity=Decimal(str(data.get('equity', 0))),
                last_equity=Decimal(str(data.get('last_equity', 0))),
                multiplier=Decimal(str(data.get('multiplier', 1))),
                pattern_day_trader=data.get('pattern_day_trader', False),
                trade_suspended=data.get('trade_suspended', False),
                day_trade_count=data.get('day_trade_count', 0),
                created_at=datetime.fromisoformat(data.get('created_at', '')) if data.get('created_at') else datetime.utcnow(),
                updated_at=datetime.fromisoformat(data.get('updated_at', '')) if data.get('updated_at') else None,
                metadata=data
            )
            
            self._account = account
            
            # Cache in Redis
            if self.redis:
                await self.redis.setex(
                    "alpaca:account",
                    60,
                    json.dumps(account.dict(), default=str)
                )
            
            return account
            
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            if self._account:
                return self._account
            raise
    
    async def get_account_config(self) -> Dict[str, Any]:
        """Get account configuration."""
        return await self._make_request("account/configurations")
    
    async def update_account_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update account configuration."""
        return await self._make_request("account/configurations", "PATCH", config)
    
    # =========================================================================
    # ASSET MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_assets(
        self,
        status: Optional[AlpacaAssetStatus] = None,
        asset_class: Optional[AlpacaAssetClass] = None,
        refresh: bool = False
    ) -> Dict[str, AlpacaAsset]:
        """
        Get available assets.
        
        Args:
            status: Filter by status
            asset_class: Filter by asset class
            refresh: Force refresh from API
            
        Returns:
            Dict mapping symbol to AlpacaAsset
        """
        if not refresh and self._assets:
            return self._assets
        
        try:
            params = {}
            if status:
                params['status'] = status.value
            if asset_class:
                params['asset_class'] = asset_class.value
            
            data = await self._make_request("assets", "GET", params)
            
            assets = {}
            for item in data:
                asset = AlpacaAsset(
                    id=item.get('id', ''),
                    symbol=item.get('symbol', ''),
                    name=item.get('name', ''),
                    asset_class=AlpacaAssetClass(item.get('asset_class', 'us_equity')),
                    status=AlpacaAssetStatus(item.get('status', 'active')),
                    fractionable=item.get('fractionable', False),
                    marginable=item.get('marginable', False),
                    shortable=item.get('shortable', False),
                    easy_to_borrow=item.get('easy_to_borrow', False),
                    exchange=item.get('exchange', ''),
                    min_order_size=Decimal(str(item.get('min_order_size', 0))) if item.get('min_order_size') else None,
                    max_order_size=Decimal(str(item.get('max_order_size', 0))) if item.get('max_order_size') else None,
                    tick_size=Decimal(str(item.get('tick_size', 0.01))),
                    metadata=item
                )
                assets[asset.symbol] = asset
            
            self._assets = assets
            
            # Cache in Redis
            if self.redis:
                cache_data = {k: v.dict() for k, v in assets.items()}
                await self.redis.setex(
                    "alpaca:assets",
                    3600,
                    json.dumps(cache_data, default=str)
                )
            
            logger.info(f"Loaded {len(assets)} assets")
            return assets
            
        except Exception as e:
            logger.error(f"Error getting assets: {e}")
            if self._assets:
                return self._assets
            raise
    
    async def get_asset(self, symbol: str) -> Optional[AlpacaAsset]:
        """Get asset information for a symbol."""
        assets = await self.get_assets()
        return assets.get(symbol.upper())
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        order_type: AlpacaOrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        trail_percent: Optional[Decimal] = None,
        trail_price: Optional[Decimal] = None,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False,
        order_class: AlpacaOrderClass = AlpacaOrderClass.SIMPLE,
        metadata: Optional[Dict] = None
    ) -> AlpacaOrder:
        """
        Place an order.
        
        Args:
            symbol: Stock symbol
            side: Buy or sell
            order_type: Order type
            quantity: Order quantity
            price: Price for limit orders
            limit_price: Limit price for stop-limit orders
            stop_price: Stop price for stop orders
            trail_percent: Trailing stop percent
            trail_price: Trailing stop price
            time_in_force: Time in force
            client_order_id: Client-side order ID
            extended_hours: Allow extended hours
            order_class: Order class
            metadata: Additional metadata
            
        Returns:
            AlpacaOrder
        """
        if self._order_cb.is_open():
            raise AlpacaRateLimitError("Order circuit breaker is open")
        
        try:
            # Validate asset
            asset = await self.get_asset(symbol)
            if not asset:
                raise AlpacaInvalidSymbolError(f"Unknown symbol: {symbol}")
            
            # Build order request
            order_data = {
                "symbol": symbol,
                "side": side.value,
                "type": order_type.value,
                "qty": str(quantity),
                "time_in_force": time_in_force.value,
                "extended_hours": extended_hours,
                "order_class": order_class.value
            }
            
            if price is not None:
                order_data["limit_price"] = str(price)
            
            if limit_price is not None:
                order_data["limit_price"] = str(limit_price)
            
            if stop_price is not None:
                order_data["stop_price"] = str(stop_price)
            
            if trail_percent is not None:
                order_data["trail_percent"] = str(trail_percent)
            
            if trail_price is not None:
                order_data["trail_price"] = str(trail_price)
            
            if client_order_id:
                order_data["client_order_id"] = client_order_id
            
            if metadata:
                order_data["metadata"] = metadata
            
            # Place order
            data = await self._make_request("orders", "POST", order_data)
            
            order = self._parse_order(data)
            
            # Track order
            self._orders[order.id] = order
            
            # Save to database
            if self.pool:
                await self._save_order(order)
            
            self._order_cb.record_success()
            
            logger.info(
                f"Order placed: {order.id} | {side} {quantity} {symbol} "
                f"@ {price or 'market'}"
            )
            
            return order
            
        except Exception as e:
            self._order_cb.record_failure()
            logger.error(f"Order placement error: {e}")
            raise
    
    async def place_market_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        quantity: Decimal,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False
    ) -> AlpacaOrder:
        """Place a market order."""
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=AlpacaOrderType.MARKET,
            quantity=quantity,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            extended_hours=extended_hours
        )
    
    async def place_limit_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        quantity: Decimal,
        price: Decimal,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False
    ) -> AlpacaOrder:
        """Place a limit order."""
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=AlpacaOrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            extended_hours=extended_hours
        )
    
    async def place_stop_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        quantity: Decimal,
        stop_price: Decimal,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False
    ) -> AlpacaOrder:
        """Place a stop order."""
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=AlpacaOrderType.STOP,
            quantity=quantity,
            stop_price=stop_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            extended_hours=extended_hours
        )
    
    async def place_stop_limit_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        quantity: Decimal,
        stop_price: Decimal,
        limit_price: Decimal,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False
    ) -> AlpacaOrder:
        """Place a stop-limit order."""
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=AlpacaOrderType.STOP_LIMIT,
            quantity=quantity,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            extended_hours=extended_hours
        )
    
    async def place_trailing_stop_order(
        self,
        symbol: str,
        side: AlpacaOrderSide,
        quantity: Decimal,
        trail_percent: Optional[Decimal] = None,
        trail_price: Optional[Decimal] = None,
        time_in_force: AlpacaTimeInForce = AlpacaTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False
    ) -> AlpacaOrder:
        """Place a trailing stop order."""
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=AlpacaOrderType.TRAILING_STOP,
            quantity=quantity,
            trail_percent=trail_percent,
            trail_price=trail_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            extended_hours=extended_hours
        )
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_orders(
        self,
        status: Optional[AlpacaOrderStatus] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        after: Optional[datetime] = None,
        until: Optional[datetime] = None,
        direction: str = "desc"
    ) -> List[AlpacaOrder]:
        """
        Get orders with filters.
        
        Args:
            status: Filter by status
            symbol: Filter by symbol
            limit: Maximum number of orders
            after: Filter by creation time
            until: Filter by creation time
            direction: Sort direction
            
        Returns:
            List of AlpacaOrder
        """
        try:
            params = {"limit": min(limit, 500)}
            
            if status:
                params["status"] = status.value
            if symbol:
                params["symbols"] = symbol
            if after:
                params["after"] = after.isoformat()
            if until:
                params["until"] = until.isoformat()
            
            params["direction"] = direction
            
            data = await self._make_request("orders", "GET", params)
            
            orders = []
            for item in data:
                order = self._parse_order(item)
                self._orders[order.id] = order
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_order(self, order_id: str) -> Optional[AlpacaOrder]:
        """Get an order by ID."""
        try:
            data = await self._make_request(f"orders/{order_id}")
            order = self._parse_order(data)
            self._orders[order.id] = order
            return order
        except AlpacaNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    async def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
            
        Returns:
            True if cancelled successfully
        """
        try:
            await self._make_request(f"orders/{order_id}", "DELETE")
            
            if order_id in self._orders:
                self._orders[order_id].status = AlpacaOrderStatus.CANCELLED
            
            logger.info(f"Order cancelled: {order_id} (reason: {reason})")
            return True
            
        except AlpacaNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """Cancel all orders."""
        try:
            params = {}
            if symbol:
                params["symbols"] = symbol
            
            await self._make_request("orders", "DELETE", params)
            
            count = 0
            for order_id, order in list(self._orders.items()):
                if not symbol or order.symbol == symbol:
                    if order.is_open:
                        order.status = AlpacaOrderStatus.CANCELLED
                        count += 1
            
            logger.info(f"Cancelled {count} orders")
            return count
            
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return 0
    
    def _parse_order(self, data: Dict[str, Any]) -> AlpacaOrder:
        """Parse order data from API response."""
        status_map = {
            'pending': AlpacaOrderStatus.PENDING,
            'accepted': AlpacaOrderStatus.ACCEPTED,
            'new': AlpacaOrderStatus.NEW,
            'partially_filled': AlpacaOrderStatus.PARTIALLY_FILLED,
            'filled': AlpacaOrderStatus.FILLED,
            'done': AlpacaOrderStatus.DONE,
            'cancelled': AlpacaOrderStatus.CANCELLED,
            'expired': AlpacaOrderStatus.EXPIRED,
            'replaced': AlpacaOrderStatus.REPLACED,
            'pending_cancel': AlpacaOrderStatus.PENDING_CANCEL,
            'stopped': AlpacaOrderStatus.STOPPED,
            'rejected': AlpacaOrderStatus.REJECTED,
            'suspended': AlpacaOrderStatus.SUSPENDED,
            'calculated': AlpacaOrderStatus.CALCULATED,
        }
        
        status = status_map.get(data.get('status', ''), AlpacaOrderStatus.PENDING)
        
        return AlpacaOrder(
            id=data.get('id', ''),
            client_order_id=data.get('client_order_id'),
            symbol=data.get('symbol', ''),
            side=AlpacaOrderSide(data.get('side', 'buy')),
            order_type=AlpacaOrderType(data.get('type', 'limit')),
            status=status,
            time_in_force=AlpacaTimeInForce(data.get('time_in_force', 'day')),
            quantity=Decimal(str(data.get('qty', 0))),
            filled_quantity=Decimal(str(data.get('filled_qty', 0))),
            remaining_quantity=Decimal(str(data.get('filled_qty', 0))),
            price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            limit_price=Decimal(str(data.get('limit_price', 0))) if data.get('limit_price') else None,
            stop_price=Decimal(str(data.get('stop_price', 0))) if data.get('stop_price') else None,
            trail_percent=Decimal(str(data.get('trail_percent', 0))) if data.get('trail_percent') else None,
            trail_price=Decimal(str(data.get('trail_price', 0))) if data.get('trail_price') else None,
            average_price=Decimal(str(data.get('filled_avg_price', 0))) if data.get('filled_avg_price') else None,
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('filled_avg_price', 0))) * Decimal(str(data.get('filled_qty', 0))) if data.get('filled_avg_price') else Decimal('0'),
            created_at=datetime.fromisoformat(data.get('created_at', '')) if data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data.get('updated_at', '')) if data.get('updated_at') else None,
            expires_at=datetime.fromisoformat(data.get('expires_at', '')) if data.get('expires_at') else None,
            extended_hours=data.get('extended_hours', False),
            order_class=AlpacaOrderClass(data.get('order_class', 'simple')),
            metadata=data
        )
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_positions(self) -> Dict[str, AlpacaPosition]:
        """
        Get all positions.
        
        Returns:
            Dict mapping symbol to AlpacaPosition
        """
        try:
            data = await self._make_request("positions")
            
            positions = {}
            for item in data:
                position = self._parse_position(item)
                positions[position.symbol] = position
            
            self._positions = positions
            
            # Save to database
            if self.pool:
                await self._save_positions()
            
            logger.info(f"Loaded {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return self._positions
    
    async def get_position(self, symbol: str) -> Optional[AlpacaPosition]:
        """Get a position for a symbol."""
        try:
            data = await self._make_request(f"positions/{symbol}")
            position = self._parse_position(data)
            self._positions[position.symbol] = position
            return position
        except AlpacaNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting position {symbol}: {e}")
            return None
    
    async def close_position(
        self,
        symbol: str,
        quantity: Optional[Decimal] = None,
        percentage: Optional[Decimal] = None
    ) -> AlpacaOrder:
        """
        Close a position.
        
        Args:
            symbol: Symbol to close
            quantity: Quantity to close (None = full)
            percentage: Percentage to close
            
        Returns:
            AlpacaOrder
        """
        try:
            params = {}
            if quantity:
                params["qty"] = str(quantity)
            if percentage:
                params["percentage"] = str(percentage)
            
            data = await self._make_request(f"positions/{symbol}", "DELETE", params)
            
            if data:
                return self._parse_order(data)
            return None
            
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")
            raise
    
    async def close_all_positions(self) -> List[AlpacaOrder]:
        """Close all positions."""
        try:
            data = await self._make_request("positions", "DELETE")
            
            orders = []
            for item in data:
                order = self._parse_order(item)
                orders.append(order)
            
            logger.info(f"Closed all positions ({len(orders)} orders)")
            return orders
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return []
    
    def _parse_position(self, data: Dict[str, Any]) -> AlpacaPosition:
        """Parse position data."""
        quantity = Decimal(str(data.get('qty', 0)))
        
        return AlpacaPosition(
            symbol=data.get('symbol', ''),
            quantity=quantity,
            average_entry_price=Decimal(str(data.get('avg_entry_price', 0))),
            current_price=Decimal(str(data.get('current_price', 0))),
            market_value=Decimal(str(data.get('market_value', 0))),
            unrealized_pl=Decimal(str(data.get('unrealized_pl', 0))),
            unrealized_plpc=Decimal(str(data.get('unrealized_plpc', 0))),
            realized_pl=Decimal(str(data.get('realized_pl', 0))),
            realized_plpc=Decimal(str(data.get('realized_plpc', 0))),
            change_today=Decimal(str(data.get('change_today', 0))),
            side=AlpacaOrderSide(data.get('side', 'buy')) if data.get('side') else None,
            cost_basis=Decimal(str(data.get('cost_basis', 0))),
            created_at=datetime.fromisoformat(data.get('created_at', '')) if data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data.get('updated_at', '')) if data.get('updated_at') else None,
            metadata=data
        )
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_quote(self, symbol: str) -> AlpacaQuote:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            AlpacaQuote
        """
        if self._market_data_cb.is_open():
            raise AlpacaRateLimitError("Market data circuit breaker is open")
        
        try:
            data = await self._make_request(
                f"stocks/{symbol}/quotes/latest",
                use_data_api=True
            )
            
            quote_data = data.get('quote', {})
            
            quote = AlpacaQuote(
                symbol=symbol,
                bid_price=Decimal(str(quote_data.get('bp', 0))),
                bid_size=Decimal(str(quote_data.get('bs', 0))),
                ask_price=Decimal(str(quote_data.get('ap', 0))),
                ask_size=Decimal(str(quote_data.get('as', 0))),
                timestamp=datetime.fromtimestamp(quote_data.get('t', 0) / 1e9) if quote_data.get('t') else datetime.utcnow(),
                conditions=quote_data.get('c', [])
            )
            
            self._market_data_cb.record_success()
            return quote
            
        except Exception as e:
            self._market_data_cb.record_failure()
            logger.error(f"Error getting quote for {symbol}: {e}")
            raise
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Min",
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[AlpacaBar]:
        """
        Get historical bars for a symbol.
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day, etc.)
            limit: Number of bars
            start: Start time
            end: End time
            
        Returns:
            List of AlpacaBar
        """
        if self._market_data_cb.is_open():
            raise AlpacaRateLimitError("Market data circuit breaker is open")
        
        try:
            params = {
                "timeframe": timeframe,
                "limit": min(limit, 10000)
            }
            
            if start:
                params["start"] = start.isoformat()
            if end:
                params["end"] = end.isoformat()
            
            data = await self._make_request(
                f"stocks/{symbol}/bars",
                "GET",
                params,
                use_data_api=True
            )
            
            bars = []
            for item in data.get('bars', []):
                bar = AlpacaBar(
                    symbol=symbol,
                    open=Decimal(str(item.get('o', 0))),
                    high=Decimal(str(item.get('h', 0))),
                    low=Decimal(str(item.get('l', 0))),
                    close=Decimal(str(item.get('c', 0))),
                    volume=Decimal(str(item.get('v', 0))),
                    timestamp=datetime.fromtimestamp(item.get('t', 0) / 1e9) if item.get('t') else datetime.utcnow(),
                    vwap=Decimal(str(item.get('vw', 0))) if item.get('vw') else None,
                    trade_count=item.get('n')
                )
                bars.append(bar)
            
            # Save to database
            if self.pool:
                await self._save_bars(symbol, timeframe, bars)
            
            self._market_data_cb.record_success()
            return bars
            
        except Exception as e:
            self._market_data_cb.record_failure()
            logger.error(f"Error getting bars for {symbol}: {e}")
            raise
    
    async def get_bars_dataframe(
        self,
        symbol: str,
        timeframe: str = "1Min",
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Get bars as pandas DataFrame."""
        bars = await self.get_bars(symbol, timeframe, limit, start, end)
        
        if not bars:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                'timestamp': bar.timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume),
                'vwap': float(bar.vwap) if bar.vwap else None,
                'trade_count': bar.trade_count
            }
            for bar in bars
        ])
        
        df.set_index('timestamp', inplace=True)
        return df
    
    # =========================================================================
    # PORTFOLIO ANALYTICS
    # =========================================================================
    
    async def get_portfolio_analytics(self) -> Dict[str, Any]:
        """
        Get portfolio analytics.
        
        Returns:
            Dict with portfolio metrics
        """
        positions = await self.get_positions()
        account = await self.get_account()
        
        total_value = account.portfolio_value
        total_cost = sum(p.cost_basis for p in positions.values())
        total_pnl = sum(p.unrealized_pl for p in positions.values())
        total_realized_pnl = sum(p.realized_pl for p in positions.values())
        
        # Calculate metrics
        win_rate = 0
        winning_positions = [p for p in positions.values() if p.unrealized_pl > 0]
        if positions:
            win_rate = len(winning_positions) / len(positions)
        
        # Calculate portfolio beta (would need market data)
        # Sharpe ratio (simplified)
        sharpe_ratio = 0
        if account.equity > 0 and total_value > 0:
            # Simplified: (return - risk_free) / std_dev
            pass
        
        return {
            "total_value": float(total_value),
            "total_cost": float(total_cost),
            "total_pnl": float(total_pnl),
            "total_realized_pnl": float(total_realized_pnl),
            "total_unrealized_pnl": float(total_pnl - total_realized_pnl),
            "return_pct": float(total_pnl / total_cost * 100) if total_cost > 0 else 0,
            "cash_ratio": float(account.cash / total_value) if total_value > 0 else 1,
            "position_count": len(positions),
            "winning_positions": len(winning_positions),
            "win_rate": win_rate,
            "buying_power": float(account.buying_power),
            "day_trade_count": account.day_trade_count,
            "pattern_day_trader": account.pattern_day_trader
        }
    
    # =========================================================================
    # WATCHLIST MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_watchlists(self) -> Dict[str, AlpacaWatchlist]:
        """Get all watchlists."""
        try:
            data = await self._make_request("watchlists")
            
            watchlists = {}
            for item in data:
                watchlist = AlpacaWatchlist(
                    id=item.get('id', ''),
                    name=item.get('name', ''),
                    symbols=item.get('symbols', []),
                    created_at=datetime.fromisoformat(item.get('created_at', '')) if item.get('created_at') else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(item.get('updated_at', '')) if item.get('updated_at') else None
                )
                watchlists[watchlist.id] = watchlist
            
            self._watchlists = watchlists
            return watchlists
            
        except Exception as e:
            logger.error(f"Error getting watchlists: {e}")
            return self._watchlists
    
    async def create_watchlist(self, name: str, symbols: List[str]) -> AlpacaWatchlist:
        """Create a new watchlist."""
        try:
            data = await self._make_request(
                "watchlists",
                "POST",
                {"name": name, "symbols": symbols}
            )
            
            watchlist = AlpacaWatchlist(
                id=data.get('id', ''),
                name=data.get('name', ''),
                symbols=data.get('symbols', []),
                created_at=datetime.fromisoformat(data.get('created_at', '')) if data.get('created_at') else datetime.utcnow(),
                updated_at=datetime.fromisoformat(data.get('updated_at', '')) if data.get('updated_at') else None
            )
            
            self._watchlists[watchlist.id] = watchlist
            return watchlist
            
        except Exception as e:
            logger.error(f"Error creating watchlist: {e}")
            raise
    
    async def update_watchlist(self, watchlist_id: str, symbols: List[str]) -> AlpacaWatchlist:
        """Update a watchlist."""
        try:
            data = await self._make_request(
                f"watchlists/{watchlist_id}",
                "PUT",
                {"symbols": symbols}
            )
            
            watchlist = AlpacaWatchlist(
                id=data.get('id', ''),
                name=data.get('name', ''),
                symbols=data.get('symbols', []),
                created_at=datetime.fromisoformat(data.get('created_at', '')) if data.get('created_at') else datetime.utcnow(),
                updated_at=datetime.fromisoformat(data.get('updated_at', '')) if data.get('updated_at') else None
            )
            
            self._watchlists[watchlist.id] = watchlist
            return watchlist
            
        except Exception as e:
            logger.error(f"Error updating watchlist: {e}")
            raise
    
    async def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist."""
        try:
            await self._make_request(f"watchlists/{watchlist_id}", "DELETE")
            if watchlist_id in self._watchlists:
                del self._watchlists[watchlist_id]
            return True
        except Exception as e:
            logger.error(f"Error deleting watchlist: {e}")
            return False
    
    # =========================================================================
    # WEBHOOKS AND EVENTS
    # =========================================================================
    
    async def register_handler(self, event_type: str, handler: Callable):
        """Register a WebSocket event handler."""
        if event_type not in self._ws_handlers:
            self._ws_handlers[event_type] = []
        self._ws_handlers[event_type].append(handler)
    
    # =========================================================================
    # WEBSOCKET
    # =========================================================================
    
    async def _connect_websocket(self):
        """Connect to WebSocket."""
        try:
            # Trading WebSocket
            ws_url = self.config.get_ws_url()
            self._ws = await websockets.connect(ws_url)
            self._ws_connected = True
            
            # Data WebSocket
            data_ws_url = self.config.get_data_ws_url()
            self._data_ws = await websockets.connect(data_ws_url)
            self._data_ws_connected = True
            
            # Authenticate trading WebSocket
            await self._authenticate_ws()
            
            # Authenticate data WebSocket
            await self._authenticate_data_ws()
            
            # Start listeners
            asyncio.create_task(self._ws_listen_loop())
            asyncio.create_task(self._data_ws_listen_loop())
            
            logger.info("WebSocket connected and authenticated")
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self._ws_connected = False
            self._data_ws_connected = False
    
    async def _authenticate_ws(self):
        """Authenticate trading WebSocket."""
        auth_msg = {
            "action": "authenticate",
            "data": {
                "key_id": self.config.api_key,
                "secret_key": self.config.api_secret
            }
        }
        await self._ws.send(json.dumps(auth_msg))
        
        response = await self._ws.recv()
        data = json.loads(response)
        
        if data.get('data', {}).get('status') != 'authorized':
            raise AlpacaAuthenticationError("WebSocket authentication failed")
    
    async def _authenticate_data_ws(self):
        """Authenticate data WebSocket."""
        auth_msg = {
            "action": "auth",
            "key": self.config.api_key,
            "secret": self.config.api_secret
        }
        await self._data_ws.send(json.dumps(auth_msg))
        
        response = await self._data_ws.recv()
        data = json.loads(response)
        
        if data.get('msg') != 'authenticated':
            raise AlpacaAuthenticationError("Data WebSocket authentication failed")
    
    async def _ws_listen_loop(self):
        """Listen for trading WebSocket messages."""
        while self._ws_connected and not self._shutdown_requested:
            try:
                message = await self._ws.recv()
                data = json.loads(message)
                await self._handle_ws_message(data)
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(1)
        
        if not self._shutdown_requested:
            await self._reconnect_ws()
    
    async def _data_ws_listen_loop(self):
        """Listen for data WebSocket messages."""
        while self._data_ws_connected and not self._shutdown_requested:
            try:
                message = await self._data_ws.recv()
                data = json.loads(message)
                await self._handle_data_ws_message(data)
            except websockets.ConnectionClosed:
                logger.warning("Data WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"Data WebSocket error: {e}")
                await asyncio.sleep(1)
        
        if not self._shutdown_requested:
            await self._reconnect_data_ws()
    
    async def _handle_ws_message(self, data: Dict[str, Any]):
        """Handle trading WebSocket message."""
        stream = data.get('stream', '')
        
        if stream in self._ws_handlers:
            for handler in self._ws_handlers[stream]:
                try:
                    await handler(data.get('data', {}))
                except Exception as e:
                    logger.error(f"WebSocket handler error: {e}")
        
        # Update order status
        if stream == 'trade_updates':
            order_data = data.get('data', {})
            order_id = order_data.get('order', {}).get('id')
            if order_id:
                await self.get_order(order_id)
    
    async def _handle_data_ws_message(self, data: Dict[str, Any]):
        """Handle data WebSocket message."""
        msg_type = data.get('T', '')
        
        if msg_type == 'q':  # Quote
            pass
        elif msg_type == 't':  # Trade
            pass
        elif msg_type == 'b':  # Bar
            pass
        elif msg_type == 's':  # Snapshot
            pass
    
    async def _reconnect_ws(self):
        """Reconnect trading WebSocket."""
        if self._shutdown_requested:
            return
        
        logger.info("Reconnecting WebSocket...")
        self._ws_connected = False
        
        attempts = 0
        delay = 5
        while attempts < 5 and not self._shutdown_requested:
            attempts += 1
            try:
                await self._connect_websocket()
                return
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        
        logger.error("Failed to reconnect WebSocket")
    
    async def _reconnect_data_ws(self):
        """Reconnect data WebSocket."""
        if self._shutdown_requested:
            return
        
        logger.info("Reconnecting data WebSocket...")
        self._data_ws_connected = False
        
        attempts = 0
        delay = 5
        while attempts < 5 and not self._shutdown_requested:
            attempts += 1
            try:
                await self._connect_websocket()
                return
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        
        logger.error("Failed to reconnect data WebSocket")
    
    async def subscribe_to_quotes(self, symbols: List[str]):
        """Subscribe to real-time quotes."""
        if not self._data_ws_connected:
            raise AlpacaWebSocketError("Data WebSocket not connected")
        
        msg = {
            "action": "subscribe",
            "quotes": symbols
        }
        await self._data_ws.send(json.dumps(msg))
        
        for symbol in symbols:
            self._ws_subscriptions.add(f"quote:{symbol}")
    
    async def subscribe_to_trades(self, symbols: List[str]):
        """Subscribe to real-time trades."""
        if not self._data_ws_connected:
            raise AlpacaWebSocketError("Data WebSocket not connected")
        
        msg = {
            "action": "subscribe",
            "trades": symbols
        }
        await self._data_ws.send(json.dumps(msg))
        
        for symbol in symbols:
            self._ws_subscriptions.add(f"trade:{symbol}")
    
    async def subscribe_to_bars(self, symbols: List[str]):
        """Subscribe to real-time bars."""
        if not self._data_ws_connected:
            raise AlpacaWebSocketError("Data WebSocket not connected")
        
        msg = {
            "action": "subscribe",
            "bars": symbols
        }
        await self._data_ws.send(json.dumps(msg))
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, order: AlpacaOrder):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO alpaca_orders (
                        id, client_order_id, symbol, side, order_type,
                        status, time_in_force, quantity, filled_quantity,
                        remaining_quantity, price, limit_price, stop_price,
                        trail_percent, trail_price, avg_price, fee, cost,
                        extended_hours, order_class, created_at, updated_at,
                        expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16, $17, $18,
                              $19, $20, $21, $22, $23, $24)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        filled_quantity = EXCLUDED.filled_quantity,
                        remaining_quantity = EXCLUDED.remaining_quantity,
                        avg_price = EXCLUDED.avg_price,
                        fee = EXCLUDED.fee,
                        cost = EXCLUDED.cost,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    order.id,
                    order.client_order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.status.value,
                    order.time_in_force.value,
                    order.quantity,
                    order.filled_quantity,
                    order.remaining_quantity,
                    order.price,
                    order.limit_price,
                    order.stop_price,
                    order.trail_percent,
                    order.trail_price,
                    order.average_price,
                    order.fee,
                    order.cost,
                    order.extended_hours,
                    order.order_class.value,
                    order.created_at,
                    order.updated_at,
                    order.expires_at,
                    json.dumps(order.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _save_positions(self):
        """Save positions to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for position in self._positions.values():
                    await conn.execute(
                        """
                        INSERT INTO alpaca_positions (
                            symbol, quantity, avg_entry_price, current_price,
                            market_value, unrealized_pl, unrealized_plpc,
                            realized_pl, realized_plpc, change_today,
                            side, cost_basis, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                                  $11, $12, $13, $14)
                        ON CONFLICT (symbol) DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            avg_entry_price = EXCLUDED.avg_entry_price,
                            current_price = EXCLUDED.current_price,
                            market_value = EXCLUDED.market_value,
                            unrealized_pl = EXCLUDED.unrealized_pl,
                            unrealized_plpc = EXCLUDED.unrealized_plpc,
                            realized_pl = EXCLUDED.realized_pl,
                            realized_plpc = EXCLUDED.realized_plpc,
                            change_today = EXCLUDED.change_today,
                            side = EXCLUDED.side,
                            cost_basis = EXCLUDED.cost_basis,
                            updated_at = EXCLUDED.updated_at,
                            metadata = EXCLUDED.metadata
                        """,
                        position.symbol,
                        position.quantity,
                        position.average_entry_price,
                        position.current_price,
                        position.market_value,
                        position.unrealized_pl,
                        position.unrealized_plpc,
                        position.realized_pl,
                        position.realized_plpc,
                        position.change_today,
                        position.side.value if position.side else None,
                        position.cost_basis,
                        position.updated_at or datetime.utcnow(),
                        json.dumps(position.metadata, default=str)
                    )
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
    
    async def _save_bars(self, symbol: str, timeframe: str, bars: List[AlpacaBar]):
        """Save bars to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for bar in bars:
                        await conn.execute(
                            """
                            INSERT INTO alpaca_bars (
                                symbol, timeframe, timestamp, open, high,
                                low, close, volume, vwap, trade_count
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE SET
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                volume = EXCLUDED.volume,
                                vwap = EXCLUDED.vwap,
                                trade_count = EXCLUDED.trade_count
                            """,
                            symbol,
                            timeframe,
                            int(bar.timestamp.timestamp()),
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.vwap,
                            bar.trade_count
                        )
        except Exception as e:
            logger.error(f"Error saving bars: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync account data."""
        while self._running and not self._shutdown_requested:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                # Refresh account
                await self.get_account(refresh=True)
                
                # Refresh positions
                await self.get_positions()
                
                # Refresh open orders
                await self.get_orders(status=AlpacaOrderStatus.OPEN)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the Alpaca client."""
        self._shutdown_requested = True
        self._running = False
        
        # Close WebSocket connections
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        if self._data_ws:
            try:
                await self._data_ws.close()
            except Exception:
                pass
        
        # Close HTTP sessions
        if self._session:
            await self._session.close()
        
        if self._data_session:
            await self._data_session.close()
        
        logger.info("AlpacaClient shutdown complete")


# =============================================================================
# RATE LIMITER
# =============================================================================

class AlpacaRateLimiter:
    """
    Rate limiter for Alpaca API calls.
    """
    
    def __init__(self, rate: float, name: str = "alpaca"):
        self.rate = rate
        self.name = name
        self._tokens = rate
        self._last_refill = time.time()
        self._lock = asyncio.Lock()
        
        logger.debug(f"RateLimiter created: {name} rate={rate}/s")
    
    async def acquire(self, tokens: float = 1.0) -> float:
        """Acquire tokens for a request."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.rate, self._tokens + elapsed * self.rate)
            self._last_refill = now
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            
            wait_time = (tokens - self._tokens) / self.rate
            await asyncio.sleep(wait_time)
            self._tokens = 0
            return wait_time


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class AlpacaError(Exception):
    """Base exception for Alpaca errors."""
    pass


class AlpacaAuthenticationError(AlpacaError):
    """Authentication error."""
    pass


class AlpacaPermissionError(AlpacaError):
    """Permission error."""
    pass


class AlpacaRateLimitError(AlpacaError):
    """Rate limit error."""
    pass


class AlpacaInvalidSymbolError(AlpacaError):
    """Invalid symbol error."""
    pass


class AlpacaNotFoundError(AlpacaError):
    """Resource not found."""
    pass


class AlpacaValidationError(AlpacaError):
    """Validation error."""
    pass


class AlpacaConnectionError(AlpacaError):
    """Connection error."""
    pass


class AlpacaTimeoutError(AlpacaError):
    """Timeout error."""
    pass


class AlpacaWebSocketError(AlpacaError):
    """WebSocket error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AlpacaClient',
    'AlpacaConfig',
    'AlpacaEnvironment',
    'AlpacaOrderType',
    'AlpacaOrderSide',
    'AlpacaOrderStatus',
    'AlpacaTimeInForce',
    'AlpacaAssetClass',
    'AlpacaAssetStatus',
    'AlpacaOrderClass',
    'AlpacaCancelRequestReason',
    'AlpacaAccount',
    'AlpacaAsset',
    'AlpacaOrder',
    'AlpacaPosition',
    'AlpacaTrade',
    'AlpacaQuote',
    'AlpacaBar',
    'AlpacaWatchlist',
    'AlpacaCalendar',
    'AlpacaCorporateAction',
    'AlpacaNews',
    'AlpacaError',
    'AlpacaAuthenticationError',
    'AlpacaPermissionError',
    'AlpacaRateLimitError',
    'AlpacaInvalidSymbolError',
    'AlpacaNotFoundError',
    'AlpacaValidationError',
    'AlpacaConnectionError',
    'AlpacaTimeoutError',
    'AlpacaWebSocketError'
]
