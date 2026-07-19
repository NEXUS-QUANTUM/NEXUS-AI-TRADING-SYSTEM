#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Exchange Base Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Base classes and interfaces for all exchange integrations.
Provides unified API for trading across multiple asset classes:
stocks, crypto, forex, futures, options, and more.

Author: Dr X...
Version: 3.0.0
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union, 
    TypeVar, Generic, Coroutine, AsyncIterator, Type
)
import aiohttp
import aiohttp.client_exceptions
from aiohttp import ClientSession, ClientTimeout, ClientResponse

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class AssetClass(str, Enum):
    """Asset classes supported by the exchange."""
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"
    BOND = "bond"
    COMMODITY = "commodity"
    INDEX = "index"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"


class ExchangeType(str, Enum):
    """Types of exchanges."""
    CENTRALIZED = "centralized"
    DECENTRALIZED = "decentralized"
    BROKER = "broker"
    MARKET_MAKER = "market_maker"
    AGGREGATOR = "aggregator"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"  # One Cancels Other
    BRACKET = "bracket"
    ICEBERG = "iceberg"
    TWAP = "twap"  # Time-Weighted Average Price
    VWAP = "vwap"  # Volume-Weighted Average Price
    PEGGED = "pegged"
    MARKET_IF_TOUCHED = "market_if_touched"
    LIMIT_IF_TOUCHED = "limit_if_touched"


class OrderSide(str, Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"
    CLOSE = "close"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    GTD = "gtd"  # Good Till Date
    OPG = "opg"  # Opening
    CLS = "cls"  # Closing
    GTX = "gtx"  # Good Till Crossing


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    HELD = "held"
    CANCEL_PENDING = "cancel_pending"
    MODIFY_PENDING = "modify_pending"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class OrderBookLevel(str, Enum):
    """Order book depth levels."""
    LEVEL_1 = "level_1"  # Best bid/ask
    LEVEL_2 = "level_2"  # Full depth
    LEVEL_3 = "level_3"  # Full depth with order IDs


class DataFrequency(str, Enum):
    """Data frequency."""
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR = "1h"
    HOUR_4 = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"
    QUARTER = "3M"
    YEAR = "1Y"


class WebSocketEvent(str, Enum):
    """WebSocket events."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    ORDER_UPDATE = "order_update"
    POSITION_UPDATE = "position_update"
    BALANCE_UPDATE = "balance_update"
    MARKET_DATA = "market_data"
    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "order_book"
    BAR = "bar"
    SIGNAL = "signal"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Price:
    """Price representation with precision."""
    value: float
    currency: str = "USD"
    precision: int = 2
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return f"{self.value:.{self.precision}f} {self.currency}"
    
    def __float__(self) -> float:
        return self.value
    
    def __add__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value + other.value, self.currency, self.precision)
        return Price(self.value + other, self.currency, self.precision)
    
    def __sub__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value - other.value, self.currency, self.precision)
        return Price(self.value - other, self.currency, self.precision)
    
    def __mul__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value * other.value, self.currency, self.precision)
        return Price(self.value * other, self.currency, self.precision)


@dataclass
class Amount:
    """Amount representation with precision."""
    value: float
    asset: str
    precision: int = 8
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return f"{self.value:.{self.precision}f} {self.asset}"
    
    def __float__(self) -> float:
        return self.value


@dataclass
class Order:
    """Unified order representation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str = ""
    client_order_id: str = ""
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    order_type: OrderType = OrderType.MARKET
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    commission: float = 0.0
    commission_asset: str = "USD"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    reduce_only: bool = False
    post_only: bool = False
    iceberg_qty: Optional[float] = None
    visible_qty: Optional[float] = None
    trigger_price: Optional[float] = None
    trail_value: Optional[float] = None
    trail_unit: str = "points"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.MODIFY_PENDING,
        ]
    
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED
    
    def is_cancelled(self) -> bool:
        """Check if order is cancelled."""
        return self.status == OrderStatus.CANCELLED
    
    def is_rejected(self) -> bool:
        """Check if order is rejected."""
        return self.status == OrderStatus.REJECTED
    
    def get_remaining_quantity(self) -> float:
        """Get remaining quantity to fill."""
        return self.quantity - self.filled_quantity
    
    def get_fill_percentage(self) -> float:
        """Get percentage filled."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100


@dataclass
class Position:
    """Unified position representation."""
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    side: PositionSide = PositionSide.FLAT
    quantity: float = 0.0
    average_price: float = 0.0
    current_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    cost_basis: float = 0.0
    market_value: float = 0.0
    margin_used: float = 0.0
    leverage: float = 1.0
    liquidation_price: Optional[float] = None
    entry_price: Optional[float] = None
    entry_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    commission: float = 0.0
    commission_asset: str = "USD"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_pnl_percentage(self) -> float:
        """Calculate PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.total_pnl / self.cost_basis) * 100
    
    def get_unrealized_pnl_percentage(self) -> float:
        """Calculate unrealized PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    def get_realized_pnl_percentage(self) -> float:
        """Calculate realized PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.realized_pnl / self.cost_basis) * 100
    
    def get_break_even_price(self) -> float:
        """Calculate break-even price including commission."""
        if self.quantity == 0:
            return self.average_price
        return self.average_price + (self.commission / self.quantity)


@dataclass
class AccountBalance:
    """Account balance representation."""
    total_equity: float = 0.0
    available_balance: float = 0.0
    used_balance: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    buying_power: float = 0.0
    leverage: float = 1.0
    maintenance_margin: float = 0.0
    initial_margin: float = 0.0
    liquidation_margin: float = 0.0
    currency: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    balances: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    """Trade execution representation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    commission_asset: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_type: str = "regular"
    is_maker: bool = False
    is_taker: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketData:
    """Unified market data representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    bid_price: Optional[float] = None
    bid_quantity: Optional[float] = None
    ask_price: Optional[float] = None
    ask_quantity: Optional[float] = None
    last_price: Optional[float] = None
    last_quantity: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[float] = None
    vwap: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    spread: Optional[float] = None
    bid_count: Optional[int] = None
    ask_count: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderBook:
    """Order book representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    bids: List[Tuple[float, float]] = field(default_factory=list)  # (price, quantity)
    asks: List[Tuple[float, float]] = field(default_factory=list)  # (price, quantity)
    bid_ids: Optional[List[str]] = None
    ask_ids: Optional[List[str]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    level: OrderBookLevel = OrderBookLevel.LEVEL_2
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_best_bid(self) -> Optional[Tuple[float, float]]:
        """Get best bid (highest price)."""
        if not self.bids:
            return None
        return self.bids[0]
    
    def get_best_ask(self) -> Optional[Tuple[float, float]]:
        """Get best ask (lowest price)."""
        if not self.asks:
            return None
        return self.asks[0]
    
    def get_spread(self) -> Optional[float]:
        """Get current bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None
    
    def get_mid_price(self) -> Optional[float]:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2
        return None


@dataclass
class Candle:
    """OHLCV candle representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    timeframe: DataFrequency = DataFrequency.MINUTE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    vwap: Optional[float] = None
    number_of_trades: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_range(self) -> float:
        """Get price range (high - low)."""
        return self.high - self.low
    
    def get_body(self) -> float:
        """Get candle body (close - open)."""
        return self.close - self.open
    
    def get_upper_wick(self) -> float:
        """Get upper wick (high - max(open, close))."""
        return self.high - max(self.open, self.close)
    
    def get_lower_wick(self) -> float:
        """Get lower wick (min(open, close) - low)."""
        return min(self.open, self.close) - self.low
    
    def is_bullish(self) -> bool:
        """Check if candle is bullish."""
        return self.close > self.open
    
    def is_bearish(self) -> bool:
        """Check if candle is bearish."""
        return self.close < self.open


@dataclass
class ExchangeInfo:
    """Exchange information."""
    name: str
    type: ExchangeType = ExchangeType.CENTRALIZED
    asset_classes: List[AssetClass] = field(default_factory=list)
    timezone: str = "UTC"
    website: str = ""
    api_version: str = ""
    supported_order_types: List[OrderType] = field(default_factory=list)
    supported_time_in_force: List[TimeInForce] = field(default_factory=list)
    max_leverage: float = 1.0
    min_trade_size: float = 0.0
    max_trade_size: float = 0.0
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    withdrawal_fee: float = 0.0
    deposit_fee: float = 0.0
    trading_pairs: List[str] = field(default_factory=list)
    quote_assets: List[str] = field(default_factory=list)
    base_assets: List[str] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)
    rate_limits: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    last_updated: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ExchangeError(Exception):
    """Base exchange exception."""
    pass


class ConnectionError(ExchangeError):
    """Connection error."""
    pass


class AuthenticationError(ExchangeError):
    """Authentication error."""
    pass


class AuthorizationError(ExchangeError):
    """Authorization error."""
    pass


class RateLimitError(ExchangeError):
    """Rate limit exceeded."""
    pass


class OrderError(ExchangeError):
    """Order error."""
    pass


class InvalidOrderError(OrderError):
    """Invalid order parameters."""
    pass


class InsufficientBalanceError(OrderError):
    """Insufficient balance."""
    pass


class MarketDataError(ExchangeError):
    """Market data error."""
    pass


class PositionError(ExchangeError):
    """Position error."""
    pass


class AccountError(ExchangeError):
    """Account error."""
    pass


class TimeoutError(ExchangeError):
    """Timeout error."""
    pass


class WebSocketError(ExchangeError):
    """WebSocket error."""
    pass


# ============================================================================
# BASE EXCHANGE CLASS
# ============================================================================

class ExchangeBase(ABC):
    """
    Abstract base class for all exchange implementations.
    
    Provides a unified interface for trading across multiple exchanges
    and asset classes.
    
    Features:
    - Order management (place, cancel, modify, get)
    - Position management (get, close)
    - Account management (balance, info)
    - Market data (quotes, order book, candles, tickers)
    - WebSocket streaming (real-time data)
    - Webhook support
    - Rate limiting
    - Error handling
    - Retry logic
    - Logging
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        paper_trading: bool = False,
        testnet: bool = False,
        **kwargs
    ):
        """
        Initialize the exchange client.
        
        Args:
            api_key: API key
            api_secret: API secret
            api_passphrase: API passphrase (for some exchanges)
            base_url: Base URL for API endpoints
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            paper_trading: Enable paper trading mode
            testnet: Use testnet endpoints
            **kwargs: Additional configuration
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.paper_trading = paper_trading
        self.testnet = testnet
        
        self._session: Optional[ClientSession] = None
        self._connected = False
        self._connection_id = None
        self._rate_limiter = None
        self._cache: Dict[str, Any] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
        self._listeners: Dict[str, List[Callable]] = {}
        self._websocket_connections: Dict[str, Any] = {}
        self._websocket_callbacks: Dict[str, Callable] = {}
        
        self._request_count = 0
        self._last_request_time = 0.0
        self._request_history: List[Dict] = []
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"Initialized {self.__class__.__name__}")
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the exchange.
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the exchange.
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to the exchange.
        
        Returns:
            bool: True if connected
        """
        pass
    
    @abstractmethod
    async def get_exchange_info(self) -> ExchangeInfo:
        """
        Get exchange information.
        
        Returns:
            ExchangeInfo: Exchange information
        """
        pass
    
    # ========================================================================
    # ACCOUNT MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def get_account_balance(self) -> AccountBalance:
        """
        Get account balance.
        
        Returns:
            AccountBalance: Account balance
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            dict: Account information
        """
        pass
    
    @abstractmethod
    async def get_account_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get account history.
        
        Args:
            start_time: Start time
            end_time: End time
            limit: Maximum number of records
        
        Returns:
            List[dict]: Account history
        """
        pass
    
    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def place_order(self, order: Order) -> Order:
        """
        Place a new order.
        
        Args:
            order: Order to place
        
        Returns:
            Order: Placed order
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
        
        Returns:
            bool: True if cancelled
        """
        pass
    
    @abstractmethod
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> bool:
        """
        Cancel all orders.
        
        Args:
            symbol: Symbol to cancel orders for (optional)
        
        Returns:
            bool: True if all orders cancelled
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        **kwargs
    ) -> Order:
        """
        Modify an existing order.
        
        Args:
            order_id: Order ID
            quantity: New quantity (optional)
            price: New price (optional)
            **kwargs: Additional parameters
        
        Returns:
            Order: Modified order
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Order:
        """
        Get order details.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order: Order details
        """
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Order]:
        """
        Get orders.
        
        Args:
            symbol: Symbol (optional)
            status: Order status filter (optional)
            limit: Maximum number of orders
            offset: Offset for pagination
        
        Returns:
            List[Order]: List of orders
        """
        pass
    
    @abstractmethod
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get order history.
        
        Args:
            symbol: Symbol (optional)
            start_time: Start time (optional)
            end_time: End time (optional)
            limit: Maximum number of orders
        
        Returns:
            List[Order]: Order history
        """
        pass
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get all positions.
        
        Returns:
            List[Position]: List of positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Symbol
        
        Returns:
            Optional[Position]: Position or None
        """
        pass
    
    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        quantity: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET
    ) -> bool:
        """
        Close a position.
        
        Args:
            symbol: Symbol
            quantity: Quantity to close (optional, all if not specified)
            order_type: Order type to use
        
        Returns:
            bool: True if position closed
        """
        pass
    
    @abstractmethod
    async def close_all_positions(self) -> bool:
        """
        Close all positions.
        
        Returns:
            bool: True if all positions closed
        """
        pass
    
    # ========================================================================
    # MARKET DATA
    # ========================================================================
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """
        Get market data for a symbol.
        
        Args:
            symbol: Symbol
        
        Returns:
            MarketData: Market data
        """
        pass
    
    @abstractmethod
    async def get_multiple_market_data(self, symbols: List[str]) -> Dict[str, MarketData]:
        """
        Get market data for multiple symbols.
        
        Args:
            symbols: List of symbols
        
        Returns:
            Dict[str, MarketData]: Market data by symbol
        """
        pass
    
    @abstractmethod
    async def get_order_book(
        self,
        symbol: str,
        level: OrderBookLevel = OrderBookLevel.LEVEL_2,
        depth: int = 10
    ) -> OrderBook:
        """
        Get order book for a symbol.
        
        Args:
            symbol: Symbol
            level: Order book level
            depth: Depth of order book
        
        Returns:
            OrderBook: Order book
        """
        pass
    
    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: DataFrequency = DataFrequency.MINUTE,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Candle]:
        """
        Get candle data.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            limit: Maximum number of candles
            start_time: Start time (optional)
            end_time: End time (optional)
        
        Returns:
            List[Candle]: List of candles
        """
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> MarketData:
        """
        Get ticker for a symbol.
        
        Args:
            symbol: Symbol
        
        Returns:
            MarketData: Ticker data
        """
        pass
    
    @abstractmethod
    async def get_all_tickers(self) -> Dict[str, MarketData]:
        """
        Get all tickers.
        
        Returns:
            Dict[str, MarketData]: Tickers by symbol
        """
        pass
    
    @abstractmethod
    async def get_trades(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Get recent trades.
        
        Args:
            symbol: Symbol
            limit: Maximum number of trades
            since: Since timestamp (optional)
        
        Returns:
            List[Trade]: List of trades
        """
        pass
    
    # ========================================================================
    # WEBSOCKET STREAMING
    # ========================================================================
    
    @abstractmethod
    async def connect_websocket(self, endpoint: str, **kwargs) -> bool:
        """
        Connect to WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint
            **kwargs: Additional parameters
        
        Returns:
            bool: True if connected
        """
        pass
    
    @abstractmethod
    async def disconnect_websocket(self, endpoint: str) -> bool:
        """
        Disconnect from WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint
        
        Returns:
            bool: True if disconnected
        """
        pass
    
    @abstractmethod
    async def subscribe_to_orders(self, callback: Callable) -> bool:
        """
        Subscribe to order updates.
        
        Args:
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_positions(self, callback: Callable) -> bool:
        """
        Subscribe to position updates.
        
        Args:
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        callback: Callable
    ) -> bool:
        """
        Subscribe to market data.
        
        Args:
            symbols: List of symbols
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_order_book(
        self,
        symbol: str,
        callback: Callable,
        level: OrderBookLevel = OrderBookLevel.LEVEL_2
    ) -> bool:
        """
        Subscribe to order book updates.
        
        Args:
            symbol: Symbol
            callback: Callback function
            level: Order book level
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_trades(
        self,
        symbols: List[str],
        callback: Callable
    ) -> bool:
        """
        Subscribe to trade updates.
        
        Args:
            symbols: List of symbols
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    # ========================================================================
    # WEBHOOK SUPPORT
    # ========================================================================
    
    @abstractmethod
    async def register_webhook(
        self,
        url: str,
        event_types: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a webhook.
        
        Args:
            url: Webhook URL
            event_types: Event types to subscribe to
            **kwargs: Additional parameters
        
        Returns:
            dict: Webhook registration details
        """
        pass
    
    @abstractmethod
    async def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook.
        
        Args:
            webhook_id: Webhook ID
        
        Returns:
            bool: True if unregistered
        """
        pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)
    
    def _generate_signature(
        self,
        payload: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> str:
        """
        Generate HMAC signature.
        
        Args:
            payload: Payload to sign
            secret: Secret key
            algorithm: Hash algorithm
        
        Returns:
            str: Signature
        """
        if algorithm == "sha256":
            return hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha512":
            return hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def _generate_nonce(self) -> str:
        """Generate a nonce for API requests."""
        return str(int(time.time() * 1000))
    
    def _generate_client_order_id(self) -> str:
        """Generate a client order ID."""
        return f"nexus_{uuid.uuid4().hex[:16]}"
    
    def _rate_limit_wait(self) -> None:
        """Wait if rate limit is reached."""
        # Implement rate limiting logic
        pass
    
    def _log_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float
    ) -> None:
        """Log API request."""
        self._logger.debug(
            f"{method} {endpoint} -> {status} ({duration:.3f}s)"
        )
    
    def _log_error(self, error: Exception, context: str = "") -> None:
        """Log error with context."""
        self._logger.error(f"{context}: {error}", exc_info=True)
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self) -> 'ExchangeBase':
        """Context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.disconnect()
    
    # ========================================================================
    # MAGIC METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(paper_trading={self.paper_trading})"
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__} - {self._connection_id or 'disconnected'}"

# ============================================================================
# EXCHANGE FACTORY
# ============================================================================

class ExchangeFactory:
    """
    Factory for creating exchange instances.
    
    Supports dynamic loading of exchange implementations.
    """
    
    _exchanges: Dict[str, Type[ExchangeBase]] = {}
    
    @classmethod
    def register(cls, name: str, exchange_class: Type[ExchangeBase]) -> None:
        """
        Register an exchange implementation.
        
        Args:
            name: Exchange name
            exchange_class: Exchange class
        """
        cls._exchanges[name.lower()] = exchange_class
    
    @classmethod
    def create(
        cls,
        exchange: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ) -> ExchangeBase:
        """
        Create an exchange instance.
        
        Args:
            exchange: Exchange name
            api_key: API key (optional)
            api_secret: API secret (optional)
            **kwargs: Additional configuration
        
        Returns:
            ExchangeBase: Exchange instance
        
        Raises:
            ValueError: If exchange is not registered
        """
        exchange = exchange.lower()
        if exchange not in cls._exchanges:
            raise ValueError(
                f"Exchange '{exchange}' not registered. "
                f"Available: {', '.join(cls._exchanges.keys())}"
            )
        
        exchange_class = cls._exchanges[exchange]
        return exchange_class(api_key=api_key, api_secret=api_secret, **kwargs)
    
    @classmethod
    def get_available_exchanges(cls) -> List[str]:
        """
        Get list of available exchanges.
        
        Returns:
            List[str]: List of exchange names
        """
        return list(cls._exchanges.keys())


# ============================================================================
# DECORATORS
# ============================================================================

def retry_on_error(max_retries: int = 3, delay: float = 1.0, exponential: bool = True):
    """
    Decorator for retrying on error.
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay in seconds
        exponential: Use exponential backoff
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt) if exponential else delay
                        await asyncio.sleep(wait_time)
            raise last_error
        return wrapper
    return decorator


def rate_limited(requests_per_second: int):
    """
    Decorator for rate limiting.
    
    Args:
        requests_per_second: Maximum requests per second
    """
    def decorator(func):
        last_call = 0.0
        
        async def wrapper(self, *args, **kwargs):
            nonlocal last_call
            now = time.time()
            if now - last_call < 1.0 / requests_per_second:
                await asyncio.sleep((1.0 / requests_per_second) - (now - last_call))
            last_call = time.time()
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


def log_request(func):
    """Decorator for logging API requests."""
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            duration = time.time() - start_time
            self._log_request(
                func.__name__,
                str(args[0] if args else ""),
                200,
                duration
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log_error(e, f"{func.__name__} ({duration:.3f}s)")
            raise
    return wrapper

# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("NEXUS AI TRADING SYSTEM - Exchange Base Module Test")
    print("=" * 70)
    print(f"Version: 3.0.0")
    print("=" * 70)
    
    # Test enums
    print("\n[1] Testing Enums:")
    print(f"  Asset Classes: {[a.value for a in AssetClass]}")
    print(f"  Order Types: {[o.value for o in OrderType]}")
    print(f"  Time in Force: {[t.value for t in TimeInForce]}")
    
    # Test data classes
    print("\n[2] Testing Data Classes:")
    order = Order(
        symbol="AAPL",
        quantity=100,
        price=150.00,
        order_type=OrderType.LIMIT
    )
    print(f"  Order: {order}")
    
    position = Position(
        symbol="AAPL",
        side=PositionSide.LONG,
        quantity=100,
        average_price=150.00,
        current_price=155.00
    )
    print(f"  Position: {position}")
    print(f"    PnL: ${position.total_pnl:.2f}")
    print(f"    PnL%: {position.get_pnl_percentage():.2f}%")
    
    candle = Candle(
        symbol="AAPL",
        open=150.00,
        high=155.00,
        low=149.00,
        close=154.00,
        volume=1000000
    )
    print(f"  Candle: {candle}")
    print(f"    Body: {candle.get_body():.2f}")
    print(f"    Upper wick: {candle.get_upper_wick():.2f}")
    print(f"    Lower wick: {candle.get_lower_wick():.2f}")
    print(f"    Bullish: {candle.is_bullish()}")
    
    order_book = OrderBook(
        symbol="AAPL",
        bids=[(150.00, 100), (149.50, 200)],
        asks=[(150.50, 100), (151.00, 200)]
    )
    print(f"  Order Book: {order_book}")
    print(f"    Best bid: {order_book.get_best_bid()}")
    print(f"    Best ask: {order_book.get_best_ask()}")
    print(f"    Spread: ${order_book.get_spread():.2f}")
    print(f"    Mid price: ${order_book.get_mid_price():.2f}")
    
    print("\n[5] Tests completed successfully!")
