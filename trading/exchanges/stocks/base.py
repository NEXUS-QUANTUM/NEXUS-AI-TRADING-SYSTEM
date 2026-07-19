# trading/exchanges/stocks/base.py
# Nexus AI Trading System - Base Stock Exchange Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Base Stock Exchange Module

This module provides the foundational infrastructure for stock trading
integrations across multiple brokers including Alpaca, Interactive Brokers,
TD Ameritrade, Robinhood, and others.

It includes:

- Core API client with authentication
- Rate limiting and request management
- WebSocket connection handling
- Error handling and retry logic
- Data normalization and validation
- Cache management
- Circuit breaker pattern
- Request signing and security
- Multi-environment support
- Comprehensive logging and monitoring
- Account management
- Order management
- Position management
- Market data streaming

Architecture:
    StockExchange -> StockBrokerAdapter -> StockDataProvider
                  -> StockOrderManager -> StockPositionManager
                  -> StockStreamManager -> StockAccountManager

Security Features:
- API key and secret encryption
- OAuth2 support
- JWT token management
- Rate limit protection
- Session management
- IP whitelisting support
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Coroutine, Tuple

import aiohttp
import websockets
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.configs.app_config import AppConfig
from shared.helpers.logging import get_logger
from shared.helpers.crypto_helpers import decrypt_data, encrypt_data
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry, retry

logger = get_logger(__name__)

# =============================================================================
# CONSTANTS AND ENUMS
# =============================================================================

class StockExchangeType(str, Enum):
    """Stock exchange types."""
    ALPACA = "alpaca"
    IBKR = "ibkr"
    TD_AMERITRADE = "td_ameritrade"
    ROBINHOOD = "robinhood"
    E_TRADE = "e_trade"
    FIDELITY = "fidelity"
    SCHWAB = "schwab"
    TRADESTATION = "tradestation"
    TRADIER = "tradier"
    INTERACTIVE_BROKERS = "interactive_brokers"
    CUSTOM = "custom"


class StockOrderType(str, Enum):
    """Stock order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    MARKET_ON_CLOSE = "market_on_close"
    LIMIT_ON_CLOSE = "limit_on_close"
    BRACKET = "bracket"
    OCO = "oco"
    OTO = "oto"


class StockOrderSide(str, Enum):
    """Stock order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"


class StockOrderStatus(str, Enum):
    """Stock order status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    DONE = "done"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    STOPPED = "stopped"
    SUSPENDED = "suspended"


class StockTimeInForce(str, Enum):
    """Stock time in force."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    OPG = "opg"  # At Opening
    CLS = "cls"  # At Closing
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    GTD = "gtd"  # Good Till Date


class StockPositionSide(str, Enum):
    """Stock position sides."""
    LONG = "long"
    SHORT = "short"


class StockOrderClass(str, Enum):
    """Stock order classes."""
    SIMPLE = "simple"
    BRACKET = "bracket"
    OCO = "oco"
    OTO = "oto"


class StockAccountStatus(str, Enum):
    """Stock account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    RESTRICTED = "restricted"


class StockMarketStatus(str, Enum):
    """Stock market status."""
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StockConfig(BaseModel):
    """Base stock exchange configuration."""
    exchange_type: StockExchangeType
    api_key: str
    api_secret: Optional[str] = None
    oauth_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    environment: str = "production"
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit: int = 100  # requests per second
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
        if not v or len(v) < 5:
            raise ValueError("Invalid API key format")
        return v

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class StockAccount(BaseModel):
    """Stock account information."""
    id: str
    account_number: Optional[str] = None
    name: Optional[str] = None
    status: StockAccountStatus = StockAccountStatus.ACTIVE
    currency: str = "USD"
    buying_power: Decimal = Decimal('0')
    cash: Decimal = Decimal('0')
    equity: Decimal = Decimal('0')
    portfolio_value: Decimal = Decimal('0')
    long_market_value: Decimal = Decimal('0')
    short_market_value: Decimal = Decimal('0')
    margin_used: Decimal = Decimal('0')
    margin_available: Decimal = Decimal('0')
    multiplier: Decimal = Decimal('1')
    day_trade_count: int = 0
    pattern_day_trader: bool = False
    trade_suspended: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StockAsset(BaseModel):
    """Stock asset information."""
    id: str
    symbol: str
    name: str
    exchange: str
    asset_class: str = "equity"
    status: str = "active"
    fractionable: bool = False
    marginable: bool = False
    shortable: bool = False
    tick_size: Decimal = Decimal('0.01')
    min_order_size: Optional[Decimal] = None
    max_order_size: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StockOrder(BaseModel):
    """Stock order."""
    id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: StockOrderSide
    order_type: StockOrderType
    status: StockOrderStatus
    time_in_force: StockTimeInForce
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
    order_class: StockOrderClass = StockOrderClass.SIMPLE
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.quantity * 100)

    @property
    def is_open(self) -> bool:
        return self.status in [StockOrderStatus.ACCEPTED, StockOrderStatus.NEW,
                              StockOrderStatus.PARTIALLY_FILLED, StockOrderStatus.PENDING]

    @property
    def is_closed(self) -> bool:
        return self.status in [StockOrderStatus.FILLED, StockOrderStatus.DONE,
                              StockOrderStatus.CANCELLED, StockOrderStatus.EXPIRED,
                              StockOrderStatus.REJECTED, StockOrderStatus.STOPPED]


class StockPosition(BaseModel):
    """Stock position."""
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
    side: Optional[StockPositionSide] = None
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


class StockQuote(BaseModel):
    """Stock quote."""
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    last_price: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    conditions: List[str] = Field(default_factory=list)


class StockBar(BaseModel):
    """Stock bar (OHLC)."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None


class StockTrade(BaseModel):
    """Stock trade."""
    id: str
    symbol: str
    side: StockOrderSide
    price: Decimal
    quantity: Decimal
    cost: Decimal
    fee: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# BASE EXCHANGE CLASS
# =============================================================================

class StockExchange(ABC):
    """
    Abstract base class for stock exchange integrations.
    
    This class provides the foundation for all stock exchange integrations
    with a unified interface for trading operations.
    
    Subclasses must implement:
    - connect(): Establish connection to the exchange
    - disconnect(): Close connection to the exchange
    - get_account(): Get account information
    - get_assets(): Get available assets
    - place_order(): Place an order
    - get_orders(): Get orders with filters
    - get_order(): Get an order by ID
    - cancel_order(): Cancel an order
    - get_positions(): Get all positions
    - get_position(): Get a position by symbol
    - close_position(): Close a position
    - get_quote(): Get real-time quote
    - get_bars(): Get historical bars
    
    Optional methods:
    - get_watchlists(): Get watchlists
    - create_watchlist(): Create a watchlist
    - update_watchlist(): Update a watchlist
    - delete_watchlist(): Delete a watchlist
    - get_news(): Get news for symbols
    - get_corporate_actions(): Get corporate actions
    - get_dividends(): Get dividend information
    """
    
    def __init__(
        self,
        config: StockConfig,
        redis: Optional[Redis] = None,
        pool: Optional[Any] = None
    ):
        self.config = config
        self.redis = redis
        self.pool = pool
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket connection
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_connected = False
        
        # State
        self._account: Optional[StockAccount] = None
        self._positions: Dict[str, StockPosition] = {}
        self._orders: Dict[str, StockOrder] = {}
        self._assets: Dict[str, StockAsset] = {}
        
        # Circuit breakers
        self._order_cb = CircuitBreaker(
            name=f"stock_order_{config.exchange_type.value}",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._market_data_cb = CircuitBreaker(
            name=f"stock_market_data_{config.exchange_type.value}",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Rate limiter
        self._rate_limiter = StockRateLimiter(
            rate=config.rate_limit,
            name=config.exchange_type.value
        )
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # WebSocket handlers
        self._ws_handlers: Dict[str, List[Callable]] = {}
        
        # Running state
        self._initialized = False
        self._running = False
        self._shutdown_requested = False
        
        # Request counter
        self._request_counter = 0
        
        logger.info(f"StockExchange initialized for {config.exchange_type.value}")
    
    # =========================================================================
    # ABSTRACT METHODS
    # =========================================================================
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the exchange."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the exchange."""
        pass
    
    @abstractmethod
    async def get_account(self, refresh: bool = False) -> StockAccount:
        """Get account information."""
        pass
    
    @abstractmethod
    async def get_assets(self, refresh: bool = False) -> Dict[str, StockAsset]:
        """Get available assets."""
        pass
    
    @abstractmethod
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
        **kwargs
    ) -> StockOrder:
        """Place an order."""
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        status: Optional[StockOrderStatus] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> List[StockOrder]:
        """Get orders with filters."""
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[StockOrder]:
        """Get an order by ID."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, StockPosition]:
        """Get all positions."""
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[StockPosition]:
        """Get a position by symbol."""
        pass
    
    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        quantity: Optional[Decimal] = None
    ) -> StockOrder:
        """Close a position."""
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> StockQuote:
        """Get real-time quote."""
        pass
    
    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[StockBar]:
        """Get historical bars."""
        pass
    
    # =========================================================================
    # OPTIONAL METHODS
    # =========================================================================
    
    async def get_watchlists(self) -> Dict[str, Any]:
        """Get watchlists. Override in subclass if supported."""
        return {}
    
    async def create_watchlist(self, name: str, symbols: List[str]) -> Any:
        """Create a watchlist. Override in subclass if supported."""
        raise NotImplementedError("Watchlists not supported")
    
    async def update_watchlist(self, watchlist_id: str, symbols: List[str]) -> Any:
        """Update a watchlist. Override in subclass if supported."""
        raise NotImplementedError("Watchlists not supported")
    
    async def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist. Override in subclass if supported."""
        raise NotImplementedError("Watchlists not supported")
    
    async def get_news(self, symbols: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        """Get news for symbols. Override in subclass if supported."""
        return []
    
    async def get_corporate_actions(
        self,
        symbol: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get corporate actions. Override in subclass if supported."""
        return []
    
    async def get_dividends(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get dividend information. Override in subclass if supported."""
        return []
    
    # =========================================================================
    # WEBSOCKET METHODS
    # =========================================================================
    
    async def register_ws_handler(self, event_type: str, handler: Callable):
        """Register a WebSocket event handler."""
        if event_type not in self._ws_handlers:
            self._ws_handlers[event_type] = []
        self._ws_handlers[event_type].append(handler)
    
    async def subscribe_to_quotes(self, symbols: List[str]):
        """Subscribe to real-time quotes. Override in subclass if supported."""
        raise NotImplementedError("Quote subscription not supported")
    
    async def subscribe_to_trades(self, symbols: List[str]):
        """Subscribe to real-time trades. Override in subclass if supported."""
        raise NotImplementedError("Trade subscription not supported")
    
    async def subscribe_to_bars(self, symbols: List[str]):
        """Subscribe to real-time bars. Override in subclass if supported."""
        raise NotImplementedError("Bar subscription not supported")
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol."""
        return symbol.upper().strip()
    
    def _normalize_currency(self, currency: str) -> str:
        """Normalize currency."""
        return currency.upper().strip()
    
    def _format_timestamp(self, dt: datetime) -> str:
        """Format timestamp for API."""
        return dt.isoformat()
    
    def _parse_timestamp(self, ts: Union[str, int, float]) -> datetime:
        """Parse timestamp from API."""
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return datetime.fromtimestamp(ts)
    
    # =========================================================================
    # CACHE METHODS
    # =========================================================================
    
    async def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached data."""
        if not self.config.use_cache:
            return None
        
        if key in self._cache:
            if time.time() - self._cache_timestamps.get(key, 0) < self.config.cache_ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_timestamps[key]
        
        if self.redis:
            try:
                data = await self.redis.get(f"stock:{key}")
                if data:
                    result = json.loads(data)
                    self._cache[key] = result
                    self._cache_timestamps[key] = time.time()
                    return result
            except Exception as e:
                logger.error(f"Redis cache read error: {e}")
        
        return None
    
    async def _set_cache(self, key: str, data: Any, ttl: Optional[int] = None):
        """Set cached data."""
        if not self.config.use_cache:
            return
        
        self._cache[key] = data
        self._cache_timestamps[key] = time.time()
        
        if self.redis:
            try:
                json_data = json.dumps(data, default=self._json_serializer)
                ttl = ttl or self.config.cache_ttl
                await self.redis.setex(f"stock:{key}", ttl, json_data)
            except Exception as e:
                logger.error(f"Redis cache write error: {e}")
    
    @staticmethod
    def _json_serializer(obj):
        """JSON serializer for non-serializable objects."""
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the exchange client."""
        self._shutdown_requested = True
        self._running = False
        
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        
        if self._session:
            await self._session.close()
        
        logger.info(f"StockExchange shutdown complete for {self.config.exchange_type.value}")


# =============================================================================
# RATE LIMITER
# =============================================================================

class StockRateLimiter:
    """
    Rate limiter for stock exchange API calls.
    
    Implements token bucket algorithm with support for:
    - Configurable rate limits
    - Burst handling
    - Wait queuing
    - Metrics tracking
    """
    
    def __init__(
        self,
        rate: float,
        burst: Optional[float] = None,
        name: str = "stock"
    ):
        self.rate = rate  # requests per second
        self.burst = burst or rate * 2  # burst capacity
        self.name = name
        
        self._tokens = self.burst
        self._last_refill = time.time()
        self._lock = asyncio.Lock()
        self._waiting = 0
        self._total_wait_time = 0.0
        self._requests = 0
        
        logger.debug(f"RateLimiter created: {name} rate={rate}/s burst={self.burst}")
    
    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens for a request.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            Wait time in seconds
        """
        async with self._lock:
            self._waiting += 1
            
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._requests += 1
                self._waiting -= 1
                return 0.0
            
            needed = tokens - self._tokens
            wait_time = needed / self.rate
            
            await asyncio.sleep(wait_time)
            
            self._tokens = 0
            self._last_refill = time.time()
            self._total_wait_time += wait_time
            self._requests += 1
            self._waiting -= 1
            
            return wait_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "name": self.name,
            "rate": self.rate,
            "burst": self.burst,
            "tokens": self._tokens,
            "waiting": self._waiting,
            "requests": self._requests,
            "total_wait_time": self._total_wait_time,
            "average_wait": self._total_wait_time / self._requests if self._requests > 0 else 0
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================

class StockError(Exception):
    """Base exception for stock exchange errors."""
    pass


class StockAuthenticationError(StockError):
    """Authentication error."""
    pass


class StockPermissionError(StockError):
    """Permission error."""
    pass


class StockRateLimitError(StockError):
    """Rate limit error."""
    pass


class StockInvalidSymbolError(StockError):
    """Invalid symbol error."""
    pass


class StockNotFoundError(StockError):
    """Resource not found."""
    pass


class StockValidationError(StockError):
    """Validation error."""
    pass


class StockConnectionError(StockError):
    """Connection error."""
    pass


class StockTimeoutError(StockError):
    """Timeout error."""
    pass


class StockWebSocketError(StockError):
    """WebSocket error."""
    pass


class StockInsufficientFundsError(StockError):
    """Insufficient funds error."""
    pass


class StockOrderError(StockError):
    """Order error."""
    pass


class StockPositionError(StockError):
    """Position error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'StockExchange',
    'StockConfig',
    'StockExchangeType',
    'StockOrderType',
    'StockOrderSide',
    'StockOrderStatus',
    'StockTimeInForce',
    'StockPositionSide',
    'StockOrderClass',
    'StockAccountStatus',
    'StockMarketStatus',
    'StockAccount',
    'StockAsset',
    'StockOrder',
    'StockPosition',
    'StockQuote',
    'StockBar',
    'StockTrade',
    'StockRateLimiter',
    'StockError',
    'StockAuthenticationError',
    'StockPermissionError',
    'StockRateLimitError',
    'StockInvalidSymbolError',
    'StockNotFoundError',
    'StockValidationError',
    'StockConnectionError',
    'StockTimeoutError',
    'StockWebSocketError',
    'StockInsufficientFundsError',
    'StockOrderError',
    'StockPositionError'
]
