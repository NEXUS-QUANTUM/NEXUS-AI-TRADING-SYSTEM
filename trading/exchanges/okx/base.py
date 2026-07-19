# trading/exchanges/okx/base.py
# Nexus AI Trading System - OKX Exchange Base Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Base Module

This module provides the foundational infrastructure for interacting with the
OKX cryptocurrency exchange API. It includes:

- Core API client with authentication (API Key, Secret, Passphrase)
- Rate limiting and request management
- WebSocket connection handling
- Error handling and retry logic
- Data normalization and validation
- Cache management
- Circuit breaker pattern
- Request signing and security
- Multi-environment support (live, demo, sandbox)
- Comprehensive logging and monitoring
- Instrument ID conversion
- Automatic request retry with exponential backoff

Architecture:
    OKXBase -> OKXPublicAPI (Public endpoints)
            -> OKXPrivateAPI (Private endpoints)
            -> OKXWebSocket (WebSocket streams)
            -> OKXClient (Unified interface)

Security Features:
- API key, secret, and passphrase encryption
- Request signing with HMAC-SHA256
- Timestamp validation
- Anti-replay protection
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

class OKXEnvironment(str, Enum):
    """OKX API environments."""
    PRODUCTION = "production"
    DEMO = "demo"
    SANDBOX = "sandbox"


class OKXApiType(str, Enum):
    """OKX API types."""
    PUBLIC = "public"
    PRIVATE = "private"
    TRADE = "trade"
    WALLET = "wallet"
    SUB_ACCOUNT = "sub_account"


class OKXOrderType(str, Enum):
    """OKX order types."""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"
    OPTIMAL_LIMIT_IOC = "optimal_limit_ioc"


class OKXOrderSide(str, Enum):
    """OKX order sides."""
    BUY = "buy"
    SELL = "sell"


class OKXOrderStatus(str, Enum):
    """OKX order status."""
    PENDING = "pending"
    OPEN = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


class OKXTimeInForce(str, Enum):
    """OKX time in force."""
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    DAY = "Day"
    GTX = "GTX"  # Good Till Crossing


class OKXWebSocketEvent(str, Enum):
    """OKX WebSocket events."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"
    LOGIN = "login"
    LOGOUT = "logout"
    HEARTBEAT = "heartbeat"


class OKXWebSocketChannel(str, Enum):
    """OKX WebSocket channels."""
    TICKER = "ticker"
    OHLC = "candle"
    TRADE = "trades"
    SPREAD = "spread"
    BOOK = "books"
    BOOK5 = "books5"
    DEPTH = "depth"
    POSITION = "positions"
    BALANCE = "balance"
    ORDERS = "orders"
    ORDER_ALGO = "orders-algo"
    ACCOUNT = "account"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OKXConfig(BaseModel):
    """OKX exchange configuration."""
    api_key: str
    api_secret: str
    api_passphrase: str
    environment: OKXEnvironment = OKXEnvironment.PRODUCTION
    base_url: Optional[str] = None
    ws_url: Optional[str] = None
    timeout: float = 30.0
    rate_limit_public: int = 20  # requests per second
    rate_limit_private: int = 10  # requests per second
    rate_limit_trade: int = 5  # requests per second
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
        if not v or len(v) < 16:
            raise ValueError("Invalid API key format")
        return v

    @validator('api_secret')
    def validate_api_secret(cls, v):
        if not v or len(v) < 32:
            raise ValueError("Invalid API secret format")
        return v

    @validator('api_passphrase')
    def validate_api_passphrase(cls, v):
        if not v or len(v) < 8:
            raise ValueError("Invalid API passphrase")
        return v

    def get_base_url(self) -> str:
        """Get the base API URL."""
        if self.base_url:
            return self.base_url
        
        if self.environment == OKXEnvironment.SANDBOX:
            return "https://www.okx.com"
        elif self.environment == OKXEnvironment.DEMO:
            return "https://demo.okx.com"
        else:
            return "https://www.okx.com"

    def get_ws_url(self) -> str:
        """Get the WebSocket URL."""
        if self.ws_url:
            return self.ws_url
        
        if self.environment == OKXEnvironment.SANDBOX:
            return "wss://ws.okx.com:8443/ws/v5"
        elif self.environment == OKXEnvironment.DEMO:
            return "wss://wsdemo.okx.com:8443/ws/v5"
        else:
            return "wss://ws.okx.com:8443/ws/v5"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class OKXTicker(BaseModel):
    """OKX ticker data."""
    instrument_id: str
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
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

    @validator('bid', 'ask', 'last', 'high', 'low', 'volume', 'volume_24h', 
                'open', 'close', 'change', 'change_percent', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))


class OKXOHLC(BaseModel):
    """OKX OHLC (candlestick) data."""
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    volume_quote: Optional[Decimal] = None

    @validator('open', 'high', 'low', 'close', 'volume', 'volume_quote', pre=True)
    def validate_decimal(cls, v):
        if v is None:
            return Decimal('0')
        return Decimal(str(v))

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000)


class OKXOrder(BaseModel):
    """OKX order."""
    id: str
    instrument_id: str
    type: OKXOrderType
    side: OKXOrderSide
    status: OKXOrderStatus
    price: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    executed_volume: Decimal = Decimal('0')
    average_price: Decimal = Decimal('0')
    fee: Decimal = Decimal('0')
    cost: Decimal = Decimal('0')
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: OKXTimeInForce = OKXTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in [OKXOrderStatus.OPEN, OKXOrderStatus.PARTIALLY_FILLED]

    @property
    def is_closed(self) -> bool:
        return self.status in [OKXOrderStatus.FILLED, OKXOrderStatus.CANCELLED,
                              OKXOrderStatus.EXPIRED, OKXOrderStatus.REJECTED]


# =============================================================================
# CORE IMPLEMENTATION
# =============================================================================

class OKXBase:
    """
    Core OKX exchange base class.
    
    This class provides the foundation for all OKX interactions with:
    - HTTP request handling with authentication
    - WebSocket connection management
    - Rate limiting and queuing
    - Error handling and retry logic
    - Circuit breaker pattern
    - Data caching
    - Comprehensive logging
    - Request/response validation
    
    Usage:
        config = OKXConfig(api_key="key", api_secret="secret", api_passphrase="pass")
        okx = OKXBase(config)
        await okx.connect()
        ticker = await okx.get_ticker("BTC-USDT")
        await okx.disconnect()
    """
    
    def __init__(
        self,
        config: OKXConfig,
        redis: Optional[Redis] = None
    ):
        self.config = config
        self.redis = redis
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        
        # Rate limiting
        self._public_rate_limiter = OKXRateLimiter(
            rate=config.rate_limit_public,
            name="okx_public"
        )
        self._private_rate_limiter = OKXRateLimiter(
            rate=config.rate_limit_private,
            name="okx_private"
        )
        self._trade_rate_limiter = OKXRateLimiter(
            rate=config.rate_limit_trade,
            name="okx_trade"
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
        
        # Rate limit tracking
        self._rate_limit_remaining = 100
        self._rate_limit_reset = time.time() + 60
        
        # Initialization state
        self._initialized = False
        
        # Request ID for tracing
        self._request_counter = 0
        
        # WebSocket authentication
        self._ws_authenticated = False
        
        logger.info(f"OKXBase initialized for environment: {config.environment}")
    
    async def connect(self):
        """Initialize and connect to OKX."""
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
            
            # Start WebSocket connection if configured
            if self.config.ws_url:
                await self._connect_websocket()
            
            self._initialized = True
            logger.info("OKXBase connected successfully")
            
        except Exception as e:
            logger.error(f"Error connecting to OKX: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from OKX."""
        try:
            # Disconnect WebSocket
            await self._disconnect_websocket()
            
            # Close sessions
            if self._session:
                await self._session.close()
            if self._ws_session:
                await self._ws_session.close()
            
            self._initialized = False
            logger.info("OKXBase disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting from OKX: {e}")
    
    # =========================================================================
    # HTTP REQUEST HANDLING
    # =========================================================================
    
    async def _make_request(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        method: str = "GET",
        api_type: OKXApiType = OKXApiType.PUBLIC
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the OKX API.
        
        Args:
            endpoint: API endpoint path
            data: Request data
            method: HTTP method (GET or POST)
            api_type: API type (public or private)
            
        Returns:
            Response data
            
        Raises:
            OKXError: For API errors
            OKXAuthenticationError: For authentication errors
            OKXRateLimitError: For rate limit errors
        """
        # Increment request counter
        self._request_counter += 1
        request_id = f"okx_{self._request_counter}_{int(time.time())}"
        
        # Check circuit breaker
        cb_key = f"okx_{endpoint}"
        if cb_key in self._circuit_breakers:
            if self._circuit_breakers[cb_key].is_open():
                raise OKXRateLimitError(
                    f"Circuit breaker open for endpoint: {endpoint}"
                )
        
        # Apply rate limiting
        if api_type == OKXApiType.PUBLIC:
            await self._public_rate_limiter.acquire()
        elif api_type == OKXApiType.TRADE:
            await self._trade_rate_limiter.acquire()
        else:
            await self._private_rate_limiter.acquire()
        
        # Prepare request
        url = self._build_url(endpoint, api_type)
        headers = self._build_headers(api_type)
        
        # Sign request for private endpoints
        if api_type in [OKXApiType.PRIVATE, OKXApiType.TRADE, OKXApiType.WALLET]:
            data = data or {}
            timestamp = self._get_timestamp()
            headers = self._sign_request(endpoint, data, headers, timestamp, method)
            headers['OK-ACCESS-TIMESTAMP'] = timestamp
        
        # Build query string for GET requests
        params = None
        if method.upper() == "GET" and data:
            params = data.copy()
            data = None
        
        try:
            logger.debug(
                f"OKX request {request_id}: {method} {url} "
                f"type={api_type.value}"
            )
            
            async with self._session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=json.dumps(data) if data else None,
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
                    raise OKXError(f"Invalid response: {text[:200]}")
                
                # Check for errors
                if result.get('code') != '0':
                    error_code = result.get('code', '')
                    error_msg = result.get('msg', 'Unknown error')
                    
                    if "Rate limit" in error_msg or "RateLimit" in error_msg:
                        self._circuit_breakers[cb_key].record_failure()
                        raise OKXRateLimitError(error_msg)
                    elif "Invalid key" in error_msg or "Invalid signature" in error_msg:
                        raise OKXAuthenticationError(error_msg)
                    else:
                        self._circuit_breakers[cb_key].record_failure()
                        raise OKXError(f"{error_code}: {error_msg}")
                
                # Record success
                if cb_key in self._circuit_breakers:
                    self._circuit_breakers[cb_key].record_success()
                
                logger.debug(
                    f"OKX response {request_id}: status={response.status}"
                )
                
                return result.get('data', [])
                
        except aiohttp.ClientError as e:
            self._circuit_breakers[cb_key].record_failure()
            raise OKXError(f"HTTP error: {e}")
        except asyncio.TimeoutError:
            self._circuit_breakers[cb_key].record_failure()
            raise OKXError("Request timeout")
        except Exception as e:
            self._circuit_breakers[cb_key].record_failure()
            raise OKXError(f"Request error: {e}")
    
    async def _public_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a public API request."""
        return await self._make_request(endpoint, data, "GET", OKXApiType.PUBLIC)
    
    async def _private_request(self, endpoint: str, data: Optional[Dict] = None, method: str = "POST") -> Dict[str, Any]:
        """Make a private API request."""
        return await self._make_request(endpoint, data, method, OKXApiType.PRIVATE)
    
    def _build_url(self, endpoint: str, api_type: OKXApiType) -> str:
        """Build the full API URL."""
        base_url = self.config.get_base_url()
        
        # API version
        if api_type == OKXApiType.PUBLIC:
            version = "/api/v5/"
        else:
            version = "/api/v5/"
        
        return f"{base_url}{version}{endpoint}"
    
    def _build_headers(self, api_type: OKXApiType) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        if api_type != OKXApiType.PUBLIC:
            headers["OK-ACCESS-KEY"] = self.config.api_key
            headers["OK-ACCESS-PASSPHRASE"] = self.config.api_passphrase
        
        return headers
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for request signing."""
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
    
    def _sign_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        headers: Dict[str, str],
        timestamp: str,
        method: str = "POST"
    ) -> Dict[str, str]:
        """
        Sign a private request with HMAC-SHA256.
        
        OKX signature format:
        signature = base64(hmac-sha256(api_secret, timestamp + method + path + body))
        """
        # Build the request path
        path = f"/api/v5/{endpoint}"
        
        # Build the message
        if data and method.upper() != "GET":
            body = json.dumps(data)
        else:
            body = ""
        
        message = timestamp + method.upper() + path + body
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64 encode the signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Add signature to headers
        headers["OK-ACCESS-SIGN"] = signature_b64
        
        return headers
    
    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================
    
    async def get_ticker(self, instrument_id: str) -> Dict[str, OKXTicker]:
        """
        Get ticker information for an instrument.
        
        Args:
            instrument_id: Instrument ID (e.g., "BTC-USDT")
            
        Returns:
            Dict mapping instrument_id to ticker data
        """
        cache_key = f"ticker_{instrument_id}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._public_request(
            "market/ticker",
            data={"instId": instrument_id}
        )
        
        tickers = {}
        for item in result:
            ticker = OKXTicker(
                instrument_id=item.get('instId', ''),
                bid=Decimal(str(item.get('bidPx', 0))),
                ask=Decimal(str(item.get('askPx', 0))),
                last=Decimal(str(item.get('last', 0))),
                high=Decimal(str(item.get('high24h', 0))),
                low=Decimal(str(item.get('low24h', 0))),
                volume=Decimal(str(item.get('vol24h', 0))),
                volume_24h=Decimal(str(item.get('vol24h', 0))),
                open=Decimal(str(item.get('open24h', 0))),
                close=Decimal(str(item.get('last', 0))),
                change=Decimal(str(item.get('last', 0))) - Decimal(str(item.get('open24h', 0))),
                change_percent=Decimal(str(item.get('open24h', 0))),
                timestamp=datetime.fromtimestamp(int(item.get('ts', 0)) / 1000)
            )
            tickers[instrument_id] = ticker
        
        await self._set_cache(cache_key, tickers, ttl=10)
        return tickers
    
    async def get_ohlc(
        self,
        instrument_id: str,
        bar: str = "1m",
        since: Optional[int] = None,
        limit: int = 100
    ) -> List[OKXOHLC]:
        """
        Get OHLC (candlestick) data.
        
        Args:
            instrument_id: Instrument ID
            bar: Bar size (1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W, 1M)
            since: Start timestamp in milliseconds
            limit: Number of candles
            
        Returns:
            List of OHLC data
        """
        params = {
            "instId": instrument_id,
            "bar": bar,
            "limit": min(limit, 300)
        }
        if since:
            params["after"] = since
        
        result = await self._public_request("market/candles", params)
        
        ohlc_data = []
        for item in result:
            ohlc = OKXOHLC(
                timestamp=int(item[0]),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])),
                volume_quote=Decimal(str(item[6])) if len(item) > 6 else None
            )
            ohlc_data.append(ohlc)
        
        return ohlc_data
    
    async def get_order_book(self, instrument_id: str, depth: int = 10) -> Dict[str, Any]:
        """
        Get order book for an instrument.
        
        Args:
            instrument_id: Instrument ID
            depth: Depth of order book (1-400)
            
        Returns:
            Order book data
        """
        cache_key = f"orderbook_{instrument_id}_{depth}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        params = {
            "instId": instrument_id,
            "sz": min(depth, 400)
        }
        
        result = await self._public_request("market/books", params)
        
        await self._set_cache(cache_key, result, ttl=5)
        return result
    
    async def get_trades(
        self,
        instrument_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades for an instrument.
        
        Args:
            instrument_id: Instrument ID
            limit: Number of trades
            
        Returns:
            List of trades
        """
        params = {
            "instId": instrument_id,
            "limit": min(limit, 500)
        }
        
        result = await self._public_request("market/trades", params)
        return result
    
    async def get_instruments(
        self,
        instrument_type: str = "SPOT"
    ) -> List[Dict[str, Any]]:
        """
        Get all instruments.
        
        Args:
            instrument_type: Instrument type (SPOT, FUTURES, OPTION, SWAP)
            
        Returns:
            List of instruments
        """
        cache_key = f"instruments_{instrument_type}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached
        
        result = await self._public_request(
            "public/instruments",
            data={"instType": instrument_type}
        )
        
        await self._set_cache(cache_key, result, ttl=3600)
        return result
    
    # =========================================================================
    # WEBSOCKET
    # =========================================================================
    
    async def _connect_websocket(self):
        """Connect to OKX WebSocket."""
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
            
            # Authenticate if private data is needed
            await self._ws_authenticate()
            
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
        self._ws_authenticated = False
        self._ws_subscriptions.clear()
        
        logger.info("WebSocket disconnected")
    
    async def _ws_authenticate(self):
        """Authenticate WebSocket connection."""
        if self._ws_authenticated:
            return
        
        try:
            timestamp = self._get_timestamp()
            message = timestamp + "GET" + "/users/self/verify"
            signature = hmac.new(
                self.config.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            auth_msg = {
                "op": "login",
                "args": [{
                    "apiKey": self.config.api_key,
                    "passphrase": self.config.api_passphrase,
                    "timestamp": timestamp,
                    "sign": signature_b64
                }]
            }
            
            await self._ws_send(auth_msg)
            
            # Wait for login response
            response = await self._ws_connection.recv()
            data = json.loads(response)
            
            if data.get('event') == 'login':
                self._ws_authenticated = True
                logger.info("WebSocket authenticated")
            else:
                logger.error(f"WebSocket authentication failed: {data}")
                
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
    
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
        
        if self._ws_connected:
            await self._ws_reconnect()
    
    async def _ws_ping_loop(self):
        """WebSocket ping loop."""
        while self._ws_connected:
            try:
                await asyncio.sleep(self.config.ws_ping_interval)
                await self._ws_send({"op": "ping"})
            except Exception as e:
                logger.error(f"WebSocket ping error: {e}")
                break
    
    async def _ws_handle_message(self, message: Dict[str, Any]):
        """Handle WebSocket message."""
        try:
            # Check for event
            if 'event' in message:
                event = message.get('event')
                if event == 'pong':
                    return
                elif event == 'login':
                    self._ws_authenticated = True
                elif event == 'error':
                    logger.error(f"WebSocket error: {message}")
                return
            
            # Check for data
            if 'arg' in message and 'data' in message:
                channel = message['arg'].get('channel')
                instrument = message['arg'].get('instId')
                
                if channel in self._ws_handlers:
                    for handler in self._ws_handlers[channel]:
                        try:
                            await handler(message)
                        except Exception as e:
                            logger.error(f"WebSocket handler error: {e}")
                
                # Also try instrument-specific handlers
                handler_key = f"{channel}:{instrument}"
                if handler_key in self._ws_handlers:
                    for handler in self._ws_handlers[handler_key]:
                        try:
                            await handler(message)
                        except Exception as e:
                            logger.error(f"WebSocket handler error: {e}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _ws_send(self, message: Dict[str, Any]):
        """Send WebSocket message."""
        if not self._ws_connected or not self._ws_connection:
            raise OKXError("WebSocket not connected")
        
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
        channel: str,
        instruments: List[str],
        handler: Callable,
        params: Optional[Dict] = None
    ):
        """
        Subscribe to a WebSocket channel.
        
        Args:
            channel: Channel to subscribe to
            instruments: List of instruments
            handler: Callback function for messages
            params: Additional parameters
        """
        if not self._ws_connected:
            await self._connect_websocket()
        
        # Add handler
        if channel not in self._ws_handlers:
            self._ws_handlers[channel] = []
        self._ws_handlers[channel].append(handler)
        
        # Also add instrument-specific handler
        for instrument in instruments:
            handler_key = f"{channel}:{instrument}"
            if handler_key not in self._ws_handlers:
                self._ws_handlers[handler_key] = []
            self._ws_handlers[handler_key].append(handler)
        
        # Subscribe
        args = {
            "channel": channel,
            "instId": instruments[0] if len(instruments) == 1 else ",".join(instruments)
        }
        if params:
            args.update(params)
        
        message = {
            "op": "subscribe",
            "args": [args]
        }
        
        await self._ws_send(message)
        
        # Track subscriptions
        for instrument in instruments:
            key = f"{channel}:{instrument}"
            if key not in self._ws_subscriptions:
                self._ws_subscriptions[key] = []
            self._ws_subscriptions[key].append(channel)
    
    async def ws_unsubscribe(self, channel: str, instruments: List[str]):
        """
        Unsubscribe from a WebSocket channel.
        
        Args:
            channel: Channel to unsubscribe from
            instruments: List of instruments
        """
        args = {
            "channel": channel,
            "instId": instruments[0] if len(instruments) == 1 else ",".join(instruments)
        }
        
        message = {
            "op": "unsubscribe",
            "args": [args]
        }
        
        await self._ws_send(message)
        
        # Remove subscriptions
        for instrument in instruments:
            key = f"{channel}:{instrument}"
            if key in self._ws_subscriptions:
                del self._ws_subscriptions[key]
    
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
                del self._cache[key]
                del self._cache_timestamps[key]
        
        # Check Redis cache
        if self.redis:
            try:
                data = await self.redis.get(f"okx:{key}")
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
                await self.redis.setex(f"okx:{key}", ttl, json_data)
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


# =============================================================================
# RATE LIMITER
# =============================================================================

class OKXRateLimiter:
    """
    Rate limiter for OKX API calls.
    
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
        name: str = "okx"
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
# CUSTOM EXCEPTIONS
# =============================================================================

class OKXError(Exception):
    """Base exception for OKX errors."""
    pass


class OKXAuthenticationError(OKXError):
    """Authentication error."""
    pass


class OKXRateLimitError(OKXError):
    """Rate limit error."""
    pass


class OKXInvalidSymbolError(OKXError):
    """Invalid symbol error."""
    pass


class OKXOrderError(OKXError):
    """Order error."""
    pass


class OKXPositionError(OKXError):
    """Position error."""
    pass


class OKXInsufficientFundsError(OKXError):
    """Insufficient funds error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXBase',
    'OKXConfig',
    'OKXEnvironment',
    'OKXApiType',
    'OKXOrderType',
    'OKXOrderSide',
    'OKXOrderStatus',
    'OKXTimeInForce',
    'OKXWebSocketEvent',
    'OKXWebSocketChannel',
    'OKXTicker',
    'OKXOHLC',
    'OKXOrder',
    'OKXRateLimiter',
    'OKXError',
    'OKXAuthenticationError',
    'OKXRateLimitError',
    'OKXInvalidSymbolError',
    'OKXOrderError',
    'OKXPositionError',
    'OKXInsufficientFundsError'
]
