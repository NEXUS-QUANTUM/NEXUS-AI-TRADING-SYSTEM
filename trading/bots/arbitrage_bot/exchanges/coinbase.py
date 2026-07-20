# trading/bots/arbitrage_bot/exchanges/coinbase.py
# NEXUS AI TRADING SYSTEM - FULL VERSION
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Author: Dr X... - Majority Shareholder

"""
NEXUS Coinbase Exchange Connector - Advanced Arbitrage Module
Version: 3.0.0 - FULL PRODUCTION READY
Description: Enterprise-grade Coinbase Advanced Trade exchange connector 
with advanced features for arbitrage detection, order execution, 
market data streaming, and institutional-grade risk management.
"""

import asyncio
import hmac
import hashlib
import time
import json
import logging
import base64
import calendar
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
from trading.bots.arbitrage_bot.exchanges.converter import CoinbaseConverter
from trading.bots.arbitrage_bot.core.rate_limiter import RateLimiter, RateLimitExceeded
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker
from trading.bots.arbitrage_bot.core.latency_monitor import LatencyMonitor
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler, RetryConfig
from trading.bots.arbitrage_bot.core.health_check import HealthCheck
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.models.exchange import (
    ExchangeInfo, SymbolInfo, OrderBook, Ticker, Trade, Balance,
    Order, Position, Kline, ExchangeStatus
)
from trading.bots.arbitrage_bot.models.order import OrderSide, OrderType, OrderStatus, TimeInForce
from trading.bots.arbitrage_bot.exceptions import (
    ExchangeError, NetworkError, AuthenticationError, RateLimitError,
    OrderError, InsufficientBalanceError, DataError, WebSocketError,
    InvalidSymbolError, OrderNotFoundError, MarketClosedError,
    ExchangeUnavailableError, ConfigurationError
)

logger = logging.getLogger("nexus.arbitrage.coinbase")


@dataclass
class CoinbaseConfig:
    """
    Advanced Coinbase Advanced Trade configuration.
    Coinbase Advanced Trade (formerly Coinbase Pro) API.
    """
    # Authentication
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    testnet: bool = False
    sandbox: bool = False
    
    # Endpoints
    base_url: str = "https://api.exchange.coinbase.com"
    ws_url: str = "wss://ws-feed.exchange.coinbase.com"
    sandbox_base_url: str = "https://api-public.sandbox.exchange.coinbase.com"
    sandbox_ws_url: str = "wss://ws-feed-public.sandbox.exchange.coinbase.com"
    
    # Connection settings
    request_timeout: float = 10.0
    connection_pool_size: int = 100
    keep_alive: bool = True
    ssl_verify: bool = True
    
    # Rate limiting
    max_requests_per_second: int = 25
    max_requests_per_minute: int = 300
    max_order_requests_per_second: int = 5
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
    subscribe_user: bool = False
    kline_interval: str = "1m"
    
    # Advanced features
    enable_order_book_snapshots: bool = True
    snapshot_interval: int = 60
    enable_latency_optimization: bool = True
    enable_compression: bool = True
    enable_request_caching: bool = True
    cache_ttl: float = 0.5
    
    # Order management
    enable_oco_orders: bool = True
    enable_trailing_stops: bool = True
    default_time_in_force: str = "GTC"
    
    # Risk management
    max_position_size: float = 1000000.0
    max_order_size: float = 100000.0
    max_leverage: float = 10.0
    min_margin_ratio: float = 0.02
    
    # Products
    products: List[str] = field(default_factory=list)  # Empty = all
    
    # Debugging
    debug_mode: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate and configure endpoints."""
        if self.sandbox:
            self.base_url = self.sandbox_base_url
            self.ws_url = self.sandbox_ws_url
            
        if self.debug_mode:
            self.log_level = "DEBUG"
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "testnet": self.testnet,
            "sandbox": self.sandbox,
            "base_url": self.base_url,
            "ws_url": self.ws_url,
            "request_timeout": self.request_timeout,
            "max_requests_per_second": self.max_requests_per_second,
            "max_order_requests_per_second": self.max_order_requests_per_second,
            "enable_compression": self.enable_compression,
            "debug_mode": self.debug_mode
        }


class CoinbaseExchange(BaseExchange):
    """
    Enterprise-grade Coinbase Advanced Trade exchange connector optimized for arbitrage.
    
    Coinbase Advanced Trade Features:
    - REST API with JSON responses
    - WebSocket feed for real-time data
    - Good 'til cancelled, fill-or-kill, immediate-or-cancel orders
    - Stop orders (stop loss, stop limit)
    - Self-trade prevention
    - Product ID-based trading (e.g., BTC-USD, ETH-USDT)
    
    Features:
    - High-performance WebSocket streaming with compression
    - Intelligent rate limiting with adaptive throttling
    - Circuit breaker pattern with automatic recovery
    - Automatic retry with exponential backoff
    - Order book reconstruction and delta management
    - Latency optimization for low-latency trading
    - Multi-product subscription management
    - Order execution with smart routing
    - Comprehensive error handling and recovery
    - Real-time metrics and monitoring
    """
    
    def __init__(self, config: CoinbaseConfig):
        """
        Initialize the Coinbase exchange connector.
        
        Args:
            config: Coinbase configuration object
        """
        super().__init__(
            name="coinbase",
            type="cex",
            testnet=config.sandbox
        )
        
        self.config = config
        self.converter = CoinbaseConverter()
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        
        # Data storage
        self._order_books: Dict[str, OrderBook] = {}
        self._order_book_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tickers: Dict[str, Ticker] = {}
        self._trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._klines: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500)))
        
        # Balances
        self._balances: Dict[str, Dict[str, Balance]] = {}
        self._balance_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._balance_update_time: Dict[str, float] = {}
        
        # Products info
        self._products: Optional[List[Dict[str, Any]]] = None
        self._product_info: Dict[str, Dict[str, Any]] = {}
        self._products_list: List[str] = []
        
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
            name="coinbase_api"
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
            name="coinbase_exchange",
            check_interval=30.0,
            timeout=5.0
        )
        
        # Metrics collector
        self._metrics = MetricsCollector(
            name="coinbase_exchange",
            labels={"exchange": "coinbase", "sandbox": str(self.config.sandbox)}
        )
        
        # Websocket subscriptions
        self._ws_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._ws_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._ws_authenticated: bool = False
        
        # Order management
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._active_orders: Set[str] = set()
        self._order_lock: asyncio.Lock = asyncio.Lock()
        self._order_history: deque = deque(maxlen=10000)
        
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
        
        logger.info(f"CoinbaseExchange initialized (sandbox={config.sandbox}, version=3.0.0)")
        
    def _setup_logging(self) -> None:
        """Configure exchange-specific logging."""
        self._log = logger.getChild("coinbase")
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
        self._metrics.register_gauge("orders_open", "Number of open orders")
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
        return f"CoinbaseExchange(name={self.name}, sandbox={self.config.sandbox}, connected={self._is_connected})"
        
    # ======================== CONNECTION MANAGEMENT ========================
    
    async def connect(self, retry: bool = True) -> bool:
        """
        Establish connection to Coinbase Advanced Trade API.
        
        Args:
            retry: Whether to retry on failure
            
        Returns:
            bool: True if connection successful
        """
        if self._is_connected:
            self._metrics.set_gauge("connection_status", 1)
            return True
            
        try:
            self._log.info("Connecting to Coinbase Advanced Trade API...")
            
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
                "User-Agent": "NEXUS/3.0.0 (Coinbase)",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers,
                raise_for_status=False
            )
            
            # Get products info
            await self._get_products()
            
            # Test authentication
            if self.config.api_key and self.config.api_secret and self.config.passphrase:
                await self._test_auth()
                self._is_authenticated = True
                
            self._is_connected = True
            self._start_time = time.time()
            self._metrics.set_gauge("connection_status", 1)
            self._log.info("Connected to Coinbase API successfully")
            
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
            raise ExchangeError(f"Coinbase connection failed: {e}")
            
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        task = asyncio.create_task(self._health_check_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        task = asyncio.create_task(self._metrics_update_loop())
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
            await self._get("/products")
            latency = (time.time() - ping_start) * 1000
            
            self._latency_monitor.record_latency(latency)
            self._metrics.record_histogram("latency_ms", latency)
            
            self._health_check.update_status(
                healthy=True,
                metrics={
                    "latency_ms": latency,
                    "ws_connections": len(self._ws_connections),
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
                self._metrics.set_gauge("orders_open", len(self._active_orders))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Metrics update error: {e}")
                
    async def disconnect(self, graceful: bool = True) -> None:
        """Cleanly disconnect from Coinbase API."""
        self._log.info("Disconnecting from Coinbase...")
        self._shutdown_requested = True
        
        # Close WebSocket connections
        for stream_name, ws in list(self._ws_connections.items()):
            try:
                await ws.close()
            except Exception as e:
                self._log.warning(f"Error closing WebSocket for {stream_name}: {e}")
        self._ws_connections.clear()
        
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
        self._log.info("Disconnected from Coinbase")
        
    # ======================== AUTHENTICATION ========================
    
    async def _test_auth(self) -> None:
        """Test authentication credentials."""
        try:
            await self._get("/accounts", signed=True)
            self._log.info("Authentication successful")
        except AuthenticationError as e:
            self._log.error(f"Authentication failed: {e}")
            raise
            
    def _generate_signature(
        self,
        method: str,
        request_path: str,
        body: str,
        timestamp: str
    ) -> Tuple[str, Dict[str, str]]:
        """
        Generate Coinbase signature.
        
        Args:
            method: HTTP method
            request_path: Request path
            body: Request body
            timestamp: Timestamp in seconds
            
        Returns:
            Tuple of (signature, headers)
        """
        message = f"{timestamp}{method}{request_path}{body}"
        
        signature = hmac.new(
            self.config.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase
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
        Make an HTTP request to Coinbase Advanced Trade API.
        
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
            raise ExchangeError("Not connected to Coinbase")
            
        async with self._request_context(endpoint, signed):
            url = f"{self.config.base_url}{endpoint}"
            headers = {}
            body = ""
            
            if data:
                body = json.dumps(data)
                
            if signed:
                if not self.config.api_key or not self.config.api_secret:
                    raise AuthenticationError("API key/secret not configured")
                    
                timestamp = str(time.time())
                signature, signature_headers = self._generate_signature(
                    method, endpoint, body, timestamp
                )
                headers.update(signature_headers)
                
            self._metrics.increment_counter("requests_total")
            
            # Execute request with retry
            async def _make_request() -> Dict[str, Any]:
                async with self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=body if data else None,
                    headers=headers,
                    ssl=self.config.ssl_verify
                ) as response:
                    try:
                        result = await response.json()
                    except aiohttp.ContentTypeError:
                        text = await response.text()
                        self._log.error(f"Unexpected response: {text[:500]}")
                        raise ExchangeError(f"Unexpected response from Coinbase: {text[:200]}")
                        
                    if response.status >= 400:
                        self._metrics.increment_counter("requests_failed")
                        error_msg = result.get("message", f"HTTP {response.status}")
                        
                        self._log.error(f"API error {response.status}: {error_msg}")
                        
                        if response.status == 429:
                            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                        elif response.status == 401:
                            raise AuthenticationError(f"Authentication failed: {error_msg}")
                        elif response.status == 404:
                            raise OrderNotFoundError(f"Order not found: {error_msg}")
                        elif response.status == 400 and "insufficient funds" in error_msg.lower():
                            raise InsufficientBalanceError(f"Insufficient funds: {error_msg}")
                        elif response.status in (500, 502, 503, 504):
                            raise ExchangeError(f"Server error: {error_msg}")
                        else:
                            raise ExchangeError(f"API error {response.status}: {error_msg}")
                            
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
        
    # ======================== PRODUCTS ========================
    
    async def _get_products(self) -> List[Dict[str, Any]]:
        """Fetch product information."""
        if self._products:
            return self._products
            
        try:
            self._log.debug("Fetching products...")
            data = await self._get("/products")
            
            self._products = data
            for product in data:
                product_id = product.get("id")
                if product_id:
                    self._product_info[product_id] = product
                    if product.get("status") == "online":
                        self._products_list.append(product_id)
                        
            self._log.info(f"Loaded {len(self._products_list)} products")
            return self._products
            
        except Exception as e:
            self._log.error(f"Failed to fetch products: {e}")
            raise
            
    async def get_product_info(self, product_id: str) -> Dict[str, Any]:
        """Get information for a specific product."""
        if not self._products:
            await self._get_products()
        return self._product_info.get(product_id, {})
        
    async def get_all_products(self) -> List[str]:
        """Get list of all trading products."""
        if not self._products_list:
            await self._get_products()
        return self._products_list.copy()
        
    # ======================== MARKET DATA ========================
    
    async def get_order_book(
        self,
        product_id: str,
        level: int = 2,
        use_cache: bool = True
    ) -> OrderBook:
        """
        Get order book snapshot.
        
        Args:
            product_id: Product ID (e.g., BTC-USD)
            level: Level (1=best bid/ask, 2=top 50, 3=full)
            use_cache: Whether to use cached data
            
        Returns:
            OrderBook object
        """
        product_id = product_id.upper()
        
        if use_cache and product_id in self._order_books:
            book = self._order_books[product_id]
            if (time.time() - book.timestamp) < 0.5:
                return book
                
        try:
            data = await self._get(
                f"/products/{product_id}/book",
                params={"level": level}
            )
            
            book = self.converter.parse_order_book(data, product_id)
            
            async with self._order_book_locks[product_id]:
                self._order_books[product_id] = book
                
            return book
            
        except Exception as e:
            self._log.error(f"Failed to get order book for {product_id}: {e}")
            if use_cache and product_id in self._order_books:
                return self._order_books[product_id]
            raise DataError(f"Order book fetch failed: {e}")
            
    async def get_ticker(self, product_id: str, use_cache: bool = True) -> Ticker:
        """
        Get 24-hour ticker for product.
        
        Args:
            product_id: Product ID
            use_cache: Whether to use cached data
            
        Returns:
            Ticker object
        """
        product_id = product_id.upper()
        
        if use_cache and product_id in self._tickers:
            ticker = self._tickers[product_id]
            if (time.time() - ticker.timestamp) < 2.0:
                return ticker
                
        try:
            data = await self._get(f"/products/{product_id}/stats")
            
            ticker = self.converter.parse_ticker(data, product_id)
            if ticker:
                self._tickers[ticker.symbol] = ticker
            return ticker
            
        except Exception as e:
            self._log.error(f"Failed to get ticker for {product_id}: {e}")
            if use_cache and product_id in self._tickers:
                return self._tickers[product_id]
            raise DataError(f"Ticker fetch failed: {e}")
            
    async def get_recent_trades(
        self,
        product_id: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> List[Trade]:
        """
        Get recent trades for product.
        
        Args:
            product_id: Product ID
            limit: Number of trades (max 1000)
            use_cache: Whether to use cached data
            
        Returns:
            List of Trade objects
        """
        product_id = product_id.upper()
        
        if use_cache and product_id in self._trades:
            trades = list(self._trades[product_id])
            if len(trades) >= limit:
                return trades[:limit]
                
        try:
            data = await self._get(
                f"/products/{product_id}/trades",
                params={"limit": min(limit, 1000)}
            )
            
            trades = []
            for item in data:
                trade = self.converter.parse_trade(item, product_id)
                if trade:
                    trades.append(trade)
                    
            self._trades[product_id] = deque(trades, maxlen=1000)
            return trades
            
        except Exception as e:
            self._log.error(f"Failed to get trades for {product_id}: {e}")
            if use_cache and product_id in self._trades:
                return list(self._trades[product_id])[:limit]
            raise DataError(f"Trades fetch failed: {e}")
            
    async def get_klines(
        self,
        product_id: str,
        granularity: str = "60",
        limit: int = 100,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get candlestick data.
        
        Args:
            product_id: Product ID
            granularity: Granularity in seconds (60, 300, 900, 3600, 21600, 86400)
            limit: Number of candles (max 1000)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with OHLCV data
        """
        product_id = product_id.upper()
        
        # Map common intervals to Coinbase granularity
        granularity_map = {
            "1m": "60", "5m": "300", "15m": "900", "30m": "1800",
            "1h": "3600", "2h": "7200", "4h": "14400", "6h": "21600",
            "12h": "43200", "1d": "86400", "1w": "604800"
        }
        coinbase_granularity = granularity_map.get(granularity, str(granularity))
        
        try:
            data = await self._get(
                f"/products/{product_id}/candles",
                params={
                    "granularity": int(coinbase_granularity),
                    "limit": min(limit, 1000)
                }
            )
            
            return self.converter.parse_klines(data)
            
        except Exception as e:
            self._log.error(f"Failed to get klines for {product_id}: {e}")
            raise DataError(f"Kline fetch failed: {e}")
            
    # ======================== WEBSOCKET STREAMING ========================
    
    async def subscribe_order_book(self, product_id: str, callback: Callable) -> None:
        """Subscribe to real-time order book updates."""
        await self._subscribe_stream(product_id, "level2", callback)
        
    async def subscribe_ticker(self, product_id: str, callback: Callable) -> None:
        """Subscribe to real-time ticker updates."""
        await self._subscribe_stream(product_id, "ticker", callback)
        
    async def subscribe_trades(self, product_id: str, callback: Callable) -> None:
        """Subscribe to real-time trade updates."""
        await self._subscribe_stream(product_id, "matches", callback)
        
    async def subscribe_user(self, callback: Callable) -> None:
        """Subscribe to user-specific updates (orders, fills)."""
        if not self._is_authenticated:
            raise AuthenticationError("Must be authenticated for user subscriptions")
        await self._subscribe_user_stream(callback)
        
    async def _subscribe_stream(
        self,
        product_id: str,
        stream_type: str,
        callback: Callable
    ) -> None:
        """Generic WebSocket subscription handler."""
        product_id = product_id.upper()
        stream_name = f"{product_id}:{stream_type}"
        
        self._ws_subscriptions[stream_type].add(product_id)
        self._ws_callbacks[stream_name].append(callback)
        
        # All subscriptions share the same WebSocket connection
        if not self._ws_connections:
            task = asyncio.create_task(self._manage_websocket())
            self._ws_tasks["main"] = task
            
        self._is_streaming = True
        self._log.debug(f"Subscribed to {stream_name}")
        
    async def _subscribe_user_stream(self, callback: Callable) -> None:
        """Subscribe to user-specific WebSocket stream."""
        stream_name = "user"
        self._ws_callbacks[stream_name].append(callback)
        
        if not self._ws_connections:
            task = asyncio.create_task(self._manage_websocket())
            self._ws_tasks["main"] = task
            
        self._is_streaming = True
        self._log.debug("Subscribed to user stream")
        
    async def _manage_websocket(self) -> None:
        """Manage WebSocket connection with automatic reconnection."""
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
                
                self._ws_connections["main"] = ws
                self._metrics.set_gauge("ws_connections", len(self._ws_connections))
                self._log.info("WebSocket connected")
                
                # Authenticate if needed
                if self._is_authenticated:
                    await self._authenticate_websocket(ws)
                    
                reconnect_delay = 1.0
                await self._handle_websocket_messages(ws)
                
            except ConnectionClosedOK:
                self._log.info("WebSocket closed normally")
                break
            except Exception as e:
                self._log.warning(f"WebSocket error: {e}")
                
            if "main" in self._ws_connections:
                del self._ws_connections["main"]
            self._metrics.set_gauge("ws_connections", len(self._ws_connections))
            
            if self._shutdown_requested:
                break
                
            if self._ws_subscriptions or self._ws_callbacks:
                self._log.info(f"Reconnecting in {reconnect_delay:.1f}s")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_delay)
                
    async def _authenticate_websocket(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Authenticate WebSocket connection."""
        timestamp = str(time.time())
        signature, _ = self._generate_signature("GET", "/users/self", "", timestamp)
        
        auth_msg = {
            "type": "subscribe",
            "channels": [{"name": "user"}],
            "signature": signature,
            "key": self.config.api_key,
            "passphrase": self.config.passphrase,
            "timestamp": timestamp
        }
        await ws.send(json.dumps(auth_msg))
        
    async def _handle_websocket_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Handle incoming WebSocket messages."""
        try:
            # Build subscription message
            channels = []
            
            for stream_type, products in self._ws_subscriptions.items():
                if stream_type == "level2":
                    channels.append({"name": "level2", "product_ids": list(products)})
                elif stream_type == "ticker":
                    channels.append({"name": "ticker", "product_ids": list(products)})
                elif stream_type == "matches":
                    channels.append({"name": "matches", "product_ids": list(products)})
                elif stream_type == "full":
                    channels.append({"name": "full", "product_ids": list(products)})
                    
            if channels:
                sub_msg = {"type": "subscribe", "channels": channels}
                await ws.send(json.dumps(sub_msg))
                
            async for message in ws:
                self._metrics.increment_counter("ws_messages_received")
                
                try:
                    data = json.loads(message)
                    await self._process_websocket_message(data)
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
            
    async def _process_websocket_message(self, data: Dict[str, Any]) -> None:
        """Process a WebSocket message."""
        msg_type = data.get("type")
        
        if msg_type == "subscriptions":
            self._log.debug(f"Subscription confirmed: {data}")
            return
            
        if msg_type == "l2update":
            await self._process_l2_update(data)
        elif msg_type == "ticker":
            await self._process_ticker_message(data)
        elif msg_type == "match":
            await self._process_match_message(data)
        elif msg_type == "received" or msg_type == "open" or msg_type == "done" or msg_type == "change":
            await self._process_order_message(data)
        elif msg_type == "error":
            self._log.error(f"WebSocket error: {data}")
            
    async def _process_l2_update(self, data: Dict[str, Any]) -> None:
        """Process level2 order book update."""
        product_id = data.get("product_id", "")
        changes = data.get("changes", [])
        
        if product_id in self._order_books:
            async with self._order_book_locks[product_id]:
                book = self._order_books[product_id]
                updated = self.converter.apply_order_book_delta(book, changes)
                if updated:
                    self._order_books[product_id] = updated
                    
        await self._dispatch_callbacks(f"{product_id}:level2", data)
        
    async def _process_ticker_message(self, data: Dict[str, Any]) -> None:
        """Process ticker message."""
        ticker = self.converter.parse_ws_ticker(data)
        if ticker:
            self._tickers[ticker.symbol] = ticker
            await self._dispatch_callbacks(f"{ticker.symbol}:ticker", ticker)
            
    async def _process_match_message(self, data: Dict[str, Any]) -> None:
        """Process match/trade message."""
        trade = self.converter.parse_ws_trade(data)
        if trade:
            self._trades[trade.symbol].append(trade)
            await self._dispatch_callbacks(f"{trade.symbol}:matches", trade)
            
    async def _process_order_message(self, data: Dict[str, Any]) -> None:
        """Process order update message."""
        order_id = data.get("order_id")
        if order_id:
            async with self._order_lock:
                self._orders[order_id] = data
                if data.get("type") == "done" and data.get("reason") in ["filled", "canceled"]:
                    self._active_orders.discard(order_id)
                elif data.get("type") in ["received", "open"]:
                    self._active_orders.add(order_id)
                    
        await self._dispatch_callbacks("user", data)
        
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
                
    # ======================== ORDER MANAGEMENT ========================
    
    async def place_order(
        self,
        product_id: str,
        side: str,
        order_type: str,
        size: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_type: str = "loss",
        time_in_force: str = "GTC",
        post_only: bool = False,
        client_order_id: Optional[str] = None,
        self_trade_prevention: str = "co"
    ) -> Dict[str, Any]:
        """
        Place an order on Coinbase Advanced Trade.
        
        Args:
            product_id: Product ID (e.g., BTC-USD)
            side: BUY or SELL
            order_type: limit, market, stop, stop_limit
            size: Order size
            price: Limit price
            stop_price: Stop price
            stop_type: loss or entry
            time_in_force: GTC, GTT, IOC, FOK
            post_only: Post-only order
            client_order_id: Client order ID
            self_trade_prevention: co (cancel-only), dc (decrease-only), or coo (cancel-oldest)
            
        Returns:
            Order confirmation
        """
        self._metrics.increment_counter("orders_placed")
        
        product_id = product_id.upper()
        side = side.lower()
        order_type = order_type.lower()
        
        # Validate product
        product_info = await self.get_product_info(product_id)
        if not product_info:
            raise InvalidSymbolError(f"Product not found: {product_id}")
            
        # Validate size
        if size <= 0:
            raise OrderError("Size must be positive")
            
        # Get min size
        min_size = float(product_info.get("base_min_size", 0))
        if size < min_size:
            raise OrderError(f"Size {size} below minimum {min_size}")
            
        # Build order parameters
        params = {
            "product_id": product_id,
            "side": side,
            "size": str(size)
        }
        
        if order_type in ["limit", "stop_limit"]:
            if price is None:
                raise OrderError("Price required for limit orders")
            params["price"] = str(price)
            
        if order_type in ["stop", "stop_limit"]:
            if stop_price is None:
                raise OrderError("Stop price required for stop orders")
            params["stop"] = stop_type
            params["stop_price"] = str(stop_price)
            
        if order_type == "market":
            params["type"] = "market"
        elif order_type in ["limit", "stop_limit"]:
            params["type"] = "limit"
            params["time_in_force"] = time_in_force
        elif order_type == "stop":
            params["type"] = "stop"
        else:
            raise OrderError(f"Unsupported order type: {order_type}")
            
        if post_only:
            params["post_only"] = True
            
        if client_order_id:
            params["client_oid"] = client_order_id
            
        params["self_trade_prevention"] = self_trade_prevention
        
        # Place order
        try:
            start_time = time.time()
            response = await self._post("/orders", data=params, signed=True)
            
            execution_time = (time.time() - start_time) * 1000
            self._metrics.record_histogram("order_execution_ms", execution_time)
            
            order_id = response.get("id")
            if order_id:
                async with self._order_lock:
                    self._orders[order_id] = response
                    self._active_orders.add(order_id)
                    
            self._log.info(f"Order placed: {product_id} {side} {order_type} {size} @ {price or 'market'}")
            return response
            
        except InsufficientBalanceError as e:
            self._log.error(f"Insufficient balance for {product_id}: {e}")
            raise
        except Exception as e:
            self._log.error(f"Order placement failed: {e}")
            self._metrics.increment_counter("orders_failed")
            raise
            
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Cancellation confirmation
        """
        self._metrics.increment_counter("orders_cancelled")
        
        try:
            response = await self._delete(f"/orders/{order_id}", signed=True)
            
            async with self._order_lock:
                self._orders.pop(order_id, None)
                self._active_orders.discard(order_id)
                
            self._log.info(f"Order cancelled: {order_id}")
            return response
            
        except Exception as e:
            self._log.error(f"Order cancellation failed: {e}")
            raise
            
    async def cancel_all_orders(self, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Cancel all open orders.
        
        Args:
            product_id: Optional product filter
            
        Returns:
            List of cancellation confirmations
        """
        try:
            params = {}
            if product_id:
                params["product_id"] = product_id.upper()
                
            response = await self._delete("/orders", params=params, signed=True)
            
            async with self._order_lock:
                if product_id:
                    for order_id in list(self._orders.keys()):
                        if self._orders[order_id].get("product_id") == product_id.upper():
                            self._orders.pop(order_id, None)
                            self._active_orders.discard(order_id)
                else:
                    self._active_orders.clear()
                    self._orders.clear()
                    
            self._log.info(f"Cancelled all orders for {product_id or 'all products'}")
            return response
            
        except Exception as e:
            self._log.error(f"Failed to cancel orders: {e}")
            raise
            
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order information
        """
        try:
            response = await self._get(f"/orders/{order_id}", signed=True)
            
            async with self._order_lock:
                self._orders[order_id] = response
                
            return response
            
        except Exception as e:
            self._log.error(f"Failed to get order {order_id}: {e}")
            raise
            
    async def get_open_orders(self, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Args:
            product_id: Optional product filter
            
        Returns:
            List of open orders
        """
        try:
            params = {"status": "open,active"}
            if product_id:
                params["product_id"] = product_id.upper()
                
            response = await self._get("/orders", params=params, signed=True)
            
            async with self._order_lock:
                for order in response:
                    order_id = order.get("id")
                    if order_id:
                        self._orders[order_id] = order
                        self._active_orders.add(order_id)
                        
            return response
            
        except Exception as e:
            self._log.error(f"Failed to get open orders: {e}")
            raise
            
    async def get_order_history(self, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get order history.
        
        Args:
            product_id: Optional product filter
            
        Returns:
            List of historical orders
        """
        try:
            params = {"status": "done"}
            if product_id:
                params["product_id"] = product_id.upper()
                
            response = await self._get("/orders", params=params, signed=True)
            
            for order in response:
                self._order_history.append(order)
                
            return response
            
        except Exception as e:
            self._log.error(f"Failed to get order history: {e}")
            raise
            
    # ======================== ACCOUNT MANAGEMENT ========================
    
    async def get_balances(self, force: bool = False) -> Dict[str, Balance]:
        """
        Get account balances.
        
        Args:
            force: Force refresh
            
        Returns:
            Dict of asset -> Balance
        """
        if not force and self._balances:
            if self._balance_update_time and (time.time() - self._balance_update_time.get("all", 0)) < 5.0:
                return self._balances.copy()
                
        try:
            response = await self._get("/accounts", signed=True)
            
            balances = {}
            for item in response:
                balance = Balance(
                    asset=item.get("currency", ""),
                    free=float(item.get("available", 0)),
                    locked=float(item.get("hold", 0))
                )
                balances[balance.asset] = balance
                
            async with self._balance_locks["all"]:
                self._balances = balances
                self._balance_update_time["all"] = time.time()
                
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
            data = await self._get("/time")
            return int(datetime.fromisoformat(data.get("iso", "").replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            return int(time.time() * 1000)
            
    def get_product_from_pair(self, base: str, quote: str) -> str:
        """Get Coinbase product from base/quote pair."""
        return f"{base.upper()}-{quote.upper()}"
        
    def get_pair_from_product(self, product_id: str) -> Tuple[str, str]:
        """Get base/quote from Coinbase product."""
        parts = product_id.split("-")
        if len(parts) == 2:
            return parts[0], parts[1]
        raise ValueError(f"Could not parse product: {product_id}")
        
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
            "open_orders": len(self._active_orders),
            "latency_p50": self._latency_monitor.get_percentile(50),
            "latency_p95": self._latency_monitor.get_percentile(95),
            "latency_p99": self._latency_monitor.get_percentile(99),
            "uptime_seconds": self._uptime_seconds,
            "is_connected": self._is_connected,
            "is_streaming": self._is_streaming,
            "is_authenticated": self._is_authenticated
        }
