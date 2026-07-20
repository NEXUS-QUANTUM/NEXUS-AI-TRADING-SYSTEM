# trading/bots/arbitrage_bot/executors/order_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Order Execution Engine

"""
Order Executor - Advanced Order Execution Engine

This module provides sophisticated order execution capabilities for
the NEXUS AI Trading System, handling order placement, management,
and monitoring across multiple exchanges.

Architecture:
    - BaseOrderExecutor: Abstract base class
    - OrderExecutor: Main executor implementation
    - OrderManager: Order lifecycle management
    - OrderMonitor: Order monitoring
    - OrderValidator: Order validation
    - OrderRouter: Smart order routing
    - ExecutionMonitor: Execution monitoring

Features:
    - Multi-exchange order execution
    - Smart order routing
    - Order lifecycle management
    - Order monitoring
    - Order validation
    - Slippage protection
    - MEV protection
    - Risk management
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    Callable,
    AsyncIterator,
    TypeVar,
    Generic,
)
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .base_executor import (
    BaseExecutor,
    ExecutionType,
    ExecutionStatus,
    ExecutionPriority,
    ExecutionRisk,
    ExecutionConfig,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionResult,
    ExecutionPlan,
    ExecutionListener,
)
from ..exchanges.base_exchange import (
    BaseExchange,
    ExchangeType,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Order,
    Trade,
    Position,
    Balance,
    Ticker,
)


# Constants
DEFAULT_ORDER_TIMEOUT = 30  # seconds
MAX_ORDER_RETRIES = 3
ORDER_RETRY_DELAY = 1  # seconds
MIN_ORDER_SIZE = Decimal("0.001")
MAX_ORDER_SIZE = Decimal("1000000")
SLIPPAGE_TOLERANCE = Decimal("0.01")  # 1%


@dataclass
class OrderConfig:
    """Order execution configuration."""
    default_timeout: int = DEFAULT_ORDER_TIMEOUT
    max_retries: int = MAX_ORDER_RETRIES
    retry_delay: int = ORDER_RETRY_DELAY
    min_order_size: Decimal = MIN_ORDER_SIZE
    max_order_size: Decimal = MAX_ORDER_SIZE
    slippage_tolerance: Decimal = SLIPPAGE_TOLERANCE
    smart_routing: bool = True
    require_confirmation: bool = True
    use_mev_protection: bool = True
    use_private_mempool: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderExecution:
    """Order execution details."""
    execution_id: str
    order: ExecutionOrder
    exchange_order: Optional[Order] = None
    trades: List[Trade] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    error: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class OrderRoute:
    """Order routing information."""
    exchange: ExchangeType
    price: Decimal
    quantity: Decimal
    estimated_fee: Decimal
    estimated_time_ms: int
    priority: int
    confidence: Decimal


@dataclass
class OrderResult:
    """Order execution result."""
    execution_id: str
    order: ExecutionOrder
    filled_quantity: Decimal
    average_price: Decimal
    total_cost: Decimal
    fee: Decimal
    fee_asset: Optional[str] = None
    trades: List[Trade] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class OrderExecutor(BaseExecutor):
    """
    Advanced Order Execution Engine.
    
    This class provides sophisticated order execution capabilities:
    1. Multi-exchange order execution
    2. Smart order routing
    3. Order lifecycle management
    4. Order monitoring
    5. Order validation
    6. Slippage protection
    7. MEV protection
    8. Risk management
    
    Features:
    - Multi-exchange execution
    - Smart order routing
    - Order lifecycle management
    - Order monitoring
    - Order validation
    - Slippage protection
    - MEV protection
    - Risk management
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        order_config: Optional[OrderConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the order executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            order_config: Order configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.order_config = order_config or OrderConfig()
        
        # Order tracking
        self.executions: Dict[str, OrderExecution] = {}
        self.active_executions: Set[str] = set()
        self.completed_executions: Set[str] = set()
        
        # Route cache
        self.route_cache: Dict[str, List[OrderRoute]] = {}
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._execution_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "orders_total": 0,
            "orders_succeeded": 0,
            "orders_failed": 0,
            "orders_cancelled": 0,
            "orders_retried": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
            "avg_execution_time_ms": 0,
            "success_rate": Decimal("0"),
            "avg_slippage": Decimal("0"),
            "smart_routing_hits": 0,
        })
        
        self.logger.info("OrderExecutor initialized")
    
    def _generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        import uuid
        return f"ord_exec_{uuid.uuid4().hex[:16]}"
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _validate_order(self, order: ExecutionOrder) -> Tuple[bool, Optional[str]]:
        """
        Validate an order.
        
        Args:
            order: Execution order
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check quantity
            if order.quantity <= Decimal("0"):
                return False, "Invalid quantity"
            
            if order.quantity < self.order_config.min_order_size:
                return False, f"Order size too small: {order.quantity}"
            
            if order.quantity > self.order_config.max_order_size:
                return False, f"Order size too large: {order.quantity}"
            
            # Check price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if order.price is None or order.price <= Decimal("0"):
                    return False, "Invalid price"
            
            # Check stop price for stop orders
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if order.stop_price is None or order.stop_price <= Decimal("0"):
                    return False, "Invalid stop price"
            
            # Check exchange
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return False, f"Exchange not found: {order.exchange}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def _get_order_route(
        self,
        order: ExecutionOrder,
    ) -> List[OrderRoute]:
        """
        Get order routes for smart routing.
        
        Args:
            order: Execution order
            
        Returns:
            List of OrderRoute objects
        """
        try:
            routes = []
            
            # Check if smart routing is enabled
            if not self.order_config.smart_routing:
                return [
                    OrderRoute(
                        exchange=order.exchange,
                        price=order.price or Decimal("0"),
                        quantity=order.quantity,
                        estimated_fee=Decimal("0.001"),
                        estimated_time_ms=100,
                        priority=1,
                        confidence=Decimal("0.8"),
                    )
                ]
            
            # Get ticker for each exchange
            for exchange_type, exchange in self.exchanges.items():
                if exchange_type == order.exchange:
                    try:
                        ticker = await exchange.get_ticker(order.symbol)
                        if ticker:
                            price = ticker.bid if order.side == OrderSide.BUY else ticker.ask
                            routes.append(OrderRoute(
                                exchange=exchange_type,
                                price=price or Decimal("0"),
                                quantity=order.quantity,
                                estimated_fee=Decimal("0.001"),
                                estimated_time_ms=50,
                                priority=1,
                                confidence=Decimal("0.9"),
                            ))
                    except Exception:
                        continue
            
            # Sort by price (best price first)
            if order.side == OrderSide.BUY:
                routes.sort(key=lambda r: r.price)
            else:
                routes.sort(key=lambda r: -r.price)
            
            return routes
            
        except Exception as e:
            self.logger.error(f"Route calculation failed: {e}")
            return []
    
    async def _execute_order_single(
        self,
        order: ExecutionOrder,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute a single order.
        
        Args:
            order: Execution order
            
        Returns:
            Tuple of (order_result, error_message)
        """
        try:
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return None, f"Exchange not found: {order.exchange}"
            
            # Place order
            result = await exchange.place_order(
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                stop_price=order.stop_price,
                time_in_force=order.time_in_force,
                reduce_only=order.reduce_only,
                post_only=order.post_only,
                client_order_id=order.client_order_id,
                **order.extra_params,
            )
            
            if result:
                return result, None
            else:
                return None, "Order placement failed"
            
        except Exception as e:
            return None, str(e)
    
    async def _execute_order_with_retry(
        self,
        order: ExecutionOrder,
        retry_count: int = 0,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute an order with retry logic.
        
        Args:
            order: Execution order
            retry_count: Current retry count
            
        Returns:
            Tuple of (order_result, error_message)
        """
        result, error = await self._execute_order_single(order)
        
        if error and retry_count < self.order_config.max_retries:
            self.metrics["orders_retried"] += 1
            self.logger.warning(f"Order retry {retry_count + 1}/{self.order_config.max_retries}: {error}")
            await asyncio.sleep(self.order_config.retry_delay)
            return await self._execute_order_with_retry(order, retry_count + 1)
        
        return result, error
    
    async def _monitor_order(
        self,
        order_id: str,
        symbol: str,
        exchange: ExchangeType,
        timeout: int = DEFAULT_ORDER_TIMEOUT,
    ) -> Tuple[bool, Optional[Order], Optional[str]]:
        """
        Monitor an order for completion.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            exchange: Exchange type
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_completed, order, error_message)
        """
        start_time = time.time()
        check_interval = 0.5
        
        while time.time() - start_time < timeout:
            try:
                exchange_obj = self._get_exchange(exchange)
                if not exchange_obj:
                    return False, None, "Exchange not found"
                
                order = await exchange_obj.get_order(order_id, symbol)
                if not order:
                    return False, None, "Order not found"
                
                if order.status == OrderStatus.FILLED:
                    return True, order, None
                elif order.status == OrderStatus.CANCELLED:
                    return False, order, "Order cancelled"
                elif order.status == OrderStatus.REJECTED:
                    return False, order, "Order rejected"
                elif order.status == OrderStatus.EXPIRED:
                    return False, order, "Order expired"
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.debug(f"Order monitoring error: {e}")
                await asyncio.sleep(check_interval)
        
        # Timeout
        return False, None, "Order monitoring timed out"
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute an order plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting order execution: {execution_id}")
        self._emit_started(execution_id)
        
        try:
            # Validate execution plan
            is_valid, error = await self.validate_execution(plan)
            if not is_valid:
                raise self.ValidationError(f"Invalid execution plan: {error}")
            
            # Check balance
            has_balance, error = await self.check_balance(plan)
            if not has_balance:
                raise self.BalanceError(f"Insufficient balance: {error}")
            
            # Calculate risk
            risk_metrics = await self.calculate_risk(plan)
            if risk_metrics.get("risk_level", ExecutionRisk.MEDIUM) == ExecutionRisk.CRITICAL:
                raise self.RiskError("Risk level too high")
            
            # Apply MEV protection
            if self.config.use_mev_protection:
                plan = await self.apply_mev_protection(plan)
            
            # Apply slippage protection
            plan = await self.apply_slippage_protection(plan)
            
            # Execute each order
            order_results = []
            failed_orders = []
            
            for order in plan.orders:
                # Validate order
                is_valid, error = await self._validate_order(order)
                if not is_valid:
                    failed_orders.append((order, error))
                    continue
                
                # Get route
                routes = await self._get_order_route(order)
                if routes:
                    self.metrics["smart_routing_hits"] += 1
                    best_route = routes[0]
                    order.exchange = best_route.exchange
                    if order.side == OrderSide.BUY:
                        order.price = best_route.price
                    else:
                        order.price = best_route.price
                
                # Create execution record
                exec_record = OrderExecution(
                    execution_id=self._generate_execution_id(),
                    order=order,
                    status=ExecutionStatus.EXECUTING,
                    timestamp=datetime.utcnow(),
                )
                
                with self._execution_lock:
                    self.executions[exec_record.execution_id] = exec_record
                    self.active_executions.add(exec_record.execution_id)
                
                # Execute order
                result, error = await self._execute_order_with_retry(order)
                
                if error or not result:
                    exec_record.status = ExecutionStatus.FAILED
                    exec_record.error = error
                    failed_orders.append((order, error))
                    self.metrics["orders_failed"] += 1
                    continue
                
                # Monitor order
                completed, monitored_order, monitor_error = await self._monitor_order(
                    result.order_id,
                    order.symbol,
                    order.exchange,
                    self.order_config.default_timeout,
                )
                
                if not completed or monitor_error:
                    exec_record.status = ExecutionStatus.FAILED
                    exec_record.error = monitor_error or "Order not completed"
                    failed_orders.append((order, monitor_error))
                    self.metrics["orders_failed"] += 1
                    continue
                
                # Update execution record
                exec_record.exchange_order = monitored_order or result
                exec_record.status = ExecutionStatus.COMPLETED
                exec_record.completed_at = datetime.utcnow()
                
                # Get trades
                try:
                    exchange_obj = self._get_exchange(order.exchange)
                    if exchange_obj:
                        trades = await exchange_obj.get_trades(order.symbol)
                        exec_record.trades = trades or []
                except Exception:
                    pass
                
                order_results.append(result)
                self.metrics["orders_succeeded"] += 1
                
                # Update active executions
                with self._execution_lock:
                    self.active_executions.remove(exec_record.execution_id)
                    self.completed_executions.add(exec_record.execution_id)
            
            # Calculate results
            total_profit = Decimal("0")
            total_volume = Decimal("0")
            total_gas = Decimal("0")
            total_fees = Decimal("0")
            
            for result in order_results:
                if result:
                    total_volume += result.quantity * result.price
                    total_fees += result.fee
                    # Simplified profit calculation
                    profit = (result.price * result.quantity) * Decimal("0.01")
                    total_profit += profit
            
            # Update metrics
            self.metrics["orders_total"] += len(plan.orders)
            self.metrics["total_volume"] += total_volume
            self.metrics["total_fees"] += total_fees
            
            if len(order_results) > 0:
                self.metrics["success_rate"] = (
                    len(order_results) / len(plan.orders)
                )
            
            # Create result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED if not failed_orders else ExecutionStatus.PARTIALLY_EXECUTED,
                orders=order_results,
                trades=[],
                positions=[],
                profit=total_profit,
                profit_percentage=(
                    total_profit / total_volume * Decimal("100")
                    if total_volume > 0 else Decimal("0")
                ),
                gas_cost=total_gas,
                fee_cost=total_fees,
                total_cost=total_volume,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                error=f"{len(failed_orders)} orders failed" if failed_orders else None,
                metadata={
                    "total_orders": len(plan.orders),
                    "successful_orders": len(order_results),
                    "failed_orders": len(failed_orders),
                    "avg_price": str(total_volume / len(order_results) if order_results else Decimal("0")),
                },
            )
            
            # Store result
            self.results[execution_id] = result
            
            # Update metrics
            self.metrics["executions_total"] += 1
            if result.status == ExecutionStatus.COMPLETED:
                self.metrics["executions_succeeded"] += 1
            elif result.status == ExecutionStatus.FAILED:
                self.metrics["executions_failed"] += 1
            
            self.metrics["avg_execution_time_ms"] = (
                (self.metrics["avg_execution_time_ms"] * (self.metrics["executions_total"] - 1) +
                 result.execution_time_ms) / self.metrics["executions_total"]
            )
            
            # Emit completion event
            self._emit_completed(result)
            
            self.logger.info(
                f"Order execution completed: {execution_id} "
                f"orders: {len(order_results)}/{len(plan.orders)}, "
                f"profit: ${float(result.profit):.2f}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Order execution failed: {error_msg}")
            self.metrics["errors"] += 1
            self.metrics["executions_failed"] += 1
            
            # Emit failure event
            self._emit_failed(execution_id, error_msg)
            
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                orders=[],
                trades=[],
                positions=[],
                profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fee_cost=Decimal("0"),
                total_cost=Decimal("0"),
                execution_time_ms=self._calculate_execution_time(start_time),
                timestamp=datetime.utcnow(),
                error=error_msg,
            )
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel an execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if cancelled successfully
        """
        self.logger.info(f"Cancelling execution: {execution_id}")
        
        cancelled = 0
        
        # Find and cancel active orders
        with self._execution_lock:
            for exec_id, execution in self.executions.items():
                if execution.status in [ExecutionStatus.PENDING, ExecutionStatus.EXECUTING]:
                    try:
                        exchange = self._get_exchange(execution.order.exchange)
                        if exchange and execution.exchange_order:
                            result = await exchange.cancel_order(
                                execution.exchange_order.order_id,
                                execution.order.symbol,
                            )
                            if result:
                                execution.status = ExecutionStatus.CANCELLED
                                cancelled += 1
                    except Exception as e:
                        self.logger.error(f"Failed to cancel order: {e}")
        
        self._emit_cancelled(execution_id)
        
        return cancelled > 0
    
    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """
        Get execution status.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionStatus or None
        """
        result = self.results.get(execution_id)
        if result:
            return result.status
        
        return None
    
    async def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """
        Get execution result.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionResult or None
        """
        return self.results.get(execution_id)
    
    async def simulate_execution(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Simulate execution without placing real orders.
        
        Args:
            plan: Execution plan
            
        Returns:
            Simulated ExecutionResult
        """
        self.logger.info(f"Simulating order execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate orders
        simulated_orders = []
        total_volume = Decimal("0")
        total_profit = Decimal("0")
        
        for order in plan.orders:
            simulated_order = Order(
                order_id=f"sim_{order.client_order_id or 'order'}",
                exchange=order.exchange,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                filled_quantity=order.quantity,
                status=OrderStatus.FILLED,
                created_at=datetime.utcnow(),
                client_order_id=order.client_order_id,
            )
            simulated_orders.append(simulated_order)
            
            total_volume += order.quantity * (order.price or Decimal("1"))
            profit = order.quantity * Decimal("0.01")  # 1% profit
            total_profit += profit
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=simulated_orders,
            trades=[],
            positions=[],
            profit=total_profit,
            profit_percentage=total_profit / total_volume * Decimal("100") if total_volume > 0 else Decimal("0"),
            gas_cost=Decimal("0.001"),
            fee_cost=Decimal("0.001"),
            total_cost=total_volume,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            metadata={"simulated": True},
        )
        
        return result
    
    async def validate_execution(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Validate an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check orders
            if not plan.orders:
                return False, "No orders to execute"
            
            # Validate each order
            for order in plan.orders:
                is_valid, error = await self._validate_order(order)
                if not is_valid:
                    return False, f"Invalid order: {error}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def calculate_risk(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Calculate risk metrics for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Risk metrics dictionary
        """
        try:
            total_value = sum(order.quantity * (order.price or Decimal("1")) for order in plan.orders)
            
            risk_ratio = total_value / (self.config.max_position_size or Decimal("100000"))
            if risk_ratio > Decimal("0.8"):
                risk_level = ExecutionRisk.CRITICAL
            elif risk_ratio > Decimal("0.5"):
                risk_level = ExecutionRisk.HIGH
            elif risk_ratio > Decimal("0.2"):
                risk_level = ExecutionRisk.MEDIUM
            else:
                risk_level = ExecutionRisk.LOW
            
            return {
                "total_value": total_value,
                "risk_ratio": risk_ratio,
                "risk_level": risk_level,
                "order_count": len(plan.orders),
                "symbols": list(set(o.symbol for o in plan.orders)),
                "exchanges": list(set(o.exchange for o in plan.orders)),
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
                "order_count": 0,
                "symbols": [],
                "exchanges": [],
                "error": str(e),
            }
    
    async def check_balance(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Check if there is sufficient balance for execution.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (has_balance, error_message)
        """
        try:
            # Group orders by exchange
            exchange_orders: Dict[ExchangeType, List[ExecutionOrder]] = defaultdict(list)
            for order in plan.orders:
                exchange_orders[order.exchange].append(order)
            
            for exchange_type, orders in exchange_orders.items():
                exchange = self._get_exchange(exchange_type)
                if not exchange:
                    return False, f"Exchange not found: {exchange_type}"
                
                balances = await exchange.get_balances()
                
                for order in orders:
                    asset = order.symbol.split("/")[0]
                    required = order.quantity * (order.price or Decimal("1"))
                    
                    balance = balances.get(asset)
                    if not balance:
                        return False, f"No balance for {asset}"
                    
                    if balance.free < required:
                        return False, f"Insufficient balance: {asset} ({balance.free} < {required})"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def apply_mev_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply MEV protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        for order in plan.orders:
            order.extra_params["mev_protection"] = True
            order.extra_params["private_mempool"] = self.config.use_private_mempool
        
        return plan
    
    async def apply_slippage_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply slippage protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        for order in plan.orders:
            order.extra_params["slippage_tolerance"] = self.config.max_slippage
        
        return plan
    
    async def optimize_gas(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize gas costs for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Optimized execution plan
        """
        # Group orders by exchange to reduce gas costs
        exchange_orders: Dict[ExchangeType, List[ExecutionOrder]] = defaultdict(list)
        for order in plan.orders:
            exchange_orders[order.exchange].append(order)
        
        optimized_orders = []
        for exchange_type, orders in exchange_orders.items():
            # Optimize orders for each exchange
            optimized_orders.extend(self._optimize_order_batching(orders))
        
        plan.orders = optimized_orders
        return plan
    
    def _optimize_order_batching(self, orders: List[ExecutionOrder]) -> List[ExecutionOrder]:
        """
        Optimize order batching for gas efficiency.
        
        Args:
            orders: List of orders
            
        Returns:
            Optimized orders
        """
        # Group by symbol and side
        grouped = defaultdict(list)
        for order in orders:
            key = f"{order.symbol}_{order.side.value}_{order.exchange.value}"
            grouped[key].append(order)
        
        optimized = []
        for key, order_group in grouped.items():
            if len(order_group) > 1:
                combined = order_group[0]
                combined.quantity = sum(o.quantity for o in order_group)
                optimized.append(combined)
            else:
                optimized.append(order_group[0])
        
        return optimized
    
    def get_executions(self) -> Dict[str, OrderExecution]:
        """
        Get all order executions.
        
        Returns:
            Dictionary of execution ID to OrderExecution
        """
        with self._execution_lock:
            return self.executions.copy()
    
    def get_active_executions(self) -> List[str]:
        """
        Get active execution IDs.
        
        Returns:
            List of active execution IDs
        """
        with self._execution_lock:
            return list(self.active_executions)
    
    def get_completed_executions(self) -> List[str]:
        """
        Get completed execution IDs.
        
        Returns:
            List of completed execution IDs
        """
        with self._execution_lock:
            return list(self.completed_executions)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **super().get_metrics(),
            "orders_total": self.metrics["orders_total"],
            "orders_succeeded": self.metrics["orders_succeeded"],
            "orders_failed": self.metrics["orders_failed"],
            "orders_cancelled": self.metrics["orders_cancelled"],
            "orders_retried": self.metrics["orders_retried"],
            "total_volume": float(self.metrics["total_volume"]),
            "total_fees": float(self.metrics["total_fees"]),
            "avg_execution_time_ms": self.metrics["avg_execution_time_ms"],
            "success_rate": float(self.metrics["success_rate"]),
            "avg_slippage": float(self.metrics["avg_slippage"]),
            "smart_routing_hits": self.metrics["smart_routing_hits"],
            "active_executions": len(self.active_executions),
            "completed_executions": len(self.completed_executions),
            "total_executions": len(self.executions),
        }


# Module exports
__all__ = [
    'OrderExecutor',
    'OrderConfig',
    'OrderExecution',
    'OrderRoute',
    'OrderResult',
]
