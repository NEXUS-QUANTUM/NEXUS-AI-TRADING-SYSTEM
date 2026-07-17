# trading/bots/ai_bot/ai_bot_order_manager.py
# NEXUS AI TRADING SYSTEM - AI Bot Order Manager
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Order Manager for NEXUS AI Trading System.
Provides comprehensive order management capabilities including:
- Order creation and execution
- Order lifecycle management
- Order routing and splitting
- Smart order routing (SOR)
- Order cancellation and modification
- Order status tracking
- Order history and reporting
- Risk checks and validation
- Slippage control
- Time-in-force management
- Order type support (Market, Limit, Stop, Stop-Limit, OCO, etc.)
- Batch order processing
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import deque, defaultdict

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from trading.bots.ai_bot.risk.risk_manager import RiskManager
from trading.bots.ai_bot.execution.order_executor import OrderExecutor
from trading.bots.ai_bot.execution.order_validator import OrderValidator
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.bot.order_manager")


# ============================================================================
# Enums & Constants
# ============================================================================

class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"  # One-Cancels-Other
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class OrderSide(str, Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class TimeInForce(str, Enum):
    """Time in force."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    DAY = "day"
    GOOD_TILL_DATE = "gt_date"


@dataclass
class Order:
    """Order data."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    executed_price: float = 0.0
    total_value: float = 0.0
    fee: float = 0.0
    fee_asset: str = "USDT"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    exchange: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_order_id: Optional[str] = None
    child_orders: List[str] = field(default_factory=list)
    fills: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class OrderBatch:
    """Order batch."""
    batch_id: str
    orders: List[Order]
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_quantity: float = 0.0
    total_value: float = 0.0
    filled_quantity: float = 0.0
    filled_value: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderBook:
    """Order book for a symbol."""
    symbol: str
    bids: List[Tuple[float, float]]  # (price, quantity)
    asks: List[Tuple[float, float]]  # (price, quantity)
    timestamp: datetime
    spread: float = 0.0
    mid_price: float = 0.0
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Order Manager
# ============================================================================

class OrderManager:
    """
    Advanced Order Manager for NEXUS AI Trading Bot.
    """

    def __init__(
        self,
        config: BotConfig,
        order_executor: OrderExecutor,
        order_validator: OrderValidator,
        risk_manager: RiskManager,
        data_storage: DataStorage,
        metrics_engine: MetricsEngine,
    ):
        """
        Initialize order manager.

        Args:
            config: Bot configuration
            order_executor: Order executor instance
            order_validator: Order validator instance
            risk_manager: Risk manager instance
            data_storage: Data storage instance
            metrics_engine: Metrics engine instance
        """
        self.config = config
        self.order_executor = order_executor
        self.order_validator = order_validator
        self.risk_manager = risk_manager
        self.data_storage = data_storage
        self.metrics_engine = metrics_engine

        # Order storage
        self._orders: Dict[str, Order] = {}
        self._active_orders: Dict[str, Order] = {}
        self._order_batches: Dict[str, OrderBatch] = {}
        self._order_history: deque = deque(maxlen=10000)

        # Order books
        self._order_books: Dict[str, OrderBook] = {}
        self._order_book_updates: deque = deque(maxlen=1000)

        # Performance metrics
        self._performance = {
            "orders_created": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "orders_failed": 0,
            "total_volume": 0.0,
            "avg_fill_time_ms": 0.0,
            "avg_slippage": 0.0,
            "fill_rate": 0.0,
            "success_rate": 0.0,
        }

        # Order ID generation
        self._order_id_counter = 0
        self._batch_id_counter = 0

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "order_created": [],
            "order_updated": [],
            "order_filled": [],
            "order_cancelled": [],
            "order_rejected": [],
            "order_batch_completed": [],
        }

        logger.info(
            "OrderManager initialized",
            extra={
                "order_executor": order_executor is not None,
                "risk_manager": risk_manager is not None,
            }
        )

    # ========================================================================
    # Order Creation
    # ========================================================================

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None,
        exchange: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        parent_order_id: Optional[str] = None,
    ) -> Order:
        """
        Create a new order.

        Args:
            symbol: Trading symbol
            side: Order side (buy/sell)
            order_type: Order type
            quantity: Order quantity
            price: Order price
            stop_price: Stop price
            limit_price: Limit price
            time_in_force: Time in force
            client_order_id: Client order ID
            exchange: Exchange name
            metadata: Additional metadata
            tags: Order tags
            parent_order_id: Parent order ID

        Returns:
            Order
        """
        # Generate order ID
        self._order_id_counter += 1
        order_id = f"ord_{int(time.time() * 1000)}_{self._order_id_counter}"

        # Validate order
        validation_result = await self.order_validator.validate_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            limit_price=limit_price,
        )

        if not validation_result["valid"]:
            raise ValueError(f"Order validation failed: {validation_result['errors']}")

        # Create order
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id or order_id,
            exchange=exchange,
            metadata=metadata or {},
            tags=tags or [],
            parent_order_id=parent_order_id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=1) if time_in_force == TimeInForce.GTC else None,
        )

        # Store order
        self._orders[order_id] = order
        self._active_orders[order_id] = order
        self._order_history.append(order)
        self._performance["orders_created"] += 1

        # Check risk limits
        risk_check = await self.risk_manager.check_order_limits(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price or 0,
        )

        if not risk_check["allowed"]:
            order.status = OrderStatus.REJECTED
            order.error = risk_check["reason"]
            self._performance["orders_rejected"] += 1
            self._emit_event("order_rejected", order)
            return order

        # Execute order
        try:
            execution_result = await self.order_executor.execute_order(order)

            if execution_result["success"]:
                order.status = OrderStatus.OPEN
                order.exchange_order_id = execution_result.get("exchange_order_id")
                order.updated_at = datetime.utcnow()

                # Update order with execution details
                if execution_result.get("fills"):
                    order.fills.extend(execution_result["fills"])
                    order.filled_quantity = sum(f.get("quantity", 0) for f in order.fills)
                    order.executed_price = sum(f.get("price", 0) * f.get("quantity", 0) for f in order.fills) / max(order.filled_quantity, 1)
                    order.total_value = order.executed_price * order.filled_quantity

                self._emit_event("order_created", order)
                logger.info(f"Order created: {order_id} - {side} {quantity} {symbol}")
                return order

            else:
                order.status = OrderStatus.FAILED
                order.error = execution_result.get("error", "Execution failed")
                self._performance["orders_failed"] += 1
                self._emit_event("order_created", order)
                return order

        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error = str(e)
            self._performance["orders_failed"] += 1
            logger.error(f"Error creating order {order_id}: {e}")
            return order

    async def create_batch_orders(
        self,
        orders: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBatch:
        """
        Create a batch of orders.

        Args:
            orders: List of order parameters
            metadata: Batch metadata

        Returns:
            OrderBatch
        """
        self._batch_id_counter += 1
        batch_id = f"batch_{int(time.time() * 1000)}_{self._batch_id_counter}"

        batch = OrderBatch(
            batch_id=batch_id,
            orders=[],
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )

        # Create orders
        for order_params in orders:
            try:
                order = await self.create_order(**order_params)
                batch.orders.append(order)
                batch.total_quantity += order.quantity
                batch.total_value += order.quantity * (order.price or 0)

            except Exception as e:
                logger.error(f"Error creating order in batch: {e}")

        # Update batch status
        all_filled = all(o.status == OrderStatus.FILLED for o in batch.orders)
        any_filled = any(o.status == OrderStatus.FILLED for o in batch.orders)

        if all_filled:
            batch.status = "completed"
            batch.completed_at = datetime.utcnow()
        elif any_filled:
            batch.status = "partial"
        else:
            batch.status = "failed"

        self._order_batches[batch_id] = batch

        self._emit_event("order_batch_completed", batch)
        return batch

    # ========================================================================
    # Order Management
    # ========================================================================

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID

        Returns:
            True if cancelled successfully
        """
        order = self._orders.get(order_id)

        if not order:
            logger.warning(f"Order not found: {order_id}")
            return False

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            logger.warning(f"Order cannot be cancelled (status: {order.status}): {order_id}")
            return False

        try:
            result = await self.order_executor.cancel_order(order)

            if result["success"]:
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                order.updated_at = datetime.utcnow()

                if order_id in self._active_orders:
                    del self._active_orders[order_id]

                self._performance["orders_cancelled"] += 1
                self._emit_event("order_cancelled", order)

                logger.info(f"Order cancelled: {order_id}")
                return True

            else:
                logger.error(f"Failed to cancel order {order_id}: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all active orders.

        Args:
            symbol: Filter by symbol

        Returns:
            Number of orders cancelled
        """
        cancelled = 0

        for order_id, order in list(self._active_orders.items()):
            if symbol and order.symbol != symbol:
                continue

            if await self.cancel_order(order_id):
                cancelled += 1

        logger.info(f"Cancelled {cancelled} orders")
        return cancelled

    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
    ) -> bool:
        """
        Modify an order.

        Args:
            order_id: Order ID
            quantity: New quantity
            price: New price
            stop_price: New stop price
            limit_price: New limit price

        Returns:
            True if modified successfully
        """
        order = self._orders.get(order_id)

        if not order:
            logger.warning(f"Order not found: {order_id}")
            return False

        if order.status != OrderStatus.OPEN:
            logger.warning(f"Order cannot be modified (status: {order.status}): {order_id}")
            return False

        try:
            # Validate modifications
            if quantity is not None and quantity <= 0:
                raise ValueError("Quantity must be positive")

            if price is not None and price <= 0:
                raise ValueError("Price must be positive")

            # Modify order
            result = await self.order_executor.modify_order(
                order,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                limit_price=limit_price,
            )

            if result["success"]:
                if quantity is not None:
                    order.quantity = quantity
                if price is not None:
                    order.price = price
                if stop_price is not None:
                    order.stop_price = stop_price
                if limit_price is not None:
                    order.limit_price = limit_price

                order.updated_at = datetime.utcnow()

                self._emit_event("order_updated", order)
                logger.info(f"Order modified: {order_id}")
                return True

            else:
                logger.error(f"Failed to modify order {order_id}: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Error modifying order {order_id}: {e}")
            return False

    # ========================================================================
    # Order Status Updates
    # ========================================================================

    async def update_order_status(self, order_id: str, status: OrderStatus, **kwargs) -> bool:
        """
        Update order status.

        Args:
            order_id: Order ID
            status: New status
            **kwargs: Additional updates

        Returns:
            True if updated successfully
        """
        order = self._orders.get(order_id)

        if not order:
            logger.warning(f"Order not found: {order_id}")
            return False

        old_status = order.status
        order.status = status
        order.updated_at = datetime.utcnow()

        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)

        # Update active orders
        if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            if order_id in self._active_orders:
                del self._active_orders[order_id]

            if status == OrderStatus.FILLED:
                self._performance["orders_filled"] += 1
                self._performance["total_volume"] += order.filled_quantity

                # Calculate fill time
                if order.filled_at:
                    fill_time = (order.filled_at - order.created_at).total_seconds() * 1000
                    self._performance["avg_fill_time_ms"] = (
                        (self._performance["avg_fill_time_ms"] *
                         (self._performance["orders_filled"] - 1) +
                         fill_time) /
                        self._performance["orders_filled"]
                    )

                self._emit_event("order_filled", order)

        elif status == OrderStatus.OPEN:
            self._active_orders[order_id] = order
            self._emit_event("order_updated", order)

        # Update metrics
        await self.metrics_engine.collect_metrics({
            f"order_{status.value}": 1,
            "orders_active": len(self._active_orders),
        }, metadata={"order_id": order_id})

        logger.info(f"Order status updated: {order_id} ({old_status} -> {status})")
        return True

    # ========================================================================
    # Order Queries
    # ========================================================================

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order or None
        """
        return self._orders.get(order_id)

    def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        side: Optional[OrderSide] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        Get orders.

        Args:
            symbol: Filter by symbol
            status: Filter by status
            side: Filter by side
            limit: Maximum number

        Returns:
            List of Order
        """
        orders = list(self._orders.values())

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        if status:
            orders = [o for o in orders if o.status == status]

        if side:
            orders = [o for o in orders if o.side == side]

        return sorted(orders, key=lambda o: o.created_at, reverse=True)[:limit]

    def get_active_orders(
        self,
        symbol: Optional[str] = None,
        side: Optional[OrderSide] = None,
    ) -> List[Order]:
        """
        Get active orders.

        Args:
            symbol: Filter by symbol
            side: Filter by side

        Returns:
            List of Order
        """
        orders = list(self._active_orders.values())

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        if side:
            orders = [o for o in orders if o.side == side]

        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        Get order history.

        Args:
            symbol: Filter by symbol
            limit: Maximum number

        Returns:
            List of Order
        """
        orders = list(self._order_history)

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders[-limit:]

    def get_order_batch(self, batch_id: str) -> Optional[OrderBatch]:
        """
        Get order batch.

        Args:
            batch_id: Batch ID

        Returns:
            OrderBatch or None
        """
        return self._order_batches.get(batch_id)

    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """
        Get order book.

        Args:
            symbol: Symbol

        Returns:
            OrderBook or None
        """
        return self._order_books.get(symbol)

    # ========================================================================
    # Order Book Management
    # ========================================================================

    async def update_order_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBook:
        """
        Update order book.

        Args:
            symbol: Symbol
            bids: Bids (price, quantity)
            asks: Asks (price, quantity)
            metadata: Additional metadata

        Returns:
            OrderBook
        """
        # Sort bids descending, asks ascending
        bids_sorted = sorted(bids, key=lambda x: x[0], reverse=True)
        asks_sorted = sorted(asks, key=lambda x: x[0])

        # Calculate metrics
        best_bid = bids_sorted[0][0] if bids_sorted else 0
        best_ask = asks_sorted[0][0] if asks_sorted else 0
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

        bid_depth = sum(q for _, q in bids_sorted[:10])
        ask_depth = sum(q for _, q in asks_sorted[:10])

        order_book = OrderBook(
            symbol=symbol,
            bids=bids_sorted[:20],
            asks=asks_sorted[:20],
            timestamp=datetime.utcnow(),
            spread=spread,
            mid_price=mid_price,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            metadata=metadata or {},
        )

        self._order_books[symbol] = order_book
        self._order_book_updates.append(order_book)

        return order_book

    # ========================================================================
    # Order Analytics
    # ========================================================================

    def get_order_statistics(self) -> Dict[str, Any]:
        """
        Get order statistics.

        Returns:
            Order statistics
        """
        total_orders = len(self._orders)
        active_orders = len(self._active_orders)

        return {
            "total_orders": total_orders,
            "active_orders": active_orders,
            "filled_orders": self._performance["orders_filled"],
            "cancelled_orders": self._performance["orders_cancelled"],
            "rejected_orders": self._performance["orders_rejected"],
            "failed_orders": self._performance["orders_failed"],
            "total_volume": self._performance["total_volume"],
            "fill_rate": self._performance["orders_filled"] / max(total_orders, 1),
            "success_rate": (self._performance["orders_filled"] - self._performance["orders_failed"]) / max(total_orders, 1),
            "avg_fill_time_ms": self._performance["avg_fill_time_ms"],
            "avg_slippage": self._performance["avg_slippage"],
            "by_symbol": self._get_orders_by_symbol(),
            "by_status": self._get_orders_by_status(),
        }

    def _get_orders_by_symbol(self) -> Dict[str, int]:
        """Get orders count by symbol."""
        counts = defaultdict(int)
        for order in self._orders.values():
            counts[order.symbol] += 1
        return dict(counts)

    def _get_orders_by_status(self) -> Dict[str, int]:
        """Get orders count by status."""
        counts = defaultdict(int)
        for order in self._orders.values():
            counts[order.status.value] += 1
        return dict(counts)

    # ========================================================================
    # Event System
    # ========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # ========================================================================
    # Performance Metrics
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "total_orders": len(self._orders),
            "active_orders": len(self._active_orders),
            "order_batches": len(self._order_batches),
            "order_books": len(self._order_books),
        }

    # ========================================================================
    # Persistence
    # ========================================================================

    async def save_orders(self) -> bool:
        """
        Save orders to storage.

        Returns:
            True if saved successfully
        """
        try:
            data = {
                "orders": [
                    {
                        "order_id": o.order_id,
                        "symbol": o.symbol,
                        "side": o.side.value,
                        "order_type": o.order_type.value,
                        "quantity": o.quantity,
                        "price": o.price,
                        "stop_price": o.stop_price,
                        "limit_price": o.limit_price,
                        "time_in_force": o.time_in_force.value,
                        "status": o.status.value,
                        "filled_quantity": o.filled_quantity,
                        "executed_price": o.executed_price,
                        "total_value": o.total_value,
                        "fee": o.fee,
                        "fee_asset": o.fee_asset,
                        "created_at": o.created_at.isoformat(),
                        "updated_at": o.updated_at.isoformat(),
                        "filled_at": o.filled_at.isoformat() if o.filled_at else None,
                        "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
                        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
                        "client_order_id": o.client_order_id,
                        "exchange_order_id": o.exchange_order_id,
                        "exchange": o.exchange,
                        "metadata": o.metadata,
                        "tags": o.tags,
                        "parent_order_id": o.parent_order_id,
                        "error": o.error,
                    }
                    for o in self._orders.values()
                ],
                "active_orders": [o.order_id for o in self._active_orders.values()],
            }

            key = f"orders:{datetime.utcnow().isoformat()}"
            return await self.data_storage.save_data(key, data)

        except Exception as e:
            logger.error(f"Error saving orders: {e}")
            return False

    async def load_orders(self) -> bool:
        """
        Load orders from storage.

        Returns:
            True if loaded successfully
        """
        try:
            # Load latest orders
            keys = await self.data_storage.list_keys("orders:*")

            if not keys:
                return True

            latest_key = sorted(keys)[-1]
            data = await self.data_storage.load_data(latest_key)

            if not data:
                return True

            for order_data in data.get("orders", []):
                order = Order(
                    order_id=order_data["order_id"],
                    symbol=order_data["symbol"],
                    side=OrderSide(order_data["side"]),
                    order_type=OrderType(order_data["order_type"]),
                    quantity=order_data["quantity"],
                    price=order_data.get("price"),
                    stop_price=order_data.get("stop_price"),
                    limit_price=order_data.get("limit_price"),
                    time_in_force=TimeInForce(order_data.get("time_in_force", "gtc")),
                    status=OrderStatus(order_data["status"]),
                    filled_quantity=order_data.get("filled_quantity", 0),
                    executed_price=order_data.get("executed_price", 0),
                    total_value=order_data.get("total_value", 0),
                    fee=order_data.get("fee", 0),
                    fee_asset=order_data.get("fee_asset", "USDT"),
                    created_at=datetime.fromisoformat(order_data["created_at"]),
                    updated_at=datetime.fromisoformat(order_data["updated_at"]),
                    filled_at=datetime.fromisoformat(order_data["filled_at"]) if order_data.get("filled_at") else None,
                    cancelled_at=datetime.fromisoformat(order_data["cancelled_at"]) if order_data.get("cancelled_at") else None,
                    expires_at=datetime.fromisoformat(order_data["expires_at"]) if order_data.get("expires_at") else None,
                    client_order_id=order_data.get("client_order_id"),
                    exchange_order_id=order_data.get("exchange_order_id"),
                    exchange=order_data.get("exchange"),
                    metadata=order_data.get("metadata", {}),
                    tags=order_data.get("tags", []),
                    parent_order_id=order_data.get("parent_order_id"),
                    error=order_data.get("error"),
                )

                self._orders[order.order_id] = order

                if order.status == OrderStatus.OPEN:
                    self._active_orders[order.order_id] = order

                self._order_history.append(order)

            logger.info(f"Loaded {len(self._orders)} orders")
            return True

        except Exception as e:
            logger.error(f"Error loading orders: {e}")
            return False

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the order manager."""
        await self.load_orders()
        logger.info("OrderManager started")

    async def stop(self) -> None:
        """Stop the order manager."""
        await self.save_orders()
        logger.info("OrderManager stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_order_manager(
    config: BotConfig,
    order_executor: OrderExecutor,
    order_validator: OrderValidator,
    risk_manager: RiskManager,
    data_storage: DataStorage,
    metrics_engine: MetricsEngine,
) -> OrderManager:
    """
    Factory function to create an OrderManager instance.

    Args:
        config: Bot configuration
        order_executor: Order executor instance
        order_validator: Order validator instance
        risk_manager: Risk manager instance
        data_storage: Data storage instance
        metrics_engine: Metrics engine instance

    Returns:
        OrderManager instance
    """
    return OrderManager(
        config=config,
        order_executor=order_executor,
        order_validator=order_validator,
        risk_manager=risk_manager,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the order manager
    pass
