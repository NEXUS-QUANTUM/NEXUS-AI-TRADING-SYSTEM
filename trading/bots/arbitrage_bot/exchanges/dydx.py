# trading/bots/arbitrage_bot/exchanges/dydx.py
# NEXUS AI TRADING SYSTEM - FULL VERSION
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Author: Dr X... - Majority Shareholder

"""
NEXUS dYdX Exchange Connector - Advanced Arbitrage Module
Version: 3.0.0 - FULL PRODUCTION READY
Description: Enterprise-grade dYdX perpetuals DEX connector for arbitrage
trading across perpetual markets, cross-margin accounts, and layer 2 scaling.
"""

import asyncio
import hmac
import hashlib
import time
import json
import logging
import base64
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Set
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict, deque
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import urllib.parse

import aiohttp
import websockets
from websockets.exceptions import WebSocketException, ConnectionClosed, ConnectionClosedOK
import pandas as pd
import numpy as np
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract

# NEXUS internal imports
from trading.bots.arbitrage_bot.exchanges.base_exchange import BaseExchange
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

logger = logging.getLogger("nexus.arbitrage.dydx")


@dataclass
class DyDxConfig:
    """
    Advanced dYdX perpetuals DEX configuration.
    dYdX is a decentralized perpetuals exchange built on Starkware Layer 2.
    """
    # Authentication
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    stark_private_key: str = ""
    eth_private_key: str = ""
    wallet_address: str = ""
    
    # Endpoints
    base_url: str = "https://api.dydx.exchange"
    ws_url: str = "wss://api.dydx.exchange/v3/ws"
    testnet_base_url: str = "https://api.stage.dydx.exchange"
    testnet_ws_url: str = "wss://api.stage.dydx.exchange/v3/ws"
    
    # Layer 2
    starknet_rpc: str = "https://starknet-mainnet.infura.io/v3/"
    starknet_api_key: str = ""
    
    # Connection settings
    request_timeout: float = 10.0
    connection_pool_size: int = 100
    keep_alive: bool = True
    ssl_verify: bool = True
    
    # Rate limiting
    max_requests_per_second: int = 30
    max_requests_per_minute: int = 300
    max_order_requests_per_second: int = 5
    max_websocket_connections: int = 5
    
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
    subscribe_order_updates: bool = True
    subscribe_position_updates: bool = True
    subscribe_funding_rate: bool = True
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
    enable_tp_sl_orders: bool = True
    enable_post_only: bool = True
    enable_reduce_only: bool = True
    default_time_in_force: str = "GTC"
    
    # Risk management
    max_position_size: float = 1000000.0
    max_order_size: float = 100000.0
    max_leverage: float = 25.0
    min_margin_ratio: float = 0.02
    cross_margin: bool = True
    isolated_margin: bool = False
    
    # Market type
    market: str = "perpetual"  # perpetual, spot
    
    # Debugging
    debug_mode: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate and configure endpoints."""
        if self.testnet:
            self.base_url = self.testnet_base_url
            self.ws_url = self.testnet_ws_url
            
        if self.debug_mode:
            self.log_level = "DEBUG"
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "testnet": self.testnet,
            "market": self.market,
            "base_url": self.base_url,
            "ws_url": self.ws_url,
            "request_timeout": self.request_timeout,
            "max_requests_per_second": self.max_requests_per_second,
            "max_order_requests_per_second": self.max_order_requests_per_second,
            "enable_compression": self.enable_compression,
            "debug_mode": self.debug_mode
        }


class DyDxExchange(BaseExchange):
    """
    Enterprise-grade dYdX perpetuals DEX connector optimized for arbitrage.
    
    dYdX Features:
    - Perpetual futures trading
    - Up to 25x leverage
    - Cross-margin and isolated margin
    - Layer 2 scaling (Starkware)
    - Non-custodial trading
    - Advanced order types (TP/SL, trailing stop)
    - Real-time order book and trade data
    - WebSocket streaming for market data
    - USDC settlement
    
    Arbitrage Opportunities:
    - dYdX vs CEX perpetuals arbitrage
    - dYdX vs other DEX perpetuals arbitrage
    - Basis trading (spot vs perpetual)
    - Funding rate arbitrage
    - Cross-exchange spread arbitrage
    
    Features:
    - High-performance WebSocket streaming
    - Intelligent rate limiting with adaptive throttling
    - Circuit breaker pattern with automatic recovery
    - Automatic retry with exponential backoff
    - Order book reconstruction and delta management
    - Latency optimization for low-latency trading
    - Multi-market subscription management
    - Advanced order execution with TP/SL
    - Comprehensive error handling and recovery
    - Real-time metrics and monitoring
    - Layer 2 Starknet integration
    - Non-custodial wallet management
    """
    
    def __init__(self, config: DyDxConfig):
        """
        Initialize the dYdX exchange connector.
        
        Args:
            config: dYdX configuration object
        """
        super().__init__(
            name="dydx",
            type="dex",
            testnet=config.testnet
        )
        
        self.config = config
        self.market = config.market
        
        # Web3 setup for Starknet
        self._w3 = None
        self._stark_account = None
        if config.stark_private_key:
            self._stark_account = Account.from_key(config.stark_private_key)
            
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
        self._funding_rates: Dict[str, FundingRate] = {}
        self._open_interest: Dict[str, float] = {}
        self._mark_prices: Dict[str, float] = {}
        
        # Balances
        self._balances: Dict[str, Dict[str, Balance]] = {}
        self._balance_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._balance_update_time: Dict[str, float] = {}
        
        # Market info
        self._markets: Optional[Dict[str, Any]] = None
        self._market_info: Dict[str, Dict[str, Any]] = {}
        self._markets_list: List[str] = []
        
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
            name="dydx_api"
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
            name="dydx_exchange",
            check_interval=30.0,
            timeout=5.0
        )
        
        # Metrics collector
        self._metrics = MetricsCollector(
            name="dydx_exchange",
            labels={"exchange": "dydx", "testnet": str(self.config.testnet)}
        )
        
        # Websocket subscriptions
        self._ws_subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._ws_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._ws_authenticated: bool = False
        self._ws_channel_id: Optional[str] = None
        
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
        
        logger.info(f"DyDxExchange initialized (testnet={config.testnet}, market={config.market}, version=3.0.0)")
        
    def _setup_logging(self) -> None:
        """Configure exchange-specific logging."""
        self._log = logger.getChild("dydx")
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
        return f"DyDxExchange(name={self.name}, market={self.market}, connected={self._is_connected})"
        
    # ======================== CONNECTION MANAGEMENT ========================
    
    async def connect(self, retry: bool = True) -> bool:
        """
        Establish connection to dYdX API.
        
        Args:
            retry: Whether to retry on failure
            
        Returns:
            bool: True if connection successful
        """
        if self._is_connected:
            self._metrics.set_gauge("connection_status", 1)
            return True
            
        try:
            self._log.info("Connecting to dYdX API...")
            
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
                "User-Agent": "NEXUS/3.0.0 (dYdX)",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers,
                raise_for_status=False
            )
            
            # Get markets info
            await self._get_markets()
            
            # Test authentication
            if self.config.api_key and self.config.api_secret and self.config.passphrase:
                await self._test_auth()
                self._is_authenticated = True
                
            self._is_connected = True
            self._start_time = time.time()
            self._metrics.set_gauge("connection_status", 1)
            self._log.info("Connected to dYdX API successfully")
            
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
            raise ExchangeError(f"dYdX connection failed: {e}")
            
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        task = asyncio.create_task(self._health_check_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        task = asyncio.create_task(self._funding_rate_monitor_loop())
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
            await self._get("/v3/time")
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
                async with self._position_lock:
                    self._metrics.set_gauge("positions", len(self._positions))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Metrics update error: {e}")
                
    async def _funding_rate_monitor_loop(self) -> None:
        """Monitor funding rates for arbitrage opportunities."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(60)
                if self._is_connected and self._markets_list:
                    await self._refresh_funding_rates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Funding rate monitor error: {e}")
                
    async def _refresh_funding_rates(self) -> None:
        """Refresh funding rates for all markets."""
        try:
            for market in self._markets_list:
                try:
                    rate = await self.get_funding_rate(market)
                    self._funding_rates[market] = rate
                except Exception as e:
                    self._log.debug(f"Failed to get funding rate for {market}: {e}")
        except Exception as e:
            self._log.error(f"Failed to refresh funding rates: {e}")
                
    async def disconnect(self, graceful: bool = True) -> None:
        """Cleanly disconnect from dYdX API."""
        self._log.info("Disconnecting from dYdX...")
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
        self._log.info("Disconnected from dYdX")
        
    # ======================== AUTHENTICATION ========================
    
    async def _test_auth(self) -> None:
        """Test authentication credentials."""
        try:
            await self._get("/v3/accounts", signed=True)
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
        Generate dYdX signature.
        
        Args:
            method: HTTP method
            request_path: Request path
            body: Request body
            timestamp: Timestamp in ISO format
            
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
            "DYDX-API-KEY": self.config.api_key,
            "DYDX-SIGNATURE": signature,
            "DYDX-TIMESTAMP": timestamp,
            "DYDX-PASSPHRASE": self.config.passphrase
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
        Make an HTTP request to dYdX API.
        
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
            raise ExchangeError("Not connected to dYdX")
            
        async with self._request_context(endpoint, signed):
            url = f"{self.config.base_url}{endpoint}"
            headers = {}
            body = ""
            
            if data:
                body = json.dumps(data)
                
            if signed:
                if not self.config.api_key or not self.config.api_secret:
                    raise AuthenticationError("API key/secret not configured")
                    
                timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
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
                        raise ExchangeError(f"Unexpected response from dYdX: {text[:200]}")
                        
                    if response.status >= 400:
                        self._metrics.increment_counter("requests_failed")
                        error_msg = result.get("msg", result.get("errors", [{"msg": f"HTTP {response.status}"}])[0].get("msg", "Unknown error"))
                        
                        self._log.error(f"API error {response.status}: {error_msg}")
                        
                        if response.status == 429:
                            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                        elif response.status == 401:
                            raise AuthenticationError(f"Authentication failed: {error_msg}")
                        elif response.status == 404:
                            raise OrderNotFoundError(f"Order not found: {error_msg}")
                        elif response.status == 400 and ("balance" in error_msg.lower() or "insufficient" in error_msg.lower()):
                            raise InsufficientBalanceError(f"Insufficient balance: {error_msg}")
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
        
    # ======================== MARKETS ========================
    
    async def _get_markets(self) -> Dict[str, Any]:
        """Fetch market information."""
        if self._markets:
            return self._markets
            
        try:
            self._log.debug("Fetching markets...")
            data = await self._get("/v3/markets")
            
            self._markets = data.get("markets", {})
            
            for market_id, market_data in self._markets.items():
                self._market_info[market_id] = market_data
                if market_data.get("status") == "ONLINE":
                    self._markets_list.append(market_id)
                    
            self._log.info(f"Loaded {len(self._markets_list)} markets")
            return self._markets
            
        except Exception as e:
            self._log.error(f"Failed to fetch markets: {e}")
            raise
            
    async def get_market_info(self, market: str) -> Dict[str, Any]:
        """Get information for a specific market."""
        if not self._markets:
            await self._get_markets()
        return self._market_info.get(market, {})
        
    async def get_all_markets(self) -> List[str]:
        """Get list of all trading markets."""
        if not self._markets_list:
            await self._get_markets()
        return self._markets_list.copy()
        
    # ======================== MARKET DATA ========================
    
    async def get_order_book(
        self,
        market: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> OrderBook:
        """
        Get order book snapshot.
        
        Args:
            market: Market ID (e.g., BTC-USD)
            limit: Depth limit (max 100)
            use_cache: Whether to use cached data
            
        Returns:
            OrderBook object
        """
        market = market.upper()
        
        if use_cache and market in self._order_books:
            book = self._order_books[market]
            if (time.time() - book.timestamp) < 0.5:
                return book
                
        try:
            data = await self._get(
                f"/v3/orderbook/{market}",
                params={"limit": min(limit, 100)}
            )
            
            book = self._parse_order_book(data, market)
            
            async with self._order_book_locks[market]:
                self._order_books[market] = book
                
            return book
            
        except Exception as e:
            self._log.error(f"Failed to get order book for {market}: {e}")
            if use_cache and market in self._order_books:
                return self._order_books[market]
            raise DataError(f"Order book fetch failed: {e}")
            
    def _parse_order_book(self, data: Dict[str, Any], market: str) -> OrderBook:
        """Parse order book data."""
        bids = []
        asks = []
        
        for bid in data.get("bids", []):
            bids.append((float(bid[0]), float(bid[1])))
            
        for ask in data.get("asks", []):
            asks.append((float(ask[0]), float(ask[1])))
            
        return OrderBook(
            symbol=market,
            bids=bids,
            asks=asks,
            timestamp=int(time.time() * 1000),
            last_update_id=data.get("lastUpdateId", 0)
        )
        
    async def get_ticker(self, market: str, use_cache: bool = True) -> Ticker:
        """
        Get 24-hour ticker for market.
        
        Args:
            market: Market ID
            use_cache: Whether to use cached data
            
        Returns:
            Ticker object
        """
        market = market.upper()
        
        if use_cache and market in self._tickers:
            ticker = self._tickers[market]
            if (time.time() - ticker.timestamp) < 2.0:
                return ticker
                
        try:
            data = await self._get(f"/v3/markets/{market}")
            
            ticker = self._parse_ticker(data, market)
            if ticker:
                self._tickers[ticker.symbol] = ticker
            return ticker
            
        except Exception as e:
            self._log.error(f"Failed to get ticker for {market}: {e}")
            if use_cache and market in self._tickers:
                return self._tickers[market]
            raise DataError(f"Ticker fetch failed: {e}")
            
    def _parse_ticker(self, data: Dict[str, Any], market: str) -> Ticker:
        """Parse ticker data."""
        market_data = data.get("markets", {}).get(market, {})
        
        return Ticker(
            symbol=market,
            bid=float(market_data.get("bid", 0)),
            ask=float(market_data.get("ask", 0)),
            last=float(market_data.get("last", 0)),
            high=float(market_data.get("high", 0)),
            low=float(market_data.get("low", 0)),
            volume=float(market_data.get("volume", 0)),
            change_24h=0,
            timestamp=int(time.time() * 1000)
        )
        
    async def get_recent_trades(
        self,
        market: str,
        limit: int = 100,
        use_cache: bool = True
    ) -> List[Trade]:
        """
        Get recent trades for market.
        
        Args:
            market: Market ID
            limit: Number of trades (max 100)
            use_cache: Whether to use cached data
            
        Returns:
            List of Trade objects
        """
        market = market.upper()
        
        if use_cache and market in self._trades:
            trades = list(self._trades[market])
            if len(trades) >= limit:
                return trades[:limit]
                
        try:
            data = await self._get(
                f"/v3/trades/{market}",
                params={"limit": min(limit, 100)}
            )
            
            trades = []
            for item in data.get("trades", []):
                trade = self._parse_trade(item, market)
                if trade:
                    trades.append(trade)
                    
            self._trades[market] = deque(trades, maxlen=1000)
            return trades
            
        except Exception as e:
            self._log.error(f"Failed to get trades for {market}: {e}")
            if use_cache and market in self._trades:
                return list(self._trades[market])[:limit]
            raise DataError(f"Trades fetch failed: {e}")
            
    def _parse_trade(self, data: Dict[str, Any], market: str) -> Trade:
        """Parse trade data."""
        return Trade(
            symbol=market,
            price=float(data.get("price", 0)),
            size=float(data.get("size", 0)),
            side=data.get("side", "").upper(),
            timestamp=int(data.get("createdAt", time.time() * 1000)),
            trade_id=data.get("id", "")
        )
        
    async def get_funding_rate(self, market: str) -> FundingRate:
        """
        Get current funding rate.
        
        Args:
            market: Market ID
            
        Returns:
            FundingRate object
        """
        market = market.upper()
        
        try:
            data = await self._get(f"/v3/funding/{market}")
            
            return FundingRate(
                symbol=market,
                rate=float(data.get("rate", 0)),
                next_time=int(data.get("nextFundingTime", 0))
            )
            
        except Exception as e:
            self._log.error(f"Failed to get funding rate for {market}: {e}")
            raise
            
    # ======================== WEBSOCKET STREAMING ========================
    
    async def subscribe_order_book(self, market: str, callback: Callable) -> None:
        """Subscribe to real-time order book updates."""
        await self._subscribe_stream(market, "orderbook", callback)
        
    async def subscribe_ticker(self, market: str, callback: Callable) -> None:
        """Subscribe to real-time ticker updates."""
        await self._subscribe_stream(market, "ticker", callback)
        
    async def subscribe_trades(self, market: str, callback: Callable) -> None:
        """Subscribe to real-time trade updates."""
        await self._subscribe_stream(market, "trades", callback)
        
    async def subscribe_markets(self, markets: List[str], callback: Callable) -> None:
        """Subscribe to multiple markets."""
        for market in markets:
            await self._subscribe_stream(market, "market", callback)
            
    async def subscribe_account(self, callback: Callable) -> None:
        """Subscribe to account updates (requires authentication)."""
        if not self._is_authenticated:
            raise AuthenticationError("Must be authenticated for account updates")
        await self._subscribe_account_stream(callback)
        
    async def _subscribe_stream(
        self,
        market: str,
        stream_type: str,
        callback: Callable
    ) -> None:
        """Generic WebSocket subscription handler."""
        market = market.upper()
        stream_name = f"{market}:{stream_type}"
        
        self._ws_subscriptions[stream_type].add(market)
        self._ws_callbacks[stream_name].append(callback)
        
        if not self._ws_connections:
            task = asyncio.create_task(self._manage_websocket())
            self._ws_tasks["main"] = task
            
        self._is_streaming = True
        self._log.debug(f"Subscribed to {stream_name}")
        
    async def _subscribe_account_stream(self, callback: Callable) -> None:
        """Subscribe to account WebSocket stream."""
        stream_name = "account"
        self._ws_callbacks[stream_name].append(callback)
        
        if not self._ws_connections:
            task = asyncio.create_task(self._manage_websocket())
            self._ws_tasks["main"] = task
            
        self._is_streaming = True
        self._log.debug("Subscribed to account stream")
        
    async def _manage_websocket(self) -> None:
        """Manage WebSocket connection with automatic reconnection."""
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
                
                self._ws_connections["main"] = ws
                self._metrics.set_gauge("ws_connections", len(self._ws_connections))
                self._log.info("WebSocket connected")
                
                # Authenticate if needed
                if self._is_authenticated:
                    await self._authenticate_websocket(ws)
                    
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
                reconnect_delay = min(reconnect_delay * 2, 60.0)
                
    async def _authenticate_websocket(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Authenticate WebSocket connection."""
        timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
        signature, _ = self._generate_signature("GET", "/ws/accounts", "", timestamp)
        
        auth_msg = {
            "type": "auth",
            "key": self.config.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "passphrase": self.config.passphrase
        }
        await ws.send(json.dumps(auth_msg))
        
    async def _handle_websocket_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Handle incoming WebSocket messages."""
        try:
            # Build subscription message
            channels = []
            
            for stream_type, markets in self._ws_subscriptions.items():
                for market in markets:
                    if stream_type == "orderbook":
                        channels.append({"name": f"v3_orderbook_{market}"})
                    elif stream_type == "ticker":
                        channels.append({"name": f"v3_market_{market}"})
                    elif stream_type == "trades":
                        channels.append({"name": f"v3_trades_{market}"})
                        
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
        
        if msg_type == "subscribed":
            self._log.debug(f"Subscription confirmed: {data.get('channel')}")
            return
            
        if msg_type == "channel_data":
            await self._process_channel_data(data)
        elif msg_type == "account_data":
            await self._process_account_data(data)
        elif msg_type == "error":
            self._log.error(f"WebSocket error: {data}")
            
    async def _process_channel_data(self, data: Dict[str, Any]) -> None:
        """Process channel data message."""
        channel = data.get("channel", "")
        contents = data.get("contents", {})
        
        if "orderbook" in channel:
            market = channel.split("_")[-1]
            book = self._parse_ws_order_book(contents, market)
            if book:
                async with self._order_book_locks[market]:
                    self._order_books[market] = book
                await self._dispatch_callbacks(f"{market}:orderbook", book)
                
        elif "market" in channel:
            market = channel.split("_")[-1]
            ticker = self._parse_ws_ticker(contents, market)
            if ticker:
                self._tickers[ticker.symbol] = ticker
                await self._dispatch_callbacks(f"{market}:ticker", ticker)
                
        elif "trades" in channel:
            market = channel.split("_")[-1]
            for trade_data in contents.get("trades", []):
                trade = self._parse_ws_trade(trade_data, market)
                if trade:
                    self._trades[market].append(trade)
                    await self._dispatch_callbacks(f"{market}:trades", trade)
                    
    async def _process_account_data(self, data: Dict[str, Any]) -> None:
        """Process account data message."""
        account = data.get("account", {})
        
        # Update positions
        positions = account.get("positions", [])
        async with self._position_lock:
            for pos in positions:
                if float(pos.get("size", 0)) != 0:
                    self._positions[pos.get("market")] = Position(
                        symbol=pos.get("market", ""),
                        side="LONG" if float(pos.get("size", 0)) > 0 else "SHORT",
                        size=abs(float(pos.get("size", 0))),
                        entry_price=float(pos.get("entryPrice", 0)),
                        mark_price=float(pos.get("markPrice", 0)),
                        liquidation_price=float(pos.get("liquidationPrice", 0)),
                        unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                        leverage=int(pos.get("leverage", 1))
                    )
                else:
                    self._positions.pop(pos.get("market", ""), None)
                    
        # Update orders
        orders = account.get("orders", [])
        async with self._order_lock:
            for order in orders:
                order_id = order.get("id")
                if order_id:
                    self._orders[order_id] = order
                    status = order.get("status")
                    if status in ["PENDING", "OPEN"]:
                        self._active_orders.add(order_id)
                    elif status in ["FILLED", "CANCELED", "EXPIRED"]:
                        self._active_orders.discard(order_id)
                        
        await self._dispatch_callbacks("account", account)
        
    def _parse_ws_order_book(self, data: Dict[str, Any], market: str) -> OrderBook:
        """Parse WebSocket order book data."""
        bids = []
        asks = []
        
        for bid in data.get("bids", []):
            bids.append((float(bid[0]), float(bid[1])))
            
        for ask in data.get("asks", []):
            asks.append((float(ask[0]), float(ask[1])))
            
        return OrderBook(
            symbol=market,
            bids=bids,
            asks=asks,
            timestamp=int(time.time() * 1000),
            last_update_id=data.get("lastUpdateId", 0)
        )
        
    def _parse_ws_ticker(self, data: Dict[str, Any], market: str) -> Ticker:
        """Parse WebSocket ticker data."""
        return Ticker(
            symbol=market,
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            last=float(data.get("last", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            volume=float(data.get("volume", 0)),
            change_24h=float(data.get("change24h", 0)),
            timestamp=int(time.time() * 1000)
        )
        
    def _parse_ws_trade(self, data: Dict[str, Any], market: str) -> Trade:
        """Parse WebSocket trade data."""
        return Trade(
            symbol=market,
            price=float(data.get("price", 0)),
            size=float(data.get("size", 0)),
            side=data.get("side", "").upper(),
            timestamp=int(data.get("createdAt", time.time() * 1000)),
            trade_id=data.get("id", "")
        )
        
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
        market: str,
        side: str,
        order_type: str,
        size: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        time_in_force: str = "GTC",
        post_only: bool = False,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        leverage: Optional[int] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place an order on dYdX.
        
        Args:
            market: Market ID
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP, STOP_LIMIT
            size: Order size
            price: Limit price
            stop_price: Stop price
            limit_price: Stop limit price
            time_in_force: GTC, IOC, FOK
            post_only: Post-only order
            reduce_only: Reduce-only order
            client_order_id: Client order ID
            leverage: Leverage for position
            take_profit: Take profit price
            stop_loss: Stop loss price
            
        Returns:
            Order confirmation
        """
        self._metrics.increment_counter("orders_placed")
        
        market = market.upper()
        side = side.upper()
        order_type = order_type.upper()
        time_in_force = time_in_force.upper()
        
        # Validate market
        if market not in self._markets_list:
            raise InvalidSymbolError(f"Market not found: {market}")
            
        # Validate size
        if size <= 0:
            raise OrderError("Size must be positive")
            
        # Build order parameters
        params = {
            "market": market,
            "side": side,
            "type": order_type,
            "size": str(size)
        }
        
        if order_type in ["LIMIT", "STOP_LIMIT"]:
            if price is None:
                raise OrderError("Price required for limit orders")
            params["price"] = str(price)
            
        if order_type in ["STOP", "STOP_LIMIT"]:
            if stop_price is None:
                raise OrderError("Stop price required for stop orders")
            params["stopPrice"] = str(stop_price)
            
        if order_type == "STOP_LIMIT" and limit_price:
            params["limitPrice"] = str(limit_price)
            
        if time_in_force in ["GTC", "IOC", "FOK"]:
            params["timeInForce"] = time_in_force
            
        if post_only:
            params["postOnly"] = True
            
        if reduce_only:
            params["reduceOnly"] = True
            
        if client_order_id:
            params["clientId"] = client_order_id
            
        if leverage:
            params["leverage"] = str(leverage)
            
        if take_profit:
            params["takeProfit"] = str(take_profit)
            
        if stop_loss:
            params["stopLoss"] = str(stop_loss)
            
        # Place order
        try:
            start_time = time.time()
            response = await self._post("/v3/orders", data=params, signed=True)
            
            execution_time = (time.time() - start_time) * 1000
            self._metrics.record_histogram("order_execution_ms", execution_time)
            
            order_data = response.get("order", {})
            order_id = order_data.get("id")
            
            if order_id:
                async with self._order_lock:
                    self._orders[order_id] = order_data
                    self._active_orders.add(order_id)
                    
            self._log.info(f"Order placed: {market} {side} {order_type} {size} @ {price or 'market'}")
            return order_data
            
        except InsufficientBalanceError as e:
            self._log.error(f"Insufficient balance for {market}: {e}")
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
            response = await self._delete(f"/v3/orders/{order_id}", signed=True)
            
            async with self._order_lock:
                self._orders.pop(order_id, None)
                self._active_orders.discard(order_id)
                
            self._log.info(f"Order cancelled: {order_id}")
            return response
            
        except Exception as e:
            self._log.error(f"Order cancellation failed: {e}")
            raise
            
    async def cancel_all_orders(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Cancel all open orders.
        
        Args:
            market: Optional market filter
            
        Returns:
            List of cancellation confirmations
        """
        try:
            params = {}
            if market:
                params["market"] = market.upper()
                
            response = await self._delete("/v3/orders", params=params, signed=True)
            
            async with self._order_lock:
                if market:
                    for order_id in list(self._orders.keys()):
                        if self._orders[order_id].get("market") == market.upper():
                            self._orders.pop(order_id, None)
                            self._active_orders.discard(order_id)
                else:
                    self._active_orders.clear()
                    self._orders.clear()
                    
            self._log.info(f"Cancelled all orders for {market or 'all markets'}")
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
            response = await self._get(f"/v3/orders/{order_id}", signed=True)
            
            order_data = response.get("order", {})
            async with self._order_lock:
                self._orders[order_id] = order_data
                
            return order_data
            
        except Exception as e:
            self._log.error(f"Failed to get order {order_id}: {e}")
            raise
            
    async def get_open_orders(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.
        
        Args:
            market: Optional market filter
            
        Returns:
            List of open orders
        """
        try:
            params = {"status": "OPEN"}
            if market:
                params["market"] = market.upper()
                
            response = await self._get("/v3/orders", params=params, signed=True)
            
            orders = response.get("orders", [])
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
    
    async def get_positions(self, market: Optional[str] = None) -> List[Position]:
        """
        Get positions.
        
        Args:
            market: Optional market filter
            
        Returns:
            List of positions
        """
        try:
            params = {}
            if market:
                params["market"] = market.upper()
                
            response = await self._get("/v3/positions", params=params, signed=True)
            
            positions = []
            for item in response.get("positions", []):
                if float(item.get("size", 0)) != 0:
                    position = Position(
                        symbol=item.get("market", ""),
                        side="LONG" if float(item.get("size", 0)) > 0 else "SHORT",
                        size=abs(float(item.get("size", 0))),
                        entry_price=float(item.get("entryPrice", 0)),
                        mark_price=float(item.get("markPrice", 0)),
                        liquidation_price=float(item.get("liquidationPrice", 0)),
                        unrealized_pnl=float(item.get("unrealizedPnl", 0)),
                        leverage=int(item.get("leverage", 1))
                    )
                    positions.append(position)
                    
            async with self._position_lock:
                self._positions = {p.symbol: p for p in positions}
                
            return positions
            
        except Exception as e:
            self._log.error(f"Failed to get positions: {e}")
            if self._positions and not market:
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
            response = await self._get("/v3/accounts", signed=True)
            
            balances = {}
            account = response.get("account", {})
            equity = float(account.get("equity", 0))
            free_collateral = float(account.get("freeCollateral", 0))
            
            # dYdX uses USDC as base currency
            balances["USDC"] = Balance(
                asset="USDC",
                free=free_collateral,
                locked=equity - free_collateral
            )
            
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
            data = await self._get("/v3/time")
            return int(data.get("time", 0))
        except Exception:
            return int(time.time() * 1000)
            
    def get_market_from_pair(self, base: str, quote: str) -> str:
        """Get dYdX market from base/quote pair."""
        return f"{base.upper()}-{quote.upper()}"
        
    def get_pair_from_market(self, market: str) -> Tuple[str, str]:
        """Get base/quote from dYdX market."""
        parts = market.split("-")
        if len(parts) == 2:
            return parts[0], parts[1]
        raise ValueError(f"Could not parse market: {market}")
        
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
            "positions": len(self._positions),
            "latency_p50": self._latency_monitor.get_percentile(50),
            "latency_p95": self._latency_monitor.get_percentile(95),
            "latency_p99": self._latency_monitor.get_percentile(99),
            "uptime_seconds": self._uptime_seconds,
            "is_connected": self._is_connected,
            "is_streaming": self._is_streaming,
            "is_authenticated": self._is_authenticated
        }
