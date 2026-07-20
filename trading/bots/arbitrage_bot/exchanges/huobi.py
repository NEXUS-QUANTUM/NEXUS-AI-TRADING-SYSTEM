# trading/bots/arbitrage_bot/exchanges/huobi.py
# NEXUS AI TRADING SYSTEM - FULL VERSION
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Author: Dr X... - Majority Shareholder

"""
NEXUS Huobi Exchange Connector - Advanced Arbitrage Module
Version: 3.0.0 - FULL PRODUCTION READY
Description: Enterprise-grade Huobi Global exchange connector with advanced 
features for arbitrage detection, order execution, market data streaming,
and institutional-grade risk management.
"""

import asyncio
import hmac
import hashlib
import time
import json
import logging
import base64
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Set
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict, deque
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import aiohttp
import websockets
from websockets.exceptions import WebSocketException, ConnectionClosed, ConnectionClosedOK
import pandas as pd
import numpy as np

# NEXUS internal imports
from trading.bots.arbitrage_bot.exchanges.base_exchange import BaseExchange
from trading.bots.arbitrage_bot.exchanges.converter import HuobiConverter
from trading.bots.arbitrage_bot.core.rate_limiter import RateLimiter, RateLimitExceeded
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker
from trading.bots.arbitrage_bot.core.latency_monitor import LatencyMonitor
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler, RetryConfig
from trading.bots.arbitrage_bot.core.health_check import HealthCheck
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.models.exchange import (
    ExchangeInfo, SymbolInfo, OrderBook, Ticker, Trade, Balance,
    Order, Position, Kline, FundingRate, ExchangeStatus
)
from trading.bots.arbitrage_bot.models.order import OrderSide, OrderType, OrderStatus, TimeInForce
from trading.bots.arbitrage_bot.exceptions import (
    ExchangeError, NetworkError, AuthenticationError, RateLimitError,
    OrderError, InsufficientBalanceError, DataError, WebSocketError,
    InvalidSymbolError, OrderNotFoundError, MarketClosedError,
    ExchangeUnavailableError, ConfigurationError
)

logger = logging.getLogger("nexus.arbitrage.huobi")


@dataclass
class HuobiConfig:
    """
    Advanced Huobi configuration with dynamic parameters.
    Huobi supports spot, margin, futures (coin-m & usdt-m), and options.
    """
    # Authentication
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = False
    
    # Endpoints - Spot
    spot_base_url: str = "https://api.huobi.pro"
    spot_ws_url: str = "wss://api.huobi.pro/ws"
    
    # Endpoints - Futures (USDT-M)
    futures_base_url: str = "https://api.hbdm.com"
    futures_ws_url: str = "wss://api.hbdm.com/ws"
    
    # Endpoints - Futures (Coin-M)
    coin_m_futures_base_url: str = "https://api.hbdm.com"
    coin_m_futures_ws_url: str = "wss://api.hbdm.com/ws"
    
    # Endpoints - Options
    options_base_url: str = "https://api.hbdm.com"
    options_ws_url: str = "wss://api.hbdm.com/ws"
    
    # Connection settings
    request_timeout: float = 10.0
    connection_pool_size: int = 100
    keep_alive: bool = True
    ssl_verify: bool = True
    
    # Rate limiting
    max_requests_per_second: int = 20
    max_requests_per_minute: int = 600
    max_order_requests_per_second: int = 10
    max_websocket_connections: int = 10
    
    # Retry configuration
    max_retries: int = 5
    retry_backoff: float = 1.0
    retry_backoff_max: float = 30.0
    retry_on_status: List[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])
    
    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_half_open_attempts: int = 3
    
    # Data subscription
    subscribe_depth: bool = True
    subscribe_ticker: bool = True
    subscribe_trade: bool = True
    subscribe_kline: bool = False
    subscribe_book_ticker: bool = False
    kline_interval: str = "1m"
    depth_level: int = 20
    
    # Advanced features
    enable_order_book_snapshots: bool = True
    snapshot_interval: int = 60
    enable_latency_optimization: bool = True
    enable_compression: bool = True
    enable_batch_requests: bool = True
    enable_request_caching: bool = True
    cache_ttl: float = 0.5
    
    # Order management
    enable_oco_orders: bool = True
    enable_trailing_stops: bool = True
    enable_tp_sl_orders: bool = True
    default_time_in_force: str = "GTC"
    
    # Risk management
    max_position_size: float = 1000000.0
    max_order_size: float = 100000.0
    max_leverage: float = 100.0
    min_margin_ratio: float = 0.01
    
    # Market type
    market_type: str = "spot"  # spot, margin, futures, coin_m_futures, options
    
    # Debugging
    debug_mode: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate and configure endpoints."""
        if self.testnet:
            self.spot_base_url = "https://api.huobi.pro"
            self.spot_ws_url = "wss://api.huobi.pro/ws"
            
        if self.debug_mode:
            self.log_level = "DEBUG"
            
        # Map market type to base URL
        if self.market_type in ["spot", "margin"]:
            self.base_url = self.spot_base_url
            self.ws_url = self.spot_ws_url
        elif self.market_type == "futures":
            self.base_url = self.futures_base_url
            self.ws_url = self.futures_ws_url
        elif self.market_type == "coin_m_futures":
            self.base_url = self.coin_m_futures_base_url
            self.ws_url = self.coin_m_futures_ws_url
        elif self.market_type == "options":
            self.base_url = self.options_base_url
            self.ws_url = self.options_ws_url
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "testnet": self.testnet,
            "market_type": self.market_type,
            "base_url": self.base_url,
            "ws_url": self.ws_url,
            "request_timeout": self.request_timeout,
            "max_requests_per_second": self.max_requests_per_second,
            "max_order_requests_per_second": self.max_order_requests_per_second,
            "enable_compression": self.enable_compression,
            "enable_batch_requests": self.enable_batch_requests,
            "debug_mode": self.debug_mode
        }


class HuobiExchange(BaseExchange):
    """
    Enterprise-grade Huobi exchange connector optimized for arbitrage trading.
    
    Huobi API Features:
    - Comprehensive spot and futures trading
    - WebSocket streaming with compression
    - Advanced order types: TP/SL, trailing stop
    - Cross-margin and isolated margin
    - USDT-M and Coin-M futures
    - Options trading
    
    Features:
    - High-performance WebSocket streaming with compression
    - Intelligent rate limiting with adaptive throttling
    - Circuit breaker pattern with automatic recovery
    - Automatic retry with exponential backoff
    - Order book reconstruction and delta management
    - Latency optimization for low-latency trading
    - Multi-symbol subscription management
    - Order execution with smart routing
    - Take-profit / Stop-loss management
    - Comprehensive error handling and recovery
    - Real-time metrics and monitoring
    """
    
    def __init__(self, config: HuobiConfig):
        """
        Initialize the Huobi exchange connector.
        
        Args:
            config: Huobi configuration object
        """
        super().__init__(
            name="huobi",
            type="cex",
            testnet=config.testnet
        )
        
        self.config = config
        self.converter = HuobiConverter()
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._ws_private: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_private_task: Optional[asyncio.Task] = None
        self._ws_private_connected: bool = False
        
        # Data storage
        self._order_books: Dict[str, OrderBook] = {}
        self._order_book_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tickers: Dict[str, Ticker] = {}
        self._trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._klines: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500)))
        self._funding_rates: Dict[str, float] = {}
        self._open_interest: Dict[str, float] = {}
        self._mark_prices: Dict[str, float] = {}
        
        # Balances
        self._balances: Dict[str, Dict[str, Balance]] = {}
        self._balance_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._balance_update_time: Dict[str, float] = {}
        
        # Exchange info
        self._exchange_info: Optional[ExchangeInfo] = None
        self._symbol_info: Dict[str, SymbolInfo] = {}
        self._symbols: List[str] = []
        self._futures_symbols: List[str] = []
        self._options_symbols: List[str] = []
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            max_requests=self.config.max_requests_per_second,
            time_window=1.0,
            wait_timeout=0.5
        )
        self._order_rate_limiter = RateLimiter(
            max_requests=self.config.max_order_requests_per_second,
            time_window=1.0,
            wait_timeout=1.0
        )
        self._minute_rate_limiter = RateLimiter(
            max_requests=self.config.max_requests_per_minute,
            time_window=60.0,
            wait_timeout=2.0
        )
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_failure_threshold,
            recovery_timeout=self.config.circuit_breaker_recovery_timeout,
            half_open_attempts=self.config.circuit_breaker_half_open_attempts,
            name="huobi_api"
        )
        
        # Latency monitor
        self._latency_monitor = LatencyMonitor(
            window_size=1000,
            alert_threshold_ms=200.0,
            critical_threshold_ms=1000.0
        )
        
        # Retry handler
        retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            backoff=self.config.retry_backoff,
            backoff_max=self.config.retry_backoff_max,
            retry_on_status=self.config.retry_on_status,
            retry_on_exceptions=[NetworkError, RateLimitError],
            jitter=True
        )
        self._retry_handler = RetryHandler(config=retry_config)
        
        # Health check
        self._health_check = HealthCheck(
            name="huobi_exchange",
            check_interval=30.0,
            timeout=5.0
        )
        
        # Metrics collector
        self._metrics = MetricsCollector(
            name="huobi_exchange",
            labels={"exchange": "huobi", "market": self.config.market_type, "testnet": str(self.config.testnet)}
        )
        
        # Websocket subscriptions
        self._ws_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._ws_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._ws_private_subscriptions: Set[str] = set()
        self._ws_message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Order management
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._active_orders: Set[str] = set()
        self._order_lock: asyncio.Lock = asyncio.Lock()
        self._order_history: deque = deque(maxlen=10000)
        
        # Position management
        self._positions: Dict[str, Position] = {}
        self._position_lock: asyncio.Lock = asyncio.Lock()
        
        # TP/SL management
        self._tp_sl_orders: Dict[str, Dict[str, Any]] = {}
        
        # Cache
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_lock: asyncio.Lock = asyncio.Lock()
        
        # State management
        self._is_connected = False
        self._is_streaming = False
        self._is_authenticated = False
        self._shutdown_requested = False
        self._uptime_seconds = 0
        self._start_time = time.time()
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Initialize
        self._setup_logging()
        self._register_metrics()
        
        logger.info(f"HuobiExchange initialized (market={config.market_type}, testnet={config.testnet}, version=3.0.0)")
        
    def _setup_logging(self) -> None:
        """Configure exchange-specific logging."""
        self._log = logger.getChild("huobi")
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        self._log.setLevel(level)
        
        if self.config.debug_mode:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self._log.addHandler(console_handler)
            
    def _register_metrics(self) -> None:
        """Register metrics for collection."""
        self._metrics.register_gauge("connection_status", "Connection status (1=connected)")
        self._metrics.register_gauge("ws_connections", "Number of WebSocket connections")
        self._metrics.register_gauge("ws_private_connected", "Private WebSocket connected")
        self._metrics.register_gauge("orders_open", "Number of open orders")
        self._metrics.register_gauge("positions", "Number of open positions")
        self._metrics.register_counter("requests_total", "Total API requests")
        self._metrics.register_counter("requests_failed", "Failed API requests")
        self._metrics.register_counter("orders_placed", "Orders placed")
        self._metrics.register_counter("orders_filled", "Orders filled")
        self._metrics.register_counter("orders_cancelled", "Orders cancelled")
        self._metrics.register_counter("ws_messages_received", "WebSocket messages received")
        self._metrics.register_counter("ws_messages_processed", "WebSocket messages processed")
        self._metrics.register_histogram("latency_ms", "Request latency in milliseconds")
        self._metrics.register_histogram("order_execution_ms", "Order execution time in milliseconds")
        
    def __repr__(self) -> str:
        return f"HuobiExchange(name={self.name}, market={self.config.market_type}, connected={self._is_connected})"
        
    # ======================== CONNECTION MANAGEMENT ========================
    
    async def connect(self, retry: bool = True) -> bool:
        """
        Establish connection to Huobi API.
        
        Args:
            retry: Whether to retry on failure
            
        Returns:
            bool: True if connection successful
        """
        if self._is_connected:
            self._metrics.set_gauge("connection_status", 1)
            return True
            
        try:
            self._log.info(f"Connecting to Huobi API (market={self.config.market_type})...")
            
            timeout = aiohttp.ClientTimeout(
                total=self.config.request_timeout,
                connect=5.0,
                sock_read=10.0
            )
            
            connector = aiohttp.TCPConnector(
                limit=self.config.connection_pool_size,
                limit_per_host=20,
                force_close=False,
                enable_cleanup_closed=True,
                ttl_dns_cache=300,
                ssl=self.config.ssl_verify
            )
            
            headers = {
                "User-Agent": "NEXUS/3.0.0 (Huobi)",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers,
                raise_for_status=False
            )
            
            # Get exchange info
            await self._get_exchange_info()
            
            # Test authentication
            if self.config.api_key and self.config.api_secret:
                await self._test_auth()
                self._is_authenticated = True
                
            self._is_connected = True
            self._start_time = time.time()
            self._metrics.set_gauge("connection_status", 1)
            self._log.info(f"Connected to Huobi API successfully (market={self.config.market_type})")
            
            # Start background tasks
            await self._start_background_tasks()
            
            return True
            
        except Exception as e:
            self._log.error(f"Connection error: {e}")
            self._metrics.set_gauge("connection_status", 0)
            if retry:
                self._log.info("Retrying connection in 5 seconds...")
                await asyncio.sleep(5)
                return await self.connect(retry=False)
            raise ExchangeError(f"Huobi connection failed: {e}")
            
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        task = asyncio.create_task(self._health_check_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Start private WebSocket for order updates if authenticated
        if self._is_authenticated:
            task = asyncio.create_task(self._manage_private_websocket())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            
    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self._health_check.check_interval)
                if self._is_connected:
                    await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Health check error: {e}")
                
    async def _perform_health_check(self) -> None:
        """Perform a health check."""
        try:
            ping_start = time.time()
            await self._get("/v1/common/timestamp")
            latency = (time.time() - ping_start) * 1000
            
            self._latency_monitor.record_latency(latency)
            self._metrics.record_histogram("latency_ms", latency)
            
            self._health_check.update_status(
                healthy=True,
                metrics={
                    "latency_ms": latency,
                    "ws_connections": len(self._ws_connections),
                    "ws_private": 1 if self._ws_private_connected else 0,
                    "orders_open": len(self._active_orders)
                }
            )
        except Exception as e:
            self._log.warning(f"Health check failed: {e}")
            self._health_check.update_status(healthy=False, error=str(e))
            
    async def _metrics_update_loop(self) -> None:
        """Periodic metrics update loop."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(10)
                self._metrics.set_gauge("ws_connections", len(self._ws_connections))
                self._metrics.set_gauge("ws_private_connected", 1 if self._ws_private_connected else 0)
                self._metrics.set_gauge("orders_open", len(self._active_orders))
                async with self._position_lock:
                    self._metrics.set_gauge("positions", len(self._positions))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Metrics update error: {e}")
                
    async def disconnect(self, graceful: bool = True) -> None:
        """Cleanly disconnect from Huobi API."""
        self._log.info("Disconnecting from Huobi...")
        self._shutdown_requested = True
        
        # Close WebSocket connections
        for stream_name, ws in list(self._ws_connections.items()):
            try:
                await ws.close()
            except Exception as e:
                self._log.warning(f"Error closing WebSocket for {stream_name}: {e}")
        self._ws_connections.clear()
        
        if self._ws_private:
            try:
                await self._ws_private.close()
            except Exception as e:
                self._log.warning(f"Error closing private WebSocket: {e}")
            self._ws_private = None
            self._ws_private_connected = False
            
        # Cancel tasks
        for task in list(self._ws_tasks.values()) + list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None
            
        self._is_connected = False
        self._is_streaming = False
        self._is_authenticated = False
        self._metrics.set_gauge("connection_status", 0)
        self._log.info("Disconnected from Huobi")
        
    # ======================== AUTHENTICATION ========================
    
    async def _test_auth(self) -> None:
        """Test authentication credentials."""
        try:
            await self._get("/v1/account/accounts", signed=True)
            self._log.info("Authentication successful")
        except AuthenticationError as e:
            self._log.error(f"Authentication failed: {e}")
            raise
            
    def _generate_signature(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
        timestamp: str
    ) -> Tuple[str, Dict[str, str]]:
        """
        Generate Huobi API signature.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            timestamp: Timestamp in ISO format
            
        Returns:
            Tuple of (signature, headers)
        """
        # Build query string
        if method.upper() == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        else:
            query_string = json.dumps(params) if params else ""
            
        # Create signature string
        sign_str = f"{method.upper()}\napi.huobi.pro\n{endpoint}\n{query_string}\n{timestamp}"
        
        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                self.config.api_secret.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        headers = {
            "AccessKeyId": self.config.api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": timestamp,
            "Signature": signature
        }
        
        return signature, headers
        
    # ======================== HTTP REQUESTS ========================
    
    @asynccontextmanager
    async def _request_context(self, endpoint: str, signed: bool = False):
        """Context manager for HTTP requests."""
        if self._circuit_breaker.is_open():
            raise ExchangeError("Circuit breaker is open")
            
        await self._rate_limiter.wait_for_token()
        await self._minute_rate_limiter.wait_for_token()
        
        if signed:
            await self._order_rate_limiter.wait_for_token()
            
        start_time = time.time()
        
        try:
            yield
            self._circuit_breaker.record_success()
        except Exception:
            self._circuit_breaker.record_failure()
            raise
        finally:
            latency = (time.time() - start_time) * 1000
            self._latency_monitor.record_latency(latency)
            self._metrics.record_histogram("latency_ms", latency)
            
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Huobi API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: URL parameters
            data: Request body
            signed: Whether to sign the request
            retry: Whether to retry on failure
            
        Returns:
            Response data
        """
        if not self._session:
            raise ExchangeError("Not connected to Huobi")
            
        async with self._request_context(endpoint, signed):
            url = f"{self.config.base_url}{endpoint}"
            headers = {}
            
            if signed:
                if not self.config.api_key or not self.config.api_secret:
                    raise AuthenticationError("API key/secret not configured")
                    
                timestamp = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                signature, signature_headers = self._generate_signature(
                    method, endpoint, params or data or {}, timestamp
                )
                headers.update(signature_headers)
                
            self._metrics.increment_counter("requests_total")
            
            # Execute request with retry
            async def _make_request() -> Dict[str, Any]:
                async with self._session.request(
                    method=method,
                    url=url,
                    params=params if method.upper() == "GET" else None,
                    json=data if method.upper() in ["POST", "PUT"] else None,
                    headers=headers,
                    ssl=self.config.ssl_verify
                ) as response:
                    try:
                        result = await response.json()
                    except aiohttp.ContentTypeError:
                        text = await response.text()
                        self._log.error(f"Unexpected response: {text[:500]}")
                        raise ExchangeError(f"Unexpected response from Huobi: {text[:200]}")
                        
                    if response.status >= 400:
                        self._metrics.increment_counter("requests_failed")
                        error_msg = result.get("message", result.get("err-msg", f"HTTP {response.status}"))
                        error_code = result.get("code", response.status)
                        
                        self._log.error(f"API error {error_code}: {error_msg}")
                        
                        if response.status == 429:
                            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                        elif response.status == 401:
                            raise AuthenticationError(f"Authentication failed: {error_msg}")
                        elif response.status == 404:
                            raise OrderNotFoundError(f"Order not found: {error_msg}")
                        elif error_code == 100002:
                            raise InsufficientBalanceError(f"Insufficient balance: {error_msg}")
                        elif response.status in (500, 502, 503, 504):
                            raise ExchangeError(f"Server error: {error_msg}")
                        else:
                            raise ExchangeError(f"API error {error_code}: {error_msg}")
                            
                    return result
                    
            if retry:
                return await self._retry_handler.execute(_make_request)
            return await _make_request()
            
    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Perform GET request."""
        return await self._request("GET", endpoint, params=params, signed=signed)
        
    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Perform POST request."""
        return await self._request("POST", endpoint, data=data, signed=signed)
        
    async def _delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Perform DELETE request."""
        return await self._request("DELETE", endpoint, params=params, signed=signed)
        
    # ======================== EXCHANGE INFO ========================
    
    async def _get_exchange_info(self) -> ExchangeInfo:
        """Fetch exchange information."""
        if self._exchange_info:
            return self._exchange_info
            
        try:
            self._log.debug("Fetching exchange info...")
            
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/v1/common/symbols"
                data = await self._get(endpoint)
                items = data.get("data", [])
            elif self.config.market_type in ["futures", "coin_m_futures"]:
                endpoint = "/api/v1/contract_contract_info"
                data = await self._get(endpoint)
                items = data.get("data", [])
            else:
                endpoint = "/v1/common/symbols"
                data = await self._get(endpoint)
                items = data.get("data", [])
                
            info = ExchangeInfo(
                timezone="UTC",
                server_time=int(time.time() * 1000),
                rate_limits=[],
                exchange_filters=[],
                symbols=[]
            )
            
            for item in items:
                symbol_info = self.converter.parse_symbol_info(item)
                if symbol_info:
                    info.symbols.append(symbol_info)
                    self._symbol_info[symbol_info.symbol] = symbol_info
                    if symbol_info.status == "online":
                        self._symbols.append(symbol_info.symbol)
                        
            self._exchange_info = info
            self._log.info(f"Loaded exchange info: {len(info.symbols)} symbols")
            return info
            
        except Exception as e:
            self._log.error(f"Failed to fetch exchange info: {e}")
            raise
            
    async def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get information for a specific symbol."""
        if not self._exchange_info:
            await self._get_exchange_info()
        symbol = symbol.upper()
        return self._symbol_info.get(symbol)
        
    async def get_all_symbols(self) -> List[str]:
        """Get list of all trading symbols."""
        if not self._symbols:
            await self._get_exchange_info()
        return self._symbols.copy()
        
    # ======================== MARKET DATA ========================
    
    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> OrderBook:
        """
        Get order book snapshot.
        
        Args:
            symbol: Trading pair symbol
            limit: Depth limit (max 100)
            use_cache: Whether to use cached data
            
        Returns:
            OrderBook object
        """
        symbol = symbol.upper()
        
        if use_cache and symbol in self._order_books:
            book = self._order_books[symbol]
            if (time.time() - book.timestamp) < 0.5:
                return book
                
        try:
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/market/depth"
                params = {"symbol": symbol, "type": "step0"}
            else:
                endpoint = "/market/depth"
                params = {"symbol": symbol, "type": "step0"}
                
            data = await self._get(endpoint, params=params)
            
            book = self.converter.parse_order_book(data, symbol)
            
            async with self._order_book_locks[symbol]:
                self._order_books[symbol] = book
                
            return book
            
        except Exception as e:
            self._log.error(f"Failed to get order book for {symbol}: {e}")
            if use_cache and symbol in self._order_books:
                return self._order_books[symbol]
            raise DataError(f"Order book fetch failed: {e}")
            
    async def get_ticker(self, symbol: str, use_cache: bool = True) -> Ticker:
        """
        Get 24-hour ticker for symbol.
        
        Args:
            symbol: Trading pair symbol
            use_cache: Whether to use cached data
            
        Returns:
            Ticker object
        """
        symbol = symbol.upper()
        
        if use_cache and symbol in self._tickers:
            ticker = self._tickers[symbol]
            if (time.time() - ticker.timestamp) < 2.0:
                return ticker
                
        try:
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/market/detail/merged"
                params = {"symbol": symbol}
            else:
                endpoint = "/market/detail/merged"
                params = {"symbol": symbol}
                
            data = await self._get(endpoint, params=params)
            
            ticker = self.converter.parse_ticker(data)
            if ticker:
                self._tickers[ticker.symbol] = ticker
            return ticker
            
        except Exception as e:
            self._log.error(f"Failed to get ticker for {symbol}: {e}")
            if use_cache and symbol in self._tickers:
                return self._tickers[symbol]
            raise DataError(f"Ticker fetch failed: {e}")
            
    async def get_tickers(self) -> Dict[str, Ticker]:
        """
        Get 24-hour tickers for all symbols.
        
        Returns:
            Dict of symbol -> Ticker
        """
        try:
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/market/tickers"
            else:
                endpoint = "/market/tickers"
                
            data = await self._get(endpoint)
            
            tickers = {}
            for item in data.get("data", []):
                ticker = self.converter.parse_ticker(item)
                if ticker:
                    tickers[ticker.symbol] = ticker
                    self._tickers[ticker.symbol] = ticker
                    
            return tickers
            
        except Exception as e:
            self._log.error(f"Failed to get tickers: {e}")
            raise DataError(f"Tickers fetch failed: {e}")
            
    async def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> List[Trade]:
        """
        Get recent trades for symbol.
        
        Args:
            symbol: Trading pair symbol
            limit: Number of trades (max 1000)
            use_cache: Whether to use cached data
            
        Returns:
            List of Trade objects
        """
        symbol = symbol.upper()
        
        if use_cache and symbol in self._trades:
            trades = list(self._trades[symbol])
            if len(trades) >= limit:
                return trades[:limit]
                
        try:
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/market/history/trade"
                params = {"symbol": symbol, "size": min(limit, 1000)}
            else:
                endpoint = "/market/history/trade"
                params = {"symbol": symbol, "size": min(limit, 1000)}
                
            data = await self._get(endpoint, params=params)
            
            trades = []
            for item in data.get("data", []):
                for trade_data in item.get("data", []):
                    trade = self.converter.parse_trade(trade_data, symbol)
                    if trade:
                        trades.append(trade)
                        
            self._trades[symbol] = deque(trades, maxlen=1000)
            return trades
            
        except Exception as e:
            self._log.error(f"Failed to get trades for {symbol}: {e}")
            if use_cache and symbol in self._trades:
                return list(self._trades[symbol])[:limit]
            raise DataError(f"Trades fetch failed: {e}")
            
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get Kline/Candlestick data.
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            limit: Number of candles (max 1000)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data
        """
        symbol = symbol.upper()
        
        try:
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "margin"]:
                endpoint = "/market/history/kline"
            else:
                endpoint = "/market/history/kline"
                
            data = await self._get(
                endpoint,
                params={
                    "symbol": symbol,
                    "period": interval,
                    "size": min(limit, 1000)
                }
            )
            
            return self.converter.parse_klines(data)
            
        except Exception as e:
            self._log.error(f"Failed to get klines for {symbol}: {e}")
            raise DataError(f"Kline fetch failed: {e}")
            
    # ======================== WEBSOCKET STREAMING ========================
    
    async def subscribe_order_book(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time order book updates."""
        await self._subscribe_stream(symbol, "depth", callback)
        
    async def subscribe_ticker(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time ticker updates."""
        await self._subscribe_stream(symbol, "ticker", callback)
        
    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time trade updates."""
        await self._subscribe_stream(symbol, "trade", callback)
        
    async def subscribe_kline(self, symbol: str, callback: Callable, interval: str = "1m") -> None:
        """Subscribe to real-time kline updates."""
        await self._subscribe_stream(symbol, "kline", callback, {"interval": interval})
        
    async def _subscribe_stream(
        self,
        symbol: str,
        stream_type: str,
        callback: Callable,
        params: Optional[Dict] = None
    ) -> None:
        """
        Generic WebSocket subscription handler.
        
        Args:
            symbol: Trading pair symbol
            stream_type: Type of stream
            callback: Async function to handle updates
            params: Additional parameters
        """
        symbol = symbol.upper()
        symbol_lower = symbol.lower()
        
        # Build channel based on stream type
        if stream_type == "depth":
            channel = f"market.{symbol_lower}.depth.step0"
        elif stream_type == "ticker":
            channel = f"market.{symbol_lower}.detail"
        elif stream_type == "trade":
            channel = f"market.{symbol_lower}.trade.detail"
        elif stream_type == "kline":
            interval = params.get("interval", "1m") if params else "1m"
            channel = f"market.{symbol_lower}.kline.{interval}"
        else:
            raise ValueError(f"Unknown stream type: {stream_type}")
            
        stream_name = channel
        self._ws_subscriptions[stream_type].add(symbol)
        self._ws_callbacks[stream_name].append(callback)
        
        if stream_name not in self._ws_connections:
            task = asyncio.create_task(self._manage_websocket(stream_name))
            self._ws_tasks[stream_name] = task
            
        self._is_streaming = True
        self._log.debug(f"Subscribed to {stream_name}")
        
    async def _manage_websocket(self, stream_name: str) -> None:
        """
        Manage WebSocket connection with automatic reconnection.
        
        Args:
            stream_name: Stream identifier
        """
        reconnect_delay = 1.0
        
        while not self._shutdown_requested:
            try:
                ws_url = self.config.ws_url
                
                ws = await websockets.connect(
                    uri=ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2 ** 26,
                    compression="deflate" if self.config.enable_compression else None
                )
                
                self._ws_connections[stream_name] = ws
                self._metrics.set_gauge("ws_connections", len(self._ws_connections))
                self._log.info(f"WebSocket connected: {stream_name}")
                
                # Send subscription request
                sub_msg = {
                    "sub": stream_name,
                    "id": str(int(time.time() * 1000))
                }
                await ws.send(json.dumps(sub_msg))
                
                reconnect_delay = 1.0
                await self._handle_websocket_messages(ws, stream_name)
                
            except ConnectionClosedOK:
                self._log.info(f"WebSocket closed normally: {stream_name}")
                break
            except Exception as e:
                self._log.warning(f"WebSocket error: {e}")
                
            if stream_name in self._ws_connections:
                del self._ws_connections[stream_name]
            self._metrics.set_gauge("ws_connections", len(self._ws_connections))
            
            if self._shutdown_requested:
                break
                
            if stream_name in self._ws_subscriptions:
                self._log.info(f"Reconnecting in {reconnect_delay:.1f}s: {stream_name}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60.0)
                
    async def _handle_websocket_messages(
        self,
        ws: websockets.WebSocketClientProtocol,
        stream_name: str
    ) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in ws:
                self._metrics.increment_counter("ws_messages_received")
                
                try:
                    # Huobi sends compressed messages
                    if isinstance(message, bytes):
                        import zlib
                        message = zlib.decompress(message)
                        
                    data = json.loads(message)
                    await self._process_websocket_message(data, stream_name)
                    self._metrics.increment_counter("ws_messages_processed")
                except json.JSONDecodeError as e:
                    self._log.error(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    self._log.error(f"Error processing WebSocket message: {e}")
                    
        except ConnectionClosed:
            raise
        except Exception as e:
            self._log.error(f"WebSocket message handling error: {e}")
            raise
            
    async def _process_websocket_message(self, data: Dict[str, Any], stream_name: str) -> None:
        """Process a WebSocket message."""
        # Check for subscription confirmation
        if data.get("id"):
            return
            
        # Handle data messages
        channel = data.get("ch", "")
        result = data.get("tick", {})
        
        if "depth" in channel:
            book = self.converter.parse_ws_order_book(result)
            if book:
                async with self._order_book_locks[book.symbol]:
                    self._order_books[book.symbol] = book
                await self._dispatch_callbacks(stream_name, book)
                
        elif "detail" in channel:
            ticker = self.converter.parse_ws_ticker(result)
            if ticker:
                self._tickers[ticker.symbol] = ticker
                await self._dispatch_callbacks(stream_name, ticker)
                
        elif "trade" in channel:
            for item in result.get("data", []):
                trade = self.converter.parse_ws_trade(item)
                if trade:
                    self._trades[trade.symbol].append(trade)
                    await self._dispatch_callbacks(stream_name, trade)
                    
        elif "kline" in channel:
            kline = self.converter.parse_ws_kline(result)
            if kline:
                await self._dispatch_callbacks(stream_name, kline)
                
    async def _dispatch_callbacks(self, stream_name: str, *args, **kwargs) -> None:
        """Dispatch callbacks for a stream."""
        for callback in self._ws_callbacks.get(stream_name, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                self._log.error(f"Callback error for {stream_name}: {e}")
                
    async def _manage_private_websocket(self) -> None:
        """Manage private WebSocket for order updates."""
        reconnect_delay = 1.0
        
        while not self._shutdown_requested and self._is_authenticated:
            try:
                ws_url = self.config.ws_url
                
                ws = await websockets.connect(
                    uri=ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2 ** 26
                )
                
                self._ws_private = ws
                self._ws_private_connected = True
                self._metrics.set_gauge("ws_private_connected", 1)
                self._log.info("Private WebSocket connected")
                
                # Authenticate
                timestamp = str(int(time.time() * 1000))
                signature = base64.b64encode(
                    hmac.new(
                        self.config.api_secret.encode('utf-8'),
                        f"GET\napi.huobi.pro\n/ws\n\n{timestamp}".encode('utf-8'),
                        hashlib.sha256
                    ).digest()
                ).decode('utf-8')
                
                auth_msg = {
                    "op": "auth",
                    "AccessKeyId": self.config.api_key,
                    "SignatureMethod": "HmacSHA256",
                    "SignatureVersion": "2",
                    "Timestamp": timestamp,
                    "Signature": signature
                }
                await ws.send(json.dumps(auth_msg))
                
                reconnect_delay = 1.0
                await self._handle_private_messages(ws)
                
            except ConnectionClosedOK:
                self._log.info("Private WebSocket closed normally")
                break
            except Exception as e:
                self._log.warning(f"Private WebSocket error: {e}")
                
            self._ws_private = None
            self._ws_private_connected = False
            self._metrics.set_gauge("ws_private_connected", 0)
            
            if self._shutdown_requested:
                break
                
            self._log.info(f"Reconnecting private WebSocket in {reconnect_delay:.1f}s")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60.0)
            
    async def _handle_private_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Handle private WebSocket messages."""
        try:
            async for message in ws:
                try:
                    if isinstance(message, bytes):
                        import zlib
                        message = zlib.decompress(message)
                    data = json.loads(message)
                    await self._process_private_message(data)
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    self._log.error(f"Private message error: {e}")
        except ConnectionClosed:
            raise
        except Exception as e:
            self._log.error(f"Private WebSocket error: {e}")
            raise
            
    async def _process_private_message(self, data: Dict[str, Any]) -> None:
        """Process private WebSocket message."""
        if data.get("op") == "auth" and data.get("status") == "ok":
            self._log.info("Private WebSocket authenticated")
            return
            
        # Handle order updates
        if "orders" in data.get("op", ""):
            order_data = data.get("data", {})
            order_id = order_data.get("order-id")
            status = order_data.get("status")
            
            if order_id:
                async with self._order_lock:
                    self._orders[order_id] = order_data
                    if status in ["canceled", "filled"]:
                        self._active_orders.discard(order_id)
                    elif status in ["submitted", "partial-filled"]:
                        self._active_orders.add(order_id)
                        
                # Update metrics
                if status == "filled":
                    self._metrics.increment_counter("orders_filled")
                    
    # ======================== ORDER MANAGEMENT ========================
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        leverage: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Place an order on Huobi.
        
        Args:
            symbol: Trading pair symbol
            side: BUY or SELL
            order_type: limit, market, stop-limit
            amount: Order amount
            price: Limit price
            stop_price: Stop price
            time_in_force: GTC, IOC, FOK
            reduce_only: Reduce-only position
            post_only: Post-only order
            client_order_id: Client order ID
            take_profit: Take profit price
            stop_loss: Stop loss price
            leverage: Leverage for futures
            
        Returns:
            Order confirmation
        """
        self._metrics.increment_counter("orders_placed")
        
        symbol = symbol.upper()
        side = side.lower()
        order_type = order_type.lower()
        time_in_force = time_in_force.upper()
        
        # Validate symbol
        symbol_info = await self.get_symbol_info(symbol)
        if not symbol_info:
            raise InvalidSymbolError(f"Symbol not found: {symbol}")
            
        # Validate amount
        if amount <= 0:
            raise OrderError("Amount must be positive")
            
        # Build order parameters
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": str(amount)
        }
        
        if order_type in ["limit", "stop-limit"]:
            if price is None:
                raise OrderError("Price required for limit orders")
            params["price"] = str(price)
            
        if order_type in ["stop", "stop-limit"]:
            if stop_price is None:
                raise OrderError("Stop price required for stop orders")
            params["stop-price"] = str(stop_price)
            
        if client_order_id:
            params["client-order-id"] = client_order_id
            
        if post_only:
            params["post-only"] = True
            
        if reduce_only:
            params["reduce-only"] = True
            
        if take_profit:
            params["take-profit"] = str(take_profit)
            
        if stop_loss:
            params["stop-loss"] = str(stop_loss)
            
        if leverage:
            params["leverage"] = str(leverage)
            
        # Determine endpoint based on market type
        if self.config.market_type in ["spot", "margin"]:
            endpoint = "/v1/order/orders/place"
        elif self.config.market_type == "futures":
            endpoint = "/api/v1/contract_order"
        else:
            endpoint = "/v1/order/orders/place"
            
        # Place order
        try:
            start_time = time.time()
            response = await self._post(endpoint, data=params, signed=True)
            
            execution_time = (time.time() - start_time) * 1000
            self._metrics.record_histogram("order_execution_ms", execution_time)
            
            order_id = response.get("data", {}).get("order-id", response.get("order-id"))
            if order_id:
                async with self._order_lock:
                    self._orders[order_id] = response
                    self._active_orders.add(order_id)
                    
            self._log.info(f"Order placed: {symbol} {side} {order_type} {amount} @ {price or 'market'}")
            return response
            
        except InsufficientBalanceError as e:
            self._log.error(f"Insufficient balance for {symbol}: {e}")
            raise
        except Exception as e:
            self._log.error(f"Order placement failed: {e}")
            self._metrics.increment_counter("orders_failed")
            raise
            
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            
        Returns:
            Cancellation confirmation
        """
        self._metrics.increment_counter("orders_cancelled")
        
        # Determine endpoint based on market type
        if self.config.market_type in ["spot", "margin"]:
            endpoint = f"/v1/order/orders/{order_id}/submitcancel"
        elif self.config.market_type == "futures":
            endpoint = f"/api/v1/contract_cancel"
        else:
            endpoint = f"/v1/order/orders/{order_id}/submitcancel"
            
        try:
            params = {"order-id": order_id}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._post(endpoint, data=params, signed=True)
            
            async with self._order_lock:
                self._orders.pop(order_id, None)
                self._active_orders.discard(order_id)
                
            self._log.info(f"Order cancelled: {order_id}")
            return response
            
        except Exception as e:
            self._log.error(f"Order cancellation failed: {e}")
            raise
            
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Cancel all open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of cancellation confirmations
        """
        # Determine endpoint based on market type
        if self.config.market_type in ["spot", "margin"]:
            endpoint = "/v1/order/orders/batchcancel"
        elif self.config.market_type == "futures":
            endpoint = "/api/v1/contract_cancel_all"
        else:
            endpoint = "/v1/order/orders/batchcancel"
            
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._post(endpoint, data=params, signed=True)
            
            async with self._order_lock:
                if symbol:
                    for order_id in list(self._orders.keys()):
                        if self._orders[order_id].get("symbol") == symbol.upper():
                            self._orders.pop(order_id, None)
                            self._active_orders.discard(order_id)
                else:
                    self._active_orders.clear()
                    self._orders.clear()
                    
            self._log.info(f"Cancelled all orders for {symbol or 'all symbols'}")
            return response
            
        except Exception as e:
            self._log.error(f"Failed to cancel orders: {e}")
            raise
            
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Get order status.
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            
        Returns:
            Order information
        """
        # Determine endpoint based on market type
        if self.config.market_type in ["spot", "margin"]:
            endpoint = f"/v1/order/orders/{order_id}"
        elif self.config.market_type == "futures":
            endpoint = f"/api/v1/contract_order_info"
        else:
            endpoint = f"/v1/order/orders/{order_id}"
            
        try:
            params = {"order-id": order_id}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._get(endpoint, params=params, signed=True)
            
            async with self._order_lock:
                self._orders[order_id] = response
                
            return response
            
        except Exception as e:
            self._log.error(f"Failed to get order {order_id}: {e}")
            raise
            
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open orders
        """
        # Determine endpoint based on market type
        if self.config.market_type in ["spot", "margin"]:
            endpoint = "/v1/order/orders"
        elif self.config.market_type == "futures":
            endpoint = "/api/v1/contract_open_orders"
        else:
            endpoint = "/v1/order/orders"
            
        try:
            params = {"state": "submitted,partial-filled"}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._get(endpoint, params=params, signed=True)
            
            orders = response.get("data", [])
            async with self._order_lock:
                for order in orders:
                    order_id = order.get("id")
                    if order_id:
                        self._orders[order_id] = order
                        self._active_orders.add(order_id)
                        
            return orders
            
        except Exception as e:
            self._log.error(f"Failed to get open orders: {e}")
            raise
            
    # ======================== POSITION MANAGEMENT ========================
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get positions (futures only).
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of positions
        """
        if self.config.market_type not in ["futures", "coin_m_futures"]:
            return []
            
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._get("/api/v1/contract_position_info", params=params, signed=True)
            
            positions = []
            for item in response.get("data", []):
                size = float(item.get("volume", 0))
                if size != 0:
                    position = Position(
                        symbol=item.get("symbol", ""),
                        side="LONG" if float(item.get("direction", "buy")) > 0 else "SHORT",
                        size=abs(size),
                        entry_price=float(item.get("cost_open", 0)),
                        mark_price=float(item.get("mark_price", 0)),
                        liquidation_price=float(item.get("liquidation_price", 0)),
                        unrealized_pnl=float(item.get("profit", 0)),
                        leverage=int(item.get("leverage", 1))
                    )
                    positions.append(position)
                    
            async with self._position_lock:
                self._positions = {p.symbol: p for p in positions}
                
            return positions
            
        except Exception as e:
            self._log.error(f"Failed to get positions: {e}")
            if self._positions and not symbol:
                return list(self._positions.values())
            raise
            
    # ======================== ACCOUNT MANAGEMENT ========================
    
    async def get_balances(self, asset: Optional[str] = None, force: bool = False) -> Dict[str, Balance]:
        """
        Get account balances.
        
        Args:
            asset: Optional asset filter
            force: Force refresh
            
        Returns:
            Dict of asset -> Balance
        """
        if not force and self._balances:
            if self._balance_update_time and (time.time() - self._balance_update_time.get("all", 0)) < 5.0:
                if asset:
                    return self._balances.get(asset, {})
                return self._balances.copy()
                
        try:
            # Get account IDs
            accounts_data = await self._get("/v1/account/accounts", signed=True)
            accounts = accounts_data.get("data", [])
            
            balances = {}
            for account in accounts:
                if account.get("type") in ["spot", "margin"]:
                    account_id = account.get("id")
                    if account_id:
                        balance_data = await self._get(
                            f"/v1/account/accounts/{account_id}/balance",
                            signed=True
                        )
                        
                        for item in balance_data.get("data", {}).get("list", []):
                            asset_name = item.get("currency", "")
                            balance = Balance(
                                asset=asset_name,
                                free=float(item.get("balance", 0)),
                                locked=float(item.get("frozen", 0))
                            )
                            if asset_name not in balances or balance.free > balances[asset_name].free:
                                balances[asset_name] = balance
                                
            async with self._balance_locks["all"]:
                self._balances = balances
                self._balance_update_time["all"] = time.time()
                
            if asset:
                return balances.get(asset.upper(), {})
            return balances
            
        except Exception as e:
            self._log.error(f"Failed to get balances: {e}")
            if self._balances:
                return self._balances.copy()
            raise
            
    async def get_balance(self, asset: str, force: bool = False) -> Optional[Balance]:
        """Get balance for a specific asset."""
        balances = await self.get_balances(force=force)
        return balances.get(asset.upper())
        
    # ======================== UTILITY METHODS ========================
    
    def get_symbol_from_pair(self, base: str, quote: str) -> str:
        """Get Huobi symbol from base/quote pair."""
        return f"{base.lower()}{quote.lower()}"
        
    def get_pair_from_symbol(self, symbol: str) -> Tuple[str, str]:
        """Get base/quote from Huobi symbol."""
        symbol = symbol.lower()
        # Huobi symbols are like btcusdt, ethusdt
        for quote in ["usdt", "btc", "eth", "bnb", "busd", "usdc", "hbtc", "ht"]:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                if base:
                    return base.upper(), quote.upper()
        raise ValueError(f"Could not parse symbol: {symbol}")
        
    # ======================== CLEANUP ========================
    
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        
    def __del__(self):
        if self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.disconnect())
                else:
                    asyncio.run(self.disconnect())
            except Exception:
                pass
                
    # ======================== MONITORING ========================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            "requests_total": self._metrics.get_counter("requests_total"),
            "requests_failed": self._metrics.get_counter("requests_failed"),
            "orders_placed": self._metrics.get_counter("orders_placed"),
            "orders_filled": self._metrics.get_counter("orders_filled"),
            "orders_cancelled": self._metrics.get_counter("orders_cancelled"),
            "ws_messages_received": self._metrics.get_counter("ws_messages_received"),
            "ws_messages_processed": self._metrics.get_counter("ws_messages_processed"),
            "ws_connections": len(self._ws_connections),
            "ws_private_connected": self._ws_private_connected,
            "open_orders": len(self._active_orders),
            "positions": len(self._positions),
            "latency_p50": self._latency_monitor.get_percentile(50),
            "latency_p95": self._latency_monitor.get_percentile(95),
            "latency_p99": self._latency_monitor.get_percentile(99),
            "uptime_seconds": self._uptime_seconds,
            "is_connected": self._is_connected,
            "is_streaming": self._is_streaming,
            "is_authenticated": self._is_authenticated
        }
