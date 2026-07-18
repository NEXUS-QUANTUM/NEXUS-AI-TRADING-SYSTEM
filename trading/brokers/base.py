# trading/brokers/base.py
"""
NEXUS AI TRADING SYSTEM - Base Broker Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides the abstract base class for all broker integrations.
All broker implementations must inherit from this class and implement
all abstract methods to ensure consistent behavior across the system.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import requests
from pydantic import BaseModel, Field, validator

from shared.types.common import OrderSide, OrderStatus, OrderType, TimeInForce
from shared.types.trading import Order, Position, AccountBalance, MarketData, Trade
from shared.utilities.retry import RetryConfig, retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.rate_limiter import RateLimiter

logger = get_logger(__name__)


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class BrokerName(str, Enum):
    """Supported broker names"""
    ALPACA = "alpaca"
    BINANCE = "binance"
    BINANCE_US = "binance_us"
    BYBIT = "bybit"
    COINBASE = "coinbase"
    COINBASE_PRO = "coinbase_pro"
    FTX = "ftx"
    KRAKEN = "kraken"
    KUCOIN = "kucoin"
    OANDA = "oanda"
    IBKR = "ibkr"
    TRADIER = "tradier"
    TRADESTATION = "tradestation"
    SCHWAB = "schwab"
    FIDELITY = "fidelity"
    ETORO = "etoro"
    INTERACTIVE_BROKERS = "interactive_brokers"
    WEBHOOK = "webhook"
    PAPER = "paper"


class AssetClass(str, Enum):
    """Asset classes supported by the trading system"""
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"
    ETF = "etf"
    FUTURES = "futures"
    OPTIONS = "options"
    COMMODITY = "commodity"
    INDEX = "index"
    BOND = "bond"


class AccountType(str, Enum):
    """Account types"""
    LIVE = "live"
    PAPER = "paper"
    DEMO = "demo"
    BACKTEST = "backtest"


class OrderResponse(BaseModel):
    """Standardized order response from broker"""
    order_id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    time_in_force: TimeInForce
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    broker_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class AccountInfo(BaseModel):
    """Standardized account information"""
    account_id: str
    account_type: AccountType = AccountType.LIVE
    status: str = "active"
    currency: str = "USD"
    buying_power: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    cash: Decimal = Decimal("0")
    margin_used: Decimal = Decimal("0")
    margin_available: Decimal = Decimal("0")
    maintenance_margin: Decimal = Decimal("0")
    initial_margin: Decimal = Decimal("0")
    day_trading_buying_power: Decimal = Decimal("0")
    open_positions_count: int = 0
    open_orders_count: int = 0
    broker_data: Dict[str, Any] = Field(default_factory=dict)


class MarketDataResponse(BaseModel):
    """Standardized market data response"""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    open: Optional[Decimal] = None
    close: Optional[Decimal] = None
    previous_close: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    broker_data: Dict[str, Any] = Field(default_factory=dict)


class BrokerConfig(BaseModel):
    """Base configuration for broker connections"""
    broker_name: BrokerName
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None  # Used by some exchanges (e.g., Coinbase, OKX)
    sandbox_mode: bool = True
    account_type: AccountType = AccountType.PAPER
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_per_second: Optional[int] = None
    base_url: Optional[str] = None
    websocket_url: Optional[str] = None
    use_ssl_verification: bool = True
    extra_params: Dict[str, Any] = Field(default_factory=dict)

    @validator("api_key", pre=True)
    def validate_api_key(cls, v, values):
        """Validate that API key is present for non-paper trading"""
        if values.get("broker_name") != BrokerName.PAPER:
            if not v:
                raise ValueError(f"API key is required for {values.get('broker_name')}")
        return v

    @validator("api_secret", pre=True)
    def validate_api_secret(cls, v, values):
        """Validate that API secret is present for non-paper trading"""
        if values.get("broker_name") != BrokerName.PAPER:
            if not v:
                raise ValueError(f"API secret is required for {values.get('broker_name')}")
        return v


# ============================================================================
# EXCEPTIONS
# ============================================================================

class BrokerException(Exception):
    """Base exception for broker-related errors"""
    def __init__(self, message: str, code: Optional[str] = None, data: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(message)


class BrokerConnectionError(BrokerException):
    """Raised when connection to broker fails"""
    pass


class BrokerAuthenticationError(BrokerException):
    """Raised when authentication with broker fails"""
    pass


class BrokerRateLimitError(BrokerException):
    """Raised when rate limit is exceeded"""
    pass


class BrokerOrderError(BrokerException):
    """Raised when order operations fail"""
    pass


class BrokerDataError(BrokerException):
    """Raised when data operations fail"""
    pass


class BrokerTimeoutError(BrokerException):
    """Raised when broker request times out"""
    pass


# ============================================================================
# BASE BROKER CLASS
# ============================================================================

class BaseBroker(ABC):
    """
    Abstract base class for all broker integrations.
    
    All broker implementations must inherit from this class and implement
    all abstract methods. This ensures consistent behavior across all
    broker connections and allows the system to switch between brokers
    seamlessly.
    
    Features:
    - Rate limiting to respect broker API limits
    - Circuit breaker pattern to prevent cascading failures
    - Automatic retry with exponential backoff
    - Standardized request/response formatting
    - Comprehensive error handling and logging
    - Support for both REST and WebSocket APIs
    """
    
    def __init__(
        self,
        config: BrokerConfig,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize the broker connection.
        
        Args:
            config: Broker configuration
            session: Optional aiohttp session (creates new if not provided)
        """
        self.config = config
        self._session = session
        self._is_connected = False
        self._rate_limiter: Optional[RateLimiter] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._last_request_time: float = 0.0
        self._request_counter: int = 0
        self._metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "last_error": None,
            "uptime": 0,
        }
        
        # Setup rate limiter if configured
        if config.rate_limit_per_second:
            self._rate_limiter = RateLimiter(
                rate=config.rate_limit_per_second,
                time_window=1.0,
            )
        
        # Setup circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=3,
        )
        
        self.logger = logger
        
    # ========================================================================
    # PROPERTIES
    # ========================================================================
    
    @property
    def name(self) -> BrokerName:
        """Get broker name"""
        return self.config.broker_name
    
    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox mode"""
        return self.config.sandbox_mode
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self._is_connected
    
    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session
    
    # ========================================================================
    # ABSTRACT METHODS - Must be implemented by concrete brokers
    # ========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the broker.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the broker.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """
        Get account information from broker.
        
        Returns:
            AccountInfo: Standardized account information
        """
        pass
    
    @abstractmethod
    async def get_balances(self) -> List[AccountBalance]:
        """
        Get account balances from broker.
        
        Returns:
            List[AccountBalance]: List of balances for all assets
        """
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketDataResponse:
        """
        Get current market data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., BTC/USD, AAPL)
            
        Returns:
            MarketDataResponse: Standardized market data
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResponse:
        """
        Place an order with the broker.
        
        Args:
            order: Order object containing order details
            
        Returns:
            OrderResponse: Standardized order response
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            symbol: Symbol of the order (required by some brokers)
            
        Returns:
            bool: True if cancellation successful
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> OrderResponse:
        """
        Get order details from broker.
        
        Args:
            order_id: ID of the order
            symbol: Symbol of the order (required by some brokers)
            
        Returns:
            OrderResponse: Standardized order response
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        """
        Get all open orders from broker.
        
        Args:
            symbol: Optional symbol to filter orders
            
        Returns:
            List[OrderResponse]: List of open orders
        """
        pass
    
    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get all open positions from broker.
        
        Args:
            symbol: Optional symbol to filter positions
            
        Returns:
            List[Position]: List of open positions
        """
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> bool:
        """
        Close an open position.
        
        Args:
            symbol: Symbol of the position to close
            
        Returns:
            bool: True if position closed successfully
        """
        pass
    
    @abstractmethod
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """
        Get trade history from broker.
        
        Args:
            symbol: Optional symbol to filter trades
            limit: Maximum number of trades to return
            
        Returns:
            List[Trade]: List of trades
        """
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MarketData]:
        """
        Get historical market data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d, etc.)
            limit: Maximum number of candles
            start_time: Start time for data
            end_time: End time for data
            
        Returns:
            List[MarketData]: List of historical market data
        """
        pass
    
    @abstractmethod
    async def get_websocket_url(self) -> str:
        """
        Get WebSocket URL for real-time data.
        
        Returns:
            str: WebSocket URL
        """
        pass
    
    @abstractmethod
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        callback: callable,
    ) -> bool:
        """
        Subscribe to real-time market data via WebSocket.
        
        Args:
            symbols: List of symbols to subscribe to
            callback: Async callback function for data updates
            
        Returns:
            bool: True if subscription successful
        """
        pass
    
    @abstractmethod
    async def unsubscribe_from_market_data(
        self,
        symbols: List[str],
    ) -> bool:
        """
        Unsubscribe from real-time market data.
        
        Args:
            symbols: List of symbols to unsubscribe from
            
        Returns:
            bool: True if unsubscription successful
        """
        pass
    
    # ========================================================================
    # CONVENIENCE METHODS
    # ========================================================================
    
    async def market_buy(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a market buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to buy
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def market_sell(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a market sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def limit_buy(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        price: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a limit buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to buy
            price: Limit price
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            price=Decimal(str(price)) if not isinstance(price, Decimal) else price,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def limit_sell(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        price: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a limit sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            price: Limit price
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            price=Decimal(str(price)) if not isinstance(price, Decimal) else price,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def stop_loss_buy(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        stop_price: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a stop-loss buy order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to buy
            stop_price: Stop price
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.STOP_LOSS,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            stop_price=Decimal(str(stop_price)) if not isinstance(stop_price, Decimal) else stop_price,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def stop_loss_sell(
        self,
        symbol: str,
        quantity: Union[Decimal, float],
        stop_price: Union[Decimal, float],
        **kwargs,
    ) -> OrderResponse:
        """
        Place a stop-loss sell order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            stop_price: Stop price
            **kwargs: Additional order parameters
            
        Returns:
            OrderResponse: Standardized order response
        """
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            quantity=Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity,
            stop_price=Decimal(str(stop_price)) if not isinstance(stop_price, Decimal) else stop_price,
            **kwargs,
        )
        return await self.place_order(order)
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        """
        Cancel all open orders.
        
        Args:
            symbol: Optional symbol to cancel orders for
            
        Returns:
            bool: True if all orders cancelled successfully
        """
        try:
            orders = await self.get_open_orders(symbol)
            for order in orders:
                await self.cancel_order(order.order_id, symbol=order.symbol)
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders: {e}")
            return False
    
    async def close_all_positions(self) -> bool:
        """
        Close all open positions.
        
        Returns:
            bool: True if all positions closed successfully
        """
        try:
            positions = await self.get_positions()
            for position in positions:
                await self.close_position(position.symbol)
            return True
        except Exception as e:
            self.logger.error(f"Failed to close all positions: {e}")
            return False
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _generate_client_order_id(self) -> str:
        """
        Generate a unique client order ID.
        
        Returns:
            str: Unique client order ID
        """
        timestamp = int(time.time() * 1000)
        random_part = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"nexus-{timestamp}-{random_part}"
    
    def _sign_request(self, data: str, secret: str) -> str:
        """
        Sign a request using HMAC-SHA256.
        
        Args:
            data: Data to sign
            secret: Secret key
            
        Returns:
            str: HMAC-SHA256 signature in hex format
        """
        return hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    
    def _format_symbo(self, symbol: str) -> str:
        """
        Format symbol according to broker's requirements.
        Override this in concrete implementations.
        
        Args:
            symbol: Raw symbol
            
        Returns:
            str: Formatted symbol
        """
        return symbol
    
    def _format_quantity(self, quantity: Decimal) -> Union[str, Decimal]:
        """
        Format quantity according to broker's requirements.
        Override this in concrete implementations.
        
        Args:
            quantity: Raw quantity
            
        Returns:
            Union[str, Decimal]: Formatted quantity
        """
        return quantity
    
    def _format_price(self, price: Decimal) -> Union[str, Decimal]:
        """
        Format price according to broker's requirements.
        Override this in concrete implementations.
        
        Args:
            price: Raw price
            
        Returns:
            Union[str, Decimal]: Formatted price
        """
        return price
    
    # ========================================================================
    # REQUEST HANDLING WITH RATE LIMITING, RETRY, AND CIRCUIT BREAKER
    # ========================================================================
    
    @retry_async(
        config=RetryConfig(
            max_attempts=3,
            delay=1.0,
            backoff=2.0,
            max_delay=30.0,
            retry_on_exceptions=(BrokerTimeoutError, aiohttp.ClientError),
        )
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        is_authenticated: bool = True,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the broker API with rate limiting and circuit breaker.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            headers: Request headers
            is_authenticated: Whether to add authentication headers
            timeout: Request timeout in seconds
            
        Returns:
            Dict: Response data
            
        Raises:
            BrokerConnectionError: If connection fails
            BrokerAuthenticationError: If authentication fails
            BrokerRateLimitError: If rate limit is exceeded
            BrokerTimeoutError: If request times out
            BrokerException: For other errors
        """
        # Check circuit breaker
        if not self._circuit_breaker.is_available():
            raise BrokerException("Circuit breaker is open - service unavailable")
        
        # Apply rate limiting
        if self._rate_limiter:
            await self._rate_limiter.acquire()
        
        # Build URL
        base_url = self.config.base_url
        if not base_url:
            raise BrokerException(f"No base URL configured for {self.config.broker_name}")
        
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Build headers
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        
        # Add authentication
        if is_authenticated:
            self._add_auth_headers(request_headers, method, endpoint, data)
        
        # Set timeout
        request_timeout = timeout or self.config.timeout
        
        self._metrics["requests_total"] += 1
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=request_timeout),
            ) as response:
                # Handle response
                response_data = await self._handle_response(response)
                
                # Record success
                self._metrics["requests_success"] += 1
                self._circuit_breaker.record_success()
                
                return response_data
                
        except aiohttp.ClientTimeout:
            self._metrics["requests_failed"] += 1
            self._circuit_breaker.record_failure()
            raise BrokerTimeoutError(f"Request to {url} timed out after {request_timeout}s")
            
        except aiohttp.ClientError as e:
            self._metrics["requests_failed"] += 1
            self._circuit_breaker.record_failure()
            raise BrokerConnectionError(f"Connection error: {str(e)}")
            
        except Exception as e:
            self._metrics["requests_failed"] += 1
            self._circuit_breaker.record_failure()
            raise BrokerException(f"Request failed: {str(e)}")
    
    @abstractmethod
    def _add_auth_headers(
        self,
        headers: Dict[str, str],
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> None:
        """
        Add authentication headers to the request.
        Each broker implementation must override this.
        
        Args:
            headers: Headers dict to modify
            method: HTTP method
            endpoint: API endpoint
            data: Request data
        """
        pass
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """
        Handle HTTP response from broker.
        
        Args:
            response: aiohttp response object
            
        Returns:
            Dict: Parsed response data
            
        Raises:
            BrokerException: If response indicates an error
        """
        try:
            data = await response.json()
        except aiohttp.ContentTypeError:
            text = await response.text()
            data = {"raw": text}
        
        if response.status >= 400:
            error_msg = data.get("error", data.get("message", data.get("msg", "Unknown error")))
            
            if response.status == 401:
                raise BrokerAuthenticationError(f"Authentication failed: {error_msg}")
            elif response.status == 429:
                raise BrokerRateLimitError(f"Rate limit exceeded: {error_msg}")
            elif response.status >= 500:
                raise BrokerException(f"Broker server error ({response.status}): {error_msg}")
            else:
                raise BrokerException(f"Broker error ({response.status}): {error_msg}")
        
        return data
    
    # ========================================================================
    # HEALTH & MONITORING
    # ========================================================================
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the broker connection.
        
        Returns:
            Dict: Health status and metrics
        """
        try:
            # Try to get account info as health check
            await self.get_account_info()
            status = "healthy"
        except Exception as e:
            status = "unhealthy"
        
        return {
            "broker": self.config.broker_name.value,
            "sandbox": self.is_sandbox,
            "connected": self.is_connected,
            "status": status,
            "metrics": self._metrics,
            "circuit_breaker": {
                "available": self._circuit_breaker.is_available(),
                "state": self._circuit_breaker.state,
            },
            "rate_limiter": {
                "enabled": self._rate_limiter is not None,
            },
        }
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
        if self._session:
            await self._session.close()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(broker={self.config.broker_name.value}, sandbox={self.is_sandbox})>"


# ============================================================================
# WEBHOOK BROKER (For signal-based trading)
# ============================================================================

class WebhookBroker(BaseBroker):
    """
    Webhook-based broker implementation for receiving signals from external systems.
    This allows the trading system to execute trades based on webhook triggers
    from other platforms, signal providers, or custom integrations.
    """
    
    def __init__(self, config: BrokerConfig, session: Optional[aiohttp.ClientSession] = None):
        super().__init__(config, session)
        self._webhook_url = config.extra_params.get("webhook_url")
        self._webhook_secret = config.extra_params.get("webhook_secret")
    
    async def connect(self) -> bool:
        self._is_connected = True
        return True
    
    async def disconnect(self) -> bool:
        self._is_connected = False
        return True
    
    async def get_account_info(self) -> AccountInfo:
        # Webhook broker doesn't have account info
        return AccountInfo(
            account_id="webhook",
            account_type=AccountType.LIVE,
            buying_power=Decimal("0"),
            equity=Decimal("0"),
            cash=Decimal("0"),
        )
    
    async def get_balances(self) -> List[AccountBalance]:
        return []
    
    async def get_market_data(self, symbol: str) -> MarketDataResponse:
        raise BrokerDataError("Market data not available via webhook broker")
    
    async def place_order(self, order: Order) -> OrderResponse:
        """Send order via webhook"""
        if not self._webhook_url:
            raise BrokerException("Webhook URL not configured")
        
        # Build webhook payload
        payload = {
            "order": {
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": str(order.quantity),
                "price": str(order.price) if order.price else None,
                "stop_price": str(order.stop_price) if order.stop_price else None,
                "time_in_force": order.time_in_force.value,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Sign webhook payload if secret is configured
        if self._webhook_secret:
            payload["signature"] = self._sign_request(
                json.dumps(payload["order"], sort_keys=True),
                self._webhook_secret,
            )
        
        # Send webhook
        try:
            async with self.session.post(
                self._webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise BrokerOrderError(f"Webhook failed: {response.status} - {error_text}")
                
                response_data = await response.json()
                
                return OrderResponse(
                    order_id=response_data.get("order_id", f"webhook-{int(time.time())}"),
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price,
                    stop_price=order.stop_price,
                    time_in_force=order.time_in_force,
                    status=OrderStatus.PLACED,
                    filled_quantity=Decimal("0"),
                    remaining_quantity=order.quantity,
                    created_at=datetime.utcnow(),
                    broker_data=response_data,
                )
                
        except aiohttp.ClientError as e:
            raise BrokerConnectionError(f"Webhook connection error: {str(e)}")
        except Exception as e:
            raise BrokerOrderError(f"Webhook order failed: {str(e)}")
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        return True
    
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> OrderResponse:
        raise BrokerDataError("Order status not available via webhook broker")
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        return []
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        return []
    
    async def close_position(self, symbol: str) -> bool:
        return True
    
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        return []
    
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MarketData]:
        return []
    
    async def get_websocket_url(self) -> str:
        raise BrokerDataError("WebSocket not available for webhook broker")
    
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        callback: callable,
    ) -> bool:
        return False
    
    async def unsubscribe_from_market_data(
        self,
        symbols: List[str],
    ) -> bool:
        return False
    
    def _add_auth_headers(self, headers: Dict[str, str], method: str, endpoint: str, data: Optional[Dict] = None) -> None:
        pass


# ============================================================================
# PAPER TRADING BROKER (For simulation/testing)
# ============================================================================

class PaperBroker(BaseBroker):
    """
    Paper trading broker implementation for simulation and testing.
    This allows the system to simulate trading without real money.
    """
    
    def __init__(self, config: BrokerConfig, session: Optional[aiohttp.ClientSession] = None):
        super().__init__(config, session)
        self._orders: Dict[str, OrderResponse] = {}
        self._positions: Dict[str, Position] = {}
        self._trades: List[Trade] = []
        self._balances: Dict[str, AccountBalance] = {}
        self._initial_balance = Decimal("100000.00")  # Default paper balance
        
    async def connect(self) -> bool:
        self._is_connected = True
        self._balances = {
            "USD": AccountBalance(
                asset="USD",
                free=Decimal("100000.00"),
                locked=Decimal("0"),
                total=Decimal("100000.00"),
            )
        }
        return True
    
    async def disconnect(self) -> bool:
        self._is_connected = False
        return True
    
    async def get_account_info(self) -> AccountInfo:
        total_equity = self._balances.get("USD", AccountBalance(
            asset="USD",
            free=Decimal("0"),
            locked=Decimal("0"),
            total=Decimal("0"),
        )).total
        
        return AccountInfo(
            account_id="paper",
            account_type=AccountType.PAPER,
            buying_power=total_equity * Decimal("2"),  # 2x leverage for paper
            equity=total_equity,
            cash=total_equity,
            open_positions_count=len(self._positions),
            open_orders_count=len([o for o in self._orders.values() if o.status in [OrderStatus.PLACED, OrderStatus.PARTIALLY_FILLED]]),
        )
    
    async def get_balances(self) -> List[AccountBalance]:
        return list(self._balances.values())
    
    async def get_market_data(self, symbol: str) -> MarketDataResponse:
        # Use mock data or integrate with a data provider
        raise BrokerDataError("Market data not available in paper broker - use MarketDataService instead")
    
    async def place_order(self, order: Order) -> OrderResponse:
        """Place a paper order"""
        # Validate order
        if order.quantity <= 0:
            raise BrokerOrderError("Order quantity must be positive")
        
        # Check balance
        if order.side == OrderSide.BUY:
            required = order.quantity * (order.price or Decimal("0"))
            balance = self._balances.get("USD", AccountBalance(asset="USD", free=Decimal("0"), locked=Decimal("0"), total=Decimal("0")))
            if balance.free < required:
                raise BrokerOrderError(f"Insufficient balance: {balance.free} < {required}")
        
        # Create order response
        order_id = f"paper-{int(time.time() * 1000)}"
        created_at = datetime.utcnow()
        
        order_response = OrderResponse(
            order_id=order_id,
            client_order_id=order.client_order_id or self._generate_client_order_id(),
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            stop_price=order.stop_price,
            time_in_force=order.time_in_force,
            status=OrderStatus.PLACED,
            filled_quantity=Decimal("0"),
            remaining_quantity=order.quantity,
            created_at=created_at,
            broker_data={"paper": True},
        )
        
        self._orders[order_id] = order_response
        return order_response
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False
    
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> OrderResponse:
        if order_id not in self._orders:
            raise BrokerOrderError(f"Order {order_id} not found")
        return self._orders[order_id]
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        return [
            o for o in self._orders.values()
            if o.status in [OrderStatus.PLACED, OrderStatus.PARTIALLY_FILLED]
            and (symbol is None or o.symbol == symbol)
        ]
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        positions = list(self._positions.values())
        if symbol:
            return [p for p in positions if p.symbol == symbol]
        return positions
    
    async def close_position(self, symbol: str) -> bool:
        if symbol in self._positions:
            del self._positions[symbol]
            return True
        return False
    
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Trade]:
        trades = self._trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        return trades[:limit]
    
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MarketData]:
        # Use mock data or integrate with a data provider
        return []
    
    async def get_websocket_url(self) -> str:
        return ""
    
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        callback: callable,
    ) -> bool:
        return False
    
    async def unsubscribe_from_market_data(
        self,
        symbols: List[str],
    ) -> bool:
        return False
    
    def _add_auth_headers(self, headers: Dict[str, str], method: str, endpoint: str, data: Optional[Dict] = None) -> None:
        pass


# ============================================================================
# BROKER FACTORY
# ============================================================================

class BrokerFactory:
    """
    Factory class for creating broker instances.
    This centralizes broker creation and configuration.
    """
    
    _brokers: Dict[BrokerName, type] = {}
    
    @classmethod
    def register(cls, broker_name: BrokerName, broker_class: type):
        """
        Register a broker class with the factory.
        
        Args:
            broker_name: Name of the broker
            broker_class: Broker class to register
        """
        cls._brokers[broker_name] = broker_class
    
    @classmethod
    def get_broker(cls, config: BrokerConfig, session: Optional[aiohttp.ClientSession] = None) -> BaseBroker:
        """
        Create a broker instance based on configuration.
        
        Args:
            config: Broker configuration
            session: Optional aiohttp session
            
        Returns:
            BaseBroker: Broker instance
            
        Raises:
            ValueError: If broker is not registered
        """
        # Handle paper trading and webhook specially
        if config.broker_name == BrokerName.PAPER:
            return PaperBroker(config, session)
        
        if config.broker_name == BrokerName.WEBHOOK:
            return WebhookBroker(config, session)
        
        # Get registered broker class
        broker_class = cls._brokers.get(config.broker_name)
        if not broker_class:
            raise ValueError(f"Broker {config.broker_name} not registered")
        
        return broker_class(config, session)
    
    @classmethod
    def list_brokers(cls) -> List[BrokerName]:
        """
        List all registered brokers.
        
        Returns:
            List[BrokerName]: List of registered broker names
        """
        return list(cls._brokers.keys())
    
    @classmethod
    def is_supported(cls, broker_name: BrokerName) -> bool:
        """
        Check if a broker is supported.
        
        Args:
            broker_name: Name of the broker
            
        Returns:
            bool: True if broker is registered
        """
        return broker_name in cls._brokers or broker_name in (BrokerName.PAPER, BrokerName.WEBHOOK)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "BrokerName",
    "AssetClass",
    "AccountType",
    
    # Models
    "BrokerConfig",
    "OrderResponse",
    "AccountInfo",
    "MarketDataResponse",
    
    # Exceptions
    "BrokerException",
    "BrokerConnectionError",
    "BrokerAuthenticationError",
    "BrokerRateLimitError",
    "BrokerOrderError",
    "BrokerDataError",
    "BrokerTimeoutError",
    
    # Base classes
    "BaseBroker",
    "WebhookBroker",
    "PaperBroker",
    
    # Factory
    "BrokerFactory",
]
