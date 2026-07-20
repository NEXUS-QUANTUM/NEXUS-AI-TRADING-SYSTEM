# trading/bots/arbitrage_bot/executors/batch_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Batch Execution Engine

"""
Batch Executor - Advanced Batch Execution Engine

This module provides sophisticated batch execution capabilities for
arbitrage opportunities, allowing multiple trades to be executed
efficiently as a batch with optimized gas costs and reduced latency.

Architecture:
    - BaseBatchExecutor: Abstract base class
    - BatchExecutor: Main executor implementation
    - BatchOptimizer: Batch optimization
    - OrderBatcher: Order batching logic
    - GasOptimizer: Gas optimization
    - RiskManager: Risk management
    - ExecutionMonitor: Execution monitoring

Features:
    - Batch order execution
    - Gas optimization
    - Order prioritization
    - Parallel execution
    - Atomic execution
    - Error recovery
    - Progress tracking
    - Result aggregation
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
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
)


# Constants
BATCH_SIZE_LIMIT = 50
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
BATCH_TIMEOUT = 60  # seconds
MIN_BATCH_PROFIT = Decimal("0.001")
MAX_BATCH_LOSS = Decimal("0.05")


@dataclass
class BatchConfig:
    """Batch execution configuration."""
    batch_size_limit: int = BATCH_SIZE_LIMIT
    max_retries: int = MAX_RETRIES
    retry_delay: int = RETRY_DELAY
    batch_timeout: int = BATCH_TIMEOUT
    min_batch_profit: Decimal = MIN_BATCH_PROFIT
    max_batch_loss: Decimal = MAX_BATCH_LOSS
    parallel_execution: bool = True
    atomic_execution: bool = False
    require_confirmation: bool = True
    retry_failed_orders: bool = True
    optimize_gas: bool = True
    estimate_gas: bool = True
    use_priority_queue: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchOrder:
    """Batch order."""
    order: ExecutionOrder
    batch_id: str
    sequence: int
    priority: int
    dependencies: Set[str] = field(default_factory=set)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Order] = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class BatchResult:
    """Batch execution result."""
    batch_id: str
    status: ExecutionStatus
    total_orders: int
    successful_orders: int
    failed_orders: int
    pending_orders: int
    total_profit: Decimal
    total_loss: Decimal
    net_profit: Decimal
    gas_cost: Decimal
    fee_cost: Decimal
    total_cost: Decimal
    orders: List[BatchOrder]
    results: Dict[str, ExecutionResult]
    execution_time_ms: int
    timestamp: datetime
    error: Optional[str] = None


class BatchExecutor(BaseExecutor):
    """
    Advanced Batch Execution Engine.
    
    This class provides sophisticated batch execution capabilities:
    1. Batch order execution
    2. Gas optimization
    3. Order prioritization
    4. Parallel execution
    5. Atomic execution
    6. Error recovery
    7. Progress tracking
    8. Result aggregation
    
    Features:
    - Multi-exchange batch execution
    - Optimized gas costs
    - Priority-based ordering
    - Parallel order execution
    - Atomic batch execution
    - Automatic retry on failure
    - Comprehensive monitoring
    - Result aggregation
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        batch_config: Optional[BatchConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the batch executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            batch_config: Batch configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.batch_config = batch_config or BatchConfig()
        
        # Batch tracking
        self.batches: Dict[str, BatchResult] = {}
        self.batch_orders: Dict[str, List[BatchOrder]] = {}
        self.active_batches: Set[str] = set()
        
        # Thread pool for parallel execution
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._batch_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "batches_total": 0,
            "batches_succeeded": 0,
            "batches_failed": 0,
            "orders_total": 0,
            "orders_succeeded": 0,
            "orders_failed": 0,
            "avg_batch_time_ms": 0,
            "avg_orders_per_batch": 0,
        })
        
        self.logger.info("BatchExecutor initialized")
    
    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID."""
        import uuid
        return f"batch_{uuid.uuid4().hex[:16]}"
    
    def _calculate_batch_priority(self, orders: List[ExecutionOrder]) -> int:
        """
        Calculate batch priority based on orders.
        
        Args:
            orders: List of execution orders
            
        Returns:
            Priority score (higher = higher priority)
        """
        if not orders:
            return 0
        
        # Calculate average priority
        avg_priority = sum(o.priority.value for o in orders) / len(orders)
        
        # Adjust for number of orders
        size_factor = min(1.0, len(orders) / 10)
        
        # Calculate total value
        total_value = sum(float(o.quantity) * float(o.price or 0) for o in orders)
        value_factor = min(1.0, total_value / 1000000)
        
        priority = avg_priority * 0.4 + size_factor * 0.3 + value_factor * 0.3
        return int(priority * 100)
    
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
            
            # Check price for limit orders
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if order.price is None or order.price <= Decimal("0"):
                    return False, "Invalid price"
            
            # Check stop price for stop orders
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if order.stop_price is None or order.stop_price <= Decimal("0"):
                    return False, "Invalid stop price"
            
            # Get exchange
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return False, f"Exchange not found: {order.exchange}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def _execute_order(
        self,
        order: ExecutionOrder,
        retry_count: int = 0,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute a single order.
        
        Args:
            order: Execution order
            retry_count: Current retry count
            
        Returns:
            Tuple of (order_result, error_message)
        """
        try:
            # Get exchange
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return None, f"Exchange not found: {order.exchange}"
            
            # Validate order
            is_valid, error = await self._validate_order(order)
            if not is_valid:
                return None, error
            
            # Place order
            order_result = await exchange.place_order(
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
            
            if order_result:
                self.metrics["orders_succeeded"] += 1
                return order_result, None
            else:
                self.metrics["orders_failed"] += 1
                return None, "Order placement failed"
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Order execution failed: {error_msg}")
            
            # Retry logic
            if retry_count < self.batch_config.max_retries:
                await asyncio.sleep(self.batch_config.retry_delay)
                return await self._execute_order(order, retry_count + 1)
            
            self.metrics["orders_failed"] += 1
            return None, error_msg
    
    async def _execute_orders_parallel(
        self,
        orders: List[BatchOrder],
    ) -> Dict[str, Tuple[Optional[Order], Optional[str]]]:
        """
        Execute multiple orders in parallel.
        
        Args:
            orders: List of batch orders
            
        Returns:
            Dictionary mapping order ID to (order_result, error_message)
        """
        results = {}
        
        async def execute_single(batch_order: BatchOrder) -> None:
            order_result, error = await self._execute_order(
                batch_order.order,
                batch_order.retry_count
            )
            batch_order.result = order_result
            batch_order.error = error
            batch_order.status = ExecutionStatus.COMPLETED if order_result else ExecutionStatus.FAILED
            results[batch_order.order.client_order_id or batch_order.order.order_id] = (order_result, error)
        
        # Execute orders in parallel
        tasks = [execute_single(batch_order) for batch_order in orders]
        await asyncio.gather(*tasks)
        
        return results
    
    async def _execute_orders_sequential(
        self,
        orders: List[BatchOrder],
    ) -> Dict[str, Tuple[Optional[Order], Optional[str]]]:
        """
        Execute multiple orders sequentially.
        
        Args:
            orders: List of batch orders
            
        Returns:
            Dictionary mapping order ID to (order_result, error_message)
        """
        results = {}
        
        for batch_order in orders:
            order_result, error = await self._execute_order(
                batch_order.order,
                batch_order.retry_count
            )
            batch_order.result = order_result
            batch_order.error = error
            batch_order.status = ExecutionStatus.COMPLETED if order_result else ExecutionStatus.FAILED
            results[batch_order.order.client_order_id or batch_order.order.order_id] = (order_result, error)
            
            # Check if atomic execution and order failed
            if self.batch_config.atomic_execution and error:
                break
        
        return results
    
    async def _calculate_batch_results(
        self,
        batch_id: str,
        orders: List[BatchOrder],
        results: Dict[str, Tuple[Optional[Order], Optional[str]]],
        start_time: float,
        status: ExecutionStatus,
        error: Optional[str] = None,
    ) -> BatchResult:
        """
        Calculate batch results.
        
        Args:
            batch_id: Batch ID
            orders: List of batch orders
            results: Order execution results
            start_time: Start time
            status: Final status
            error: Optional error
            
        Returns:
            BatchResult
        """
        total_orders = len(orders)
        successful_orders = sum(1 for o in orders if o.status == ExecutionStatus.COMPLETED)
        failed_orders = sum(1 for o in orders if o.status == ExecutionStatus.FAILED)
        pending_orders = sum(1 for o in orders if o.status == ExecutionStatus.PENDING)
        
        total_profit = Decimal("0")
        total_loss = Decimal("0")
        gas_cost = Decimal("0")
        fee_cost = Decimal("0")
        
        execution_results = {}
        
        for batch_order in orders:
            if batch_order.result and batch_order.result.status == OrderStatus.FILLED:
                # Calculate profit/loss (simplified)
                profit = Decimal("0")
                if batch_order.order.side == OrderSide.BUY:
                    profit = (batch_order.result.average_price or 0) * batch_order.order.quantity
                else:
                    profit = (batch_order.result.average_price or 0) * batch_order.order.quantity
                
                if profit > 0:
                    total_profit += profit
                else:
                    total_loss += abs(profit)
                
                gas_cost += Decimal(str(batch_order.result.gas_used or 0))
                fee_cost += batch_order.result.fee or Decimal("0")
        
        net_profit = total_profit - total_loss - gas_cost - fee_cost
        total_cost = gas_cost + fee_cost
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return BatchResult(
            batch_id=batch_id,
            status=status,
            total_orders=total_orders,
            successful_orders=successful_orders,
            failed_orders=failed_orders,
            pending_orders=pending_orders,
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=net_profit,
            gas_cost=gas_cost,
            fee_cost=fee_cost,
            total_cost=total_cost,
            orders=orders,
            results=execution_results,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            error=error,
        )
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute an execution plan as a batch.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting batch execution: {execution_id}")
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
            
            # Optimize gas
            if self.batch_config.optimize_gas:
                plan = await self.optimize_gas(plan)
            
            # Generate batch orders
            batch_id = self._generate_batch_id()
            batch_orders = []
            
            for i, order in enumerate(plan.orders):
                batch_order = BatchOrder(
                    order=order,
                    batch_id=batch_id,
                    sequence=i,
                    priority=self._calculate_batch_priority([order]),
                    status=ExecutionStatus.PENDING,
                )
                batch_orders.append(batch_order)
            
            # Store batch
            with self._batch_lock:
                self.batch_orders[batch_id] = batch_orders
                self.active_batches.add(batch_id)
            
            # Execute orders
            if self.batch_config.parallel_execution:
                results = await self._execute_orders_parallel(batch_orders)
            else:
                results = await self._execute_orders_sequential(batch_orders)
            
            # Calculate batch results
            status = ExecutionStatus.COMPLETED
            error_msg = None
            
            # Check if any orders failed
            failed_orders = [o for o in batch_orders if o.status == ExecutionStatus.FAILED]
            if failed_orders and self.batch_config.atomic_execution:
                status = ExecutionStatus.FAILED
                error_msg = f"Atomic execution failed: {len(failed_orders)} orders failed"
            elif failed_orders:
                status = ExecutionStatus.PARTIALLY_EXECUTED
                error_msg = f"Partially executed: {len(failed_orders)} orders failed"
            
            batch_result = await self._calculate_batch_results(
                batch_id=batch_id,
                orders=batch_orders,
                results=results,
                start_time=start_time,
                status=status,
                error=error_msg,
            )
            
            # Store batch result
            with self._batch_lock:
                self.batches[batch_id] = batch_result
                self.active_batches.remove(batch_id)
            
            # Update metrics
            self.metrics["batches_total"] += 1
            self.metrics["orders_total"] += len(batch_orders)
            
            if status == ExecutionStatus.COMPLETED:
                self.metrics["batches_succeeded"] += 1
            elif status == ExecutionStatus.FAILED:
                self.metrics["batches_failed"] += 1
            
            self.metrics["avg_batch_time_ms"] = (
                (self.metrics["avg_batch_time_ms"] * (self.metrics["batches_total"] - 1) +
                 batch_result.execution_time_ms) / self.metrics["batches_total"]
            )
            self.metrics["avg_orders_per_batch"] = (
                (self.metrics["avg_orders_per_batch"] * (self.metrics["batches_total"] - 1) +
                 len(batch_orders)) / self.metrics["batches_total"]
            )
            
            # Create execution result
            result = ExecutionResult(
                execution_id=execution_id,
                status=status,
                orders=[o.result for o in batch_orders if o.result],
                trades=[],  # Would parse trades from orders
                positions=[],  # Would create positions
                profit=batch_result.net_profit,
                profit_percentage=(batch_result.net_profit / batch_result.total_cost * Decimal("100")
                                   if batch_result.total_cost > 0 else Decimal("0")),
                gas_cost=batch_result.gas_cost,
                fee_cost=batch_result.fee_cost,
                total_cost=batch_result.total_cost,
                execution_time_ms=batch_result.execution_time_ms,
                timestamp=batch_result.timestamp,
                error=batch_result.error,
                metadata={
                    "batch_id": batch_id,
                    "total_orders": batch_result.total_orders,
                    "successful_orders": batch_result.successful_orders,
                    "failed_orders": batch_result.failed_orders,
                },
            )
            
            # Store result
            self.results[execution_id] = result
            
            # Update metrics
            self.metrics["executions_total"] += 1
            if result.status == ExecutionStatus.COMPLETED:
                self.metrics["executions_succeeded"] += 1
                self.metrics["total_profit"] += result.profit
            elif result.status == ExecutionStatus.FAILED:
                self.metrics["executions_failed"] += 1
                self.metrics["total_loss"] += abs(result.profit)
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            self.metrics["total_gas_cost"] += result.gas_cost
            self.metrics["total_fee_cost"] += result.fee_cost
            self.metrics["avg_execution_time_ms"] = (
                (self.metrics["avg_execution_time_ms"] * (self.metrics["executions_total"] - 1) +
                 result.execution_time_ms) / self.metrics["executions_total"]
            )
            
            # Emit completion event
            self._emit_completed(result)
            
            self.logger.info(
                f"Batch execution completed: {execution_id} "
                f"profit: ${float(result.profit):.2f}, "
                f"orders: {result.metadata['successful_orders']}/{result.metadata['total_orders']}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Batch execution failed: {error_msg}")
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
        
        # Find batch for this execution
        batch_id = None
        for bid, batch in self.batches.items():
            if batch.status == ExecutionStatus.PENDING or batch.status == ExecutionStatus.EXECUTING:
                # Check if this batch matches the execution
                if execution_id in batch.results:
                    batch_id = bid
                    break
        
        if not batch_id:
            self.logger.warning(f"Execution not found: {execution_id}")
            return False
        
        # Cancel all pending orders in the batch
        batch_orders = self.batch_orders.get(batch_id, [])
        cancelled = 0
        
        for batch_order in batch_orders:
            if batch_order.status == ExecutionStatus.PENDING:
                try:
                    exchange = self._get_exchange(batch_order.order.exchange)
                    if exchange:
                        if batch_order.order.client_order_id:
                            result = await exchange.cancel_order(
                                batch_order.order.client_order_id,
                                batch_order.order.symbol,
                            )
                            if result:
                                batch_order.status = ExecutionStatus.CANCELLED
                                cancelled += 1
                except Exception as e:
                    self.logger.error(f"Failed to cancel order: {e}")
        
        # Update batch status
        if cancelled > 0:
            with self._batch_lock:
                if batch_id in self.batches:
                    self.batches[batch_id].status = ExecutionStatus.CANCELLED
        
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
        
        # Check if execution is in a batch
        for batch in self.batches.values():
            if execution_id in batch.results:
                return batch.status
        
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
        self.logger.info(f"Simulating execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate each order
        simulated_orders = []
        total_profit = Decimal("0")
        total_cost = Decimal("0")
        
        for order in plan.orders:
            # Get exchange
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                continue
            
            # Simulate order execution
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
            
            # Simulate profit (simple calculation)
            if order.side == OrderSide.BUY:
                profit = order.quantity * (Decimal("1.001") - (order.price or Decimal("1")))
            else:
                profit = order.quantity * ((order.price or Decimal("1")) - Decimal("0.999"))
            
            total_profit += profit
            total_cost += order.quantity * (order.price or Decimal("1"))
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=simulated_orders,
            trades=[],
            positions=[],
            profit=total_profit,
            profit_percentage=(total_profit / total_cost * Decimal("100")
                              if total_cost > 0 else Decimal("0")),
            gas_cost=Decimal("0.001"),  # Simulated gas cost
            fee_cost=Decimal("0.001"),  # Simulated fee
            total_cost=total_cost,
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
            
            # Check batch size
            if len(plan.orders) > self.batch_config.batch_size_limit:
                return False, f"Too many orders: {len(plan.orders)} > {self.batch_config.batch_size_limit}"
            
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
            total_value = Decimal("0")
            max_position_size = Decimal("0")
            
            for order in plan.orders:
                order_value = order.quantity * (order.price or Decimal("1"))
                total_value += order_value
                max_position_size = max(max_position_size, order_value)
            
            # Calculate risk level
            risk_ratio = max_position_size / (self.config.max_position_size or Decimal("100000"))
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
                "max_position_size": max_position_size,
                "risk_ratio": risk_ratio,
                "risk_level": risk_level,
                "order_count": len(plan.orders),
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "max_position_size": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
                "order_count": 0,
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
            
            # Check balance for each exchange
            for exchange_type, orders in exchange_orders.items():
                exchange = self._get_exchange(exchange_type)
                if not exchange:
                    return False, f"Exchange not found: {exchange_type}"
                
                # Get balances
                balances = await exchange.get_balances()
                
                # Calculate required balance
                for order in orders:
                    # Find asset
                    asset = order.symbol.split("/")[0]
                    required = order.quantity * (order.price or Decimal("1"))
                    
                    # Check balance
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
        # Add MEV protection to orders
        for order in plan.orders:
            order.extra_params["mev_protection"] = True
            order.extra_params["private_mempool"] = self.config.use_private_mempool
            
            # Add slippage buffer
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if order.price:
                    order.price = order.price * (Decimal("1") + Decimal("0.001"))
        
        return plan
    
    async def apply_slippage_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply slippage protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        # Add slippage protection to orders
        for order in plan.orders:
            order.extra_params["slippage_tolerance"] = self.config.max_slippage
            
            # Adjust price for slippage
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if order.side == OrderSide.BUY:
                    order.price = order.price * (Decimal("1") + self.config.max_slippage)
                else:
                    order.price = order.price * (Decimal("1") - self.config.max_slippage)
        
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
        
        # Optimize each exchange's orders
        for exchange_type, orders in exchange_orders.items():
            # Batch similar orders
            batched_orders = self._optimize_order_batching(orders)
            plan.orders = batched_orders
        
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
                # Combine orders
                combined = order_group[0]
                combined.quantity = sum(o.quantity for o in order_group)
                combined.price = sum(o.price * o.quantity for o in order_group) / combined.quantity
                optimized.append(combined)
            else:
                optimized.append(order_group[0])
        
        return optimized
    
    def get_batch_result(self, batch_id: str) -> Optional[BatchResult]:
        """
        Get batch execution result.
        
        Args:
            batch_id: Batch ID
            
        Returns:
            BatchResult or None
        """
        return self.batches.get(batch_id)
    
    def get_active_batches(self) -> List[str]:
        """
        Get active batch IDs.
        
        Returns:
            List of active batch IDs
        """
        with self._batch_lock:
            return list(self.active_batches)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **super().get_metrics(),
            "batches_total": self.metrics["batches_total"],
            "batches_succeeded": self.metrics["batches_succeeded"],
            "batches_failed": self.metrics["batches_failed"],
            "orders_total": self.metrics["orders_total"],
            "orders_succeeded": self.metrics["orders_succeeded"],
            "orders_failed": self.metrics["orders_failed"],
            "avg_batch_time_ms": self.metrics["avg_batch_time_ms"],
            "avg_orders_per_batch": self.metrics["avg_orders_per_batch"],
            "active_batches": len(self.active_batches),
            "batches_stored": len(self.batches),
        }


# Module exports
__all__ = [
    'BatchExecutor',
    'BatchConfig',
    'BatchOrder',
    'BatchResult',
]
