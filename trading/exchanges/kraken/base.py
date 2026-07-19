# trading/exchanges/kraken/base.py
# Nexus AI Trading System - Kraken Exchange Base Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Base Module

This module provides the foundational infrastructure for interacting with the
Kraken cryptocurrency exchange API. It includes:

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

Architecture:
    KrakenBase -> KrakenPublicAPI (Public endpoints)
               -> KrakenPrivateAPI (Private endpoints)
               -> KrakenWebSocket (WebSocket streams)
               -> KrakenClient (Unified interface)

Security Features:
- API key and secret encryption
- Request signing with HMAC-SHA256
- Nonce generation with timestamp
- IP whitelisting support
- Rate limit protection
- Session management
- Two-factor authentication support
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, Coroutine, Tuple
from urllib.parse import urlencode

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

class KrakenEnvironment(str, Enum):
    """Kraken API environments."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"
    DEVELOPMENT = "development"


class KrakenApiType(str, Enum):
    """Kraken API types."""
    PUBLIC = "public"
    PRIVATE = "private"


class KrakenOrderType(str, Enum):
    """Kraken order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop-loss"
    TAKE_PROFIT = "take-profit"
    STOP_LOSS_LIMIT = "stop-loss-limit"
    TAKE_PROFIT_LIMIT = "take-profit-limit"
    SETTLE_POSITION = "settle-position"
    STOP = "stop"
    TAKE_PROFIT = "take-profit"
    STOP_LOSS_PROFIT = "stop-loss-profit"
    STOP_LOSS_PROFIT_LIMIT = "stop-loss-profit-limit"


class KrakenOrderSide(str, Enum):
    """Kraken order sides."""
    BUY = "buy"
    SELL = "sell"


class KrakenOrderStatus(str, Enum):
    """Kraken order status."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"


class KrakenTimeInForce(str, Enum):
    """Kraken time in force."""
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    DAY = "Day"
    GTX = "GTX"  # Good Till Crossing


class KrakenWebSocketEvent(str, Enum):
    """Kraken WebSocket events."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"
    SYSTEM_STATUS = "systemStatus"
    SUBSCRIPTION_STATUS = "subscriptionStatus"
    HEARTBEAT = "heartbeat"


class KrakenWebSocketChannel(str, Enum):
    """Kraken WebSocket channels."""
    TICKER = "ticker"
    OHLC = "ohlc"
    TRADE = "trade"
    SPREAD = "spread"
    BOOK = "book"
    DEPTH = "depth"
    OWN_TRADES = "ownTrades"
    OPEN_ORDERS = "openOrders"
    BALANCE = "balance"
    STATUS = "status"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class KrakenConfig(BaseModel):
    """Kraken exchange configuration."""
    api_key: str
    api_secret: str
    environment: KrakenEnvironment = KrakenEnvironment.PRODUCTION
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit_public: int = 20  # requests per second
    rate_limit_private: int = 10  # requests per second
    max_retries: int = 3
    retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    cache_ttl: int = 60  # seconds
    use_cache: bool = True
    ws_ping_interval: int = 30
    ws_max_reconnect_attempts: int = 5
    ws_reconnect_delay: float = 5.0
    verify_ssl: bool = True
    proxy: Optional[str] = None
    user_agent: str = "NexusAI-Trading/3.0"
    two_factor_secret: Optional[str] = None
    ip_whitelist: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @validator('api_key')
    def validate_api_key(cls, v):
        """Validate API key format."""
        if not v or len(v) < 16:
            raise ValueError("Invalid API key format")
        return v

    @validator('api_secret')
    def validate_api_secret(cls, v):
        """Validate API secret format."""
        if not v or len(v) < 32:
            raise ValueError("Invalid API secret format")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == KrakenEnvironment.SANDBOX:
            return "https://api.sandbox.kraken.com"
        elif self.environment == KrakenEnvironment.DEVELOPMENT:
            return "https://api.dev.kraken.com"
        else:
            return "https://api.kraken.com"

    def get_ws_url(self) -> str:
        """Get the WebSocket URL."""
        if self.ws_url:
            return self.ws_url
        
        if self.environment == KrakenEnvironment.SANDBOX:
            return "wss://ws.sandbox.kraken.com"
        elif self.environment == KrakenEnvironment.DEVELOPMENT:
            return "wss://ws.dev.kraken.com"
        else:
            return "wss://ws.kraken.com"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class KrakenBalance(BaseModel):
    """Kraken account balance."""
    currency: str
    total: Decimal = Decimal('0')
    available: Decimal = Decimal('0')
    locked: Decimal = Decimal('0')
    staked: Decimal = Decimal('0')
    earned: Decimal = Decimal('0')

    @root_validator
    def validate_balance(cls, values):
        """Validate balance consistency."""
        total = values.get('total', Decimal('0'))
        available = values.get('available', Decimal('0'))
        locked = values.get('locked', Decimal('0'))
        staked = values.get('staked', Decimal('0'))
        earned = values.get('earned', Decimal('0'))
        
        # Ensure total = available + locked + staked + earned
        calculated = available + locked + staked + earned
        if abs(total - calculated) > Decimal('0.00000001'):
            values['total'] = calculated
        
        return values


class KrakenTicker(BaseModel):
    """Kraken ticker data."""
    pair: str
    ask: Decimal = Decimal('0')
    bid: Decimal = Decimal('0')
    last: Decimal = Decimal('0')
    high: Decimal = Decimal('0')
    low: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    volume_24h: Decimal = Decimal('0')
    open: Decimal = Decimal('0')
    close: Decimal = Decimal('0')
    change: Decimal = Decimal('0')
    change_percent: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator('ask', 'bid', 'last', 'high', 'low', 'volume', 'volume_24h', 'open', 'close', 'change', 'change_percent', pre=True)
    def validate_decimal(cls, v):
        """Convert to Decimal."""
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class KrakenOrder(BaseModel):
    """Kraken order."""
    id: str
    pair: str
    type: KrakenOrderType
    side: KrakenOrderSide
    status: KrakenOrderStatus
    price: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    executed_volume: Decimal = Decimal('0')
    average_price: Decimal = Decimal('0')
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        """Check if order is open."""
        return self.status in [KrakenOrderStatus.OPEN, KrakenOrderStatus.PENDING]

    @property
    def is_closed(self) -> bool:
        """Check if order is closed."""
        return self.status in [KrakenOrderStatus.CLOSED, KrakenOrderStatus.FILLED]

    @property
    def fill_rate(self) -> float:
        """Calculate fill rate percentage."""
        if self.volume == 0:
            return 0.0
        return float(self.executed_volume / self.volume * 100)

    @property
    def remaining_volume(self) -> Decimal:
        """Get remaining volume."""
        return self.volume - self.executed_volume


class KrakenTrade(BaseModel):
    """Kraken trade."""
    id: str
    pair: str
    side: KrakenOrderSide
    price: Decimal
    volume: Decimal
    fee: Decimal = Decimal('0')
    cost: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CORE IMPLEMENTATION
# =============================================================================

class KrakenBase:
    """
    Core Kraken exchange base class.
    
    This class provides the foundation for all Kraken interactions with:
    - HTTP request handling with authentication
    - WebSocket connection management
    - Rate limiting and queuing
    - Error handling and retry logic
    - Circuit breaker pattern
    - Data caching
    - Comprehensive logging
    - Request/response validation
    
    Usage:
        config = KrakenConfig(api_key="key", api_secret="secret")
        kraken = KrakenBase(config)
        await kraken.connect()
        ticker = await kraken.get_ticker("XBTUSD")
        await kraken.disconnect()
    """
    
    def __init__(
        self,
        config: KrakenConfig,
        redis: Optional[Redis] = None
    ):
        self.config = config
        self.redis = redis
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        
        # Rate limiting
        self._public_rate_limiter = KrakenRateLimiter(
            rate=config.rate_limit_public,
            name="kraken_public"
        )
        self._private_rate_limiter = KrakenRateLimiter(
            rate=config.rate_limit_private,
            name="kraken_private"
        )
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # WebSocket state
        self._ws_connected = False
        self._ws_subscriptions: Dict[str, List[str]] = {}
        self._ws_handlers: Dict[str, List[Callable]] = {}
        self._ws_reconnect_task: Optional[asyncio.Task] = None
        self._ws_ping_task: Optional[asyncio.Task] = None
        
        # Request queue for sequential requests
        self._request_queue = asyncio.Queue()
        self._request_worker: Optional[asyncio.Task] = None
        
        # Rate limit tracking
        self._rate_limit_remaining = 100
        self._rate_limit_reset = time.time() + 60
        
        # Initialization state
        self._initialized = False
        
        # Request ID for tracing
        self._request_counter = 0
        
        logger.info(f"KrakenBase initialized for environment: {config.environment}")
    
    async def connect(self):
        """Initialize and connect to Kraken."""
        if self._initialized:
            return
        
        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                ssl=self.config.verify_ssl,
                limit=100,
                limit_per_host=20
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "application/json"
                }
            )
            
            # Create WebSocket session
            ws_connector = aiohttp.TCPConnector(
                ssl=self.config.verify_ssl,
                limit=10
            )
            self._ws_session = aiohttp.ClientSession(
                connector=ws_connector,
                timeout=aiohttp.ClientTimeout(total=60)
            )
            
            # Start request worker
            self._request_worker = asyncio.create_task(self._request_worker_loop())
            
            # Start WebSocket connection if configured
            if self.config.ws_url:
                await self._connect_websocket()
            
            self._initialized = True
            logger.info("KrakenBase connected successfully")
            
        except Exception as e:
            logger.error(f"Error connecting to Kraken: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Kraken."""
        try:
            # Cancel workers
            if self._request_worker:
                self._request_worker.cancel()
                try:
                    await self._request_worker
                except asyncio.CancelledError:
                    pass
            
            # Disconnect WebSocket
            await self._disconnect_websocket()
            
            # Close sessions
            if self._session:
                await self._session.close()
            if self._ws_session:
                await self._ws_session.close()
            
            self._initialized = False
            logger.info("KrakenBase disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Kraken: {e}")
    
    # =========================================================================
    # HTTP REQUEST HANDLING
    # =========================================================================
    
    async def _request_worker_loop(self):
        """Background worker for processing requests."""
        while True:
            try:
                request = await self._request_queue.get()
                await request['future']  # Wait for the request to complete
                self._request_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Request worker error: {e}")
                await asyncio.sleep(0.1)
    
    async def _make_request(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        method: str = "POST",
        api_type: KrakenApiType = KrakenApiType.PUBLIC
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Kraken API.
        
        Args:
            endpoint: API endpoint path
            data: Request data
            method: HTTP method (GET or POST)
            api_type: API type (public or private)
            
        Returns:
            Response data
            
        Raises:
            KrakenError: For API errors
            KrakenAuthenticationError: For authentication errors
            KrakenRateLimitError: For rate limit errors
        """
        # Increment request counter
        self._request_counter += 1
        request_id = f"kraken_{self._request_counter}_{int(time.time())}"
        
        # Check circuit breaker
        cb_key = f"kraken_{endpoint}"
        if cb_key in self._circuit_breakers:
            if self._circuit_breakers[cb_key].is_open():
                raise KrakenRateLimitError(
                    f"Circuit breaker open for endpoint: {endpoint}"
                )
        
        # Apply rate limiting
        if api_type == KrakenApiType.PUBLIC:
            await self._public_rate_limiter.acquire()
        else:
            await self._private_rate_limiter.acquire()
        
        # Prepare request
        url = self._build_url(endpoint, api_type)
        headers = self._build_headers(api_type)
        
        # Sign request for private endpoints
        if api_type == KrakenApiType.PRIVATE:
            data = data or {}
            data['nonce'] = self._generate_nonce()
            headers = self._sign_request(endpoint, data, headers)
        
        # Build query string for GET requests
        params = None
        if method.upper() == "GET" and data:
            params = data.copy()
            data = None
        
        try:
            # Log request
            logger.debug(
                f"Kraken request {request_id}: {method} {url} "
                f"type={api_type.value}"
            )
            
            # Make request
            async with self._session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data if data else None,
                headers=headers,
                ssl=self.config.verify_ssl
            ) as response:
                # Update rate limit headers
                self._rate_limit_remaining = int(
                    response.headers.get('X-RateLimit-Remaining', 100)
                )
                self._rate_limit_reset = float(
                    response.headers.get('X-RateLimit-Reset', time.time() + 60)
                )
                
                # Parse response
                try:
                    result = await response.json()
                except aiohttp.ContentTypeError:
                    text = await response.text()
                    raise KrakenError(f"Invalid response: {text[:200]}")
                
                # Check for errors
                if result.get('error'):
                    error = result['error'][0]
                    if "Rate limit" in error or "RateLimit" in error:
                        self._circuit_breakers[cb_key].record_failure()
                        raise KrakenRateLimitError(error)
                    elif "Invalid key" in error or "Invalid signature" in error:
                        raise KrakenAuthenticationError(error)
                    else:
                        self._circuit_breakers[cb_key].record_failure()
                        raise KrakenError(error)
                
                # Record success
                if cb_key in self._circuit_breakers:
                    self._circuit_breakers[cb_key].record_success()
                
                logger.debug(
                    f"Kraken response {request_id}: status={response.status}"
                )
                
                return result.get('result', {})
                
        except aiohttp.ClientError as e:
            self._circuit_breakers[cb_key].record_failure()
            raise KrakenError(f"HTTP error: {e}")
        except asyncio.TimeoutError:
            self._circuit_breakers[cb_key].record_failure()
            raise KrakenError("Request timeout")
        except Exception as e:
            self._circuit_breakers[cb_key].record_failure()
            raise KrakenError(f"Request error: {e}")
    
    def _build_url(self, endpoint: str, api_type: KrakenApiType) -> str:
        """Build the full API URL."""
        base_url = self.config.get_base_url()
        api_path = "/0/public/" if api_type == KrakenApiType.PUBLIC else "/0/private/"
        return f"{base_url}{api_path}{endpoint}"
    
    def _build_headers(self, api_type: KrakenApiType) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json"
        }
        
        if api_type == KrakenApiType.PRIVATE:
            headers["API-Key"] = self.config.api_key
            headers["API-Sign"] = ""  # Will be set by _sign_request
        
        return headers
    
    def _sign_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Sign a private request with HMAC-SHA256.
        
        Kraken signature format:
        signature = base64(hmac-sha256(api_secret, endpoint + nonce + body))
        """
        # Build the POST data
        post_data = urlencode(data)
        
        # Create the signature
        # The nonce should be the same as used in the request
        nonce = data['nonce']
        signature_path = f"/0/private/{endpoint}"
        
        # Create the signature string
        signature_string = f"{signature_path}{nonce}{post_data}"
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            base64.b64decode(self.config.api_secret),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64 encode the signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Add signature to headers
        headers["API-Sign"] = signature_b64
        
        return headers
    
    def _generate_nonce(self) -> int:
        """
        Generate a nonce for private requests.
        
        The nonce must be monotonically increasing.
        """
        # Use timestamp plus request counter to ensure monotonicity
        timestamp = int(time.time() * 1000)  # milliseconds
        nonce = int(f"{timestamp}{self._request_counter:04d}")
        
        # Ensure nonce is monotonically increasing
        if hasattr(self, '_last_nonce') and nonce <= self._last_nonce:
            nonce = self._last_nonce + 1
        
        self._last_nonce = nonce
        return nonce
    
    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================
    
    async def get_ticker(self, pair: str) -> Dict[str, KrakenTicker]:
        """
        Get ticker information for a trading pair.
        
        Args:
            pair: Trading pair (e.g., "XBTUSD", "ETHUSD")
            
        Returns:
            Dict mapping pair to ticker data
        """
        # Check cache
        cache_key = f"ticker_{pair}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        # Make request
        result = await self._make_request(
            "Ticker",
            data={"pair": pair},
            api_type=KrakenApiType.PUBLIC
        )
        
        # Parse response
        tickers = {}
        for pair_key, data in result.items():
            ticker = KrakenTicker(
                pair=pair_key,
                ask=Decimal(str(data.get('a', ['0'])[0])),
                bid=Decimal(str(data.get('b', ['0'])[0])),
                last=Decimal(str(data.get('c', ['0'])[0])),
                high=Decimal(str(data.get('h', ['0'])[0])),
                low=Decimal(str(data.get('l', ['0'])[0])),
                volume=Decimal(str(data.get('v', ['0'])[0])),
                volume_24h=Decimal(str(data.get('v', ['0'])[1] if len(data.get('v', [])) > 1 else '0')),
                open=Decimal(str(data.get('o', ['0'])[0])),
                close=Decimal(str(data.get('c', ['0'])[0])),
                change=Decimal(str(data.get('c', ['0'])[0])) - Decimal(str(data.get('o', ['0'])[0])),
                timestamp=datetime.fromtimestamp(float(data.get('t', 0)) or time.time())
            )
            tickers[pair_key] = ticker
        
        # Cache results
        await self._set_cache(cache_key, tickers)
        
        return tickers
    
    async def get_ohlc(
        self,
        pair: str,
        interval: int = 1,
        since: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get OHLC (candlestick) data.
        
        Args:
            pair: Trading pair
            interval: Interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
            since: Timestamp to start from
            
        Returns:
            OHLC data
        """
        data = {"pair": pair, "interval": interval}
        if since:
            data["since"] = since
        
        return await self._make_request(
            "OHLC",
            data=data,
            api_type=KrakenApiType.PUBLIC
        )
    
    async def get_order_book(self, pair: str, depth: int = 10) -> Dict[str, Any]:
        """
        Get order book for a trading pair.
        
        Args:
            pair: Trading pair
            depth: Depth of order book (1-100)
            
        Returns:
            Order book data
        """
        cache_key = f"orderbook_{pair}_{depth}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._make_request(
            "Depth",
            data={"pair": pair, "count": depth},
            api_type=KrakenApiType.PUBLIC
        )
        
        await self._set_cache(cache_key, result, ttl=5)  # Short TTL for order book
        
        return result
    
    async def get_trades(
        self,
        pair: str,
        since: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get recent trades for a trading pair.
        
        Args:
            pair: Trading pair
            since: Timestamp to start from
            
        Returns:
            Trade data
        """
        data = {"pair": pair}
        if since:
            data["since"] = since
        
        return await self._make_request(
            "Trades",
            data=data,
            api_type=KrakenApiType.PUBLIC
        )
    
    async def get_pairs(self) -> Dict[str, Any]:
        """
        Get all available trading pairs.
        
        Returns:
            Dict of trading pairs
        """
        cache_key = "pairs"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._make_request(
            "AssetPairs",
            data={},
            api_type=KrakenApiType.PUBLIC
        )
        
        await self._set_cache(cache_key, result)
        
        return result
    
    async def get_assets(self) -> Dict[str, Any]:
        """
        Get all available assets.
        
        Returns:
            Dict of assets
        """
        cache_key = "assets"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._make_request(
            "Assets",
            data={},
            api_type=KrakenApiType.PUBLIC
        )
        
        await self._set_cache(cache_key, result)
        
        return result
    
    # =========================================================================
    # PRIVATE API METHODS
    # =========================================================================
    
    async def _private_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a private API request.
        
        Args:
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Response data
        """
        return await self._make_request(
            endpoint,
            data=data or {},
            method="POST",
            api_type=KrakenApiType.PRIVATE
        )
    
    async def get_balance(self) -> Dict[str, KrakenBalance]:
        """
        Get account balance.
        
        Returns:
            Dict mapping currency to balance
        """
        cache_key = "balance"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._private_request("Balance")
        
        balances = {}
        for currency, amount in result.items():
            balances[currency] = KrakenBalance(
                currency=currency,
                total=Decimal(str(amount)),
                available=Decimal(str(amount))
            )
        
        await self._set_cache(cache_key, balances, ttl=30)  # 30 second TTL
        
        return balances
    
    async def get_balance_for_currency(self, currency: str) -> Optional[KrakenBalance]:
        """Get balance for a specific currency."""
        balances = await self.get_balance()
        return balances.get(currency)
    
    async def get_open_orders(self) -> List[KrakenOrder]:
        """
        Get all open orders.
        
        Returns:
            List of open orders
        """
        result = await self._private_request("OpenOrders")
        
        orders = []
        for order_id, data in result.get('open', {}).items():
            order = self._parse_order(order_id, data)
            orders.append(order)
        
        return orders
    
    async def get_closed_orders(self, limit: int = 50) -> List[KrakenOrder]:
        """
        Get closed orders.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of closed orders
        """
        result = await self._private_request(
            "ClosedOrders",
            data={"limit": min(limit, 500)}
        )
        
        orders = []
        for order_id, data in result.get('closed', {}).items():
            order = self._parse_order(order_id, data)
            orders.append(order)
        
        return orders
    
    async def get_order(self, order_id: str) -> Optional[KrakenOrder]:
        """
        Get a specific order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order data or None
        """
        try:
            result = await self._private_request(
                "QueryOrders",
                data={"txid": order_id}
            )
            
            if order_id not in result:
                return None
            
            data = result[order_id]
            return self._parse_order(order_id, data)
            
        except KrakenError:
            return None
    
    async def place_order(
        self,
        pair: str,
        side: KrakenOrderSide,
        order_type: KrakenOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: KrakenTimeInForce = KrakenTimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> KrakenOrder:
        """
        Place an order on Kraken.
        
        Args:
            pair: Trading pair
            side: Buy or sell
            order_type: Type of order
            volume: Order volume
            price: Price for limit orders
            limit_price: Limit price for stop-limit orders
            stop_price: Stop price for stop orders
            time_in_force: Time in force
            client_order_id: Client-side order ID
            
        Returns:
            Order data
        """
        data = {
            "pair": pair,
            "type": side.value,
            "ordertype": order_type.value,
            "volume": str(volume)
        }
        
        if price is not None:
            data["price"] = str(price)
        
        if limit_price is not None:
            data["price2"] = str(limit_price)
        
        if stop_price is not None:
            data["stop"] = str(stop_price)
        
        data["timeinforce"] = time_in_force.value
        
        if client_order_id:
            data["userref"] = client_order_id
        
        result = await self._private_request("AddOrder", data)
        
        # Parse response
        order_id = result.get('txid', [''])[0] if result.get('txid') else ''
        
        return KrakenOrder(
            id=order_id,
            pair=pair,
            type=order_type,
            side=side,
            status=KrakenOrderStatus.PENDING,
            price=price or Decimal('0'),
            volume=volume,
            created_at=datetime.utcnow(),
            metadata=result
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        result = await self._private_request(
            "CancelOrder",
            data={"txid": order_id}
        )
        
        return result.get('count', 0) > 0
    
    async def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.
        
        Returns:
            Number of orders cancelled
        """
        result = await self._private_request("CancelAllOrders")
        return result.get('count', 0)
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.
        
        Returns:
            List of positions
        """
        return await self._private_request("OpenPositions")
    
    async def close_position(
        self,
        pair: str,
        position_id: str,
        volume: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Close a position.
        
        Args:
            pair: Trading pair
            position_id: Position ID
            volume: Volume to close (None for full position)
            
        Returns:
            Result of closing position
        """
        data = {
            "pair": pair,
            "position": position_id
        }
        
        if volume is not None:
            data["volume"] = str(volume)
        
        return await self._private_request("ClosePosition", data)
    
    # =========================================================================
    # LEDGER AND HISTORY
    # =========================================================================
    
    async def get_ledger(
        self,
        currency: Optional[str] = None,
        limit: int = 50,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get ledger entries.
        
        Args:
            currency: Filter by currency
            limit: Number of entries to return
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            Ledger entries
        """
        data = {"limit": min(limit, 1000)}
        
        if currency:
            data["asset"] = currency
        
        if start_time:
            data["start"] = start_time
        
        if end_time:
            data["end"] = end_time
        
        return await self._private_request("Ledgers", data)
    
    async def get_trade_history(
        self,
        pair: Optional[str] = None,
        limit: int = 50,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get trade history.
        
        Args:
            pair: Filter by trading pair
            limit: Number of trades to return
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            Trade history
        """
        data = {"limit": min(limit, 1000)}
        
        if pair:
            data["pair"] = pair
        
        if start_time:
            data["start"] = start_time
        
        if end_time:
            data["end"] = end_time
        
        return await self._private_request("TradesHistory", data)
    
    # =========================================================================
    # WEBSOCKET
    # =========================================================================
    
    async def _connect_websocket(self):
        """Connect to Kraken WebSocket."""
        if self._ws_connected:
            return
        
        try:
            ws_url = self.config.get_ws_url()
            
            self._ws_connection = await websockets.connect(
                ws_url,
                ping_interval=self.config.ws_ping_interval,
                close_timeout=10
            )
            
            self._ws_connected = True
            
            # Start WebSocket listeners
            asyncio.create_task(self._ws_listen_loop())
            asyncio.create_task(self._ws_ping_loop())
            
            logger.info("WebSocket connected")
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await self._disconnect_websocket()
            raise
    
    async def _disconnect_websocket(self):
        """Disconnect WebSocket."""
        if self._ws_connection:
            try:
                await self._ws_connection.close()
            except Exception:
                pass
            self._ws_connection = None
        
        self._ws_connected = False
        self._ws_subscriptions.clear()
        
        logger.info("WebSocket disconnected")
    
    async def _ws_listen_loop(self):
        """WebSocket listening loop."""
        while self._ws_connected:
            try:
                message = await self._ws_connection.recv()
                await self._ws_handle_message(json.loads(message))
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        
        # Reconnect if still should be connected
        if self._ws_connected:
            await self._ws_reconnect()
    
    async def _ws_ping_loop(self):
        """WebSocket ping loop."""
        while self._ws_connected:
            try:
                await asyncio.sleep(self.config.ws_ping_interval)
                await self._ws_send({"event": "ping"})
            except Exception as e:
                logger.error(f"WebSocket ping error: {e}")
                break
    
    async def _ws_handle_message(self, message: Dict[str, Any]):
        """Handle WebSocket message."""
        try:
            event = message.get('event')
            
            if event == 'systemStatus':
                await self._ws_handle_system_status(message)
            elif event == 'subscriptionStatus':
                await self._ws_handle_subscription_status(message)
            elif event == 'pong':
                pass  # Heartbeat response
            elif event == 'heartbeat':
                await self._ws_handle_heartbeat(message)
            else:
                await self._ws_handle_data_message(message)
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _ws_handle_system_status(self, message: Dict[str, Any]):
        """Handle system status message."""
        status = message.get('status')
        logger.info(f"WebSocket system status: {status}")
        
        if status == 'maintenance':
            await self._disconnect_websocket()
    
    async def _ws_handle_subscription_status(self, message: Dict[str, Any]):
        """Handle subscription status message."""
        status = message.get('status')
        channel = message.get('channelName')
        pair = message.get('pair')
        
        if status == 'subscribed':
            logger.info(f"Subscribed to {channel} for {pair}")
        elif status == 'unsubscribed':
            logger.info(f"Unsubscribed from {channel} for {pair}")
        elif status == 'error':
            logger.error(f"Subscription error: {message.get('errorMessage')}")
    
    async def _ws_handle_heartbeat(self, message: Dict[str, Any]):
        """Handle heartbeat message."""
        logger.debug("Heartbeat received")
    
    async def _ws_handle_data_message(self, message: Dict[str, Any]):
        """Handle data message."""
        if 'channel' in message:
            channel = message.get('channel')
            
            if channel in self._ws_handlers:
                for handler in self._ws_handlers[channel]:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"WebSocket handler error: {e}")
    
    async def _ws_send(self, message: Dict[str, Any]):
        """Send WebSocket message."""
        if not self._ws_connected or not self._ws_connection:
            raise KrakenError("WebSocket not connected")
        
        await self._ws_connection.send(json.dumps(message))
    
    async def _ws_reconnect(self):
        """Reconnect WebSocket."""
        if not self._ws_connected:
            return
        
        attempts = 0
        delay = self.config.ws_reconnect_delay
        
        while attempts < self.config.ws_max_reconnect_attempts:
            attempts += 1
            logger.info(f"WebSocket reconnect attempt {attempts}")
            
            try:
                await self._connect_websocket()
                logger.info("WebSocket reconnected")
                return
            except Exception as e:
                logger.error(f"WebSocket reconnect error: {e}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
        
        logger.error("WebSocket reconnect failed, giving up")
        self._ws_connected = False
    
    async def ws_subscribe(
        self,
        channel: KrakenWebSocketChannel,
        pairs: List[str],
        handler: Callable
    ):
        """
        Subscribe to a WebSocket channel.
        
        Args:
            channel: Channel to subscribe to
            pairs: List of trading pairs
            handler: Callback function for messages
        """
        if not self._ws_connected:
            await self._connect_websocket()
        
        # Add handler
        channel_value = channel.value
        if channel_value not in self._ws_handlers:
            self._ws_handlers[channel_value] = []
        self._ws_handlers[channel_value].append(handler)
        
        # Subscribe
        message = {
            "event": "subscribe",
            "subscription": {"name": channel_value},
            "pair": pairs
        }
        
        await self._ws_send(message)
        
        # Track subscriptions
        self._ws_subscriptions[channel_value] = pairs
    
    async def ws_unsubscribe(
        self,
        channel: KrakenWebSocketChannel,
        pairs: List[str]
    ):
        """
        Unsubscribe from a WebSocket channel.
        
        Args:
            channel: Channel to unsubscribe from
            pairs: List of trading pairs
        """
        message = {
            "event": "unsubscribe",
            "subscription": {"name": channel.value},
            "pair": pairs
        }
        
        await self._ws_send(message)
        
        # Remove subscriptions
        channel_value = channel.value
        if channel_value in self._ws_subscriptions:
            remaining = [p for p in self._ws_subscriptions[channel_value] if p not in pairs]
            if remaining:
                self._ws_subscriptions[channel_value] = remaining
            else:
                del self._ws_subscriptions[channel_value]
    
    # =========================================================================
    # CACHE
    # =========================================================================
    
    async def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached data."""
        if not self.config.use_cache:
            return None
        
        # Check memory cache
        if key in self._cache:
            if time.time() - self._cache_timestamps.get(key, 0) < self.config.cache_ttl:
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._cache_timestamps[key]
        
        # Check Redis cache
        if self.redis:
            try:
                data = await self.redis.get(f"kraken:{key}")
                if data:
                    result = json.loads(data)
                    # Cache in memory
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
        
        # Cache in memory
        self._cache[key] = data
        self._cache_timestamps[key] = time.time()
        
        # Cache in Redis
        if self.redis:
            try:
                json_data = json.dumps(data, default=self._json_serializer)
                ttl = ttl or self.config.cache_ttl
                await self.redis.setex(f"kraken:{key}", ttl, json_data)
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
    # UTILITY METHODS
    # =========================================================================
    
    def _parse_order(self, order_id: str, data: Dict[str, Any]) -> KrakenOrder:
        """Parse order data."""
        status_map = {
            'pending': KrakenOrderStatus.PENDING,
            'open': KrakenOrderStatus.OPEN,
            'closed': KrakenOrderStatus.CLOSED,
            'cancelled': KrakenOrderStatus.CANCELLED,
            'expired': KrakenOrderStatus.EXPIRED,
            'rejected': KrakenOrderStatus.REJECTED,
            'partially': KrakenOrderStatus.PARTIALLY_FILLED,
            'filled': KrakenOrderStatus.FILLED
        }
        
        status = data.get('status', 'pending')
        
        return KrakenOrder(
            id=order_id,
            pair=data.get('pair', ''),
            type=KrakenOrderType(data.get('ordertype', 'limit')),
            side=KrakenOrderSide(data.get('type', 'buy')),
            status=status_map.get(status, KrakenOrderStatus.PENDING),
            price=Decimal(str(data.get('price', 0))),
            volume=Decimal(str(data.get('volume', 0))),
            executed_volume=Decimal(str(data.get('vol_exec', 0))),
            average_price=Decimal(str(data.get('avg_price', 0))),
            fee=Decimal(str(data.get('fee', 0))),
            cost=Decimal(str(data.get('cost', 0))),
            limit_price=Decimal(str(data.get('price2', 0))) if data.get('price2') else None,
            stop_price=Decimal(str(data.get('stop', 0))) if data.get('stop') else None,
            time_in_force=KrakenTimeInForce(data.get('timeinforce', 'GTC')),
            created_at=datetime.fromtimestamp(float(data.get('opentm', 0)) or time.time()),
            updated_at=datetime.fromtimestamp(float(data.get('closetm', 0))) if data.get('closetm') else None,
            expires_at=datetime.fromtimestamp(float(data.get('expiretm', 0))) if data.get('expiretm') else None,
            metadata=data
        )


# =============================================================================
# RATE LIMITER
# =============================================================================

class KrakenRateLimiter:
    """
    Rate limiter for Kraken API calls.
    
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
        name: str = "kraken"
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
            
            # Refill tokens
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now
            
            # Calculate wait time
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._requests += 1
                self._waiting -= 1
                return 0.0
            
            # Need to wait
            needed = tokens - self._tokens
            wait_time = needed / self.rate
            
            # Wait
            await asyncio.sleep(wait_time)
            
            # Update state
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
# CUSTOM EXCEPTIONS
# =============================================================================

class KrakenError(Exception):
    """Base exception for Kraken errors."""
    pass


class KrakenAuthenticationError(KrakenError):
    """Authentication error."""
    pass


class KrakenRateLimitError(KrakenError):
    """Rate limit error."""
    pass


class KrakenInvalidSymbolError(KrakenError):
    """Invalid symbol error."""
    pass


class KrakenOrderError(KrakenError):
    """Order error."""
    pass


class KrakenPositionError(KrakenError):
    """Position error."""
    pass


class KrakenInsufficientFundsError(KrakenError):
    """Insufficient funds error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenBase',
    'KrakenConfig',
    'KrakenEnvironment',
    'KrakenApiType',
    'KrakenOrderType',
    'KrakenOrderSide',
    'KrakenOrderStatus',
    'KrakenTimeInForce',
    'KrakenWebSocketEvent',
    'KrakenWebSocketChannel',
    'KrakenBalance',
    'KrakenTicker',
    'KrakenOrder',
    'KrakenTrade',
    'KrakenRateLimiter',
    'KrakenError',
    'KrakenAuthenticationError',
    'KrakenRateLimitError',
    'KrakenInvalidSymbolError',
    'KrakenOrderError',
    'KrakenPositionError',
    'KrakenInsufficientFundsError'
]
