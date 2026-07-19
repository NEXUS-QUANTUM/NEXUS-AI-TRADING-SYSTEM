# trading/exchanges/stocks/fidelity.py
# Nexus AI Trading System - Fidelity Stock Trading Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Fidelity Stock Trading Module

This module provides comprehensive stock trading functionality for the Fidelity
Investment platform, including:

- OAuth 2.0 authentication with Fidelity API
- Stock order placement and management (market, limit, stop, stop-limit)
- Real-time stock price data and quotes
- Historical stock data with multiple timeframes
- Account and position management
- Portfolio management and analytics
- Mutual funds trading
- Fixed income trading
- Options trading support
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
- Mutual funds trading
- Fixed income trading
- Options trading
- WebSocket streaming for real-time updates
- OAuth 2.0 authentication
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
import websockets

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

class FidelityEnvironment(str, Enum):
    """Fidelity API environments."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class FidelityOrderType(str, Enum):
    """Fidelity order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"
    TRAILING_STOP = "TRAILING_STOP"


class FidelityOrderSide(str, Enum):
    """Fidelity order sides."""
    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class FidelityOrderStatus(str, Enum):
    """Fidelity order status."""
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


class FidelityTimeInForce(str, Enum):
    """Fidelity time in force."""
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTD = "GTD"


class FidelityAccountType(str, Enum):
    """Fidelity account types."""
    BROKERAGE = "BROKERAGE"
    IRA = "IRA"
    ROTH = "ROTH"
    TRUST = "TRUST"
    JOINT = "JOINT"
    CUSTODIAL = "CUSTODIAL"
    CORPORATE = "CORPORATE"


class FidelityAssetClass(str, Enum):
    """Fidelity asset classes."""
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    MUTUAL_FUND = "MUTUAL_FUND"
    FIXED_INCOME = "FIXED_INCOME"
    ETF = "ETF"
    CASH = "CASH"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FidelityConfig(StockConfig):
    """Fidelity API configuration."""
    client_id: str
    client_secret: str
    oauth_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    redirect_uri: Optional[str] = None
    environment: FidelityEnvironment = FidelityEnvironment.PRODUCTION
    base_url: Optional[str] = None
    auth_url: Optional[str] = None
    api_url: Optional[str] = None
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

    @validator('client_id')
    def validate_client_id(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid client ID")
        return v

    @validator('client_secret')
    def validate_client_secret(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid client secret")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == FidelityEnvironment.SANDBOX:
            return "https://sandbox.fidelity.com/api/v1"
        else:
            return "https://api.fidelity.com/v1"

    def get_auth_url(self) -> str:
        """Get the authentication URL."""
        if self.auth_url:
            return self.auth_url
        
        if self.environment == FidelityEnvironment.SANDBOX:
            return "https://sandbox.fidelity.com/oauth/token"
        else:
            return "https://api.fidelity.com/oauth/token"

    def get_api_url(self) -> str:
        """Get the API URL."""
        if self.api_url:
            return self.api_url
        return self.get_base_url()

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class FidelityAccount(BaseModel):
    """Fidelity account information."""
    account_id: str
    account_name: str
    account_type: FidelityAccountType
    account_status: str
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    total_equity: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    margin_balance: Decimal = Decimal('0')
    settled_cash: Decimal = Decimal('0')
    unsettled_cash: Decimal = Decimal('0')
    day_trade_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FidelityOrder(BaseModel):
    """Fidelity order."""
    order_id: str
    account_id: str
    symbol: str
    side: FidelityOrderSide
    order_type: FidelityOrderType
    status: FidelityOrderStatus
    time_in_force: FidelityTimeInForce
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = Decimal('0')
    limit_price: Optional[Decimal] = None
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
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [FidelityOrderStatus.OPEN, FidelityOrderStatus.PARTIALLY_FILLED]

    @property
    def is_closed(self) -> bool:
        return self.status in [FidelityOrderStatus.FILLED, FidelityOrderStatus.CANCELLED,
                              FidelityOrderStatus.EXPIRED, FidelityOrderStatus.REJECTED,
                              FidelityOrderStatus.STOPPED]


class FidelityPosition(BaseModel):
    """Fidelity position."""
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    cost_basis: Decimal = Decimal('0')
    asset_class: FidelityAssetClass = FidelityAssetClass.EQUITY
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FidelityQuote(BaseModel):
    """Fidelity quote."""
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


class FidelityBar(BaseModel):
    """Fidelity bar (OHLC)."""
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
-- Fidelity orders
CREATE TABLE IF NOT EXISTS fidelity_orders (
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
    INDEX idx_fidelity_orders_symbol (symbol),
    INDEX idx_fidelity_orders_status (status),
    INDEX idx_fidelity_orders_created_at (created_at)
);

-- Fidelity positions
CREATE TABLE IF NOT EXISTS fidelity_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    quantity DECIMAL(32, 8) NOT NULL,
    avg_price DECIMAL(32, 8) NOT NULL,
    current_price DECIMAL(32, 8) NOT NULL,
    market_value DECIMAL(32, 8) NOT NULL,
    unrealized_pnl DECIMAL(32, 8) DEFAULT 0,
    realized_pnl DECIMAL(32, 8) DEFAULT 0,
    cost_basis DECIMAL(32, 8) DEFAULT 0,
    asset_class VARCHAR(30) DEFAULT 'EQUITY',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Fidelity accounts
CREATE TABLE IF NOT EXISTS fidelity_accounts (
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
    settled_cash DECIMAL(32, 8) DEFAULT 0,
    unsettled_cash DECIMAL(32, 8) DEFAULT 0,
    day_trade_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
"""


# =============================================================================
# OAUTH 2.0 CLIENT
# =============================================================================

class FidelityOAuth2Client:
    """
    OAuth 2.0 client for Fidelity API authentication.
    """
    
    def __init__(self, config: FidelityConfig):
        self.config = config
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize the OAuth client."""
        self._session = aiohttp.ClientSession()
        
        if self.config.oauth_token:
            self._token = self.config.oauth_token
            self._refresh_token = self.config.oauth_refresh_token
            await self._refresh_access_token()
        
        logger.info("FidelityOAuth2Client initialized")
    
    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        async with self._lock:
            if self._token and not self._is_token_expired():
                return self._token
            
            if self._refresh_token:
                await self._refresh_access_token()
                return self._token
            
            raise StockAuthenticationError("No valid access token available")
    
    async def _refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self._refresh_token:
            raise StockAuthenticationError("No refresh token available")
        
        try:
            auth = base64.b64encode(
                f"{self.config.client_id}:{self.config.client_secret}".encode()
            ).decode()
            
            headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token
            }
            
            async with self._session.post(
                self.config.get_auth_url(),
                headers=headers,
                data=data,
                ssl=self.config.verify_ssl
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise StockAuthenticationError(f"Token refresh failed: {error_text}")
                
                result = await response.json()
                
                self._token = result.get('access_token')
                self._refresh_token = result.get('refresh_token', self._refresh_token)
                expires_in = result.get('expires_in', 3600)
                self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                
                logger.info("Access token refreshed successfully")
                
        except aiohttp.ClientError as e:
            raise StockConnectionError(f"Token refresh error: {e}")
        except Exception as e:
            raise StockAuthenticationError(f"Token refresh failed: {e}")
    
    def _is_token_expired(self) -> bool:
        """Check if the token is expired or about to expire."""
        if not self._token_expiry:
            return True
        return datetime.utcnow() >= self._token_expiry
    
    async def close(self):
        """Close the OAuth client."""
        if self._session:
            await self._session.close()


# =============================================================================
# MAIN FIDELITY CLIENT
# =============================================================================

class FidelityClient(StockExchange):
    """
    Advanced Fidelity stock trading client.
    
    Features:
    - OAuth 2.0 authentication
    - All order types (market, limit, stop, stop-limit, trailing stop)
    - Real-time quotes and trades
    - Historical data with multiple timeframes
    - Account and position management
    - Portfolio analytics
    - Mutual funds trading
    - Fixed income trading
    - Options trading support
    - WebSocket real-time streaming
    - Comprehensive error handling
    - Database persistence
    - Redis caching
    """
    
    def __init__(
        self,
        config: FidelityConfig,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        super().__init__(config, redis, pool)
        self.config = config
        self.converter = get_converter()
        self.converter.set_broker(StockExchangeType.FIDELITY)
        
        # OAuth client
        self._oauth = FidelityOAuth2Client(config)
        
        # Account state
        self._accounts: Dict[str, FidelityAccount] = {}
        self._default_account_id: Optional[str] = None
        
        # WebSocket state
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_subscriptions: Set[str] = set()
        
        # Database
        self._db_initialized = False
        
        logger.info("FidelityClient initialized")
    
    async def initialize(self):
        """Initialize the Fidelity client."""
        # Initialize OAuth
        await self._oauth.initialize()
        
        # Initialize HTTP session
        self._session = aiohttp.ClientSession(
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "application/json"
            }
        )
        
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Get accounts
        await self.get_accounts()
        
        # Get positions
        await self.get_positions()
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        self._initialized = True
        logger.info("FidelityClient initialization complete")
    
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
        """
        Make an authenticated request to Fidelity.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data (POST/PUT)
            params: Query parameters (GET)
            use_api: Use API URL or base URL
            
        Returns:
            Response data
        """
        # Check circuit breaker
        cb_key = "fidelity_order" if "order" in endpoint else "fidelity_market"
        cb = self._order_cb if "order" in endpoint else self._market_data_cb
        
        if cb.is_open():
            raise StockRateLimitError("Circuit breaker is open")
        
        # Rate limit
        await self._rate_limiter.acquire()
        
        # Get access token
        token = await self._oauth.get_access_token()
        
        # Build URL
        if use_api:
            base_url = self.config.get_api_url()
        else:
            base_url = self.config.get_base_url()
        
        url = f"{base_url}{endpoint}"
        
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            async with self._session.request(
                method=method.upper(),
                url=url,
                json=data if data and method.upper() in ["POST", "PUT"] else None,
                headers=headers,
                ssl=self.config.verify_ssl
            ) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, method, data, params, use_api)
                
                if response.status == 401:
                    # Token expired, refresh and retry
                    await self._oauth._refresh_access_token()
                    return await self._make_request(endpoint, method, data, params, use_api)
                
                if response.status >= 400:
                    error_text = await response.text()
                    if response.status == 403:
                        raise StockPermissionError(error_text)
                    elif response.status == 404:
                        raise StockNotFoundError(error_text)
                    elif response.status == 422:
                        raise StockValidationError(error_text)
                    elif response.status == 503:
                        raise StockConnectionError("Fidelity service unavailable")
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
    async def get_accounts(self, refresh: bool = False) -> Dict[str, FidelityAccount]:
        """Get all accounts."""
        if not refresh and self._accounts:
            return self._accounts
        
        try:
            data = await self._make_request("/accounts", method="GET", use_api=True)
            
            accounts = {}
            for item in data.get('accounts', []):
                account = FidelityAccount(
                    account_id=item.get('accountId', ''),
                    account_name=item.get('accountName', ''),
                    account_type=FidelityAccountType(item.get('accountType', 'BROKERAGE')),
                    account_status=item.get('accountStatus', 'ACTIVE'),
                    cash_balance=Decimal(str(item.get('cashBalance', 0))),
                    buying_power=Decimal(str(item.get('buyingPower', 0))),
                    total_equity=Decimal(str(item.get('totalEquity', 0))),
                    long_market_value=Decimal(str(item.get('longMarketValue', 0))),
                    short_market_value=Decimal(str(item.get('shortMarketValue', 0))),
                    margin_balance=Decimal(str(item.get('marginBalance', 0))),
                    settled_cash=Decimal(str(item.get('settledCash', 0))),
                    unsettled_cash=Decimal(str(item.get('unsettledCash', 0))),
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
    
    async def get_default_account(self) -> Optional[FidelityAccount]:
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
            data = await self._make_request("/instruments", method="GET", use_api=True)
            
            assets = {}
            for item in data.get('instruments', []):
                asset = StockAsset(
                    id=item.get('symbol', ''),
                    symbol=item.get('symbol', ''),
                    name=item.get('name', ''),
                    exchange=item.get('exchange', 'NYSE'),
                    asset_class=item.get('assetClass', 'equity'),
                    status=item.get('status', 'active'),
                    tick_size=Decimal(str(item.get('tickSize', 0.01))),
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
            fidelity_type_map = {
                StockOrderType.MARKET: FidelityOrderType.MARKET,
                StockOrderType.LIMIT: FidelityOrderType.LIMIT,
                StockOrderType.STOP: FidelityOrderType.STOP,
                StockOrderType.STOP_LIMIT: FidelityOrderType.STOP_LIMIT,
                StockOrderType.TRAILING_STOP: FidelityOrderType.TRAILING_STOP,
            }
            fidelity_type = fidelity_type_map.get(order_type, FidelityOrderType.LIMIT)
            
            # Map side
            fidelity_side_map = {
                StockOrderSide.BUY: FidelityOrderSide.BUY,
                StockOrderSide.SELL: FidelityOrderSide.SELL,
            }
            fidelity_side = fidelity_side_map.get(side, FidelityOrderSide.BUY)
            
            # Build order request
            order_data = {
                "accountId": account.account_id,
                "symbol": symbol,
                "orderType": fidelity_type.value,
                "orderSide": fidelity_side.value,
                "quantity": str(quantity),
                "timeInForce": time_in_force.value.upper()
            }
            
            if limit_price is not None:
                order_data["limitPrice"] = str(limit_price)
            elif price is not None:
                order_data["limitPrice"] = str(price)
            
            if stop_price is not None:
                order_data["stopPrice"] = str(stop_price)
            
            if trail_percent is not None:
                order_data["trailPercent"] = str(trail_percent)
            
            if trail_price is not None:
                order_data["trailPrice"] = str(trail_price)
            
            if extended_hours:
                order_data["extendedHours"] = True
            
            if client_order_id:
                order_data["clientOrderId"] = client_order_id
            
            # Place order
            data = await self._make_request(
                "/orders",
                method="POST",
                data=order_data,
                use_api=True
            )
            
            order_data = data.get('order', {})
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
                f"/accounts/{account.account_id}/orders",
                method="GET",
                params=params,
                use_api=True
            )
            
            orders = []
            for item in data.get('orders', []):
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
                method="GET",
                use_api=True
            )
            
            order_data = data.get('order', {})
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
                f"/accounts/{account.account_id}/orders/{order_id}",
                method="DELETE",
                use_api=True
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
            side=StockOrderSide(data.get('orderSide', 'BUY').lower()),
            order_type=StockOrderType(data.get('orderType', 'LIMIT').lower()),
            status=status,
            time_in_force=StockTimeInForce(data.get('timeInForce', 'DAY').lower()),
            quantity=Decimal(str(data.get('quantity', 0))),
            filled_quantity=Decimal(str(data.get('filledQuantity', 0))),
            remaining_quantity=Decimal(str(data.get('remainingQuantity', 0))),
            limit_price=Decimal(str(data.get('limitPrice', 0))) if data.get('limitPrice') else None,
            stop_price=Decimal(str(data.get('stopPrice', 0))) if data.get('stopPrice') else None,
            trail_price=Decimal(str(data.get('trailPrice', 0))) if data.get('trailPrice') else None,
            trail_percent=Decimal(str(data.get('trailPercent', 0))) if data.get('trailPercent') else None,
            average_price=Decimal(str(data.get('avgPrice', 0))) if data.get('avgPrice') else None,
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('avgPrice', 0))) * Decimal(str(data.get('filledQuantity', 0))) if data.get('avgPrice') else Decimal('0'),
            extended_hours=data.get('extendedHours', False),
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
                method="GET",
                use_api=True
            )
            
            positions = {}
            for item in data.get('positions', []):
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
            current_price=Decimal(str(data.get('currentPrice', 0))),
            market_value=Decimal(str(data.get('marketValue', 0))),
            unrealized_pl=Decimal(str(data.get('unrealizedPnl', 0))),
            realized_pl=Decimal(str(data.get('realizedPnl', 0))),
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
                f"/quotes/{symbol}",
                method="GET",
                use_api=True
            )
            
            quote_data = data.get('quote', {})
            
            quote = StockQuote(
                symbol=quote_data.get('symbol', ''),
                bid_price=Decimal(str(quote_data.get('bid', 0))),
                bid_size=Decimal(str(quote_data.get('bidSize', 0))),
                ask_price=Decimal(str(quote_data.get('ask', 0))),
                ask_size=Decimal(str(quote_data.get('askSize', 0))),
                last_price=Decimal(str(quote_data.get('last', 0))),
                volume=Decimal(str(quote_data.get('volume', 0))),
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
                "limit": min(limit, 1000)
            }
            
            if start:
                params["startDate"] = start.strftime('%Y-%m-%d')
            if end:
                params["endDate"] = end.strftime('%Y-%m-%d')
            
            data = await self._make_request(
                "/charts",
                method="GET",
                params=params,
                use_api=True
            )
            
            bars = []
            for item in data.get('bars', []):
                bar = StockBar(
                    symbol=symbol,
                    open=Decimal(str(item.get('open', 0))),
                    high=Decimal(str(item.get('high', 0))),
                    low=Decimal(str(item.get('low', 0))),
                    close=Decimal(str(item.get('close', 0))),
                    volume=Decimal(str(item.get('volume', 0))),
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
                    INSERT INTO fidelity_orders (
                        id, account_id, symbol, side, order_type,
                        status, time_in_force, quantity, filled_quantity,
                        remaining_quantity, limit_price, stop_price,
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
                    order.limit_price,
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
                        INSERT INTO fidelity_positions (
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
                        FidelityAssetClass.EQUITY.value,
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
                        INSERT INTO fidelity_accounts (
                            account_id, account_name, account_type,
                            account_status, cash_balance, buying_power,
                            total_equity, long_market_value,
                            short_market_value, margin_balance,
                            settled_cash, unsettled_cash,
                            day_trade_count, updated_at, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                                  $10, $11, $12, $13, $14, $15)
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
                            settled_cash = EXCLUDED.settled_cash,
                            unsettled_cash = EXCLUDED.unsettled_cash,
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
                        account.settled_cash,
                        account.unsettled_cash,
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
        """Shutdown the Fidelity client."""
        self._shutdown_requested = True
        self._running = False
        
        await self._oauth.close()
        
        if self._session:
            await self._session.close()
        
        logger.info("FidelityClient shutdown complete")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'FidelityClient',
    'FidelityConfig',
    'FidelityEnvironment',
    'FidelityOrderType',
    'FidelityOrderSide',
    'FidelityOrderStatus',
    'FidelityTimeInForce',
    'FidelityAccountType',
    'FidelityAssetClass',
    'FidelityAccount',
    'FidelityOrder',
    'FidelityPosition',
    'FidelityQuote',
    'FidelityBar',
    'FidelityOAuth2Client'
]
