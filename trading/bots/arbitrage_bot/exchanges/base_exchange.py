# trading/bots/arbitrage_bot/exchanges/base_exchange.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Base Exchange Interface

"""
Base Exchange Interface - Abstract Base Class for All Exchange Integrations

This module provides the abstract base class for all exchange integrations
in the NEXUS AI Trading System. It defines the standard interface that
all exchange adapters must implement.

Architecture:
    - BaseExchange: Abstract base class
    - ExchangeType: Exchange type enumeration
    - OrderType: Order type enumeration
    - OrderSide: Order side enumeration
    - OrderStatus: Order status enumeration
    - ExchangeConfig: Configuration dataclass
    - Order: Order dataclass
    - Balance: Balance dataclass
    - MarketData: Market data dataclass
    - Ticker: Ticker dataclass
    - OHLCV: OHLCV dataclass

Exchange Adapters:
    - Binance
    - Bybit
    - Coinbase
    - Kraken
    - OKX
    - Alpaca
    - Interactive Brokers
    - OANDA
    - DEX (Uniswap, PancakeSwap, etc.)
    - 1inch
    - Balancer
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Callable,
    AsyncIterator,
    TypeVar,
    Generic,
    Protocol,
    runtime_checkable,
)


# Enums
class ExchangeType(Enum):
    """Exchange type enumeration."""
    BINANCE = "binance"
    BINANCE_FUTURES = "binance_futures"
    BYBIT = "bybit"
    BYBIT_FUTURES = "bybit_futures"
    COINBASE = "coinbase"
    COINBASE_FUTURES = "coinbase_futures"
    KRAKEN = "kraken"
    KRAKEN_FUTURES = "kraken_futures"
    OKX = "okx"
    OKX_FUTURES = "okx_futures"
    ALPACA = "alpaca"
    IBKR = "interactive_brokers"
    OANDA = "oanda"
    UNISWAP = "uniswap"
    PANCAKESWAP = "pancakeswap"
    SUSHISWAP = "sushiswap"
    ONEINCH = "1inch"
    BALANCER = "balancer"
    CURVE = "curve"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    MARKET_IF_TOUCHED = "market_if_touched"
    LIMIT_IF_TOUCHED = "limit_if_touched"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class TimeInForce(Enum):
    """Time in force enumeration."""
    GTC = "gtc"  # Good Till Cancel
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    DAY = "day"  # Day order
    GTD = "gtd"  # Good Till Date
    POST_ONLY = "post_only"


class MarketType(Enum):
    """Market type enumeration."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTION = "option"
    MARGIN = "margin"
    LEVERAGED = "leveraged"


class Interval(Enum):
    """OHLCV interval enumeration."""
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H8 = "8h"
    H12 = "12h"
    D1 = "1d"
    D3 = "3d"
    W1 = "1w"
    MN1 = "1M"


# Dataclasses
@dataclass
class ExchangeConfig:
    """Exchange configuration."""
    exchange_type: ExchangeType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None
    sandbox_mode: bool = False
    testnet: bool = False
    web3_provider: Optional[str] = None
    chain_id: Optional[int] = None
    private_key: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 1
    rate_limit_per_second: int = 10
    ws_endpoint: Optional[str] = None
    rest_endpoint: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Balance:
    """Account balance."""
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal
    usd_value: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Ticker:
    """Ticker information."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    volume_usd: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OHLCV:
    """OHLCV candlestick data."""
    symbol: str
    interval: Interval
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime
    close_time: datetime


@dataclass
class Order:
    """Order information."""
    order_id: str
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    client_order_id: Optional[str] = None
    reduce_only: bool = False
    post_only: bool = False
    iceberg: bool = False
    iceberg_quantity: Optional[Decimal] = None
    twap: bool = False
    twap_duration: Optional[int] = None  # seconds
    vwap: bool = False
    vwap_duration: Optional[int] = None  # seconds
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderBook:
    """Order book data."""
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # (price, quantity)
    asks: List[Tuple[Decimal, Decimal]]  # (price, quantity)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    """Position information."""
    symbol: str
    side: OrderSide
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    mark_price: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    leverage: Decimal = Decimal("1")
    margin: Decimal = Decimal("0")
    maintenance_margin: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Trade:
    """Trade/execution information."""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    cost: Decimal
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DepositWithdrawal:
    """Deposit/withdrawal information."""
    tx_id: str
    asset: str
    amount: Decimal
    address: str
    status: str  # "pending", "processing", "completed", "failed", "cancelled"
    transaction_type: str  # "deposit" or "withdrawal"
    network: Optional[str] = None
    confirmations: int = 0
    required_confirmations: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class FundingRate:
    """Funding rate information."""
    symbol: str
    funding_rate: Decimal
    predicted_rate: Optional[Decimal] = None
    next_funding_time: datetime
    interval_hours: int = 8
    mark_price: Optional[Decimal] = None
    index_price: Optional[Decimal] = None


# Event types
class WebSocketEvent:
    """WebSocket event types."""
    ORDER_BOOK = "order_book"
    TRADE = "trade"
    TICKER = "ticker"
    OHLCV = "ohlcv"
    BALANCE = "balance"
    ORDER = "order"
    POSITION = "position"
    USER_DATA = "user_data"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


# Protocols
@runtime_checkable
class ExchangeWebSocket(Protocol):
    """WebSocket protocol for exchanges."""
    
    async def connect(self) -> None:
        """Connect to WebSocket."""
        ...
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        ...
    
    async def subscribe(
        self,
        channel: str,
        symbols: List[str],
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Subscribe to a channel."""
        ...
    
    async def unsubscribe(self, channel: str, symbols: List[str]) -> None:
        """Unsubscribe from a channel."""
        ...
    
    async def listen(self) -> AsyncIterator[Dict[str, Any]]:
        """Listen for messages."""
        ...


# Base Exchange Class
class BaseExchange(ABC):
    """
    Abstract base class for all exchange integrations.
    
    This class defines the standard interface that all exchange adapters
    must implement. It provides common functionality and type definitions.
    
    Features:
    - Market data (ticker, order book, OHLCV)
    - Order management (place, cancel, get status)
    - Account management (balance, positions)
    - WebSocket support
    - Error handling
    - Rate limiting
    - Logging
    
    All exchange adapters must inherit from this class and implement
    all abstract methods.
    """
    
    def __init__(
        self,
        config: ExchangeConfig,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the exchange adapter.
        
        Args:
            config: Exchange configuration
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or self._setup_logger()
        self.exchange_type = config.exchange_type
        self.sandbox_mode = config.sandbox_mode
        self.testnet = config.testnet
        
        # Rate limiting
        self._rate_limit_per_second = config.rate_limit_per_second
        self._last_request_time = 0
        self._request_count = 0
        
        # Connection state
        self._is_connected = False
        self._is_authenticated = False
        
        # WebSocket
        self._websocket: Optional[ExchangeWebSocket] = None
        
        # Callbacks
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._balance_callbacks: List[Callable[[Balance], None]] = []
        self._position_callbacks: List[Callable[[Position], None]] = []
        self._trade_callbacks: List[Callable[[Trade], None]] = []
        
        # Metrics
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "orders_placed": 0,
            "orders_cancelled": 0,
            "websocket_messages": 0,
            "errors": 0,
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger."""
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _check_rate_limit(self) -> None:
        """Check and apply rate limiting."""
        import time
        now = time.time()
        if now - self._last_request_time < 1.0 / self._rate_limit_per_second:
            time.sleep(1.0 / self._rate_limit_per_second)
        self._last_request_time = now
        self._request_count += 1
    
    # Abstract Methods - Market Data
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """
        Get ticker information for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker or None
        """
        pass
    
    @abstractmethod
    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100,
    ) -> Optional[OrderBook]:
        """
        Get order book for a symbol.
        
        Args:
            symbol: Trading symbol
            limit: Order book depth limit
            
        Returns:
            OrderBook or None
        """
        pass
    
    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        interval: Interval,
        limit: int = 100,
    ) -> List[OHLCV]:
        """
        Get OHLCV candlestick data.
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            limit: Number of candles to return
            
        Returns:
            List of OHLCV objects
        """
        pass
    
    @abstractmethod
    async def get_historical_prices(
        self,
        symbol: str,
        interval: Interval,
        start_time: datetime,
        end_time: datetime,
    ) -> List[OHLCV]:
        """
        Get historical prices for a time range.
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_time: Start time
            end_time: End time
            
        Returns:
            List of OHLCV objects
        """
        pass
    
    # Abstract Methods - Order Management
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[Order]:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            order_type: Market, limit, stop, etc.
            quantity: Order quantity
            price: Limit price (required for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: Time in force
            reduce_only: Reduce only position
            post_only: Post only order
            client_order_id: Client order ID
            **kwargs: Additional exchange-specific parameters
            
        Returns:
            Order or None
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> bool:
        """
        Cancel all orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            
        Returns:
            Order or None
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: str) -> List[Order]:
        """
        Get open orders for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of open orders
        """
        pass
    
    @abstractmethod
    async def get_order_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Order]:
        """
        Get order history.
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of orders
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            List of orders
        """
        pass
    
    # Abstract Methods - Account Management
    
    @abstractmethod
    async def get_balances(self) -> Dict[str, Balance]:
        """
        Get account balances.
        
        Returns:
            Dictionary of asset to Balance
        """
        pass
    
    @abstractmethod
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """
        Get balance for a specific asset.
        
        Args:
            asset: Asset symbol
            
        Returns:
            Balance or None
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position or None
        """
        pass
    
    # Abstract Methods - Market Data (Additional)
    
    @abstractmethod
    async def get_symbols(self) -> List[str]:
        """
        Get all available trading symbols.
        
        Returns:
            List of symbols
        """
        pass
    
    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """
        Get funding rate for a perpetual symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            FundingRate or None
        """
        pass
    
    # WebSocket Methods
    
    @abstractmethod
    async def connect_websocket(self) -> bool:
        """
        Connect to WebSocket stream.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect_websocket(self) -> bool:
        """
        Disconnect from WebSocket stream.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def subscribe_ticker(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None],
    ) -> bool:
        """
        Subscribe to ticker updates.
        
        Args:
            symbols: List of symbols
            callback: Callback function
            
        Returns:
            True if subscribed successfully
        """
        pass
    
    @abstractmethod
    async def subscribe_order_book(
        self,
        symbols: List[str],
        callback: Callable[[OrderBook], None],
    ) -> bool:
        """
        Subscribe to order book updates.
        
        Args:
            symbols: List of symbols
            callback: Callback function
            
        Returns:
            True if subscribed successfully
        """
        pass
    
    @abstractmethod
    async def subscribe_trades(
        self,
        symbols: List[str],
        callback: Callable[[Trade], None],
    ) -> bool:
        """
        Subscribe to trade updates.
        
        Args:
            symbols: List of symbols
            callback: Callback function
            
        Returns:
            True if subscribed successfully
        """
        pass
    
    @abstractmethod
    async def subscribe_user_data(
        self,
        callback: Callable[[Dict[str, Any]], None],
    ) -> bool:
        """
        Subscribe to user data updates (orders, balances, positions).
        
        Args:
            callback: Callback function
            
        Returns:
            True if subscribed successfully
        """
        pass
    
    # Callback Management
    
    def add_order_callback(self, callback: Callable[[Order], None]) -> None:
        """Add an order callback."""
        self._order_callbacks.append(callback)
    
    def add_balance_callback(self, callback: Callable[[Balance], None]) -> None:
        """Add a balance callback."""
        self._balance_callbacks.append(callback)
    
    def add_position_callback(self, callback: Callable[[Position], None]) -> None:
        """Add a position callback."""
        self._position_callbacks.append(callback)
    
    def add_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Add a trade callback."""
        self._trade_callbacks.append(callback)
    
    def _emit_order(self, order: Order) -> None:
        """Emit order event to callbacks."""
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                self.logger.error(f"Order callback error: {e}")
    
    def _emit_balance(self, balance: Balance) -> None:
        """Emit balance event to callbacks."""
        for callback in self._balance_callbacks:
            try:
                callback(balance)
            except Exception as e:
                self.logger.error(f"Balance callback error: {e}")
    
    def _emit_position(self, position: Position) -> None:
        """Emit position event to callbacks."""
        for callback in self._position_callbacks:
            try:
                callback(position)
            except Exception as e:
                self.logger.error(f"Position callback error: {e}")
    
    def _emit_trade(self, trade: Trade) -> None:
        """Emit trade event to callbacks."""
        for callback in self._trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                self.logger.error(f"Trade callback error: {e}")
    
    # Utility Methods
    
    @abstractmethod
    async def ping(self) -> bool:
        """
        Ping the exchange to check connectivity.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    async def get_server_time(self) -> datetime:
        """
        Get server time.
        
        Returns:
            Server time
        """
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get exchange metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "is_connected": self._is_connected,
            "is_authenticated": self._is_authenticated,
            "exchange_type": self.exchange_type.value,
            "sandbox_mode": self.sandbox_mode,
            "testnet": self.testnet,
        }
    
    # Context Managers
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_websocket()
    
    # Error Handling
    
    class ExchangeError(Exception):
        """Base exchange error."""
        pass
    
    class AuthenticationError(ExchangeError):
        """Authentication error."""
        pass
    
    class RateLimitError(ExchangeError):
        """Rate limit error."""
        pass
    
    class OrderError(ExchangeError):
        """Order error."""
        pass
    
    class InsufficientBalanceError(OrderError):
        """Insufficient balance error."""
        pass
    
    class InvalidSymbolError(ExchangeError):
        """Invalid symbol error."""
        pass


# Factory Protocol
@runtime_checkable
class ExchangeFactory(Protocol):
    """Exchange factory protocol."""
    
    def create(self, config: ExchangeConfig) -> BaseExchange:
        """
        Create an exchange adapter.
        
        Args:
            config: Exchange configuration
            
        Returns:
            Exchange adapter
        """
        ...


# Module exports
__all__ = [
    # Enums
    'ExchangeType',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'TimeInForce',
    'MarketType',
    'Interval',
    
    # Dataclasses
    'ExchangeConfig',
    'Balance',
    'Ticker',
    'OHLCV',
    'Order',
    'OrderBook',
    'Position',
    'Trade',
    'DepositWithdrawal',
    'FundingRate',
    
    # Protocols
    'ExchangeWebSocket',
    'ExchangeFactory',
    
    # Base Class
    'BaseExchange',
    
    # Events
    'WebSocketEvent',
]
