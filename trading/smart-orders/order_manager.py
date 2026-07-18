"""
NEXUS AI TRADING SYSTEM - Order Manager Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/order_manager.py
Version: 1.0.0
Description: Centralized order management with full API integration
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Set
from enum import Enum
from collections import defaultdict

from pydantic import BaseModel, Field, ConfigDict

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import round_to_tick_size
from shared.constants.trading_constants import (
    MAX_ORDERS_PER_SYMBOL,
    MAX_OPEN_ORDERS,
    ORDER_EXPIRY_CHECK_INTERVAL
)
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async
from shared.utilities.circuit_breaker import CircuitBreaker

from trading.smart_orders.base_order import SmartOrder, SmartOrderConfig
from trading.smart_orders.trailing_stop import TrailingStop, TrailingStopConfig
from trading.smart_orders.smart_take_profit import SmartTakeProfit, SmartTakeProfitConfig
from trading.smart_orders.smart_stop import SmartStop, SmartStopConfig
from trading.smart_orders.scaling_order import ScalingOrder, ScalingOrderConfig

logger = get_logger(__name__)


class OrderTypeCategory(str, Enum):
    """Categories of order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    SMART = "smart"
    SCALING = "scaling"
    COMPOSITE = "composite"


class OrderPriority(str, Enum):
    """Order priority levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class OrderFilter(BaseModel):
    """Filter for querying orders"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    order_ids: Optional[List[str]] = Field(None, description="Filter by order IDs")
    symbols: Optional[List[str]] = Field(None, description="Filter by symbols")
    sides: Optional[List[OrderSide]] = Field(None, description="Filter by order sides")
    types: Optional[List[OrderType]] = Field(None, description="Filter by order types")
    statuses: Optional[List[OrderStatus]] = Field(None, description="Filter by statuses")
    min_price: Optional[float] = Field(None, description="Minimum price")
    max_price: Optional[float] = Field(None, description="Maximum price")
    created_after: Optional[datetime] = Field(None, description="Created after timestamp")
    created_before: Optional[datetime] = Field(None, description="Created before timestamp")
    updated_after: Optional[datetime] = Field(None, description="Updated after timestamp")
    updated_before: Optional[datetime] = Field(None, description="Updated before timestamp")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    priority: Optional[OrderPriority] = Field(None, description="Filter by priority")
    limit: int = Field(100, description="Maximum number of results")
    offset: int = Field(0, description="Offset for pagination")


class OrderSummary(BaseModel):
    """Summary of order statistics"""
    total_orders: int = Field(0, description="Total number of orders")
    open_orders: int = Field(0, description="Number of open orders")
    filled_orders: int = Field(0, description="Number of filled orders")
    cancelled_orders: int = Field(0, description="Number of cancelled orders")
    rejected_orders: int = Field(0, description="Number of rejected orders")
    expired_orders: int = Field(0, description="Number of expired orders")
    
    total_volume: float = Field(0.0, description="Total volume traded")
    total_value: float = Field(0.0, description="Total value traded")
    total_fees: float = Field(0.0, description="Total fees paid")
    average_fill_rate: float = Field(0.0, description="Average fill rate")
    
    orders_by_symbol: Dict[str, int] = Field(default_factory=dict, description="Orders per symbol")
    orders_by_type: Dict[str, int] = Field(default_factory=dict, description="Orders by type")
    orders_by_status: Dict[str, int] = Field(default_factory=dict, description="Orders by status")


class OrderEvent(BaseModel):
    """Order event for event-driven architecture"""
    event_type: str = Field(..., description="Event type")
    order_id: str = Field(..., description="Order ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")


class OrderManager:
    """
    Centralized order management system with full API integration.
    
    Features:
    - Order lifecycle management
    - Smart order coordination
    - Risk management
    - Position tracking
    - Event-driven architecture
    - Performance monitoring
    - Persistence support
    """

    def __init__(
        self,
        broker: BrokerInterface,
        persistence_backend: Optional[Any] = None,
        max_orders: int = MAX_OPEN_ORDERS,
        enable_persistence: bool = True,
        enable_events: bool = True
    ):
        """
        Initialize the order manager.

        Args:
            broker: Broker interface for order execution
            persistence_backend: Optional persistence backend
            max_orders: Maximum number of concurrent orders
            enable_persistence: Enable order persistence
            enable_events: Enable event emission
        """
        self._broker = broker
        self._persistence_backend = persistence_backend
        self._max_orders = max_orders
        self._enable_persistence = enable_persistence
        self._enable_events = enable_events

        # Order storage
        self._orders: Dict[str, SmartOrder] = {}
        self._order_status: Dict[str, OrderStatus] = {}
        self._order_mappings: Dict[str, str] = {}  # broker_order_id -> internal_order_id
        
        # Position tracking
        self._positions: Dict[str, Dict[str, Any]] = {}  # symbol -> position data
        self._position_summary: Dict[str, Dict[str, Any]] = {}
        
        # Event system
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_worker_task: Optional[asyncio.Task] = None
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Rate limiting
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        
        # Order tracking
        self._order_counter: int = 0
        self._order_by_symbol: Dict[str, Set[str]] = defaultdict(set)
        self._order_by_type: Dict[str, Set[str]] = defaultdict(set)
        self._order_by_status: Dict[str, Set[str]] = defaultdict(set)
        
        # Locks
        self._order_lock = asyncio.Lock()
        self._position_lock = asyncio.Lock()
        
        # Monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Startup
        self._initialized = False
        self._running = False

        logger.info(f"Initialized OrderManager with max_orders={max_orders}")

    async def initialize(self) -> bool:
        """
        Initialize the order manager.

        Returns:
            bool: True if initialized successfully
        """
        if self._initialized:
            return True

        try:
            # Initialize broker connection
            if hasattr(self._broker, 'initialize'):
                await self._broker.initialize()

            # Load persisted orders
            if self._enable_persistence and self._persistence_backend:
                await self._load_persisted_orders()

            # Start monitoring tasks
            await self._start_monitoring()

            # Start cleanup tasks
            await self._start_cleanup()

            # Start event worker
            if self._enable_events:
                await self._start_event_worker()

            self._initialized = True
            self._running = True

            logger.info("OrderManager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize OrderManager: {e}")
            return False

    async def shutdown(self):
        """Shutdown the order manager gracefully."""
        self._running = False

        # Cancel tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._event_worker_task:
            self._event_worker_task.cancel()

        # Cancel all orders
        await self.cancel_all_orders()

        # Persist orders
        if self._enable_persistence and self._persistence_backend:
            await self._persist_orders()

        logger.info("OrderManager shut down")

    # ==================== Order Management ====================

    async def place_order(
        self,
        order: SmartOrder,
        priority: OrderPriority = OrderPriority.MEDIUM
    ) -> Optional[str]:
        """
        Place a smart order.

        Args:
            order: Smart order instance
            priority: Order priority

        Returns:
            Optional[str]: Order ID if successful
        """
        async with self._order_lock:
            if len(self._orders) >= self._max_orders:
                logger.warning(f"Maximum orders reached: {self._max_orders}")
                return None

            if order.id in self._orders:
                logger.warning(f"Order {order.id} already exists")
                return None

            # Check symbol limit
            if len(self._order_by_symbol.get(order.config.symbol, set())) >= MAX_ORDERS_PER_SYMBOL:
                logger.warning(f"Maximum orders for symbol {order.config.symbol} reached")
                return None

            # Store order
            self._orders[order.id] = order
            self._order_status[order.id] = OrderStatus.PENDING
            self._order_by_symbol[order.config.symbol].add(order.id)
            self._order_by_type[order.__class__.__name__].add(order.id)
            self._order_by_status[OrderStatus.PENDING.value].add(order.id)

            # Generate unique order ID
            self._order_counter += 1
            order_id = order.id

            # Store broker mapping if available
            if hasattr(order, '_order_ids') and order._order_ids:
                for _, broker_id in order._order_ids.items():
                    self._order_mappings[broker_id] = order_id

            # Emit event
            await self._emit_event(OrderEvent(
                event_type="order_placed",
                order_id=order_id,
                data={
                    'order': await order.to_dict(),
                    'priority': priority.value
                }
            ))

            # Persist
            if self._enable_persistence:
                await self._persist_order(order_id)

            logger.info(f"Order {order_id} placed successfully")

            return order_id

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        async with self._order_lock:
            order = self._orders.get(order_id)
            if not order:
                logger.warning(f"Order {order_id} not found")
                return False

            if order.get_state() in ['EXECUTED', 'CANCELLED']:
                return False

            result = await order.cancel()
            if result:
                self._order_status[order_id] = OrderStatus.CANCELLED
                self._order_by_status[OrderStatus.PENDING.value].discard(order_id)
                self._order_by_status[OrderStatus.CANCELLED.value].add(order_id)

                await self._emit_event(OrderEvent(
                    event_type="order_cancelled",
                    order_id=order_id,
                    data={'order': await order.to_dict()}
                ))

                if self._enable_persistence:
                    await self._persist_order(order_id)

                logger.info(f"Order {order_id} cancelled")
                return True

            return False

    async def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
        order_type: Optional[str] = None
    ) -> int:
        """
        Cancel all orders with optional filters.

        Args:
            symbol: Optional symbol filter
            order_type: Optional order type filter

        Returns:
            int: Number of orders cancelled
        """
        cancelled_count = 0
        orders_to_cancel = []

        async with self._order_lock:
            for order_id, order in self._orders.items():
                if order.get_state() in ['EXECUTED', 'CANCELLED']:
                    continue

                if symbol and order.config.symbol != symbol:
                    continue

                if order_type and order.__class__.__name__ != order_type:
                    continue

                orders_to_cancel.append(order_id)

            for order_id in orders_to_cancel:
                if await self.cancel_order(order_id):
                    cancelled_count += 1

        logger.info(f"Cancelled {cancelled_count} orders")
        return cancelled_count

    async def get_order(self, order_id: str) -> Optional[SmartOrder]:
        """
        Get an order by ID.

        Args:
            order_id: Order ID

        Returns:
            Optional[SmartOrder]: Order instance
        """
        return self._orders.get(order_id)

    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status.

        Args:
            order_id: Order ID

        Returns:
            Optional[Dict]: Order status information
        """
        order = self._orders.get(order_id)
        if not order:
            return None

        return {
            'order_id': order_id,
            'state': order.get_state(),
            'status': self._order_status.get(order_id),
            'details': await order.to_dict()
        }

    async def get_orders(
        self,
        filter_params: Optional[OrderFilter] = None
    ) -> List[SmartOrder]:
        """
        Get orders with filtering.

        Args:
            filter_params: Filter parameters

        Returns:
            List[SmartOrder]: Matching orders
        """
        result = []
        filter_params = filter_params or OrderFilter()

        for order_id, order in self._orders.items():
            # Apply filters
            if filter_params.order_ids and order_id not in filter_params.order_ids:
                continue

            if filter_params.symbols and order.config.symbol not in filter_params.symbols:
                continue

            if filter_params.statuses and self._order_status.get(order_id) not in filter_params.statuses:
                continue

            # Add to result
            result.append(order)

        # Apply pagination
        start = filter_params.offset
        end = start + filter_params.limit
        return result[start:end]

    async def get_order_summary(self) -> OrderSummary:
        """
        Get order summary.

        Returns:
            OrderSummary: Order statistics
        """
        summary = OrderSummary()
        summary.total_orders = len(self._orders)

        for order_id, order in self._orders.items():
            status = self._order_status.get(order_id, OrderStatus.PENDING)
            symbol = order.config.symbol

            # Count by status
            if status == OrderStatus.FILLED:
                summary.filled_orders += 1
                summary.orders_by_status['filled'] = summary.orders_by_status.get('filled', 0) + 1
            elif status == OrderStatus.CANCELLED:
                summary.cancelled_orders += 1
                summary.orders_by_status['cancelled'] = summary.orders_by_status.get('cancelled', 0) + 1
            elif status == OrderStatus.REJECTED:
                summary.rejected_orders += 1
                summary.orders_by_status['rejected'] = summary.orders_by_status.get('rejected', 0) + 1
            elif status == OrderStatus.EXPIRED:
                summary.expired_orders += 1
                summary.orders_by_status['expired'] = summary.orders_by_status.get('expired', 0) + 1
            else:
                summary.open_orders += 1
                summary.orders_by_status['open'] = summary.orders_by_status.get('open', 0) + 1

            # Count by symbol
            summary.orders_by_symbol[symbol] = summary.orders_by_symbol.get(symbol, 0) + 1

            # Count by type
            order_type = order.__class__.__name__
            summary.orders_by_type[order_type] = summary.orders_by_type.get(order_type, 0) + 1

        return summary

    # ==================== Position Management ====================

    async def update_position(
        self,
        symbol: str,
        size: float,
        price: float,
        side: OrderSide
    ):
        """
        Update position tracking.

        Args:
            symbol: Symbol
            size: Position size
            price: Execution price
            side: Order side
        """
        async with self._position_lock:
            if symbol not in self._positions:
                self._positions[symbol] = {
                    'size': 0,
                    'average_price': 0,
                    'total_cost': 0,
                    'last_update': datetime.utcnow()
                }

            pos = self._positions[symbol]
            if side == OrderSide.BUY:
                pos['total_cost'] += size * price
                pos['size'] += size
            else:
                pos['total_cost'] -= size * price
                pos['size'] -= size

            if pos['size'] != 0:
                pos['average_price'] = pos['total_cost'] / pos['size']
            else:
                pos['average_price'] = 0
                pos['total_cost'] = 0

            pos['last_update'] = datetime.utcnow()

            await self._emit_event(OrderEvent(
                event_type="position_updated",
                order_id="",
                data={
                    'symbol': symbol,
                    'position': pos.copy()
                }
            ))

            logger.debug(f"Position updated for {symbol}: {pos}")

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for a symbol.

        Args:
            symbol: Symbol

        Returns:
            Optional[Dict]: Position data
        """
        return self._positions.get(symbol)

    async def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all positions.

        Returns:
            Dict: All positions
        """
        return self._positions.copy()

    async def get_position_summary(self) -> Dict[str, Any]:
        """
        Get position summary.

        Returns:
            Dict: Position summary
        """
        total_size = 0
        total_value = 0
        total_cost = 0

        for symbol, pos in self._positions.items():
            total_size += abs(pos['size'])
            total_value += abs(pos['size']) * pos['average_price']
            total_cost += abs(pos['total_cost'])

        return {
            'total_positions': len(self._positions),
            'total_size': total_size,
            'total_value': total_value,
            'total_cost': total_cost,
            'unrealized_pnl': total_value - total_cost,
            'positions': self._positions
        }

    # ==================== Smart Order Factory ====================

    def create_trailing_stop(
        self,
        config: Dict[str, Any]
    ) -> TrailingStop:
        """
        Create a trailing stop order.

        Args:
            config: Configuration dictionary

        Returns:
            TrailingStop: Trailing stop instance
        """
        order_config = TrailingStopConfig(**config)
        return TrailingStop(config=order_config, broker=self._broker)

    def create_smart_take_profit(
        self,
        config: Dict[str, Any]
    ) -> SmartTakeProfit:
        """
        Create a smart take profit order.

        Args:
            config: Configuration dictionary

        Returns:
            SmartTakeProfit: Smart take profit instance
        """
        order_config = SmartTakeProfitConfig(**config)
        return SmartTakeProfit(config=order_config, broker=self._broker)

    def create_smart_stop(
        self,
        config: Dict[str, Any]
    ) -> SmartStop:
        """
        Create a smart stop order.

        Args:
            config: Configuration dictionary

        Returns:
            SmartStop: Smart stop instance
        """
        order_config = SmartStopConfig(**config)
        return SmartStop(config=order_config, broker=self._broker)

    def create_scaling_order(
        self,
        config: Dict[str, Any]
    ) -> ScalingOrder:
        """
        Create a scaling order.

        Args:
            config: Configuration dictionary

        Returns:
            ScalingOrder: Scaling order instance
        """
        order_config = ScalingOrderConfig(**config)
        return ScalingOrder(config=order_config, broker=self._broker)

    # ==================== Event System ====================

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[OrderEvent], Awaitable[None]]
    ):
        """
        Subscribe to order events.

        Args:
            event_type: Event type to subscribe to
            handler: Async handler function
        """
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type} events")

    async def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[OrderEvent], Awaitable[None]]
    ):
        """
        Unsubscribe from order events.

        Args:
            event_type: Event type to unsubscribe from
            handler: Handler function to remove
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type].remove(handler)

    async def _emit_event(self, event: OrderEvent):
        """Emit an event to subscribers."""
        if not self._enable_events:
            return

        await self._event_queue.put(event)

    async def _start_event_worker(self):
        """Start the event worker task."""
        self._event_worker_task = asyncio.create_task(self._process_events())

    async def _process_events(self):
        """Process events from the queue."""
        while self._running:
            try:
                event = await self._event_queue.get()

                # Get handlers for this event type
                handlers = self._event_handlers.get(event.event_type, [])
                # Also get wildcard handlers
                wildcard_handlers = self._event_handlers.get('*', [])

                all_handlers = handlers + wildcard_handlers

                # Execute handlers
                for handler in all_handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")

                self._event_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    # ==================== Monitoring ====================

    async def _start_monitoring(self):
        """Start order monitoring task."""
        self._monitoring_task = asyncio.create_task(self._monitor_orders())

    async def _monitor_orders(self):
        """Monitor orders for changes."""
        while self._running:
            try:
                # Get all active orders
                active_orders = []
                for order_id, order in self._orders.items():
                    state = order.get_state()
                    if state in ['ACTIVE', 'PENDING', 'TRIGGERED']:
                        active_orders.append((order_id, order))

                # Check each order
                for order_id, order in active_orders:
                    try:
                        # Update from broker if needed
                        if hasattr(order, 'check_conditions'):
                            await order.check_conditions()

                        # Check for events
                        new_status = order.get_state()
                        old_status = self._order_status.get(order_id)

                        if new_status != old_status:
                            self._order_status[order_id] = new_status
                            self._order_by_status[old_status.value].discard(order_id)
                            self._order_by_status[new_status.value].add(order_id)

                            await self._emit_event(OrderEvent(
                                event_type=f"order_status_changed",
                                order_id=order_id,
                                data={
                                    'old_status': old_status.value if old_status else None,
                                    'new_status': new_status
                                }
                            ))

                    except Exception as e:
                        logger.error(f"Error monitoring order {order_id}: {e}")

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in order monitoring: {e}")

    async def _start_cleanup(self):
        """Start cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_orders())

    async def _cleanup_orders(self):
        """Clean up expired and completed orders."""
        while self._running:
            try:
                now = datetime.utcnow()
                expired_orders = []

                for order_id, order in self._orders.items():
                    # Check for expiration
                    if hasattr(order.config, 'expire_after') and order.config.expire_after:
                        created_at = getattr(order, 'created_at', None)
                        if created_at and (now - created_at) > order.config.expire_after:
                            expired_orders.append(order_id)

                    # Clean up completed orders from memory after some time
                    if order.get_state() in ['EXECUTED', 'CANCELLED', 'EXPIRED']:
                        # Keep in memory for some time before cleanup
                        if hasattr(order, 'completed_at'):
                            if (now - getattr(order, 'completed_at')).days > 7:
                                expired_orders.append(order_id)

                # Cancel expired orders
                for order_id in expired_orders:
                    await self.cancel_order(order_id)

                # Clean up old orders from active sets
                for order_id in expired_orders:
                    order = self._orders.get(order_id)
                    if order:
                        self._order_by_symbol[order.config.symbol].discard(order_id)
                        self._order_by_type[order.__class__.__name__].discard(order_id)

                await asyncio.sleep(ORDER_EXPIRY_CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in order cleanup: {e}")

    # ==================== Persistence ====================

    async def _persist_order(self, order_id: str):
        """Persist an order."""
        if not self._enable_persistence or not self._persistence_backend:
            return

        try:
            order = self._orders.get(order_id)
            if not order:
                return

            data = await order.to_dict()
            data['status'] = self._order_status.get(order_id)

            await self._persistence_backend.save(
                key=f"order:{order_id}",
                value=json.dumps(data, default=str)
            )

        except Exception as e:
            logger.error(f"Error persisting order {order_id}: {e}")

    async def _persist_orders(self):
        """Persist all orders."""
        if not self._enable_persistence or not self._persistence_backend:
            return

        try:
            for order_id in self._orders:
                await self._persist_order(order_id)

        except Exception as e:
            logger.error(f"Error persisting orders: {e}")

    async def _load_persisted_orders(self):
        """Load persisted orders."""
        if not self._enable_persistence or not self._persistence_backend:
            return

        try:
            # Get all order keys
            keys = await self._persistence_backend.scan("order:*")
            for key in keys:
                try:
                    data = await self._persistence_backend.get(key)
                    if not data:
                        continue

                    order_data = json.loads(data)
                    order_type = order_data.get('type', '')

                    # Recreate order based on type
                    order = None
                    if 'TrailingStop' in order_type:
                        order = self.create_trailing_stop(order_data.get('config', {}))
                    elif 'SmartTakeProfit' in order_type:
                        order = self.create_smart_take_profit(order_data.get('config', {}))
                    elif 'SmartStop' in order_type:
                        order = self.create_smart_stop(order_data.get('config', {}))
                    elif 'ScalingOrder' in order_type:
                        order = self.create_scaling_order(order_data.get('config', {}))

                    if order:
                        # Restore order state
                        order_id = order_data.get('id')
                        self._orders[order_id] = order
                        self._order_status[order_id] = OrderStatus(order_data.get('status', 'PENDING'))

                        # Restore order state from data
                        if hasattr(order, 'from_dict'):
                            await order.from_dict(order_data)

                        logger.debug(f"Loaded order {order_id} from persistence")

                except Exception as e:
                    logger.error(f"Error loading order from {key}: {e}")

        except Exception as e:
            logger.error(f"Error loading persisted orders: {e}")

    # ==================== Risk Management ====================

    async def check_risk_limits(self, order: SmartOrder) -> bool:
        """
        Check if order violates risk limits.

        Args:
            order: Order to check

        Returns:
            bool: True if risk limits are satisfied
        """
        # Check position limits
        symbol = order.config.symbol
        current_position = self._positions.get(symbol, {}).get('size', 0)

        # Determine proposed size change
        if hasattr(order, 'config'):
            order_size = getattr(order.config, 'order_size', 0)
            if hasattr(order, '_trade_direction') and order._trade_direction == OrderSide.SELL:
                order_size = -order_size
        else:
            order_size = 0

        # Check maximum position size
        max_position = getattr(self._broker, 'max_position_size', float('inf'))
        if abs(current_position + order_size) > max_position:
            logger.warning(f"Position limit exceeded for {symbol}")
            return False

        # Check maximum order value
        max_order_value = getattr(self._broker, 'max_order_value', float('inf'))
        if hasattr(order, 'config') and order.config.order_size * order.config.start_price > max_order_value:
            logger.warning(f"Order value limit exceeded")
            return False

        return True

    # ==================== Utility Methods ====================

    async def sync_with_broker(self):
        """Synchronize order state with broker."""
        try:
            # Get all open orders from broker
            broker_orders = await self._broker.get_open_orders()

            # Update local state
            for broker_order in broker_orders:
                broker_id = broker_order.get('order_id')
                order_id = self._order_mappings.get(broker_id)

                if order_id:
                    order = self._orders.get(order_id)
                    if order:
                        # Update order status
                        status = broker_order.get('status')
                        if status:
                            self._order_status[order_id] = status

                        # Update order data
                        if hasattr(order, '_order_ids'):
                            for level_idx, bid in order._order_ids.items():
                                if bid == broker_id:
                                    if hasattr(order, '_update_order_data'):
                                        await order._update_order_data(level_idx, broker_order)

                else:
                    # Unknown order from broker
                    logger.warning(f"Unknown broker order: {broker_id}")

        except Exception as e:
            logger.error(f"Error syncing with broker: {e}")

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get order history.

        Args:
            symbol: Optional symbol filter
            start_time: Optional start time
            end_time: Optional end time
            limit: Maximum number of results

        Returns:
            List[Dict]: Order history
        """
        history = []

        for order_id, order in self._orders.items():
            if symbol and order.config.symbol != symbol:
                continue

            order_data = await order.to_dict()
            order_data['order_id'] = order_id
            order_data['status'] = self._order_status.get(order_id)

            # Filter by time
            created_at = order_data.get('created_at')
            if created_at:
                if start_time and created_at < start_time:
                    continue
                if end_time and created_at > end_time:
                    continue

            history.append(order_data)

        # Sort by creation time
        history.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        return history[:limit]

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Dict: Performance metrics
        """
        metrics = {
            'total_orders': len(self._orders),
            'successful_orders': len(self._order_by_status.get(OrderStatus.FILLED.value, set())),
            'cancelled_orders': len(self._order_by_status.get(OrderStatus.CANCELLED.value, set())),
            'rejected_orders': len(self._order_by_status.get(OrderStatus.REJECTED.value, set())),
            'expired_orders': len(self._order_by_status.get(OrderStatus.EXPIRED.value, set())),
            'open_orders': len(self._order_by_status.get(OrderStatus.PENDING.value, set())),
            'active_positions': len(self._positions),
            'total_value': sum(
                abs(pos.get('size', 0) * pos.get('average_price', 0))
                for pos in self._positions.values()
            )
        }

        # Calculate fill rate
        total_completed = metrics['successful_orders'] + metrics['cancelled_orders'] + metrics['rejected_orders']
        if total_completed > 0:
            metrics['fill_rate'] = metrics['successful_orders'] / total_completed * 100
        else:
            metrics['fill_rate'] = 0

        return metrics

    # ==================== Error Handling ====================

    async def handle_order_error(self, order_id: str, error: Exception):
        """
        Handle order errors.

        Args:
            order_id: Order ID
            error: Exception that occurred
        """
        logger.error(f"Order error for {order_id}: {error}")

        # Update order status
        self._order_status[order_id] = OrderStatus.REJECTED
        self._order_by_status[OrderStatus.PENDING.value].discard(order_id)
        self._order_by_status[OrderStatus.REJECTED.value].add(order_id)

        # Emit error event
        await self._emit_event(OrderEvent(
            event_type="order_error",
            order_id=order_id,
            data={
                'error': str(error),
                'error_type': error.__class__.__name__
            }
        ))

        # Try to recover if possible
        if isinstance(error, ConnectionError):
            # Retry connection
            await asyncio.sleep(1)
            await self.sync_with_broker()

    # ==================== Cleanup ====================

    def __del__(self):
        """Destructor to ensure cleanup."""
        if self._initialized:
            asyncio.create_task(self.shutdown())
