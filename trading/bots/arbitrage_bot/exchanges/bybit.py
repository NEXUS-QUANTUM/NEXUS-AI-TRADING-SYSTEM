# trading/bots/arbitrage_bot/exchanges/bybit.py
# NEXUS AI TRADING SYSTEM - FULL VERSION
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Author: Dr X... - Majority Shareholder

"""
NEXUS Bybit Exchange Connector - Advanced Arbitrage Module
Version: 3.0.0 - FULL PRODUCTION READY
Description: Enterprise-grade Bybit exchange connector with advanced 
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
from trading.bots.arbitrage_bot.exchanges.converter import BybitConverter
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

logger = logging.getLogger("nexus.arbitrage.bybit")


@dataclass
class BybitConfig:
    """
    Advanced Bybit configuration with dynamic parameters.
    Bybit supports spot, futures (linear & inverse), and options.
    """
    # Authentication
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = False
    
    # Endpoints - Spot
    spot_base_url: str = "https://api.bybit.com"
    spot_ws_url: str = "wss://stream.bybit.com/v5/public/spot"
    
    # Endpoints - Futures (Linear)
    futures_base_url: str = "https://api.bybit.com"
    futures_ws_url: str = "wss://stream.bybit.com/v5/public/linear"
    
    # Endpoints - Futures (Inverse)
    inverse_futures_ws_url: str = "wss://stream.bybit.com/v5/public/inverse"
    
    # Endpoints - Options
    options_ws_url: str = "wss://stream.bybit.com/v5/public/option"
    
    # Private WebSocket
    private_ws_url: str = "wss://stream.bybit.com/v5/private"
    
    # Connection settings
    request_timeout: float = 10.0
    connection_pool_size: int = 100
    keep_alive: bool = True
    ssl_verify: bool = True
    
    # Rate limiting
    max_requests_per_second: int = 50
    max_requests_per_minute: int = 1200
    max_order_requests_per_second: int = 10
    max_websocket_connections: int = 20
    
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
    subscribe_derivatives_ticker: bool = False
    subscribe_funding_rate: bool = False
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
    enable_iceberg_orders: bool = True
    enable_tp_sl_orders: bool = True
    default_time_in_force: str = "GTC"
    
    # Risk management
    max_position_size: float = 1000000.0
    max_order_size: float = 100000.0
    max_leverage: float = 100.0
    min_margin_ratio: float = 0.01
    
    # Market type
    market_type: str = "spot"  # spot, futures, inverse, options
    
    # Debugging
    debug_mode: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate and configure endpoints."""
        if self.testnet:
            self.spot_base_url = "https://api-testnet.bybit.com"
            self.spot_ws_url = "wss://stream-testnet.bybit.com/v5/public/spot"
            self.futures_ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
            self.inverse_futures_ws_url = "wss://stream-testnet.bybit.com/v5/public/inverse"
            self.options_ws_url = "wss://stream-testnet.bybit.com/v5/public/option"
            self.private_ws_url = "wss://stream-testnet.bybit.com/v5/private"
            
        if self.debug_mode:
            self.log_level = "DEBUG"
            
        # Map market type to base URL
        if self.market_type == "spot":
            self.base_url = self.spot_base_url
            self.ws_url = self.spot_ws_url
        elif self.market_type in ["futures", "linear"]:
            self.base_url = self.futures_base_url
            self.ws_url = self.futures_ws_url
        elif self.market_type == "inverse":
            self.base_url = self.futures_base_url
            self.ws_url = self.inverse_futures_ws_url
        elif self.market_type == "options":
            self.base_url = self.spot_base_url  # Options use same base
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


class BybitExchange(BaseExchange):
    """
    Enterprise-grade Bybit exchange connector optimized for arbitrage trading.
    
    Bybit API Features:
    - V5 API with unified endpoints
    - Spot, Linear Futures, Inverse Futures, Options support
    - WebSocket streaming with compression
    - Advanced order types: TP/SL, trailing stop, iceberg, TWAP
    - Unified account structure
    
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
    
    def __init__(self, config: BybitConfig):
        """
        Initialize the Bybit exchange connector.
        
        Args:
            config: Bybit configuration object
        """
        super().__init__(
            name="bybit",
            type="cex",
            testnet=config.testnet
        )
        
        self.config = config
        self.converter = BybitConverter()
        
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
        self._derivatives_tickers: Dict[str, Ticker] = {}
        self._trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._klines: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500)))
        self._funding_rates: Dict[str, float] = {}
        self._open_interest: Dict[str, float] = {}
        
        # Balances
        self._balances: Dict[str, Dict[str, Balance]] = {}
        self._balance_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._balance_update_time: Dict[str, float] = {}
        
        # Exchange info
        self._exchange_info: Optional[ExchangeInfo] = None
        self._symbol_info: Dict[str, SymbolInfo] = {}
        self._symbols: List[str] = []
        self._futures_symbols: List[str] = []
        self._inverse_symbols: List[str] = []
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
            name="bybit_api"
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
            name="bybit_exchange",
            check_interval=30.0,
            timeout=5.0
        )
        
        # Metrics collector
        self._metrics = MetricsCollector(
            name="bybit_exchange",
            labels={"exchange": "bybit", "market": self.config.market_type, "testnet": str(self.config.testnet)}
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
        
        logger.info(f"BybitExchange initialized (market={config.market_type}, testnet={config.testnet}, version=3.0.0)")
        
    def _setup_logging(self) -> None:
        """Configure exchange-specific logging."""
        self._log = logger.getChild("bybit")
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
        return f"BybitExchange(name={self.name}, market={self.config.market_type}, connected={self._is_connected})"
        
    # ======================== CONNECTION MANAGEMENT ========================
    
    async def connect(self, retry: bool = True) -> bool:
        """
        Establish connection to Bybit API.
        
        Args:
            retry: Whether to retry on failure
            
        Returns:
            bool: True if connection successful
        """
        if self._is_connected:
            self._metrics.set_gauge("connection_status", 1)
            return True
            
        try:
            self._log.info(f"Connecting to Bybit API (market={self.config.market_type})...")
            
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
                "User-Agent": "NEXUS/3.0.0 (Bybit)",
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
            self._log.info(f"Connected to Bybit API successfully (market={self.config.market_type})")
            
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
            raise ExchangeError(f"Bybit connection failed: {e}")
            
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
            await self._get("/v5/market/time")
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
        """Cleanly disconnect from Bybit API."""
        self._log.info("Disconnecting from Bybit...")
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
        self._log.info("Disconnected from Bybit")
        
    # ======================== AUTHENTICATION ========================
    
    async def _test_auth(self) -> None:
        """Test authentication credentials."""
        try:
            await self._get("/v5/account/wallet-balance", signed=True)
            self._log.info("Authentication successful")
        except AuthenticationError as e:
            self._log.error(f"Authentication failed: {e}")
            raise
            
    def _generate_signature(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
        timestamp: int,
        recv_window: int = 5000
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate Bybit API signature (V5).
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            timestamp: Timestamp in milliseconds
            recv_window: Receive window
            
        Returns:
            Tuple of (signature, headers)
        """
        # Build query string
        if method.upper() == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        else:
            query_string = json.dumps(params) if params else ""
            
        # Create signature string
        sign_str = f"{str(timestamp)}{self.config.api_key}{recv_window}{query_string}"
        
        # Generate signature
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-BAPI-API-KEY": self.config.api_key,
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": str(recv_window)
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
        retry: bool = True,
        recv_window: int = 5000
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Bybit API (V5).
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: URL parameters
            data: Request body
            signed: Whether to sign the request
            retry: Whether to retry on failure
            recv_window: Receive window for signed requests
            
        Returns:
            Response data
        """
        if not self._session:
            raise ExchangeError("Not connected to Bybit")
            
        async with self._request_context(endpoint, signed):
            url = f"{self.config.base_url}{endpoint}"
            headers = {}
            
            if signed:
                if not self.config.api_key or not self.config.api_secret:
                    raise AuthenticationError("API key/secret not configured")
                    
                timestamp = int(time.time() * 1000)
                _, signature_headers = self._generate_signature(
                    method, endpoint, params or data or {}, timestamp, recv_window
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
                        raise ExchangeError(f"Unexpected response from Bybit: {text[:200]}")
                        
                    # Bybit V5 returns retCode, retMsg, result
                    ret_code = result.get("retCode", -1)
                    ret_msg = result.get("retMsg", "Unknown error")
                    
                    if ret_code != 0:
                        self._metrics.increment_counter("requests_failed")
                        self._log.error(f"API error {ret_code}: {ret_msg}")
                        
                        # Handle specific error codes
                        if ret_code == 10001:
                            raise AuthenticationError(f"Authentication failed: {ret_msg}")
                        elif ret_code == 10002:
                            raise RateLimitError(f"Rate limit exceeded: {ret_msg}")
                        elif ret_code == 10016:
                            raise InsufficientBalanceError(f"Insufficient balance: {ret_msg}")
                        elif ret_code == 10017:
                            raise OrderNotFoundError(f"Order not found: {ret_msg}")
                        elif ret_code in [10004, 10005, 10006]:
                            raise RateLimitError(f"Rate limit: {ret_msg}")
                        elif response.status in (500, 502, 503, 504):
                            raise ExchangeError(f"Server error: {ret_msg}")
                        else:
                            raise ExchangeError(f"API error {ret_code}: {ret_msg}")
                            
                    return result.get("result", {})
                    
            if retry:
                return await self._retry_handler.execute(_make_request)
            return await _make_request()
            
    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False,
        recv_window: int = 5000
    ) -> Dict:
        """Perform GET request."""
        return await self._request("GET", endpoint, params=params, signed=signed, recv_window=recv_window)
        
    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        signed: bool = False,
        recv_window: int = 5000
    ) -> Dict:
        """Perform POST request."""
        return await self._request("POST", endpoint, data=data, signed=signed, recv_window=recv_window)
        
    async def _put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        signed: bool = False,
        recv_window: int = 5000
    ) -> Dict:
        """Perform PUT request."""
        return await self._request("PUT", endpoint, data=data, signed=signed, recv_window=recv_window)
        
    async def _delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False,
        recv_window: int = 5000
    ) -> Dict:
        """Perform DELETE request."""
        return await self._request("DELETE", endpoint, params=params, signed=signed, recv_window=recv_window)
        
    # ======================== EXCHANGE INFO ========================
    
    async def _get_exchange_info(self) -> ExchangeInfo:
        """Fetch exchange information."""
        if self._exchange_info:
            return self._exchange_info
            
        try:
            self._log.debug("Fetching exchange info...")
            
            # Determine endpoint based on market type
            if self.config.market_type in ["spot", "options"]:
                endpoint = "/v5/market/instruments-info"
                if self.config.market_type == "spot":
                    params = {"category": "spot"}
                else:
                    params = {"category": "option"}
            else:
                endpoint = "/v5/market/instruments-info"
                params = {"category": "linear"}  # or "inverse"
                
            data = await self._get(endpoint, params=params)
            
            info = ExchangeInfo(
                timezone="UTC",
                server_time=int(time.time() * 1000),
                rate_limits=[],
                exchange_filters=[],
                symbols=[]
            )
            
            for item in data.get("list", []):
                symbol_info = self.converter.parse_symbol_info(item)
                if symbol_info:
                    info.symbols.append(symbol_info)
                    self._symbol_info[symbol_info.symbol] = symbol_info
                    if symbol_info.status == "Trading":
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
        
    async def get_all_symbols(self, category: Optional[str] = None) -> List[str]:
        """Get list of all trading symbols."""
        if not self._symbols:
            await self._get_exchange_info()
            
        if category:
            # Filter by category if needed
            return [s for s in self._symbols if self._symbol_info.get(s) and 
                   self._symbol_info[s].quote_asset in ["USDT", "USDC", "BTC", "ETH"]]
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
            limit: Depth limit (1, 50, 200)
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
            params = {"symbol": symbol, "limit": min(limit, 200)}
            
            # Add category for futures
            if self.config.market_type in ["futures", "linear", "inverse"]:
                params["category"] = "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
                
            data = await self._get("/v5/market/orderbook", params=params)
            
            book_data = data.get("list", [{}])[0] if isinstance(data.get("list"), list) else data.get("list", {})
            book = self.converter.parse_order_book(book_data, symbol)
            
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
            params = {"symbol": symbol}
            
            # Add category for futures
            if self.config.market_type in ["futures", "linear", "inverse"]:
                params["category"] = "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
                
            data = await self._get("/v5/market/tickers", params=params)
            
            items = data.get("list", [])
            if not items:
                raise DataError(f"No ticker data for {symbol}")
                
            ticker = self.converter.parse_ticker(items[0])
            if ticker:
                self._tickers[ticker.symbol] = ticker
            return ticker
            
        except Exception as e:
            self._log.error(f"Failed to get ticker for {symbol}: {e}")
            if use_cache and symbol in self._tickers:
                return self._tickers[symbol]
            raise DataError(f"Ticker fetch failed: {e}")
            
    async def get_tickers(self, category: Optional[str] = None) -> Dict[str, Ticker]:
        """
        Get 24-hour tickers for all symbols.
        
        Args:
            category: Optional category filter (spot, linear, inverse, option)
            
        Returns:
            Dict of symbol -> Ticker
        """
        try:
            params = {}
            if category:
                params["category"] = category
            elif self.config.market_type in ["futures", "linear"]:
                params["category"] = "linear"
            elif self.config.market_type == "inverse":
                params["category"] = "inverse"
            elif self.config.market_type == "spot":
                params["category"] = "spot"
            else:
                params["category"] = "spot"
                
            data = await self._get("/v5/market/tickers", params=params)
            
            tickers = {}
            for item in data.get("list", []):
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
            params = {"symbol": symbol, "limit": min(limit, 1000)}
            
            if self.config.market_type in ["futures", "linear", "inverse"]:
                params["category"] = "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
                
            data = await self._get("/v5/market/recent-trade", params=params)
            
            trades = []
            for item in data.get("list", []):
                trade = self.converter.parse_trade(item, symbol)
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
            interval: Kline interval (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Number of candles (max 1000)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data
        """
        symbol = symbol.upper()
        
        # Map interval to Bybit format
        interval_map = {
            "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
            "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
            "1d": "D", "1w": "W", "1M": "M"
        }
        bybit_interval = interval_map.get(interval, "1")
        
        try:
            params = {
                "symbol": symbol,
                "interval": bybit_interval,
                "limit": min(limit, 1000)
            }
            
            if self.config.market_type in ["futures", "linear", "inverse"]:
                params["category"] = "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
                
            data = await self._get("/v5/market/kline", params=params)
            
            return self.converter.parse_klines(data.get("list", []))
            
        except Exception as e:
            self._log.error(f"Failed to get klines for {symbol}: {e}")
            raise DataError(f"Kline fetch failed: {e}")
            
    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """
        Get current funding rate (futures only).
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            FundingRate object
        """
        if self.config.market_type not in ["futures", "linear", "inverse"]:
            raise ExchangeError("Funding rates only available for futures markets")
            
        try:
            params = {
                "symbol": symbol.upper(),
                "category": "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
            }
            data = await self._get("/v5/market/funding-rate-history", params=params)
            
            items = data.get("list", [])
            if not items:
                raise DataError(f"No funding rate data for {symbol}")
                
            latest = items[0]
            return FundingRate(
                symbol=symbol.upper(),
                rate=float(latest.get("fundingRate", 0)),
                next_time=int(latest.get("nextFundingTime", 0))
            )
            
        except Exception as e:
            self._log.error(f"Failed to get funding rate for {symbol}: {e}")
            raise
            
    # ======================== WEBSOCKET STREAMING ========================
    
    async def subscribe_order_book(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time order book updates."""
        await self._subscribe_stream(symbol, "orderbook", callback)
        
    async def subscribe_ticker(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time ticker updates."""
        await self._subscribe_stream(symbol, "ticker", callback)
        
    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """Subscribe to real-time trade updates."""
        await self._subscribe_stream(symbol, "trade", callback)
        
    async def subscribe_kline(self, symbol: str, callback: Callable, interval: str = "1m") -> None:
        """Subscribe to real-time kline updates."""
        await self._subscribe_stream(symbol, "kline", callback, {"interval": interval})
        
    async def subscribe_funding_rate(self, symbol: str, callback: Callable) -> None:
        """Subscribe to funding rate updates (futures only)."""
        await self._subscribe_stream(symbol, "funding_rate", callback)
        
    async def subscribe_derivatives_ticker(self, symbol: str, callback: Callable) -> None:
        """Subscribe to derivatives ticker updates."""
        await self._subscribe_stream(symbol, "derivatives_ticker", callback)
        
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
        
        # Build topic based on stream type
        if stream_type == "orderbook":
            topic = f"orderbook.50.{symbol}"
        elif stream_type == "ticker":
            topic = f"tickers.{symbol}"
        elif stream_type == "trade":
            topic = f"publicTrade.{symbol}"
        elif stream_type == "kline":
            interval = params.get("interval", "1m") if params else "1m"
            interval_map = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}
            kline_interval = interval_map.get(interval, "1")
            topic = f"kline.{kline_interval}.{symbol}"
        elif stream_type == "funding_rate":
            topic = f"funding_rate.{symbol}"
        elif stream_type == "derivatives_ticker":
            topic = f"derivatives_tickers.{symbol}"
        else:
            raise ValueError(f"Unknown stream type: {stream_type}")
            
        stream_name = topic
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
        max_delay = 60.0
        
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
                    "op": "subscribe",
                    "args": [stream_name]
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
                reconnect_delay = min(reconnect_delay * 2, max_delay)
                
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
        if data.get("op") == "subscribe":
            self._log.debug(f"Subscription confirmed: {stream_name}")
            return
            
        if data.get("op") == "unsubscribe":
            self._log.debug(f"Unsubscription confirmed: {stream_name}")
            return
            
        # Handle data messages
        if "data" not in data:
            return
            
        topic = data.get("topic", "")
        stream_data = data.get("data", {})
        
        # Parse based on topic
        if "orderbook" in topic:
            book = self.converter.parse_ws_order_book(stream_data)
            if book:
                async with self._order_book_locks[book.symbol]:
                    self._order_books[book.symbol] = book
                await self._dispatch_callbacks(stream_name, book)
                
        elif "tickers" in topic:
            ticker = self.converter.parse_ws_ticker(stream_data)
            if ticker:
                self._tickers[ticker.symbol] = ticker
                await self._dispatch_callbacks(stream_name, ticker)
                
        elif "publicTrade" in topic:
            for item in stream_data:
                trade = self.converter.parse_ws_trade(item)
                if trade:
                    self._trades[trade.symbol].append(trade)
                    await self._dispatch_callbacks(stream_name, trade)
                    
        elif "kline" in topic:
            kline = self.converter.parse_ws_kline(stream_data)
            if kline:
                await self._dispatch_callbacks(stream_name, kline)
                
        elif "funding_rate" in topic:
            rate = float(stream_data.get("fundingRate", 0))
            symbol = stream_data.get("symbol", "")
            if symbol:
                self._funding_rates[symbol] = rate
                await self._dispatch_callbacks(stream_name, rate)
                
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
                ws_url = self.config.private_ws_url
                
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
                timestamp = int(time.time() * 1000)
                recv_window = 5000
                signature, _ = self._generate_signature(
                    "GET", "/v5/private", {}, timestamp, recv_window
                )
                
                auth_msg = {
                    "op": "auth",
                    "args": [self.config.api_key, str(timestamp), signature]
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
        if data.get("op") == "auth":
            if data.get("success", False):
                self._log.info("Private WebSocket authenticated")
                # Subscribe to order updates
                sub_msg = {
                    "op": "subscribe",
                    "args": ["order"]
                }
                await self._ws_private.send(json.dumps(sub_msg))
            else:
                self._log.error(f"Private WebSocket auth failed: {data.get('retMsg', 'Unknown')}")
                return
                
        if "data" not in data:
            return
            
        # Handle order updates
        order_data = data.get("data", {})
        order_id = order_data.get("orderId")
        status = order_data.get("status")
        
        if order_id:
            async with self._order_lock:
                self._orders[order_id] = order_data
                if status == "Filled" or status == "Cancelled":
                    self._active_orders.discard(order_id)
                elif status == "New" or status == "PartiallyFilled":
                    self._active_orders.add(order_id)
                    
            # Update metrics
            if status == "Filled":
                self._metrics.increment_counter("orders_filled")
                
    # ======================== ORDER MANAGEMENT ========================
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
        market_type: Optional[str] = None,
        leverage: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Place an order on Bybit with advanced features.
        
        Args:
            symbol: Trading pair symbol
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP, STOP_LIMIT
            quantity: Order quantity
            price: Limit price
            stop_price: Stop price
            take_profit: Take profit price
            stop_loss: Stop loss price
            time_in_force: GTC, IOC, FOK, PostOnly
            reduce_only: Reduce-only position
            post_only: Post-only order
            client_order_id: Client order ID
            market_type: Optional market type override
            leverage: Leverage for futures
            
        Returns:
            Order confirmation
        """
        self._metrics.increment_counter("orders_placed")
        
        symbol = symbol.upper()
        side = side.upper()
        order_type = order_type.upper()
        time_in_force = time_in_force.upper()
        
        # Determine category
        category = market_type or self.config.market_type
        if category in ["futures", "linear"]:
            category = "linear"
        elif category == "inverse":
            category = "inverse"
        elif category == "options":
            category = "option"
        else:
            category = "spot"
            
        # Validate symbol
        symbol_info = await self.get_symbol_info(symbol)
        if not symbol_info:
            raise InvalidSymbolError(f"Symbol not found: {symbol}")
            
        # Validate quantity
        if quantity <= 0:
            raise OrderError("Quantity must be positive")
            
        # Build order parameters
        params = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(quantity),
            "timeInForce": time_in_force
        }
        
        if order_type in ["LIMIT", "STOP_LIMIT"]:
            if price is None:
                raise OrderError("Price required for limit orders")
            params["price"] = str(price)
            
        if order_type in ["STOP", "STOP_LIMIT"]:
            if stop_price is None:
                raise OrderError("Stop price required for stop orders")
            params["stopPrice"] = str(stop_price)
            
        if take_profit:
            params["takeProfit"] = str(take_profit)
            
        if stop_loss:
            params["stopLoss"] = str(stop_loss)
            
        if client_order_id:
            params["orderLinkId"] = client_order_id
            
        if reduce_only:
            params["reduceOnly"] = True
            
        if post_only:
            params["postOnly"] = True
            
        if leverage:
            params["leverage"] = str(leverage)
            
        # Place order
        try:
            start_time = time.time()
            response = await self._post("/v5/order/create", data=params, signed=True)
            
            execution_time = (time.time() - start_time) * 1000
            self._metrics.record_histogram("order_execution_ms", execution_time)
            
            order_data = response.get("list", [{}])[0] if isinstance(response.get("list"), list) else response
            order_id = order_data.get("orderId")
            
            if order_id:
                async with self._order_lock:
                    self._orders[order_id] = order_data
                    self._active_orders.add(order_id)
                    
            self._log.info(f"Order placed: {symbol} {side} {order_type} {quantity} @ {price or 'market'}")
            return order_data
            
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
        
        category = self.config.market_type
        if category in ["futures", "linear"]:
            category = "linear"
        elif category == "inverse":
            category = "inverse"
        else:
            category = "spot"
            
        try:
            response = await self._post(
                "/v5/order/cancel",
                data={"category": category, "symbol": symbol.upper(), "orderId": order_id},
                signed=True
            )
            
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
        category = self.config.market_type
        if category in ["futures", "linear"]:
            category = "linear"
        elif category == "inverse":
            category = "inverse"
        else:
            category = "spot"
            
        try:
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._post("/v5/order/cancel-all", data=params, signed=True)
            
            async with self._order_lock:
                if symbol:
                    self._active_orders.clear()
                    self._orders.clear()
                else:
                    # Remove orders for specific symbol
                    for order_id in list(self._orders.keys()):
                        if self._orders[order_id].get("symbol") == symbol.upper():
                            self._orders.pop(order_id, None)
                            self._active_orders.discard(order_id)
                    
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
        category = self.config.market_type
        if category in ["futures", "linear"]:
            category = "linear"
        elif category == "inverse":
            category = "inverse"
        else:
            category = "spot"
            
        try:
            response = await self._get(
                "/v5/order/realtime",
                params={"category": category, "symbol": symbol.upper(), "orderId": order_id},
                signed=True
            )
            
            order_data = response.get("list", [{}])[0] if isinstance(response.get("list"), list) else response
            async with self._order_lock:
                if order_data:
                    self._orders[order_id] = order_data
                    
            return order_data
            
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
        category = self.config.market_type
        if category in ["futures", "linear"]:
            category = "linear"
        elif category == "inverse":
            category = "inverse"
        else:
            category = "spot"
            
        try:
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._get("/v5/order/realtime", params=params, signed=True)
            
            orders = response.get("list", [])
            async with self._order_lock:
                for order in orders:
                    order_id = order.get("orderId")
                    if order_id:
                        self._orders[order_id] = order
                        if order.get("orderStatus") in ["New", "PartiallyFilled"]:
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
        if self.config.market_type not in ["futures", "linear", "inverse"]:
            return []
            
        try:
            category = "linear" if self.config.market_type in ["futures", "linear"] else "inverse"
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol.upper()
                
            response = await self._get("/v5/position/list", params=params, signed=True)
            
            positions = []
            for item in response.get("list", []):
                size = float(item.get("size", 0))
                if size != 0:
                    position = Position(
                        symbol=item.get("symbol", ""),
                        side="LONG" if size > 0 else "SHORT",
                        size=abs(size),
                        entry_price=float(item.get("avgPrice", 0)),
                        mark_price=float(item.get("markPrice", 0)),
                        liquidation_price=float(item.get("liqPrice", 0)),
                        unrealized_pnl=float(item.get("unrealisedPnl", 0)),
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
            params = {
                "accountType": "UNIFIED" if self.config.market_type in ["futures", "linear", "inverse"] else "SPOT"
            }
            response = await self._get("/v5/account/wallet-balance", params=params, signed=True)
            
            balances = {}
            for item in response.get("list", []):
                for coin in item.get("coin", []):
                    balance = Balance(
                        asset=coin.get("coin", ""),
                        free=float(coin.get("walletBalance", 0)),
                        locked=float(coin.get("locked", 0))
                    )
                    balances[balance.asset] = balance
                    
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
    
    async def get_server_time(self) -> int:
        """Get server time in milliseconds."""
        try:
            data = await self._get("/v5/market/time")
            return data.get("timeSecond", 0) * 1000
        except Exception:
            return int(time.time() * 1000)
            
    def get_symbol_from_pair(self, base: str, quote: str) -> str:
        """Get Bybit symbol from base/quote pair."""
        return f"{base.upper()}{quote.upper()}"
        
    def get_pair_from_symbol(self, symbol: str) -> Tuple[str, str]:
        """Get base/quote from Bybit symbol."""
        symbol = symbol.upper()
        for quote in ["USDT", "BUSD", "USDC", "BTC", "ETH", "BNB"]:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                if base:
                    return base, quote
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
