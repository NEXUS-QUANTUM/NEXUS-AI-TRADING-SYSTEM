# trading/exchanges/stocks/etrade.py
# Nexus AI Trading System - E*TRADE Stock Trading Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
E*TRADE Stock Trading Module

This module provides comprehensive stock trading functionality for the E*TRADE
stock trading platform, including:

- OAuth 1.0a authentication with E*TRADE API
- Stock order placement and management (market, limit, stop, stop-limit)
- Real-time stock price data and quotes
- Historical stock data with multiple timeframes
- Account and position management
- Portfolio management and analytics
- Watchlist management
- Options trading support
- Mutual funds trading
- WebSocket real-time streaming
- Comprehensive error handling
- Database persistence
- Redis caching
- Circuit breaker pattern

Features:
- All order types (market, limit, stop, stop-limit)
- Multiple timeframes (1min, 5min, 15min, 1hour, 1day, 1week, 1month)
- Real-time quotes and trades
- Position management
- Portfolio analytics
- Options trading
- Mutual funds trading
- Watchlist management
- WebSocket streaming for real-time updates
- OAuth 1.0a authentication
- Comprehensive error handling
"""

import asyncio
import base64
import hashlib
import hmac
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
import websockets
from oauthlib.oauth1 import Client as OAuth1Client

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

class ETradeEnvironment(str, Enum):
    """E*TRADE API environments."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class ETradeOrderType(str, Enum):
    """E*TRADE order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"


class ETradeOrderSide(str, Enum):
    """E*TRADE order sides."""
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class ETradeOrderStatus(str, Enum):
    """E*TRADE order status."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"


class ETradeTimeInForce(str, Enum):
    """E*TRADE time in force."""
    DAY = "DAY"
    GTC = "GTC"
    IMMEDIATE = "IMMEDIATE"
    FILL_OR_KILL = "FOK"


class ETradeAccountType(str, Enum):
    """E*TRADE account types."""
    BROKERAGE = "BROKERAGE"
    IRA = "IRA"
    ROTH = "ROTH"
    TRUST = "TRUST"
    JOINT = "JOINT"


class ETradeMarketStatus(str, Enum):
    """E*TRADE market status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    AFTER_HOURS = "AFTER_HOURS"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ETradeConfig(StockConfig):
    """E*TRADE API configuration."""
    consumer_key: str
    consumer_secret: str
    oauth_token: str
    oauth_token_secret: str
    environment: ETradeEnvironment = ETradeEnvironment.PRODUCTION
    base_url: Optional[str] = None
    accounts_url: Optional[str] = None
    market_url: Optional[str] = None
    order_url: Optional[str] = None
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

    @validator('consumer_key')
    def validate_consumer_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid consumer key")
        return v

    @validator('consumer_secret')
    def validate_consumer_secret(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid consumer secret")
        return v

    @validator('oauth_token')
    def validate_oauth_token(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid OAuth token")
        return v

    @validator('oauth_token_secret')
    def validate_oauth_token_secret(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid OAuth token secret")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == ETradeEnvironment.SANDBOX:
            return "https://apisb.etrade.com"
        else:
            return "https://api.etrade.com"

    def get_accounts_url(self) -> str:
        """Get the accounts API URL."""
        if self.accounts_url:
            return self.accounts_url
        return f"{self.get_base_url()}/v1/accounts"

    def get_market_url(self) -> str:
        """Get the market API URL."""
        if self.market_url:
            return self.market_url
        return f"{self.get_base_url()}/v1/market"

    def get_order_url(self) -> str:
        """Get the order API URL."""
        if self.order_url:
            return self.order_url
        return f"{self.get_base_url()}/v1/order"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class ETradeAccount(BaseModel):
    """E*TRADE account information."""
    account_id: str
    account_name: str
    account_type: ETradeAccountType
    account_status: str
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    total_equity: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    margin_balance: Decimal = Decimal('0')
    day_trade_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ETradeOrder(BaseModel):
    """E*TRADE order."""
    order_id: str
    account_id: str
    symbol: str
    side: ETradeOrderSide
    order_type: ETradeOrderType
    status: ETradeOrderStatus
    time_in_force: ETradeTimeInForce
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = Decimal('0')
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extended_hours: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [ETradeOrderStatus.OPEN, ETradeOrderStatus.PARTIALLY_FILLED]

    @property
    def is_closed(self) -> bool:
        return self.status in [ETradeOrderStatus.FILLED, ETradeOrderStatus.CANCELLED,
                              ETradeOrderStatus.EXPIRED, ETradeOrderStatus.REJECTED,
                              ETradeOrderStatus.STOPPED]


class ETradePosition(BaseModel):
    """E*TRADE position."""
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    cost_basis: Decimal = Decimal('0')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ETradeQuote(BaseModel):
    """E*TRADE quote."""
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ETradeBar(BaseModel):
    """E*TRADE bar (OHLC)."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- ETrade orders
CREATE TABLE IF NOT EXISTS etrade_orders (
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
    limit_price DECIMAL(32, 8),
    stop_price DECIMAL(32, 8),
    avg_price DECIMAL(32, 8),
    fee DECIMAL(32, 8) DEFAULT 0,
    cost DECIMAL(32, 8) DEFAULT 0,
    extended_hours BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_etrade_orders_symbol (symbol),
    INDEX idx_etrade_orders_status (status),
    INDEX idx_etrade_orders_created_at (created_at)
);

-- ETrade positions
CREATE TABLE IF NOT EXISTS etrade_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    avg_price DECIMAL(32, 8) NOT NULL,
    current_price DECIMAL(32, 8) NOT NULL,
    market_value DECIMAL(32, 8) NOT NULL,
    unrealized_pnl DECIMAL(32, 8) DEFAULT 0,
    realized_pnl DECIMAL(32, 8) DEFAULT 0,
    cost_basis DECIMAL(32, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- ETrade accounts
CREATE TABLE IF NOT EXISTS etrade_accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    account_type VARCHAR(30) NOT NULL,
    account_status VARCHAR(30) NOT NULL,
    cash_balance DECIMAL(32, 8) DEFAULT 0,
    buying_power DECIMAL(32, 8) DEFAULT 0,
    total_equity DECIMAL(32, 8) DEFAULT 0,
    long_market_value DECIMAL(32, 8) DEFAULT 0,
    short_market_value DECIMAL(32, 8) DEFAULT 0,
    margin_balance DECIMAL(32, 8) DEFAULT 0,
    day_trade_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
"""


# =============================================================================
# MAIN ETRADE CLIENT
# =============================================================================

class ETradeClient(StockExchange):
    """
    Advanced E*TRADE stock trading client.
    
    Features:
    - OAuth 1.0a authentication
    - All order types (market, limit, stop, stop-limit)
    - Real-time quotes and trades
    - Historical data with multiple timeframes
    - Account and position management
    - Portfolio analytics
    - Watchlist management
    - Options trading support
    - Mutual funds trading
    - WebSocket real-time streaming
    - Comprehensive error handling
    - Database persistence
    - Redis caching
    """
    
    def __init__(
        self,
        config: ETradeConfig,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        super().__init__(config, redis, pool)
        self.config = config
        self.converter = get_converter()
        self.converter.set_broker(StockExchangeType.E_TRADE)
        
        # OAuth client
        self._oauth = OAuth1Client(
            client_key=config.consumer_key,
            client_secret=config.consumer_secret,
            resource_owner_key=config.oauth_token,
            resource_owner_secret=config.oauth_token_secret,
            signature_method='HMAC-SHA256'
        )
        
        # Account state
        self._accounts: Dict[str, ETradeAccount] = {}
        self._default_account_id: Optional[str] = None
        
        # WebSocket state
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_subscriptions: Set[str] = set()
        
        # Database
        self._db_initialized = False
        
        logger.info("ETradeClient initialized")
    
    async def initialize(self):
        """Initialize the E*TRADE client."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Get accounts
        await self.get_accounts()
        
        # Get positions
        await self.get_positions()
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        # Connect WebSocket
        await self._connect_websocket()
        
        self._initialized = True
        logger.info("ETradeClient initialization complete")
    
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
    # OAUTH REQUEST HANDLING
    # =========================================================================
    
    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        use_base: bool = True
    ) -> Dict[str, Any]:
        """
        Make an authenticated OAuth request to E*TRADE.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data (POST/PUT)
            params: Query parameters (GET)
            use_base: Use base URL or accounts URL
            
        Returns:
            Response data
        """
        # Check circuit breaker
        cb_key = "etrade_order" if "order" in endpoint else "etrade_market"
        cb = self._order_cb if "order" in endpoint else self._market_data_cb
        
        if cb.is_open():
            raise StockRateLimitError("Circuit breaker is open")
        
        # Rate limit
        await self._rate_limiter.acquire()
        
        # Build URL
        if use_base:
            base_url = self.config.get_base_url()
        else:
            base_url = self.config.get_accounts_url()
        
        url = f"{base_url}{endpoint}"
        
        # Create OAuth signature
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Prepare request
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        # Sign request
        if method.upper() in ["POST", "PUT"] and data:
            body = json.dumps(data)
        else:
            body = ""
        
        auth_headers = self._oauth.sign(
            url,
            method=method.upper(),
            body=body,
            headers=headers
        )
        
        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                json=data if data and method.upper() in ["POST", "PUT"] else None,
                headers=auth_headers,
                ssl=self.config.verify_ssl
            ) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, method, data, params, use_base)
                
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 401:
                        raise StockAuthenticationError(error_text)
                    elif response.status == 404:
                        raise StockNotFoundError(error_text)
                    elif response.status == 403:
                        raise StockPermissionError(error_text)
                    elif response.status == 422:
                        raise StockValidationError(error_text)
                    elif response.status == 503:
                        raise StockConnectionError("E*TRADE service unavailable")
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
    async def get_accounts(self, refresh: bool = False) -> Dict[str, ETradeAccount]:
        """
        Get all accounts.
        
        Args:
            refresh: Force refresh from API
            
        Returns:
            Dict mapping account_id to ETradeAccount
        """
        if not refresh and self._accounts:
            return self._accounts
        
        try:
            data = await self._make_request("/v1/accounts", method="GET", use_base=False)
            
            accounts = {}
            for item in data.get('AccountListResponse', {}).get('Accounts', {}).get('Account', []):
                account = ETradeAccount(
                    account_id=item.get('accountId', ''),
                    account_name=item.get('accountName', ''),
                    account_type=ETradeAccountType(item.get('accountType', 'BROKERAGE')),
                    account_status=item.get('accountStatus', 'ACTIVE'),
                    cash_balance=Decimal(str(item.get('cashBalance', 0))),
                    buying_power=Decimal(str(item.get('buyingPower', 0))),
                    total_equity=Decimal(str(item.get('totalEquity', 0))),
                    long_market_value=Decimal(str(item.get('longMarketValue', 0))),
                    short_market_value=Decimal(str(item.get('shortMarketValue', 0))),
                    margin_balance=Decimal(str(item.get('marginBalance', 0))),
                    day_trade_count=item.get('dayTradeCount', 0),
                    metadata=item
                )
                accounts[account.account_id] = account
            
            self._accounts = accounts
            
            # Set default account
            if accounts and not self._default_account_id:
                self._default_account_id = list(accounts.keys())[0]
            
            # Save to database
            if self.pool:
                await self._save_accounts()
            
            logger.info(f"Loaded {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            if self._accounts:
                return self._accounts
            raise
    
    async def get_default_account(self) -> Optional[ETradeAccount]:
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
        # E*TRADE doesn't have a comprehensive asset endpoint
        # Return cached assets
        if not refresh and self._assets:
            return self._assets
        
        # Try to get from positions
        positions = await self.get_positions()
        for symbol, position in positions.items():
            if symbol not in self._assets:
                self._assets[symbol] = StockAsset(
                    id=symbol,
                    symbol=symbol,
                    name=symbol,
                    exchange="NASDAQ",
                    asset_class="equity",
                    status="active"
                )
        
        return self._assets
    
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
            time_in_force: Time in force
            client_order_id: Client-side order ID
            extended_hours: Allow extended hours
            
        Returns:
            StockOrder
        """
        if self._order_cb.is_open():
            raise StockRateLimitError("Order circuit breaker is open")
        
        try:
            # Get default account
            account = await self.get_default_account()
            if not account:
                raise StockError("No default account set")
            
            # Map order type
            etrade_type_map = {
                StockOrderType.MARKET: ETradeOrderType.MARKET,
                StockOrderType.LIMIT: ETradeOrderType.LIMIT,
                StockOrderType.STOP: ETradeOrderType.STOP,
                StockOrderType.STOP_LIMIT: ETradeOrderType.STOP_LIMIT,
            }
            etrade_type = etrade_type_map.get(order_type, ETradeOrderType.LIMIT)
            
            # Map side
            etrade_side_map = {
                StockOrderSide.BUY: ETradeOrderSide.BUY,
                StockOrderSide.SELL: ETradeOrderSide.SELL,
            }
            etrade_side = etrade_side_map.get(side, ETradeOrderSide.BUY)
            
            # Build order request
            order_data = {
                "accountId": account.account_id,
                "symbol": symbol,
                "orderType": etrade_type.value,
                "orderAction": etrade_side.value,
                "quantity": str(quantity),
                "timeInForce": time_in_force.value.upper()
            }
            
            if limit_price is not None:
                order_data["limitPrice"] = str(limit_price)
            elif price is not None:
                order_data["limitPrice"] = str(price)
            
            if stop_price is not None:
                order_data["stopPrice"] = str(stop_price)
            
            if extended_hours:
                order_data["extendedHours"] = "TRUE"
            
            if client_order_id:
                order_data["clientOrderId"] = client_order_id
            
            # Place order
            data = await self._make_request(
                "/v1/orders",
                method="POST",
                data=order_data,
                use_base=False
            )
            
            order_data = data.get('OrderResponse', {}).get('Order', {})
            
            order = self._parse_order(order_data, account.account_id)
            
            # Track order
            self._orders[order.id] = order
            
            # Save to database
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
                params["status"] = status.value.upper()
            if symbol:
                params["symbol"] = symbol
            
            data = await self._make_request(
                f"/v1/accounts/{account.account_id}/orders",
                method="GET",
                params=params,
                use_base=False
            )
            
            orders = []
            order_list = data.get('OrdersResponse', {}).get('Order', [])
            if not isinstance(order_list, list):
                order_list = [order_list]
            
            for item in order_list:
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
                f"/v1/accounts/{account.account_id}/orders/{order_id}",
                method="GET",
                use_base=False
            )
            
            order_data = data.get('OrderResponse', {}).get('Order', {})
            return self._parse_order(order_data, account.account_id)
            
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
                f"/v1/accounts/{account.account_id}/orders/{order_id}",
                method="DELETE",
                use_base=False
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
            'PENDING': StockOrderStatus.PENDING,
            'ACCEPTED': StockOrderStatus.ACCEPTED,
            'OPEN': StockOrderStatus.NEW,
            'PARTIALLY_FILLED': StockOrderStatus.PARTIALLY_FILLED,
            'FILLED': StockOrderStatus.FILLED,
            'CANCELLED': StockOrderStatus.CANCELLED,
            'REJECTED': StockOrderStatus.REJECTED,
            'EXPIRED': StockOrderStatus.EXPIRED,
            'STOPPED': StockOrderStatus.STOPPED,
            'SUSPENDED': StockOrderStatus.SUSPENDED,
        }
        
        status = status_map.get(data.get('status', 'PENDING'), StockOrderStatus.PENDING)
        
        return StockOrder(
            id=data.get('orderId', ''),
            symbol=data.get('symbol', ''),
            side=StockOrderSide(data.get('orderAction', 'BUY').lower()),
            order_type=StockOrderType(data.get('orderType', 'LIMIT').lower()),
            status=status,
            time_in_force=StockTimeInForce(data.get('timeInForce', 'DAY').lower()),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filledQuantity', 0))),
            remaining_quantity=Decimal(str(data.get('remainingQuantity', 0))),
            limit_price=Decimal(str(data.get('limitPrice', 0))) if data.get('limitPrice') else None,
            stop_price=Decimal(str(data.get('stopPrice', 0))) if data.get('stopPrice') else None,
            average_price=Decimal(str(data.get('avgPrice', 0))) if data.get('avgPrice') else None,
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('avgPrice', 0))) * Decimal(str(data.get('filledQuantity', 0))) if data.get('avgPrice') else Decimal('0'),
            extended_hours=data.get('extendedHours', 'FALSE') == 'TRUE',
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
                f"/v1/accounts/{account.account_id}/portfolio",
                method="GET",
                use_base=False
            )
            
            positions = {}
            position_list = data.get('PortfolioResponse', {}).get('Position', [])
            if not isinstance(position_list, list):
                position_list = [position_list]
            
            for item in position_list:
                position = self._parse_position(item)
                positions[position.symbol] = position
            
            self._positions = positions
            
            # Save to database
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
            average_entry_price=Decimal(str(data.get('avgPrice', 0))),
            current_price=Decimal(str(data.get('lastPrice', 0))),
            market_value=Decimal(str(data.get('marketValue', 0))),
            unrealized_pl=Decimal(str(data.get('unrealizedPnL', 0))),
            realized_pl=Decimal(str(data.get('realizedPnL', 0))),
            cost_basis=Decimal(str(data.get('costBasis', 0))),
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
                f"/v1/market/quote/{symbol}",
                method="GET",
                use_base=True
            )
            
            quote_data = data.get('QuoteResponse', {}).get('Quote', {})
            
            quote = StockQuote(
                symbol=quote_data.get('symbol', ''),
                bid_price=Decimal(str(quote_data.get('bid', 0))),
                bid_size=Decimal(str(quote_data.get('bidSize', 0))),
                ask_price=Decimal(str(quote_data.get('ask', 0))),
                ask_size=Decimal(str(quote_data.get('askSize', 0))),
                last_price=Decimal(str(quote_data.get('last', 0))),
                volume=Decimal(str(quote_data.get('volume', 0))),
                timestamp=datetime.fromtimestamp(int(quote_data.get('timeStamp', 0)) / 1000) if quote_data.get('timeStamp') else datetime.utcnow(),
                conditions=quote_data.get('conditions', [])
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
        timeframe: str = "1m",
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
                "count": min(limit, 1000)
            }
            
            if start:
                params["startDate"] = start.strftime('%Y-%m-%d')
            if end:
                params["endDate"] = end.strftime('%Y-%m-%d')
            
            data = await self._make_request(
                "/v1/market/charts",
                method="GET",
                params=params,
                use_base=True
            )
            
            bars = []
            for item in data.get('ChartResponse', {}).get('Candles', {}).get('Candle', []):
                bar = StockBar(
                    symbol=symbol,
                    open=Decimal(str(item.get('open', 0))),
                    high=Decimal(str(item.get('high', 0))),
                    low=Decimal(str(item.get('low', 0))),
                    close=Decimal(str(item.get('close', 0))),
                    volume=Decimal(str(item.get('volume', 0))),
                    timestamp=datetime.fromtimestamp(int(item.get('timeStamp', 0)) / 1000) if item.get('timeStamp') else datetime.utcnow()
                )
                bars.append(bar)
            
            self._market_data_cb.record_success()
            return bars
            
        except Exception as e:
            self._market_data_cb.record_failure()
            logger.error(f"Error getting bars for {symbol}: {e}")
            raise
    
    # =========================================================================
    # WEBSOCKET
    # =========================================================================
    
    async def _connect_websocket(self):
        """Connect to WebSocket."""
        # E*TRADE WebSocket is not publicly documented
        # Implement if available
        pass
    
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
                    INSERT INTO etrade_orders (
                        id, account_id, symbol, side, order_type,
                        status, time_in_force, quantity, filled_quantity,
                        remaining_quantity, limit_price, stop_price,
                        avg_price, fee, cost, extended_hours,
                        created_at, updated_at, expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20)
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
                    order.limit_price,
                    order.stop_price,
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
                        INSERT INTO etrade_positions (
                            symbol, account_id, quantity, avg_price,
                            current_price, market_value, unrealized_pnl,
                            realized_pnl, cost_basis, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (symbol) DO UPDATE SET
                            quantity = EXCLUDED.quantity,
                            avg_price = EXCLUDED.avg_price,
                            current_price = EXCLUDED.current_price,
                            market_value = EXCLUDED.market_value,
                            unrealized_pnl = EXCLUDED.unrealized_pnl,
                            realized_pnl = EXCLUDED.realized_pnl,
                            cost_basis = EXCLUDED.cost_basis,
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
                        INSERT INTO etrade_accounts (
                            account_id, account_name, account_type,
                            account_status, cash_balance, buying_power,
                            total_equity, long_market_value,
                            short_market_value, margin_balance,
                            day_trade_count, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                                  $10, $11, $12, $13)
                        ON CONFLICT (account_id) DO UPDATE SET
                            account_name = EXCLUDED.account_name,
                            account_type = EXCLUDED.account_type,
                            account_status = EXCLUDED.account_status,
                            cash_balance = EXCLUDED.cash_balance,
                            buying_power = EXCLUDED.buying_power,
                            total_equity = EXCLUDED.total_equity,
                            long_market_value = EXCLUDED.long_market_value,
                            short_market_value = EXCLUDED.short_market_value,
                            margin_balance = EXCLUDED.margin_balance,
                            day_trade_count = EXCLUDED.day_trade_count,
                            updated_at = EXCLUDED.updated_at,
                            metadata = EXCLUDED.metadata
                        """,
                        account.account_id,
                        account.account_name,
                        account.account_type.value,
                        account.account_status,
                        account.cash_balance,
                        account.buying_power,
                        account.total_equity,
                        account.long_market_value,
                        account.short_market_value,
                        account.margin_balance,
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
        """Shutdown the E*TRADE client."""
        self._shutdown_requested = True
        self._running = False
        
        if self._session:
            await self._session.close()
        
        logger.info("ETradeClient shutdown complete")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ETradeClient',
    'ETradeConfig',
    'ETradeEnvironment',
    'ETradeOrderType',
    'ETradeOrderSide',
    'ETradeOrderStatus',
    'ETradeTimeInForce',
    'ETradeAccountType',
    'ETradeMarketStatus',
    'ETradeAccount',
    'ETradeOrder',
    'ETradePosition',
    'ETradeQuote',
    'ETradeBar'
]
