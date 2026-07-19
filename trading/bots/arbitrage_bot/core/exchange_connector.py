# trading/bots/arbitrage_bot/core/exchange_connector.py
# Nexus AI Trading System - Arbitrage Bot Exchange Connector Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Exchange Connector Module

This module provides a unified interface for connecting to multiple
cryptocurrency exchanges for arbitrage operations. It includes:

- Exchange connection management
- Market data retrieval
- Order placement and management
- Balance management
- WebSocket integration
- Rate limiting
- Error handling and retry
- Connection pooling
- Multi-exchange support
- Health checking
- Circuit breaker integration

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
- DEX (Uniswap, PancakeSwap, etc.)
"""

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker
from trading.bots.arbitrage_bot.core.balance_manager import BalanceManager
from trading.exchanges.binance.base import BinanceBase, BinanceConfig
from trading.exchanges.okx.base import OKXBase, OKXConfig
from trading.exchanges.kraken.base import KrakenBase, KrakenConfig
from trading.exchanges.coinbase.base import CoinbaseBase, CoinbaseConfig
from shared.helpers.logging import get_logger
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ExchangeStatus(str, Enum):
    """Exchange connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    RATE_LIMITED = "rate_limited"


class ExchangeOrderType(str, Enum):
    """Exchange order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class ExchangeOrderSide(str, Enum):
    """Exchange order sides."""
    BUY = "buy"
    SELL = "sell"


class ExchangeOrderStatus(str, Enum):
    """Exchange order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ExchangeTimeInForce(str, Enum):
    """Exchange time in force."""
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    DAY = "Day"
    GTX = "GTX"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ExchangeConnectionConfig(BaseModel):
    """Exchange connection configuration."""
    exchange: str
    api_key: str
    api_secret: str
    api_passphrase: Optional[str] = None
    environment: str = "production"
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit: int = 20
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
            raise ValueError("Invalid API key")
        return v

    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Invalid API secret")
        return v


class ExchangeBalance(BaseModel):
    """Exchange balance."""
    exchange: str
    currency: str
    total: Decimal
    available: Decimal
    locked: Decimal = Decimal('0')
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExchangePrice(BaseModel):
    """Exchange price data."""
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    mid: Decimal
    spread: Decimal
    spread_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    volume_24h: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None


class ExchangeOrder(BaseModel):
    """Exchange order."""
    id: str
    exchange: str
    symbol: str
    side: ExchangeOrderSide
    order_type: ExchangeOrderType
    status: ExchangeOrderStatus
    price: Decimal
    volume: Decimal
    filled_volume: Decimal = Decimal('0')
    remaining_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    time_in_force: ExchangeTimeInForce = ExchangeTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)


class ExchangeOrderBook(BaseModel):
    """Exchange order book."""
    exchange: str
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # (price, volume)
    asks: List[Tuple[Decimal, Decimal]]  # (price, volume)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExchangeTrade(BaseModel):
    """Exchange trade."""
    id: str
    exchange: str
    symbol: str
    side: ExchangeOrderSide
    price: Decimal
    volume: Decimal
    fee: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# EXCHANGE CONNECTOR INTERFACE
# =============================================================================

class ExchangeConnector(ABC):
    """
    Abstract base class for exchange connectors.
    
    This class defines the interface for all exchange connectors.
    Subclasses must implement the specific exchange API integration.
    """
    
    def __init__(
        self,
        config: ExchangeConnectionConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        """
        Initialize the exchange connector.
        
        Args:
            config: Exchange connection configuration
            circuit_breaker: Circuit breaker instance
            redis: Redis client for caching
            pool: PostgreSQL connection pool
        """
        self.config = config
        self.circuit_breaker = circuit_breaker
        self.redis = redis
        self.pool = pool
        
        # Status
        self._status = ExchangeStatus.DISCONNECTED
        
        # Rate limiting
        self._rate_limiter = ExchangeRateLimiter(
            rate=config.rate_limit,
            name=config.exchange
        )
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket connection
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_connected = False
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # Running state
        self._initialized = False
        self._running = False
        
        # WebSocket handlers
        self._ws_handlers: Dict[str, List[Callable]] = {}
        
        # Metrics
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = 0
        self._last_error_time = 0
        
        logger.info(f"Exchange connector initialized for {config.exchange}")
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the exchange.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the exchange.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to the exchange.
        
        Returns:
            True if connected
        """
        pass
    
    async def reconnect(self) -> bool:
        """
        Reconnect to the exchange.
        
        Returns:
            True if reconnected successfully
        """
        await self.disconnect()
        await asyncio.sleep(1)
        return await self.connect()
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check.
        
        Returns:
            Health check results
        """
        pass
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    @abstractmethod
    async def get_price(self, symbol: str) -> ExchangePrice:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            ExchangePrice
        """
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int = 10) -> ExchangeOrderBook:
        """
        Get order book for a symbol.
        
        Args:
            symbol: Trading symbol
            depth: Order book depth
            
        Returns:
            ExchangeOrderBook
        """
        pass
    
    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get k-line (candlestick) data.
        
        Args:
            symbol: Trading symbol
            interval: K-line interval
            limit: Number of k-lines
            
        Returns:
            List of k-line data
        """
        pass
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: ExchangeOrderSide,
        order_type: ExchangeOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: ExchangeTimeInForce = ExchangeTimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> ExchangeOrder:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            order_type: Order type
            volume: Order volume
            price: Price for limit orders
            time_in_force: Time in force
            client_order_id: Client-side order ID
            
        Returns:
            ExchangeOrder
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[ExchangeOrder]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            ExchangeOrder or None
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[ExchangeOrder]:
        """
        Get open orders.
        
        Args:
            symbol: Filter by symbol
            
        Returns:
            List of open orders
        """
        pass
    
    @abstractmethod
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[ExchangeOrder]:
        """
        Get order history.
        
        Args:
            symbol: Filter by symbol
            limit: Number of orders
            
        Returns:
            List of orders
        """
        pass
    
    # =========================================================================
    # BALANCE MANAGEMENT
    # =========================================================================
    
    @abstractmethod
    async def get_balances(self) -> Dict[str, ExchangeBalance]:
        """
        Get all account balances.
        
        Returns:
            Dict mapping currency to balance
        """
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str) -> Optional[ExchangeBalance]:
        """
        Get balance for a specific currency.
        
        Args:
            currency: Currency code
            
        Returns:
            ExchangeBalance or None
        """
        pass
    
    # =========================================================================
    # WEBSOCKET
    # =========================================================================
    
    @abstractmethod
    async def subscribe_to_ticker(self, symbols: List[str], handler: Callable):
        """
        Subscribe to ticker updates.
        
        Args:
            symbols: List of symbols
            handler: Callback function
        """
        pass
    
    @abstractmethod
    async def subscribe_to_order_book(self, symbols: List[str], handler: Callable):
        """
        Subscribe to order book updates.
        
        Args:
            symbols: List of symbols
            handler: Callback function
        """
        pass
    
    @abstractmethod
    async def subscribe_to_trades(self, symbols: List[str], handler: Callable):
        """
        Subscribe to trade updates.
        
        Args:
            symbols: List of symbols
            handler: Callback function
        """
        pass
    
    @abstractmethod
    async def unsubscribe_all(self):
        """Unsubscribe from all channels."""
        pass
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker is open."""
        if self.circuit_breaker and self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker open for {self.config.exchange}"
            )
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        await self._rate_limiter.acquire()
    
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
                data = await self.redis.get(f"exchange:{self.config.exchange}:{key}")
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
                await self.redis.setex(
                    f"exchange:{self.config.exchange}:{key}",
                    ttl,
                    json_data
                )
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
        """Shutdown the exchange connector."""
        self._running = False
        
        if self._session:
            await self._session.close()
        
        if self._ws:
            await self._ws.close()
        
        logger.info(f"Exchange connector shutdown for {self.config.exchange}")


# =============================================================================
# EXCHANGE CONNECTOR FACTORY
# =============================================================================

class ExchangeConnectorFactory:
    """
    Factory for creating exchange connectors.
    
    This factory provides a unified interface for creating different
    exchange connector implementations.
    """
    
    _connectors: Dict[str, Type[ExchangeConnector]] = {}
    
    @classmethod
    def register_connector(
        cls,
        exchange: str,
        connector_class: Type[ExchangeConnector]
    ):
        """
        Register a connector class.
        
        Args:
            exchange: Exchange name
            connector_class: Connector class
        """
        cls._connectors[exchange.lower()] = connector_class
        logger.info(f"Registered exchange connector: {exchange}")
    
    @classmethod
    def create_connector(
        cls,
        config: ExchangeConnectionConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> ExchangeConnector:
        """
        Create an exchange connector.
        
        Args:
            config: Exchange connection configuration
            circuit_breaker: Circuit breaker instance
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            Exchange connector instance
        """
        exchange = config.exchange.lower()
        
        if exchange not in cls._connectors:
            raise ValueError(f"Unknown exchange: {exchange}")
        
        connector_class = cls._connectors[exchange]
        return connector_class(config, circuit_breaker, redis, pool)


# =============================================================================
# EXCHANGE RATE LIMITER
# =============================================================================

class ExchangeRateLimiter:
    """
    Rate limiter for exchange API calls.
    
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
        name: str = "exchange"
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
# EXCHANGE CONNECTOR IMPLEMENTATIONS
# =============================================================================

# These would be implemented in separate files
# from trading.bots.arbitrage_bot.exchanges.binance import BinanceConnector
# from trading.bots.arbitrage_bot.exchanges.okx import OKXConnector
# from trading.bots.arbitrage_bot.exchanges.kraken import KrakenConnector
# etc.


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class ExchangeConnectionError(Exception):
    """Exchange connection error."""
    pass


class ExchangeAuthenticationError(Exception):
    """Exchange authentication error."""
    pass


class ExchangeRateLimitError(Exception):
    """Exchange rate limit error."""
    pass


class ExchangeInvalidSymbolError(Exception):
    """Invalid symbol error."""
    pass


class ExchangeInsufficientFundsError(Exception):
    """Insufficient funds error."""
    pass


class ExchangeOrderError(Exception):
    """Order error."""
    pass


class ExchangeOrderNotFoundError(Exception):
    """Order not found error."""
    pass


class ExchangeWebSocketError(Exception):
    """WebSocket error."""
    pass


class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    'ExchangeStatus',
    'ExchangeOrderType',
    'ExchangeOrderSide',
    'ExchangeOrderStatus',
    'ExchangeTimeInForce',
    
    # Models
    'ExchangeConnectionConfig',
    'ExchangeBalance',
    'ExchangePrice',
    'ExchangeOrder',
    'ExchangeOrderBook',
    'ExchangeTrade',
    
    # Base class
    'ExchangeConnector',
    
    # Factory
    'ExchangeConnectorFactory',
    
    # Rate limiter
    'ExchangeRateLimiter',
    
    # Exceptions
    'ExchangeConnectionError',
    'ExchangeAuthenticationError',
    'ExchangeRateLimitError',
    'ExchangeInvalidSymbolError',
    'ExchangeInsufficientFundsError',
    'ExchangeOrderError',
    'ExchangeOrderNotFoundError',
    'ExchangeWebSocketError',
    'CircuitBreakerOpenError'
]
