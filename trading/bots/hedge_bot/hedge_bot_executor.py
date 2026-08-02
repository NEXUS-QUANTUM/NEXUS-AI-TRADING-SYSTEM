# trading/bots/hedge_bot/hedge_bot_executor.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class ExecutionType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    SOR = "sor"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ROUTING = "routing"
    EXECUTING = "executing"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class ExecutionSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    DAY = "day"
    GTD = "gtd"


@dataclass
class ExecutionOrder:
    id: str
    symbol: str
    side: ExecutionSide
    type: ExecutionType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: ExecutionStatus = ExecutionStatus.PENDING
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ExecutionFill:
    id: str
    order_id: str
    symbol: str
    side: ExecutionSide
    price: float
    quantity: float
    fee: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionStrategy:
    id: str
    name: str
    type: ExecutionType
    parameters: Dict[str, Any]
    priority: int = 0
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class HedgeBotExecutor:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._orders: Dict[str, ExecutionOrder] = {}
        self._fills: Dict[str, ExecutionFill] = {}
        self._strategies: Dict[str, ExecutionStrategy] = {}
        self._order_queue: asyncio.Queue = asyncio.Queue()
        self._executing_orders: Set[str] = set()
        self._observers: List[Callable] = []
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_strategies()

    def _initialize_default_strategies(self) -> None:
        default_strategies = [
            ExecutionStrategy(
                id="market_default",
                name="Market Execution",
                type=ExecutionType.MARKET,
                parameters={"slippage_tolerance": 0.01},
                priority=1
            ),
            ExecutionStrategy(
                id="limit_default",
                name="Limit Execution",
                type=ExecutionType.LIMIT,
                parameters={"price_offset": 0.001},
                priority=2
            ),
            ExecutionStrategy(
                id="twap_default",
                name="TWAP Execution",
                type=ExecutionType.TWAP,
                parameters={"duration": 60, "slices": 10},
                priority=3
            ),
            ExecutionStrategy(
                id="vwap_default",
                name="VWAP Execution",
                type=ExecutionType.VWAP,
                parameters={"duration": 60, "slices": 10},
                priority=3
            )
        ]
        
        for strategy in default_strategies:
            self._strategies[strategy.id] = strategy

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def submit_order(
        self,
        symbol: str,
        side: ExecutionSide,
        quantity: float,
        order_type: ExecutionType = ExecutionType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionOrder:
        async with self._lock:
            order_id = hashlib.md5(f"{symbol}_{side.value}_{time.time()}".encode()).hexdigest()
            
            order = ExecutionOrder(
                id=order_id,
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                limit_price=limit_price,
                time_in_force=time_in_force,
                status=ExecutionStatus.PENDING,
                metadata=metadata or {}
            )
            
            if strategy_id and strategy_id in self._strategies:
                strategy = self._strategies[strategy_id]
                order.metadata["strategy"] = strategy.name
                order.metadata["strategy_id"] = strategy_id
            else:
                # Use default strategy based on order type
                for strategy in self._strategies.values():
                    if strategy.type == order_type and strategy.active:
                        order.metadata["strategy"] = strategy.name
                        order.metadata["strategy_id"] = strategy.id
                        break
            
            self._orders[order_id] = order
            
            await self._notify_observers("order_submitted", order)
            
            await self._order_queue.put(order_id)
            return order

    async def execute_order(self, order_id: str) -> bool:
        async with self._lock:
            if order_id not in self._orders:
                return False
            
            order = self._orders[order_id]
            
            if order.status != ExecutionStatus.PENDING:
                return False
            
            if order_id in self._executing_orders:
                return False
            
            self._executing_orders.add(order_id)
            order.status = ExecutionStatus.EXECUTING
            
            await self._notify_observers("order_executing", order)
            
            try:
                if order.type == ExecutionType.MARKET:
                    await self._execute_market(order)
                elif order.type == ExecutionType.LIMIT:
                    await self._execute_limit(order)
                elif order.type == ExecutionType.STOP:
                    await self._execute_stop(order)
                elif order.type == ExecutionType.STOP_LIMIT:
                    await self._execute_stop_limit(order)
                elif order.type == ExecutionType.TRAILING_STOP:
                    await self._execute_trailing_stop(order)
                elif order.type == ExecutionType.TAKE_PROFIT:
                    await self._execute_take_profit(order)
                elif order.type == ExecutionType.TAKE_PROFIT_LIMIT:
                    await self._execute_take_profit_limit(order)
                elif order.type == ExecutionType.OCO:
                    await self._execute_oco(order)
                elif order.type == ExecutionType.ICEBERG:
                    await self._execute_iceberg(order)
                elif order.type == ExecutionType.TWAP:
                    await self._execute_twap(order)
                elif order.type == ExecutionType.VWAP:
                    await self._execute_vwap(order)
                elif order.type == ExecutionType.SOR:
                    await self._execute_sor(order)
                else:
                    raise ValueError(f"Unsupported order type: {order.type}")
                
            except Exception as e:
                logger.error(f"Error executing order {order_id}: {e}")
                order.status = ExecutionStatus.FAILED
                order.error = str(e)
                await self._notify_observers("order_failed", order)
            
            finally:
                self._executing_orders.discard(order_id)
            
            return True

    async def _execute_market(self, order: ExecutionOrder) -> None:
        # Simulate market execution with potential slippage
        await asyncio.sleep(0.1)
        
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        order.filled_quantity = order.quantity
        order.avg_price = price
        order.status = ExecutionStatus.FILLED
        order.executed_at = time.time()
        
        await self._create_fill(order, price, order.quantity)
        await self._notify_observers("order_filled", order)

    async def _execute_limit(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        limit_price = order.price or price
        
        if order.side == ExecutionSide.BUY and limit_price >= price:
            order.filled_quantity = order.quantity
            order.avg_price = price
            order.status = ExecutionStatus.FILLED
            order.executed_at = time.time()
            await self._create_fill(order, price, order.quantity)
        elif order.side == ExecutionSide.SELL and limit_price <= price:
            order.filled_quantity = order.quantity
            order.avg_price = price
            order.status = ExecutionStatus.FILLED
            order.executed_at = time.time()
            await self._create_fill(order, price, order.quantity)
        else:
            order.status = ExecutionStatus.PENDING
            # Place limit order
            order.status = ExecutionStatus.PENDING

    async def _execute_stop(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        stop_price = order.stop_price or 0
        
        if order.side == ExecutionSide.BUY and price >= stop_price:
            await self._execute_market(order)
        elif order.side == ExecutionSide.SELL and price <= stop_price:
            await self._execute_market(order)
        else:
            order.status = ExecutionStatus.PENDING

    async def _execute_stop_limit(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        stop_price = order.stop_price or 0
        limit_price = order.limit_price or order.price or 0
        
        if order.side == ExecutionSide.BUY and price >= stop_price:
            if price <= limit_price:
                await self._execute_limit(order)
            else:
                order.status = ExecutionStatus.PENDING
        elif order.side == ExecutionSide.SELL and price <= stop_price:
            if price >= limit_price:
                await self._execute_limit(order)
            else:
                order.status = ExecutionStatus.PENDING
        else:
            order.status = ExecutionStatus.PENDING

    async def _execute_trailing_stop(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        trail_amount = order.metadata.get("trail_amount", 0)
        trail_percent = order.metadata.get("trail_percent", 0)
        
        if trail_percent:
            trail_value = price * trail_percent
        else:
            trail_value = trail_amount
        
        if order.side == ExecutionSide.SELL:
            stop_price = price - trail_value
            if stop_price <= order.metadata.get("highest_price", price):
                order.metadata["highest_price"] = price
        else:
            stop_price = price + trail_value
            if stop_price >= order.metadata.get("lowest_price", price):
                order.metadata["lowest_price"] = price
        
        if order.side == ExecutionSide.SELL and stop_price >= order.metadata.get("stop_trigger", float('inf')):
            await self._execute_market(order)
        elif order.side == ExecutionSide.BUY and stop_price <= order.metadata.get("stop_trigger", 0):
            await self._execute_market(order)
        else:
            order.status = ExecutionStatus.PENDING

    async def _execute_take_profit(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        take_profit_price = order.price or 0
        
        if order.side == ExecutionSide.BUY and price >= take_profit_price:
            await self._execute_market(order)
        elif order.side == ExecutionSide.SELL and price <= take_profit_price:
            await self._execute_market(order)
        else:
            order.status = ExecutionStatus.PENDING

    async def _execute_take_profit_limit(self, order: ExecutionOrder) -> None:
        price = await self._get_market_price(order.symbol)
        if not price:
            order.status = ExecutionStatus.FAILED
            order.error = "Cannot get market price"
            return
        
        take_profit_price = order.price or 0
        limit_price = order.limit_price or 0
        
        if order.side == ExecutionSide.BUY and price >= take_profit_price:
            if price <= limit_price:
                await self._execute_limit(order)
            else:
                order.status = ExecutionStatus.PENDING
        elif order.side == ExecutionSide.SELL and price <= take_profit_price:
            if price >= limit_price:
                await self._execute_limit(order)
            else:
                order.status = ExecutionStatus.PENDING
        else:
            order.status = ExecutionStatus.PENDING

    async def _execute_oco(self, order: ExecutionOrder) -> None:
        # One-Cancels-Other: Place both a limit and a stop order
        limit_price = order.price or 0
        stop_price = order.stop_price or 0
        
        if order.side == ExecutionSide.BUY:
            # Buy limit at lower price, stop at higher price
            limit_order = await self.submit_order(
                order.symbol,
                ExecutionSide.BUY,
                order.quantity,
                ExecutionType.LIMIT,
                price=limit_price,
                metadata={"oco_parent": order.id}
            )
            
            stop_order = await self.submit_order(
                order.symbol,
                ExecutionSide.BUY,
                order.quantity,
                ExecutionType.STOP,
                stop_price=stop_price,
                metadata={"oco_parent": order.id}
            )
            
            order.metadata["limit_order_id"] = limit_order.id
            order.metadata["stop_order_id"] = stop_order.id

    async def _execute_iceberg(self, order: ExecutionOrder) -> None:
        visible_size = order.metadata.get("visible_size", order.quantity * 0.1)
        interval = order.metadata.get("interval", 1)
        
        remaining = order.quantity
        while remaining > 0:
            slice_size = min(visible_size, remaining)
            slice_order = await self.submit_order(
                order.symbol,
                order.side,
                slice_size,
                ExecutionType.LIMIT,
                price=order.price,
                metadata={"parent_order": order.id}
            )
            
            await asyncio.sleep(interval)
            remaining -= slice_size

    async def _execute_twap(self, order: ExecutionOrder) -> None:
        duration = order.metadata.get("duration", 60)
        slices = order.metadata.get("slices", 10)
        slice_size = order.quantity / slices
        interval = duration / slices
        
        for i in range(slices):
            slice_order = await self.submit_order(
                order.symbol,
                order.side,
                slice_size,
                ExecutionType.MARKET,
                metadata={"parent_order": order.id, "slice": i + 1}
            )
            
            if i < slices - 1:
                await asyncio.sleep(interval)

    async def _execute_vwap(self, order: ExecutionOrder) -> None:
        duration = order.metadata.get("duration", 60)
        slices = order.metadata.get("slices", 10)
        
        # Get volume profile
        volume_profile = await self._get_volume_profile(order.symbol, duration)
        
        total_volume = sum(volume_profile.values()) if volume_profile else 1
        
        for i in range(slices):
            slice_percent = volume_profile.get(i + 1, 1) / total_volume
            slice_size = order.quantity * slice_percent
            
            slice_order = await self.submit_order(
                order.symbol,
                order.side,
                slice_size,
                ExecutionType.MARKET,
                metadata={"parent_order": order.id, "slice": i + 1}
            )
            
            if i < slices - 1:
                await asyncio.sleep(duration / slices)

    async def _execute_sor(self, order: ExecutionOrder) -> None:
        # Smart Order Routing - Simulate routing to multiple venues
        venues = ["venue1", "venue2", "venue3"]
        
        remaining = order.quantity
        for venue in venues:
            if remaining <= 0:
                break
            
            venue_size = min(remaining, order.quantity * 0.4)
            await self.submit_order(
                order.symbol,
                order.side,
                venue_size,
                ExecutionType.MARKET,
                metadata={"venue": venue, "parent_order": order.id}
            )
            remaining -= venue_size

    async def _create_fill(self, order: ExecutionOrder, price: float, quantity: float) -> None:
        fill_id = hashlib.md5(f"{order.id}_{time.time()}".encode()).hexdigest()
        
        fill = ExecutionFill(
            id=fill_id,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=price,
            quantity=quantity,
            fee=price * quantity * 0.001,  # 0.1% fee
            timestamp=time.time()
        )
        
        self._fills[fill_id] = fill
        await self._notify_observers("fill_created", fill)

    async def _get_market_price(self, symbol: str) -> Optional[float]:
        # Simulate getting market price
        return 100.0

    async def _get_volume_profile(self, symbol: str, duration: int) -> Dict[int, float]:
        # Simulate volume profile
        import random
        return {i: random.uniform(0.5, 1.5) for i in range(1, 11)}

    async def cancel_order(self, order_id: str) -> bool:
        async with self._lock:
            if order_id not in self._orders:
                return False
            
            order = self._orders[order_id]
            
            if order.status in [ExecutionStatus.FILLED, ExecutionStatus.CANCELLED, ExecutionStatus.EXPIRED]:
                return False
            
            order.status = ExecutionStatus.CANCELLED
            await self._notify_observers("order_cancelled", order)
            return True

    async def get_order(self, order_id: str) -> Optional[ExecutionOrder]:
        return self._orders.get(order_id)

    async def get_orders(self, status: Optional[ExecutionStatus] = None) -> List[ExecutionOrder]:
        if status:
            return [o for o in self._orders.values() if o.status == status]
        return list(self._orders.values())

    async def get_fills(self, order_id: Optional[str] = None) -> List[ExecutionFill]:
        if order_id:
            return [f for f in self._fills.values() if f.order_id == order_id]
        return list(self._fills.values())

    async def get_strategy(self, strategy_id: str) -> Optional[ExecutionStrategy]:
        return self._strategies.get(strategy_id)

    async def get_strategies(self) -> List[ExecutionStrategy]:
        return list(self._strategies.values())

    async def _executor_loop(self) -> None:
        while self._running:
            try:
                order_id = await self._order_queue.get()
                await self.execute_order(order_id)
                self._order_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Executor loop error: {e}")
                await asyncio.sleep(1)

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                # Check for pending orders
                pending_orders = await self.get_orders(ExecutionStatus.PENDING)
                
                for order in pending_orders:
                    if order.type in [ExecutionType.LIMIT, ExecutionType.STOP, ExecutionType.STOP_LIMIT,
                                      ExecutionType.TRAILING_STOP, ExecutionType.TAKE_PROFIT,
                                      ExecutionType.TAKE_PROFIT_LIMIT]:
                        await self.execute_order(order.id)
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            
            self._running = True
            self._executor_task = asyncio.create_task(self._executor_loop())
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            
            logger.info("Executor started")

    async def stop(self) -> None:
        async with self._lock:
            self._running = False
            
            if self._executor_task:
                self._executor_task.cancel()
                try:
                    await self._executor_task
                except asyncio.CancelledError:
                    pass
                self._executor_task = None
            
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None
            
            logger.info("Executor stopped")

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        total_orders = len(self._orders)
        filled_orders = len([o for o in self._orders.values() if o.status == ExecutionStatus.FILLED])
        pending_orders = len([o for o in self._orders.values() if o.status == ExecutionStatus.PENDING])
        cancelled_orders = len([o for o in self._orders.values() if o.status == ExecutionStatus.CANCELLED])
        failed_orders = len([o for o in self._orders.values() if o.status == ExecutionStatus.FAILED])
        
        return {
            "orders": total_orders,
            "filled": filled_orders,
            "pending": pending_orders,
            "cancelled": cancelled_orders,
            "failed": failed_orders,
            "fills": len(self._fills),
            "strategies": len(self._strategies),
            "running": self._running
        }


__all__ = [
    "ExecutionType",
    "ExecutionStatus",
    "ExecutionSide",
    "TimeInForce",
    "ExecutionOrder",
    "ExecutionFill",
    "ExecutionStrategy",
    "HedgeBotExecutor"
]
