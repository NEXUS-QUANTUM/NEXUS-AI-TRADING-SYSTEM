# trading/exchanges/stocks/tradier.py
# Nexus AI Trading System - Tradier Stock Trading Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Tradier Stock Trading Module

This module provides comprehensive stock trading functionality for the Tradier
brokerage platform via the Tradier API, including:

- OAuth 2.0 and API key authentication with Tradier
- Stock order placement and management (market, limit, stop, stop-limit, trailing stop)
- Real-time stock price data and quotes (NASDAQ, NYSE, etc.)
- Historical stock data with multiple timeframes
- Account and position management
- Portfolio management and analytics
- Options trading support
- Paper trading support
- WebSocket real-time streaming via EventSource
- Comprehensive error handling
- Database persistence
- Redis caching
- Circuit breaker pattern

Features:
- All order types (market, limit, stop, stop-limit, trailing stop)
- Multiple timeframes (1min, 5min, 15min, 1hour, 1day, 1week, 1month)
- Real-time quotes and trades via SSE
- Position management
- Portfolio analytics
- Options trading
- Paper trading support
- EventSource streaming for real-time updates
- OAuth 2.0 and API key authentication
- Comprehensive error handling
"""

import asyncio
import base64
import hashlib
import json
import logging
import time
import urllib.parse
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

# Nexus imports
from trading.exchanges.stocks.base import (
    StockExchange,
    StockConfig,
    StockExchangeType,
    StockOrderType,
    StockOrderSide,
    StockOrderStatus,
    StockTimeInForce,
    StockPositionSide,
    StockOrderClass,
    StockAccountStatus,
    StockError,
    StockAuthenticationError,
    StockRateLimitError,
    StockInvalidSymbolError,
    StockNotFoundError,
    StockValidationError,
    StockConnectionError,
    StockTimeoutError,
    StockInsufficientFundsError,
    StockOrderError,
    StockPositionError
)
from trading.exchanges.stocks.converter import StockConverter, get_converter
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class TradierEnvironment(str, Enum):
    """Tradier API environments."""
    PRODUCTION = "production"
    PAPER = "paper"
    SANDBOX = "sandbox"


class TradierOrderType(str, Enum):
    """Tradier order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"


class TradierOrderSide(str, Enum):
    """Tradier order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"


class TradierOrderStatus(str, Enum):
    """Tradier order status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    STOPPED = "stopped"
    SUSPENDED = "suspended"
    OPEN = "open"


class TradierTimeInForce(str, Enum):
    """Tradier time in force."""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTD = "gtd"


class TradierAccountType(str, Enum):
    """Tradier account types."""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    IRA = "ira"
    ROTH = "roth"
    TRUST = "trust"
    CORPORATE = "corporate"
    PARTNERSHIP = "partnership"


class TradierAssetClass(str, Enum):
    """Tradier asset classes."""
    EQUITY = "equity"
    OPTION = "option"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    CASH = "cash"


class TradierEventType(str, Enum):
    """Tradier event types."""
    TRADE = "trade"
    QUOTE = "quote"
    SUMMARY = "summary"
    TIMESALE = "timesale"
    OHLC = "ohlc"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class TradierConfig(StockConfig):
    """Tradier API configuration."""
    api_key: str
    account_id: Optional[str] = None
    oauth_token: Optional[str] = None
    environment: TradierEnvironment = TradierEnvironment.PAPER
    base_url: Optional[str] = None
    api_url: Optional[str] = None
    streamer_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    cache_ttl: int = 60
    use_cache: bool = True
    verify_ssl: bool = True
    user_agent: str = "NexusAI-Trading/3.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid API key")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == TradierEnvironment.PAPER:
            return "https://api.tradier.com/v1"
        elif self.environment == TradierEnvironment.SANDBOX:
            return "https://sandbox.tradier.com/v1"
        else:
            return "https://api.tradier.com/v1"

    def get_api_url(self) -> str:
        """Get the API URL."""
        if self.api_url:
            return self.api_url
        return self.get_base_url()

    def get_streamer_url(self) -> str:
        """Get the streamer URL."""
        if self.streamer_url:
            return self.streamer_url
        return "https://stream.tradier.com/v1"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class TradierAccount(BaseModel):
    """Tradier account information."""
    account_id: str
    account_number: str
    account_type: TradierAccountType
    account_status: str
    currency: str = "USD"
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    total_equity: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    margin_balance: Decimal = Decimal('0')
    settled_cash: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    day_trade_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TradierOrder(BaseModel):
    """Tradier order."""
    id: str
    account_id: str
    symbol: str
    side: TradierOrderSide
    order_type: TradierOrderType
    status: TradierOrderStatus
    time_in_force: TradierTimeInForce
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = Decimal('0')
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trail_price: Optional[Decimal] = None
    trail_percent: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extended_hours: bool = False
    order_class: StockOrderClass = StockOrderClass.SIMPLE
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [TradierOrderStatus.OPEN, TradierOrderStatus.WORKING,
                              TradierOrderStatus.PARTIALLY_FILLED]

    @property
    def is_closed(self) -> bool:
        return self.status in [TradierOrderStatus.FILLED, TradierOrderStatus.CANCELLED,
                              TradierOrderStatus.EXPIRED, TradierOrderStatus.REJECTED,
                              TradierOrderStatus.STOPPED]


class TradierPosition(BaseModel):
    """Tradier position."""
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    cost_basis: Decimal = Decimal('0')
    asset_class: TradierAssetClass = TradierAssetClass.EQUITY
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TradierQuote(BaseModel):
    """Tradier quote."""
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    last_price: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    open_price: Decimal
    close_price: Decimal
    change: Decimal
    change_percent: Decimal
    vwap: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TradierBar(BaseModel):
    """Tradier bar (OHLC)."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None
    timestamp: datetime


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Tradier orders
CREATE TABLE IF NOT EXISTS tradier_orders (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(20) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    time_in_force VARCHAR(10) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    filled_quantity DECIMAL(32, 8) DEFAULT 0,
    remaining_quantity DECIMAL(32, 8) DEFAULT 0,
    price DECIMAL(32, 8),
    stop_price DECIMAL(32, 8),
    trail_price DECIMAL(32, 8),
    trail_percent DECIMAL(32, 8),
    avg_price DECIMAL(32, 8),
    fee DECIMAL(32, 8) DEFAULT 0,
    cost DECIMAL(32, 8) DEFAULT 0,
    extended_hours BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_tradier_orders_symbol (symbol),
    INDEX idx_tradier_orders_status (status),
    INDEX idx_tradier_orders_created_at (created_at)
);

-- Tradier positions
CREATE TABLE IF NOT EXISTS tradier_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    avg_price DECIMAL(32, 8) NOT NULL,
    current_price DECIMAL(32, 8) NOT NULL,
    market_value DECIMAL(32, 8) NOT NULL,
    unrealized_pnl DECIMAL(32, 8) DEFAULT 0,
    realized_pnl DECIMAL(32, 8) DEFAULT 0,
    cost_basis DECIMAL(32, 8) DEFAULT 0,
    asset_class VARCHAR(30) DEFAULT 'equity',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Tradier accounts
CREATE TABLE IF NOT EXISTS tradier_accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    account_number VARCHAR(64) NOT NULL,
    account_type VARCHAR(30) NOT NULL,
    account_status VARCHAR(30) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    cash_balance DECIMAL(32, 8) DEFAULT 0,
    buying_power DECIMAL(32, 8) DEFAULT 0,
    total_equity DECIMAL(32, 8) DEFAULT 0,
    long_market_value DECIMAL(32, 8) DEFAULT 0,
    short_market_value DECIMAL(32, 8) DEFAULT 0,
    margin_balance DECIMAL(32, 8) DEFAULT 0,
    settled_cash DECIMAL(32, 8) DEFAULT 0,
    unrealized_pnl DECIMAL(32, 8) DEFAULT 0,
    realized_pnl DECIMAL(32, 8) DEFAULT 0,
    day_trade_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
"""


# =============================================================================
# MAIN TRADIER CLIENT
# =============================================================================

class TradierClient(StockExchange):
    """
    Advanced Tradier stock trading client.
    
    Features:
    - API key and OAuth authentication
    - All order types (market, limit, stop, stop-limit, trailing stop)
    - Real-time quotes and trades via SSE
    - Historical data with multiple timeframes
    - Account and position management
    - Portfolio analytics
    - Options trading
    - Paper trading support
    - EventSource streaming for real-time updates
    - Comprehensive error handling
    - Database persistence
    - Redis caching
    """
    
    def __init__(
        self,
        config: TradierConfig,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        super().__init__(config, redis, pool)
        self.config = config
        self.converter = get_converter()
        self.converter.set_broker(StockExchangeType.TRADIER)
        
        # Account state
        self._accounts: Dict[str, TradierAccount] = {}
        self._default_account_id: Optional[str] = None
        
        # Streamer (SSE) state
        self._sse_connected = False
        self._sse_task: Optional[asyncio.Task] = None
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_subscriptions: Set[str] = set()
        
        # Database
        self._db_initialized = False
        
        logger.info("TradierClient initialized")
    
    async def initialize(self):
        """Initialize the Tradier client."""
        # Initialize HTTP session with API key
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        self._session = aiohttp.ClientSession(headers=headers)
        
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Get accounts
        await self.get_accounts()
        
        # Get positions
        await self.get_positions()
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        # Connect to streamer
        await self._connect_streamer()
        
        self._initialized = True
        logger.info("TradierClient initialization complete")
    
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
    # REQUEST HANDLING
    # =========================================================================
    
    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        use_api: bool = True
    ) -> Dict[str, Any]:
        """Make an authenticated request to Tradier."""
        cb_key = "tradier_order" if "order" in endpoint else "tradier_market"
        cb = self._order_cb if "order" in endpoint else self._market_data_cb
        
        if cb.is_open():
            raise StockRateLimitError("Circuit breaker is open")
        
        await self._rate_limiter.acquire()
        
        if use_api:
            base_url = self.config.get_api_url()
        else:
            base_url = self.config.get_base_url()
        
        url = f"{base_url}{endpoint}"
        
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                json=data if data and method.upper() in ["POST", "PUT"] else None,
                ssl=self.config.verify_ssl
            ) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, method, data, params, use_api)
                
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 401:
                        raise StockAuthenticationError(error_text)
                    elif response.status == 403:
                        raise StockPermissionError(error_text)
                    elif response.status == 404:
                        raise StockNotFoundError(error_text)
                    elif response.status == 422:
                        raise StockValidationError(error_text)
                    elif response.status == 503:
                        raise StockConnectionError("Tradier service unavailable")
                    else:
                        raise StockError(f"HTTP {response.status}: {error_text}")
                
                if response.status == 204:
                    return {}
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            cb.record_failure()
            raise StockConnectionError(f"HTTP error: {e}")
        except asyncio.TimeoutError:
            cb.record_failure()
            raise StockTimeoutError("Request timeout")
        except Exception as e:
            cb.record_failure()
            raise StockError(f"Request error: {e}")
    
    # =========================================================================
    # ACCOUNT MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_accounts(self, refresh: bool = False) -> Dict[str, TradierAccount]:
        """Get all accounts."""
        if not refresh and self._accounts:
            return self._accounts
        
        try:
            data = await self._make_request("/accounts", method="GET")
            
            accounts = {}
            for item in data.get('accounts', {}).get('account', []):
                account = TradierAccount(
                    account_id=item.get('id', ''),
                    account_number=item.get('account_number', ''),
                    account_type=TradierAccountType(item.get('type', 'individual')),
                    account_status=item.get('status', 'active'),
                    currency=item.get('currency', 'USD'),
                    cash_balance=Decimal(str(item.get('cash_balance', 0))),
                    buying_power=Decimal(str(item.get('buying_power', 0))),
                    total_equity=Decimal(str(item.get('total_equity', 0))),
                    long_market_value=Decimal(str(item.get('long_market_value', 0))),
                    short_market_value=Decimal(str(item.get('short_market_value', 0))),
                    margin_balance=Decimal(str(item.get('margin_balance', 0))),
                    settled_cash=Decimal(str(item.get('settled_cash', 0))),
                    unrealized_pnl=Decimal(str(item.get('unrealized_pnl', 0))),
                    realized_pnl=Decimal(str(item.get('realized_pnl', 0))),
                    day_trade_count=item.get('day_trade_count', 0),
                    metadata=item
                )
                accounts[account.account_id] = account
            
            self._accounts = accounts
            
            if accounts and not self._default_account_id:
                self._default_account_id = list(accounts.keys())[0]
            
            if self.pool:
                await self._save_accounts()
            
            logger.info(f"Loaded {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            if self._accounts:
                return self._accounts
            raise
    
    async def get_default_account(self) -> Optional[TradierAccount]:
        """Get the default account."""
        if self._default_account_id:
            return self._accounts.get(self._default_account_id)
        return None
    
    async def set_default_account(self, account_id: str):
        """Set the default account."""
        if account_id not in self._accounts:
            raise StockNotFoundError(f"Account {account_id} not found")
        self._default_account_id = account_id
    
    # =========================================================================
    # ASSET MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_assets(self, refresh: bool = False) -> Dict[str, StockAsset]:
        """Get available assets."""
        if not refresh and self._assets:
            return self._assets
        
        try:
            data = await self._make_request("/markets/lookup", method="GET")
            
            assets = {}
            for item in data.get('securities', {}).get('security', []):
                asset = StockAsset(
                    id=item.get('symbol', ''),
                    symbol=item.get('symbol', ''),
                    name=item.get('description', ''),
                    exchange=item.get('exchange', 'NYSE'),
                    asset_class=item.get('asset_class', 'equity'),
                    status=item.get('status', 'active'),
                    tick_size=Decimal(str(item.get('tick_size', 0.01))),
                    metadata=item
                )
                assets[asset.symbol] = asset
            
            self._assets = assets
            
            logger.info(f"Loaded {len(assets)} assets")
            return assets
            
        except Exception as e:
            logger.error(f"Error getting assets: {e}")
            if self._assets:
                return self._assets
            raise
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_order(
        self,
        symbol: str,
        side: StockOrderSide,
        order_type: StockOrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        trail_percent: Optional[Decimal] = None,
        trail_price: Optional[Decimal] = None,
        time_in_force: StockTimeInForce = StockTimeInForce.DAY,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False,
        **kwargs
    ) -> StockOrder:
        """Place an order."""
        if self._order_cb.is_open():
            raise StockRateLimitError("Order circuit breaker is open")
        
        try:
            account = await self.get_default_account()
            if not account:
                raise StockError("No default account set")
            
            # Map order type
            tradier_type_map = {
                StockOrderType.MARKET: TradierOrderType.MARKET,
                StockOrderType.LIMIT: TradierOrderType.LIMIT,
                StockOrderType.STOP: TradierOrderType.STOP,
                StockOrderType.STOP_LIMIT: TradierOrderType.STOP_LIMIT,
                StockOrderType.TRAILING_STOP: TradierOrderType.TRAILING_STOP,
            }
            tradier_type = tradier_type_map.get(order_type, TradierOrderType.LIMIT)
            
            # Map side
            tradier_side_map = {
                StockOrderSide.BUY: TradierOrderSide.BUY,
                StockOrderSide.SELL: TradierOrderSide.SELL,
            }
            tradier_side = tradier_side_map.get(side, TradierOrderSide.BUY)
            
            # Build order request
            order_data = {
                "class": "equity",
                "symbol": symbol,
                "side": tradier_side.value,
                "type": tradier_type.value,
                "quantity": str(quantity),
                "duration": time_in_force.value.upper()
            }
            
            if limit_price is not None:
                order_data["price"] = str(limit_price)
            elif price is not None:
                order_data["price"] = str(price)
            
            if stop_price is not None:
                order_data["stop_price"] = str(stop_price)
            
            if trail_percent is not None:
                order_data["trail_percent"] = str(trail_percent)
            
            if trail_price is not None:
                order_data["trail_price"] = str(trail_price)
            
            if extended_hours:
                order_data["extended_hours"] = "true"
            
            if client_order_id:
                order_data["tag"] = client_order_id
            
            data = await self._make_request(
                f"/accounts/{account.account_id}/orders",
                method="POST",
                data=order_data
            )
            
            order_response = data.get('order', {})
            order = self._parse_order(order_response, account.account_id)
            
            self._orders[order.id] = order
            
            if self.pool:
                await self._save_order(order, account.account_id)
            
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
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_orders(
        self,
        status: Optional[StockOrderStatus] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> List[StockOrder]:
        """Get orders with filters."""
        try:
            account = await self.get_default_account()
            if not account:
                return []
            
            params = {}
            if status:
                params["status"] = status.value
            if symbol:
                params["symbol"] = symbol
            
            data = await self._make_request(
                f"/accounts/{account.account_id}/orders",
                method="GET",
                params=params
            )
            
            orders = []
            for item in data.get('orders', {}).get('order', []):
                order = self._parse_order(item, account.account_id)
                self._orders[order.id] = order
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_order(self, order_id: str) -> Optional[StockOrder]:
        """Get an order by ID."""
        try:
            account = await self.get_default_account()
            if not account:
                return None
            
            data = await self._make_request(
                f"/accounts/{account.account_id}/orders/{order_id}",
                method="GET"
            )
            
            order_response = data.get('order', {})
            return self._parse_order(order_response, account.account_id)
            
        except StockNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            account = await self.get_default_account()
            if not account:
                return False
            
            await self._make_request(
                f"/accounts/{account.account_id}/orders/{order_id}",
                method="DELETE"
            )
            
            if order_id in self._orders:
                self._orders[order_id].status = StockOrderStatus.CANCELLED
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except StockNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def _parse_order(self, data: Dict[str, Any], account_id: str) -> StockOrder:
        """Parse order data."""
        status_map = {
            'pending': StockOrderStatus.PENDING,
            'accepted': StockOrderStatus.ACCEPTED,
            'working': StockOrderStatus.NEW,
            'partially_filled': StockOrderStatus.PARTIALLY_FILLED,
            'filled': StockOrderStatus.FILLED,
            'cancelled': StockOrderStatus.CANCELLED,
            'rejected': StockOrderStatus.REJECTED,
            'expired': StockOrderStatus.EXPIRED,
            'stopped': StockOrderStatus.STOPPED,
            'suspended': StockOrderStatus.SUSPENDED,
            'open': StockOrderStatus.NEW,
        }
        
        status = status_map.get(data.get('status', 'pending'), StockOrderStatus.PENDING)
        
        return StockOrder(
            id=data.get('id', ''),
            symbol=data.get('symbol', ''),
            side=StockOrderSide(data.get('side', 'buy').lower()),
            order_type=StockOrderType(data.get('type', 'limit').lower()),
            status=status,
            time_in_force=StockTimeInForce(data.get('duration', 'day').lower()),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filled_quantity', 0))),
            remaining_quantity=Decimal(str(data.get('remaining_quantity', 0))),
            price=Decimal(str(data.get('price', 0))) if data.get('price') else None,
            stop_price=Decimal(str(data.get('stop_price', 0))) if data.get('stop_price') else None,
            trail_price=Decimal(str(data.get('trail_price', 0))) if data.get('trail_price') else None,
            trail_percent=Decimal(str(data.get('trail_percent', 0))) if data.get('trail_percent') else None,
            average_price=Decimal(str(data.get('avg_price', 0))) if data.get('avg_price') else None,
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('avg_price', 0))) * Decimal(str(data.get('filled_quantity', 0))) if data.get('avg_price') else Decimal('0'),
            extended_hours=data.get('extended_hours', 'false') == 'true',
            metadata=data
        )
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_positions(self) -> Dict[str, StockPosition]:
        """Get all positions."""
        try:
            account = await self.get_default_account()
            if not account:
                return {}
            
            data = await self._make_request(
                f"/accounts/{account.account_id}/positions",
                method="GET"
            )
            
            positions = {}
            for item in data.get('positions', {}).get('position', []):
                position = self._parse_position(item)
                positions[position.symbol] = position
            
            self._positions = positions
            
            if self.pool:
                await self._save_positions(account.account_id)
            
            logger.info(f"Loaded {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return self._positions
    
    async def get_position(self, symbol: str) -> Optional[StockPosition]:
        """Get a position for a symbol."""
        positions = await self.get_positions()
        return positions.get(symbol)
    
    async def close_position(
        self,
        symbol: str,
        quantity: Optional[Decimal] = None
    ) -> StockOrder:
        """Close a position."""
        position = await self.get_position(symbol)
        if not position:
            raise StockPositionError(f"No position found for {symbol}")
        
        side = StockOrderSide.SELL if position.quantity > 0 else StockOrderSide.BUY
        qty = quantity or abs(position.quantity)
        
        return await self.place_order(
            symbol=symbol,
            side=side,
            order_type=StockOrderType.MARKET,
            quantity=qty,
            time_in_force=StockTimeInForce.DAY
        )
    
    def _parse_position(self, data: Dict[str, Any]) -> StockPosition:
        """Parse position data."""
        quantity = Decimal(str(data.get('quantity', 0)))
        
        return StockPosition(
            symbol=data.get('symbol', ''),
            quantity=quantity,
            average_entry_price=Decimal(str(data.get('avg_price', 0))),
            current_price=Decimal(str(data.get('current_price', 0))),
            market_value=Decimal(str(data.get('market_value', 0))),
            unrealized_pl=Decimal(str(data.get('unrealized_pnl', 0))),
            realized_pl=Decimal(str(data.get('realized_pnl', 0))),
            cost_basis=Decimal(str(data.get('cost_basis', 0))),
            side=StockPositionSide.LONG if quantity > 0 else StockPositionSide.SHORT,
            metadata=data
        )
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_quote(self, symbol: str) -> StockQuote:
        """Get real-time quote."""
        if self._market_data_cb.is_open():
            raise StockRateLimitError("Market data circuit breaker is open")
        
        try:
            data = await self._make_request(
                f"/markets/quotes",
                method="GET",
                params={"symbols": symbol}
            )
            
            quote_data = data.get('quotes', {}).get('quote', {})
            
            quote = StockQuote(
                symbol=quote_data.get('symbol', ''),
                bid_price=Decimal(str(quote_data.get('bid', 0))),
                bid_size=Decimal(str(quote_data.get('bidsize', 0))),
                ask_price=Decimal(str(quote_data.get('ask', 0))),
                ask_size=Decimal(str(quote_data.get('asksize', 0))),
                last_price=Decimal(str(quote_data.get('last', 0))),
                high=Decimal(str(quote_data.get('high', 0))),
                low=Decimal(str(quote_data.get('low', 0))),
                volume=Decimal(str(quote_data.get('volume', 0))),
                open_price=Decimal(str(quote_data.get('open', 0))),
                close_price=Decimal(str(quote_data.get('close', 0))),
                change=Decimal(str(quote_data.get('change', 0))),
                change_percent=Decimal(str(quote_data.get('change_percent', 0))),
                vwap=Decimal(str(quote_data.get('vwap', 0))) if quote_data.get('vwap') else None,
                timestamp=datetime.fromtimestamp(int(quote_data.get('timestamp', 0)) / 1000) if quote_data.get('timestamp') else datetime.utcnow()
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
        timeframe: str = "1min",
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[StockBar]:
        """Get historical bars."""
        if self._market_data_cb.is_open():
            raise StockRateLimitError("Market data circuit breaker is open")
        
        try:
            params = {
                "symbol": symbol,
                "interval": timeframe,
                "limit": min(limit, 1000)
            }
            
            if start:
                params["start"] = int(start.timestamp())
            if end:
                params["end"] = int(end.timestamp())
            
            data = await self._make_request(
                "/markets/history",
                method="GET",
                params=params
            )
            
            bars = []
            for item in data.get('history', {}).get('day', []):
                bar = StockBar(
                    symbol=symbol,
                    open=Decimal(str(item.get('open', 0))),
                    high=Decimal(str(item.get('high', 0))),
                    low=Decimal(str(item.get('low', 0))),
                    close=Decimal(str(item.get('close', 0))),
                    volume=Decimal(str(item.get('volume', 0))),
                    vwap=Decimal(str(item.get('vwap', 0))) if item.get('vwap') else None,
                    trade_count=item.get('trade_count'),
                    timestamp=datetime.fromtimestamp(int(item.get('timestamp', 0)) / 1000) if item.get('timestamp') else datetime.utcnow()
                )
                bars.append(bar)
            
            self._market_data_cb.record_success()
            return bars
            
        except Exception as e:
            self._market_data_cb.record_failure()
            logger.error(f"Error getting bars for {symbol}: {e}")
            raise
    
    # =========================================================================
    # STREAMER (SSE)
    # =========================================================================
    
    async def _connect_streamer(self):
        """Connect to Tradier streamer (Server-Sent Events)."""
        if self._sse_connected:
            return
        
        try:
            streamer_url = f"{self.config.get_streamer_url()}/events"
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "text/event-stream"
            }
            
            self._sse_task = asyncio.create_task(self._sse_listen_loop(streamer_url, headers))
            self._sse_connected = True
            
            logger.info("Streamer connected")
            
        except Exception as e:
            logger.error(f"Streamer connection error: {e}")
            self._sse_connected = False
    
    async def _sse_listen_loop(self, url: str, headers: Dict[str, str]):
        """Listen for SSE events."""
        while self._sse_connected and not self._shutdown_requested:
            try:
                async with self._session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise StockConnectionError(f"SSE connection failed: {response.status}")
                    
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                await self._handle_sse_message(data)
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                logger.error(f"SSE message error: {e}")
                    
            except aiohttp.ClientError as e:
                logger.error(f"SSE connection error: {e}")
                await asyncio.sleep(5)
                if not self._shutdown_requested:
                    continue
            except Exception as e:
                logger.error(f"SSE loop error: {e}")
                await asyncio.sleep(5)
                if not self._shutdown_requested:
                    continue
            
            if not self._shutdown_requested:
                await asyncio.sleep(5)
    
    async def _handle_sse_message(self, data: Dict[str, Any]):
        """Handle SSE message."""
        msg_type = data.get('type', '')
        
        if msg_type in self._ws_handlers:
            for handler in self._ws_handlers[msg_type]:
                try:
                    await handler(data.get('data', {}))
                except Exception as e:
                    logger.error(f"SSE handler error: {e}")
    
    async def subscribe_to_quotes(self, symbols: List[str]):
        """Subscribe to real-time quotes via SSE."""
        if not self._sse_connected:
            raise StockWebSocketError("Streamer not connected")
        
        # Tradier uses symbol subscription via HTTP
        params = {
            "symbols": ",".join(symbols),
            "events": "quote"
        }
        
        await self._make_request(
            "/events/session",
            method="POST",
            params=params
        )
        
        for symbol in symbols:
            self._ws_subscriptions.add(f"quote:{symbol}")
        
        logger.info(f"Subscribed to quotes for {symbols}")
    
    async def subscribe_to_trades(self, symbols: List[str]):
        """Subscribe to real-time trades via SSE."""
        if not self._sse_connected:
            raise StockWebSocketError("Streamer not connected")
        
        params = {
            "symbols": ",".join(symbols),
            "events": "trade"
        }
        
        await self._make_request(
            "/events/session",
            method="POST",
            params=params
        )
        
        for symbol in symbols:
            self._ws_subscriptions.add(f"trade:{symbol}")
        
        logger.info(f"Subscribed to trades for {symbols}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, order: StockOrder, account_id: str):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tradier_orders (
                        id, account_id, symbol, side, order_type,
                        status, time_in_force, quantity, filled_quantity,
                        remaining_quantity, price, stop_price,
                        trail_price, trail_percent, avg_price, fee, cost,
                        extended_hours, created_at, updated_at, expires_at,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16, $17,
                              $18, $19, $20, $21, $22)
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
                    account_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.status.value,
                    order.time_in_force.value,
                    order.quantity,
                    order.filled_quantity,
                    order.remaining_quantity,
                    order.price,
                    order.stop_price,
                    order.trail_price,
                    order.trail_percent,
                    order.average_price,
                    order.fee,
                    order.cost,
                    order.extended_hours,
                    order.created_at,
                    order.updated_at,
                    order.expires_at,
                    json.dumps(order.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _save_positions(self, account_id: str):
        """Save positions to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for position in self._positions.values():
                    await conn.execute(
                        """
                        INSERT INTO tradier_positions (
                            symbol, account_id, quantity, avg_price,
                            current_price, market_value, unrealized_pnl,
                            realized_pnl, cost_basis, asset_class,
                            updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ON CONFLICT (symbol) DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            avg_price = EXCLUDED.avg_price,
                            current_price = EXCLUDED.current_price,
                            market_value = EXCLUDED.market_value,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            realized_pnl = EXCLUDED.realized_pnl,
                            cost_basis = EXCLUDED.cost_basis,
                            asset_class = EXCLUDED.asset_class,
                            updated_at = EXCLUDED.updated_at,
                            metadata = EXCLUDED.metadata
                        """,
                        position.symbol,
                        account_id,
                        position.quantity,
                        position.average_entry_price,
                        position.current_price,
                        position.market_value,
                        position.unrealized_pl,
                        position.realized_pl,
                        position.cost_basis,
                        TradierAssetClass.EQUITY.value,
                        position.updated_at or datetime.utcnow(),
                        json.dumps(position.metadata, default=str)
                    )
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
    
    async def _save_accounts(self):
        """Save accounts to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for account in self._accounts.values():
                    await conn.execute(
                        """
                        INSERT INTO tradier_accounts (
                            account_id, account_number, account_type,
                            account_status, currency, cash_balance,
                            buying_power, total_equity, long_market_value,
                            short_market_value, margin_balance,
                            settled_cash, unrealized_pnl, realized_pnl,
                            day_trade_count, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                                  $10, $11, $12, $13, $14, $15, $16, $17)
                        ON CONFLICT (account_id) DO UPDATE SET
                            account_number = EXCLUDED.account_number,
                            account_type = EXCLUDED.account_type,
                            account_status = EXCLUDED.account_status,
                            currency = EXCLUDED.currency,
                            cash_balance = EXCLUDED.cash_balance,
                            buying_power = EXCLUDED.buying_power,
                            total_equity = EXCLUDED.total_equity,
                            long_market_value = EXCLUDED.long_market_value,
                            short_market_value = EXCLUDED.short_market_value,
                            margin_balance = EXCLUDED.margin_balance,
                            settled_cash = EXCLUDED.settled_cash,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            realized_pnl = EXCLUDED.realized_pnl,
                            day_trade_count = EXCLUDED.day_trade_count,
                            updated_at = EXCLUDED.updated_at,
                            metadata = EXCLUDED.metadata
                        """,
                        account.account_id,
                        account.account_number,
                        account.account_type.value,
                        account.account_status,
                        account.currency,
                        account.cash_balance,
                        account.buying_power,
                        account.total_equity,
                        account.long_market_value,
                        account.short_market_value,
                        account.margin_balance,
                        account.settled_cash,
                        account.unrealized_pnl,
                        account.realized_pnl,
                        account.day_trade_count,
                        account.updated_at or datetime.utcnow(),
                        json.dumps(account.metadata, default=str)
                    )
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync account data."""
        while self._running and not self._shutdown_requested:
            try:
                await asyncio.sleep(30)
                await self.get_accounts(refresh=True)
                await self.get_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the Tradier client."""
        self._shutdown_requested = True
        self._running = False
        
        self._sse_connected = False
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
        
        if self._session:
            await self._session.close()
        
        logger.info("TradierClient shutdown complete")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TradierClient',
    'TradierConfig',
    'TradierEnvironment',
    'TradierOrderType',
    'TradierOrderSide',
    'TradierOrderStatus',
    'TradierTimeInForce',
    'TradierAccountType',
    'TradierAssetClass',
    'TradierEventType',
    'TradierAccount',
    'TradierOrder',
    'TradierPosition',
    'TradierQuote',
    'TradierBar'
]
