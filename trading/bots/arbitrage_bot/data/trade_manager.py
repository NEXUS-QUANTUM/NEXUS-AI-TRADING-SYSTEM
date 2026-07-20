"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Trade Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced trade management system for arbitrage execution with:
- Real-time trade execution and monitoring
- Multi-exchange trade coordination
- Trade lifecycle management
- Order book integration
- Slippage management
- Position tracking
- Trade analytics and reporting
"""

import asyncio
import json
import logging
import math
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable

import numpy as np
from pydantic import BaseModel, Field, validator, root_validator

# Local imports
from .base import BaseTradeManager
from .exceptions import (
    TradeManagerError,
    TradeExecutionError,
    TradeValidationError,
    TradeNotFoundError,
    OrderBookError,
    SlippageError,
)
from .price_manager import PriceManager, PriceSource
from .order_book_manager import OrderBookManager, OrderBook
from .config import TradeManagerConfig
from .constants import (
    ORDER_TYPES,
    ORDER_SIDES,
    ORDER_STATUS,
    TRADE_CACHE_TTL,
    MAX_TRADE_HISTORY,
    DEFAULT_SLIPPAGE_TOLERANCE,
    DEFAULT_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    MARKET_IF_TOUCHED = "market_if_touched"
    LIMIT_IF_TOUCHED = "limit_if_touched"
    FILL_OR_KILL = "fill_or_kill"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"
    POST_ONLY = "post_only"
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"
    BUY_MAKER = "buy_maker"
    SELL_MAKER = "sell_maker"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    PENDING_CANCEL = "pending_cancel"
    PARTIALLY_CANCELLED = "partially_cancelled"


class TimeInForce(str, Enum):
    """Time in force."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    DAY = "day"
    GTD = "gtd"  # Good Till Date


class TradeType(str, Enum):
    """Trade type."""
    ARBITRAGE = "arbitrage"
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    HEDGE = "hedge"
    SCALP = "scalp"
    SWING = "swing"


class TradeStatus(str, Enum):
    """Trade status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_EXECUTED = "partially_executed"
    ROLLBACK = "rollback"


# ============================================================
# DATA MODELS
# ============================================================

class Order(BaseModel):
    """Represents a trading order."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fees: Decimal = Decimal('0')
    commission: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_reports: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError(f"Quantity must be positive: {v}")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError(f"Price must be positive: {v}")
        return v

    @root_validator
    def validate_order_type_price(cls, values):
        order_type = values.get('order_type')
        price = values.get('price')
        
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.LIMIT_IF_TOUCHED]:
            if price is None or price <= 0:
                raise ValueError(f"Price required for {order_type}")
        
        if order_type == OrderType.STOP:
            stop_price = values.get('stop_price')
            if stop_price is None or stop_price <= 0:
                raise ValueError(f"Stop price required for {order_type}")
        
        if order_type == OrderType.STOP_LIMIT:
            stop_price = values.get('stop_price')
            limit_price = values.get('limit_price')
            if stop_price is None or stop_price <= 0:
                raise ValueError(f"Stop price required for {order_type}")
            if limit_price is None or limit_price <= 0:
                raise ValueError(f"Limit price required for {order_type}")
        
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'exchange': self.exchange,
            'symbol': self.symbol,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'order_type': self.order_type.value if isinstance(self.order_type, OrderType) else self.order_type,
            'quantity': str(self.quantity),
            'price': str(self.price) if self.price else None,
            'stop_price': str(self.stop_price) if self.stop_price else None,
            'limit_price': str(self.limit_price) if self.limit_price else None,
            'time_in_force': self.time_in_force.value if isinstance(self.time_in_force, TimeInForce) else self.time_in_force,
            'status': self.status.value if isinstance(self.status, OrderStatus) else self.status,
            'filled_quantity': str(self.filled_quantity),
            'average_price': str(self.average_price) if self.average_price else None,
            'fees': str(self.fees),
            'commission': str(self.commission),
            'timestamp': self.timestamp.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'client_order_id': self.client_order_id,
            'exchange_order_id': self.exchange_order_id,
            'metadata': self.metadata,
            'execution_reports': self.execution_reports,
            'error_message': self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """Create Order from dictionary."""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'expires_at' in data and isinstance(data['expires_at'], str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if 'side' in data and isinstance(data['side'], str):
            data['side'] = OrderSide(data['side'])
        if 'order_type' in data and isinstance(data['order_type'], str):
            data['order_type'] = OrderType(data['order_type'])
        if 'time_in_force' in data and isinstance(data['time_in_force'], str):
            data['time_in_force'] = TimeInForce(data['time_in_force'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = OrderStatus(data['status'])
        return cls(**data)

    def is_active(self) -> bool:
        """Check if order is active."""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.PENDING_CANCEL,
        ]

    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED

    def is_cancelled(self) -> bool:
        """Check if order is cancelled."""
        return self.status in [OrderStatus.CANCELLED, OrderStatus.PARTIALLY_CANCELLED]

    def is_terminal(self) -> bool:
        """Check if order is in terminal state."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        ]

    def get_remaining_quantity(self) -> Decimal:
        """Get remaining quantity."""
        return self.quantity - self.filled_quantity

    def get_fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.quantity == 0:
            return 0
        return float(self.filled_quantity / self.quantity * 100)

    def get_execution_value(self) -> Decimal:
        """Get execution value."""
        if self.average_price:
            return self.filled_quantity * self.average_price
        return Decimal('0')


@dataclass
class Trade:
    """Represents a completed trade."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    fees: Decimal = Decimal('0')
    net_value: Decimal = Decimal('0')
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_type: TradeType = TradeType.SPOT
    order_id: Optional[str] = None
    exchange_trade_id: Optional[str] = None
    pnl: Optional[Decimal] = None
    pnl_pct: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @validator('quantity', 'price', 'total_value')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError(f"Value must be positive: {v}")
        return v

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'exchange': self.exchange,
            'symbol': self.symbol,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'quantity': str(self.quantity),
            'price': str(self.price),
            'total_value': str(self.total_value),
            'fees': str(self.fees),
            'net_value': str(self.net_value),
            'timestamp': self.timestamp.isoformat(),
            'trade_type': self.trade_type.value if isinstance(self.trade_type, TradeType) else self.trade_type,
            'order_id': self.order_id,
            'exchange_trade_id': self.exchange_trade_id,
            'pnl': str(self.pnl) if self.pnl else None,
            'pnl_pct': self.pnl_pct,
            'metadata': self.metadata,
        }


@dataclass
class Position:
    """Represents a trading position."""
    
    symbol: str
    exchange: str
    side: OrderSide
    quantity: Decimal = Decimal('0')
    average_price: Decimal = Decimal('0')
    current_price: Optional[Decimal] = None
    pnl: Decimal = Decimal('0')
    pnl_pct: float = 0.0
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    total_quantity: Decimal = Decimal('0')
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'side': self.side.value if isinstance(self.side, OrderSide) else self.side,
            'quantity': str(self.quantity),
            'average_price': str(self.average_price),
            'current_price': str(self.current_price) if self.current_price else None,
            'pnl': str(self.pnl),
            'pnl_pct': self.pnl_pct,
            'realized_pnl': str(self.realized_pnl),
            'unrealized_pnl': str(self.unrealized_pnl),
            'total_quantity': str(self.total_quantity),
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ArbitrageTrade:
    """Represents an arbitrage trade across exchanges."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    buy_order: Order
    sell_order: Order
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    quantity: Decimal
    gross_profit: Decimal
    gross_profit_pct: float
    net_profit: Decimal
    net_profit_pct: float
    fees: Dict[str, Decimal]
    status: TradeStatus = TradeStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'buy_order': self.buy_order.to_dict(),
            'sell_order': self.sell_order.to_dict(),
            'buy_exchange': self.buy_exchange,
            'sell_exchange': self.sell_exchange,
            'buy_price': str(self.buy_price),
            'sell_price': str(self.sell_price),
            'quantity': str(self.quantity),
            'gross_profit': str(self.gross_profit),
            'gross_profit_pct': self.gross_profit_pct,
            'net_profit': str(self.net_profit),
            'net_profit_pct': self.net_profit_pct,
            'fees': {k: str(v) for k, v in self.fees.items()},
            'status': self.status.value if isinstance(self.status, TradeStatus) else self.status,
            'timestamp': self.timestamp.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'latency_ms': self.latency_ms,
            'metadata': self.metadata,
        }


@dataclass
class TradeResult:
    """Result of a trade execution."""
    
    success: bool
    trade: Optional[ArbitrageTrade] = None
    orders: List[Order] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================
# TRADE MANAGER IMPLEMENTATION
# ============================================================

class TradeManager(BaseTradeManager):
    """
    Advanced trade manager with:
    - Real-time trade execution
    - Multi-exchange coordination
    - Trade lifecycle management
    - Slippage control
    - Position tracking
    - Trade analytics
    """

    def __init__(
        self,
        price_manager: PriceManager,
        config: Optional[TradeManagerConfig] = None,
        redis_client: Optional[Any] = None,
        cache_ttl: int = 5,
        max_retries: int = 3,
        slippage_tolerance: float = 0.01,
    ):
        """
        Initialize trade manager.

        Args:
            price_manager: PriceManager instance
            config: Configuration instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
            max_retries: Maximum number of retries
            slippage_tolerance: Slippage tolerance percentage
        """
        self.price_manager = price_manager
        self.config = config or TradeManagerConfig()
        self.redis = redis_client
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.slippage_tolerance = slippage_tolerance

        # Storage
        self._orders: Dict[str, Order] = {}  # order_id -> Order
        self._trades: Dict[str, Trade] = {}  # trade_id -> Trade
        self._arbitrage_trades: Dict[str, ArbitrageTrade] = {}  # trade_id -> ArbitrageTrade
        self._positions: Dict[str, Dict[str, Position]] = {}  # exchange -> symbol -> Position
        
        # Order history
        self._order_history: Dict[str, deque] = {}  # exchange -> deque of orders
        self._trade_history: Dict[str, deque] = {}  # exchange -> deque of trades
        
        # Metrics
        self._metrics = {
            'total_orders': 0,
            'successful_orders': 0,
            'failed_orders': 0,
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_pnl': Decimal('0'),
            'total_fees': Decimal('0'),
            'win_rate': 0.0,
            'avg_profit_pct': 0.0,
            'total_arbitrage_trades': 0,
            'successful_arbitrage': 0,
            'failed_arbitrage': 0,
            'avg_latency_ms': 0,
            'last_trade_timestamp': None,
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()
        self._running = False

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)

        # Slippage history
        self._slippage_history: Dict[str, List[float]] = defaultdict(list)

        logger.info("TradeManager initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def place_order(
        self,
        exchange: str,
        symbol: str,
        side: Union[str, OrderSide],
        quantity: Union[float, Decimal, str],
        order_type: Union[str, OrderType] = OrderType.MARKET,
        price: Optional[Union[float, Decimal, str]] = None,
        stop_price: Optional[Union[float, Decimal, str]] = None,
        limit_price: Optional[Union[float, Decimal, str]] = None,
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """
        Place an order on an exchange.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            side: Order side (buy/sell)
            quantity: Order quantity
            order_type: Order type
            price: Order price (for limit orders)
            stop_price: Stop price (for stop orders)
            limit_price: Limit price (for stop-limit orders)
            time_in_force: Time in force
            client_order_id: Client order ID
            metadata: Additional metadata

        Returns:
            Order instance
        """
        try:
            # Convert values
            quantity_decimal = self._to_decimal(quantity)
            price_decimal = self._to_decimal(price) if price is not None else None
            stop_price_decimal = self._to_decimal(stop_price) if stop_price is not None else None
            limit_price_decimal = self._to_decimal(limit_price) if limit_price is not None else None

            # Convert enums
            if isinstance(side, str):
                side = OrderSide(side)
            if isinstance(order_type, str):
                order_type = OrderType(order_type)
            if isinstance(time_in_force, str):
                time_in_force = TimeInForce(time_in_force)

            # Validate
            if quantity_decimal <= 0:
                raise TradeValidationError(f"Invalid quantity: {quantity_decimal}")

            # Get current price for validation
            price_source = await self.price_manager.get_price(exchange, symbol)
            if price_source is None:
                raise TradeValidationError(f"No price found for {exchange}:{symbol}")

            # Validate price
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.LIMIT_IF_TOUCHED]:
                if price_decimal is None or price_decimal <= 0:
                    raise TradeValidationError(f"Price required for {order_type}")

            if order_type == OrderType.STOP:
                if stop_price_decimal is None or stop_price_decimal <= 0:
                    raise TradeValidationError(f"Stop price required for {order_type}")

            if order_type == OrderType.STOP_LIMIT:
                if stop_price_decimal is None or stop_price_decimal <= 0:
                    raise TradeValidationError(f"Stop price required for {order_type}")
                if limit_price_decimal is None or limit_price_decimal <= 0:
                    raise TradeValidationError(f"Limit price required for {order_type}")

            # Create order
            order = Order(
                exchange=exchange,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity_decimal,
                price=price_decimal,
                stop_price=stop_price_decimal,
                limit_price=limit_price_decimal,
                time_in_force=time_in_force,
                client_order_id=client_order_id or f"nexus_{uuid.uuid4().hex[:8]}",
                metadata=metadata or {},
                timestamp=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            # Validate order
            if not await self._validate_order(order):
                order.status = OrderStatus.REJECTED
                order.error_message = "Order validation failed"
                await self._store_order(order)
                raise TradeValidationError("Order validation failed")

            # Store order
            await self._store_order(order)

            # Execute order
            try:
                executed_order = await self._execute_order(order)
                await self._update_order(executed_order)
                return executed_order
            except Exception as e:
                order.status = OrderStatus.FAILED
                order.error_message = str(e)
                await self._update_order(order)
                raise TradeExecutionError(f"Order execution failed: {e}")

        except Exception as e:
            logger.error(f"Failed to place order on {exchange}:{symbol}: {e}")
            raise TradeManagerError(f"Failed to place order: {e}")

    async def cancel_order(
        self,
        exchange: str,
        order_id: str,
        symbol: Optional[str] = None,
    ) -> bool:
        """
        Cancel an order.

        Args:
            exchange: Exchange name
            order_id: Order ID
            symbol: Trading pair symbol (optional)

        Returns:
            True if cancelled, False otherwise
        """
        try:
            # Get order
            order = await self.get_order(exchange, order_id)
            if order is None:
                raise TradeNotFoundError(f"Order not found: {order_id}")

            if not order.is_active():
                logger.warning(f"Order {order_id} is not active (status: {order.status})")
                return False

            # Update status
            order.status = OrderStatus.PENDING_CANCEL
            await self._update_order(order)

            # Cancel order
            try:
                cancelled = await self._cancel_order(order)
                if cancelled:
                    order.status = OrderStatus.CANCELLED
                    await self._update_order(order)
                    return True
                else:
                    order.status = OrderStatus.FAILED
                    order.error_message = "Cancel failed"
                    await self._update_order(order)
                    return False
            except Exception as e:
                order.status = OrderStatus.FAILED
                order.error_message = str(e)
                await self._update_order(order)
                raise TradeExecutionError(f"Cancel failed: {e}")

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise TradeManagerError(f"Failed to cancel order: {e}")

    async def get_order(
        self,
        exchange: str,
        order_id: str,
    ) -> Optional[Order]:
        """
        Get an order.

        Args:
            exchange: Exchange name
            order_id: Order ID

        Returns:
            Order or None
        """
        async with self._lock:
            return self._orders.get(order_id)

    async def get_orders(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[Union[str, OrderStatus]] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        Get orders.

        Args:
            exchange: Exchange name (optional)
            symbol: Trading pair symbol (optional)
            status: Order status (optional)
            limit: Maximum number of orders

        Returns:
            List of Order
        """
        orders = []

        async with self._lock:
            for order in self._orders.values():
                if exchange and order.exchange != exchange:
                    continue
                if symbol and order.symbol != symbol:
                    continue
                if status:
                    if isinstance(status, str):
                        status = OrderStatus(status)
                    if order.status != status:
                        continue
                orders.append(order)

        # Sort by timestamp descending
        orders.sort(key=lambda o: o.timestamp, reverse=True)
        return orders[:limit]

    async def get_order_history(
        self,
        exchange: str,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        Get order history.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol (optional)
            limit: Maximum number of orders

        Returns:
            List of Order
        """
        orders = await self.get_orders(exchange, symbol, limit=limit)
        return [o for o in orders if o.is_terminal()]

    async def execute_arbitrage_trade(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        quantity: Union[float, Decimal, str],
        buy_price: Optional[Union[float, Decimal, str]] = None,
        sell_price: Optional[Union[float, Decimal, str]] = None,
        order_type: Union[str, OrderType] = OrderType.MARKET,
        time_in_force: Union[str, TimeInForce] = TimeInForce.GTC,
        slippage_tolerance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TradeResult:
        """
        Execute an arbitrage trade across two exchanges.

        Args:
            buy_exchange: Exchange to buy on
            sell_exchange: Exchange to sell on
            symbol: Trading pair symbol
            quantity: Trade quantity
            buy_price: Buy price (optional)
            sell_price: Sell price (optional)
            order_type: Order type
            time_in_force: Time in force
            slippage_tolerance: Slippage tolerance
            metadata: Additional metadata

        Returns:
            TradeResult instance
        """
        start_time = time.perf_counter()
        slippage_tolerance = slippage_tolerance or self.slippage_tolerance

        try:
            # Convert quantity
            quantity_decimal = self._to_decimal(quantity)
            buy_price_decimal = self._to_decimal(buy_price) if buy_price is not None else None
            sell_price_decimal = self._to_decimal(sell_price) if sell_price is not None else None

            if quantity_decimal <= 0:
                raise TradeValidationError(f"Invalid quantity: {quantity_decimal}")

            # Get prices
            buy_price_source = await self.price_manager.get_price(buy_exchange, symbol)
            sell_price_source = await self.price_manager.get_price(sell_exchange, symbol)

            if buy_price_source is None:
                raise TradeValidationError(f"No price found for {buy_exchange}:{symbol}")
            if sell_price_source is None:
                raise TradeValidationError(f"No price found for {sell_exchange}:{symbol}")

            # Get best prices
            buy_price = buy_price_decimal or buy_price_source.ask or buy_price_source.price
            sell_price = sell_price_decimal or sell_price_source.bid or sell_price_source.price

            # Calculate expected profit
            gross_profit = sell_price - buy_price
            gross_profit_pct = float(gross_profit / buy_price * 100) if buy_price > 0 else 0

            # Calculate fees
            fee_rate_buy = self._get_fee_rate(buy_exchange)
            fee_rate_sell = self._get_fee_rate(sell_exchange)

            buy_fees = buy_price * quantity_decimal * fee_rate_buy
            sell_fees = sell_price * quantity_decimal * fee_rate_sell
            total_fees = buy_fees + sell_fees

            net_profit = gross_profit * quantity_decimal - total_fees
            net_profit_pct = float(net_profit / (buy_price * quantity_decimal) * 100) if buy_price > 0 else 0

            # Check if profitable
            if net_profit <= 0:
                logger.warning(
                    f"Arbitrage not profitable: net_profit={net_profit}, "
                    f"buy={buy_price}, sell={sell_price}"
                )
                return TradeResult(
                    success=False,
                    error=f"Not profitable: net_profit={net_profit}",
                )

            # Check slippage
            buy_slippage = self._calculate_slippage(buy_exchange, symbol, buy_price)
            sell_slippage = self._calculate_slippage(sell_exchange, symbol, sell_price)

            if buy_slippage > slippage_tolerance:
                return TradeResult(
                    success=False,
                    error=f"Buy slippage {buy_slippage:.2f}% > tolerance {slippage_tolerance:.2f}%",
                )

            if sell_slippage > slippage_tolerance:
                return TradeResult(
                    success=False,
                    error=f"Sell slippage {sell_slippage:.2f}% > tolerance {slippage_tolerance:.2f}%",
                )

            # Place buy order
            buy_order = await self.place_order(
                exchange=buy_exchange,
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity_decimal,
                order_type=order_type,
                price=buy_price if order_type != OrderType.MARKET else None,
                time_in_force=time_in_force,
                metadata={"arbitrage": True, "counterpart": sell_exchange},
            )

            if buy_order.status == OrderStatus.FAILED:
                return TradeResult(
                    success=False,
                    error=f"Buy order failed: {buy_order.error_message}",
                )

            # Place sell order
            sell_order = await self.place_order(
                exchange=sell_exchange,
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity_decimal,
                order_type=order_type,
                price=sell_price if order_type != OrderType.MARKET else None,
                time_in_force=time_in_force,
                metadata={"arbitrage": True, "counterpart": buy_exchange},
            )

            if sell_order.status == OrderStatus.FAILED:
                # Try to cancel buy order
                try:
                    await self.cancel_order(buy_exchange, buy_order.id)
                except Exception as e:
                    logger.warning(f"Failed to cancel buy order: {e}")

                return TradeResult(
                    success=False,
                    error=f"Sell order failed: {sell_order.error_message}",
                )

            # Create arbitrage trade
            arbitrage_trade = ArbitrageTrade(
                symbol=symbol,
                buy_order=buy_order,
                sell_order=sell_order,
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                buy_price=buy_order.average_price or buy_price,
                sell_price=sell_order.average_price or sell_price,
                quantity=quantity_decimal,
                gross_profit=gross_profit * quantity_decimal,
                gross_profit_pct=gross_profit_pct,
                net_profit=net_profit,
                net_profit_pct=net_profit_pct,
                fees={
                    'buy_fee': buy_fees,
                    'sell_fee': sell_fees,
                    'total': total_fees,
                },
                status=TradeStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                metadata=metadata or {},
            )

            # Store arbitrage trade
            await self._store_arbitrage_trade(arbitrage_trade)

            # Update metrics
            await self._update_arbitrage_metrics(arbitrage_trade)

            logger.info(
                "Arbitrage trade completed: %s -> %s, profit=%.4f%%",
                buy_exchange, sell_exchange, net_profit_pct
            )

            return TradeResult(
                success=True,
                trade=arbitrage_trade,
                orders=[buy_order, sell_order],
                latency_ms=arbitrage_trade.latency_ms,
            )

        except Exception as e:
            logger.error(f"Arbitrage trade failed: {e}")
            return TradeResult(
                success=False,
                error=str(e),
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def get_position(
        self,
        exchange: str,
        symbol: str,
    ) -> Optional[Position]:
        """
        Get position for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol

        Returns:
            Position or None
        """
        async with self._lock:
            return self._positions.get(exchange, {}).get(symbol)

    async def get_positions(
        self,
        exchange: Optional[str] = None,
    ) -> List[Position]:
        """
        Get all positions.

        Args:
            exchange: Exchange name (optional)

        Returns:
            List of Position
        """
        positions = []

        async with self._lock:
            if exchange:
                for symbol, position in self._positions.get(exchange, {}).items():
                    positions.append(position)
            else:
                for exchange_positions in self._positions.values():
                    for position in exchange_positions.values():
                        positions.append(position)

        return positions

    async def get_trade_history(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """
        Get trade history.

        Args:
            exchange: Exchange name (optional)
            symbol: Trading pair symbol (optional)
            limit: Maximum number of trades

        Returns:
            List of Trade
        """
        trades = []

        async with self._lock:
            for trade in self._trades.values():
                if exchange and trade.exchange != exchange:
                    continue
                if symbol and trade.symbol != symbol:
                    continue
                trades.append(trade)

        trades.sort(key=lambda t: t.timestamp, reverse=True)
        return trades[:limit]

    async def get_arbitrage_history(
        self,
        limit: int = 100,
    ) -> List[ArbitrageTrade]:
        """
        Get arbitrage trade history.

        Args:
            limit: Maximum number of trades

        Returns:
            List of ArbitrageTrade
        """
        trades = []

        async with self._lock:
            trades = list(self._arbitrage_trades.values())

        trades.sort(key=lambda t: t.timestamp, reverse=True)
        return trades[:limit]

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._metrics,
            'total_orders': self._metrics['total_orders'],
            'active_orders': len([o for o in self._orders.values() if o.is_active()]),
            'positions': len(self._positions),
            'total_pnl': str(self._metrics['total_pnl']),
            'total_fees': str(self._metrics['total_fees']),
            'win_rate': self._metrics['win_rate'],
            'avg_profit_pct': self._metrics['avg_profit_pct'],
        }

    # ============================================================
    # EVENT HANDLING
    # ============================================================

    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register an event handler."""
        self._event_handlers[event_type].append(handler)

    async def _emit_event(self, event_type: str, data: Any) -> None:
        """Emit an event."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _to_decimal(self, value: Union[float, Decimal, str, None]) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except:
                return None
        return Decimal(str(value))

    def _get_fee_rate(self, exchange: str) -> Decimal:
        """Get fee rate for an exchange."""
        fee_rates = {
            'binance': Decimal('0.001'),
            'bybit': Decimal('0.001'),
            'coinbase': Decimal('0.005'),
            'kraken': Decimal('0.0026'),
            'okx': Decimal('0.001'),
            'gateio': Decimal('0.002'),
            'kucoin': Decimal('0.001'),
            'mexc': Decimal('0.001'),
            'bitget': Decimal('0.001'),
        }
        return fee_rates.get(exchange.lower(), Decimal('0.001'))

    def _calculate_slippage(
        self,
        exchange: str,
        symbol: str,
        expected_price: Decimal,
    ) -> float:
        """Calculate expected slippage."""
        # Get order book depth
        # For simplicity, use historical slippage
        slippage_history = self._slippage_history.get(f"{exchange}:{symbol}", [])
        if slippage_history:
            return statistics.mean(slippage_history)
        return 0.001  # Default 0.1%

    async def _validate_order(self, order: Order) -> bool:
        """Validate an order."""
        # Check quantity
        if order.quantity <= 0:
            return False

        # Check price
        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if order.price is None or order.price <= 0:
                return False

        # Check stop price
        if order.order_type == OrderType.STOP_LIMIT:
            if order.stop_price is None or order.stop_price <= 0:
                return False
            if order.limit_price is None or order.limit_price <= 0:
                return False

        # Validate against market
        try:
            price_source = await self.price_manager.get_price(order.exchange, order.symbol)
            if price_source is None:
                return False

            # Check price limits
            if order.price is not None:
                current_price = price_source.price
                if abs(float(order.price - current_price) / float(current_price)) > 0.5:
                    logger.warning(f"Order price {order.price} far from market {current_price}")
                    return False

        except Exception as e:
            logger.warning(f"Price validation failed: {e}")
            return False

        return True

    async def _execute_order(self, order: Order) -> Order:
        """Execute an order."""
        try:
            # Simulate order execution
            # In production, this would call the exchange API
            await asyncio.sleep(0.01)  # Simulate latency

            # Get current price
            price_source = await self.price_manager.get_price(order.exchange, order.symbol)
            if price_source is None:
                order.status = OrderStatus.FAILED
                order.error_message = "No price available"
                return order

            # Determine execution price
            if order.order_type == OrderType.MARKET:
                execution_price = price_source.price
            elif order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY:
                    # Check if limit price is below current price
                    if order.price and order.price >= price_source.price:
                        execution_price = price_source.price
                    else:
                        execution_price = order.price or price_source.price
                else:
                    if order.price and order.price <= price_source.price:
                        execution_price = price_source.price
                    else:
                        execution_price = order.price or price_source.price
            else:
                execution_price = order.price or price_source.price

            # Execute
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.average_price = execution_price
            order.updated_at = datetime.utcnow()

            # Calculate fees
            fee_rate = self._get_fee_rate(order.exchange)
            order.fees = order.quantity * execution_price * fee_rate
            order.commission = order.fees

            # Create trade
            trade = Trade(
                exchange=order.exchange,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=execution_price,
                total_value=order.quantity * execution_price,
                fees=order.fees,
                net_value=order.quantity * execution_price - order.fees,
                order_id=order.id,
                trade_type=TradeType.SPOT,
                metadata=order.metadata,
            )

            # Store trade
            await self._store_trade(trade)

            # Update position
            await self._update_position(trade)

            # Update metrics
            self._metrics['total_orders'] += 1
            self._metrics['successful_orders'] += 1

            await self._emit_event('order_filled', order)
            await self._emit_event('trade_executed', trade)

            return order

        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            self._metrics['total_orders'] += 1
            self._metrics['failed_orders'] += 1
            raise

    async def _cancel_order(self, order: Order) -> bool:
        """Cancel an order."""
        try:
            # Simulate cancellation
            await asyncio.sleep(0.01)
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    async def _store_order(self, order: Order) -> None:
        """Store an order."""
        async with self._lock:
            self._orders[order.id] = order
            if order.exchange not in self._order_history:
                self._order_history[order.exchange] = deque(maxlen=MAX_TRADE_HISTORY)
            self._order_history[order.exchange].append(order)

    async def _update_order(self, order: Order) -> None:
        """Update an order."""
        async with self._lock:
            if order.id in self._orders:
                self._orders[order.id] = order

    async def _store_trade(self, trade: Trade) -> None:
        """Store a trade."""
        async with self._lock:
            self._trades[trade.id] = trade
            if trade.exchange not in self._trade_history:
                self._trade_history[trade.exchange] = deque(maxlen=MAX_TRADE_HISTORY)
            self._trade_history[trade.exchange].append(trade)

    async def _store_arbitrage_trade(self, trade: ArbitrageTrade) -> None:
        """Store an arbitrage trade."""
        async with self._lock:
            self._arbitrage_trades[trade.id] = trade

    async def _update_position(self, trade: Trade) -> None:
        """Update position based on trade."""
        async with self._lock:
            if trade.exchange not in self._positions:
                self._positions[trade.exchange] = {}

            position = self._positions[trade.exchange].get(trade.symbol)

            if position is None:
                position = Position(
                    symbol=trade.symbol,
                    exchange=trade.exchange,
                    side=trade.side,
                    quantity=Decimal('0'),
                    average_price=Decimal('0'),
                )
                self._positions[trade.exchange][trade.symbol] = position

            # Update position
            if trade.side == OrderSide.BUY:
                total_cost = position.quantity * position.average_price + trade.total_value
                position.quantity += trade.quantity
                if position.quantity > 0:
                    position.average_price = total_cost / position.quantity
            else:
                if position.quantity >= trade.quantity:
                    position.quantity -= trade.quantity
                    if position.quantity > 0:
                        # Update average price
                        total_cost = position.quantity * position.average_price - trade.total_value
                        position.average_price = total_cost / position.quantity
                else:
                    # Short position
                    position.quantity -= trade.quantity

            # Update realized PnL
            if trade.side == OrderSide.SELL:
                realized_pnl = (trade.price - position.average_price) * trade.quantity
                position.realized_pnl += realized_pnl
                self._metrics['total_pnl'] += realized_pnl

            position.timestamp = datetime.utcnow()

    async def _update_arbitrage_metrics(self, trade: ArbitrageTrade) -> None:
        """Update arbitrage metrics."""
        self._metrics['total_arbitrage_trades'] += 1
        if trade.status == TradeStatus.COMPLETED:
            self._metrics['successful_arbitrage'] += 1
            self._metrics['total_pnl'] += trade.net_profit
            self._metrics['total_fees'] += sum(trade.fees.values())

            # Update win rate
            total = self._metrics['successful_arbitrage'] + self._metrics['failed_arbitrage']
            if total > 0:
                self._metrics['win_rate'] = self._metrics['successful_arbitrage'] / total

            # Update average profit
            total_profit = self._metrics['total_pnl']
            if self._metrics['successful_arbitrage'] > 0:
                self._metrics['avg_profit_pct'] = float(
                    total_profit / self._metrics['successful_arbitrage']
                )

        else:
            self._metrics['failed_arbitrage'] += 1

        self._metrics['last_trade_timestamp'] = datetime.utcnow().isoformat()

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the trade manager."""
        self._running = True
        logger.info("TradeManager started")

    async def stop(self) -> None:
        """Stop the trade manager."""
        self._running = False
        logger.info("TradeManager stopped")

    async def __aenter__(self) -> 'TradeManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_trade_manager(
    price_manager: PriceManager,
    config: Optional[TradeManagerConfig] = None,
    redis_client: Optional[Any] = None,
    cache_ttl: int = 5,
    max_retries: int = 3,
    slippage_tolerance: float = 0.01,
) -> TradeManager:
    """
    Create a trade manager instance.

    Args:
        price_manager: PriceManager instance
        config: Configuration instance
        redis_client: Redis client for caching
        cache_ttl: Cache TTL in seconds
        max_retries: Maximum number of retries
        slippage_tolerance: Slippage tolerance percentage

    Returns:
        TradeManager instance
    """
    return TradeManager(
        price_manager=price_manager,
        config=config,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
        max_retries=max_retries,
        slippage_tolerance=slippage_tolerance,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the trade manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize price manager
        from .price_manager import create_price_manager
        price_manager = create_price_manager()

        # Initialize trade manager
        trade_manager = create_trade_manager(price_manager)

        # Update some prices
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
        )

        await price_manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            bid=45010.0,
            ask=45030.0,
            volume=67.89,
        )

        # Place an order
        order = await trade_manager.place_order(
            exchange="binance",
            symbol="BTC-USDT",
            side="buy",
            quantity=0.1,
            order_type="market",
        )
        print(f"Order: {order.to_dict()}")

        # Execute arbitrage trade
        result = await trade_manager.execute_arbitrage_trade(
            buy_exchange="binance",
            sell_exchange="bybit",
            symbol="BTC-USDT",
            quantity=0.01,
        )
        if result.success:
            print(f"Arbitrage trade successful: profit={result.trade.net_profit_pct:.4f}%")
        else:
            print(f"Arbitrage trade failed: {result.error}")

        # Get positions
        positions = await trade_manager.get_positions()
        for pos in positions:
            print(f"Position: {pos.to_dict()}")

        # Get metrics
        metrics = trade_manager.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")

        await trade_manager.stop()
        await price_manager.stop()

    asyncio.run(main())
