# trading/bots/arbitrage_bot/executors/parallel_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Parallel Execution Engine

"""
Parallel Executor - Advanced Parallel Execution Engine

This module provides sophisticated parallel execution capabilities for
arbitrage opportunities, enabling simultaneous execution of multiple
strategies and orders across different exchanges.

Architecture:
    - BaseParallelExecutor: Abstract base class
    - ParallelExecutor: Main executor implementation
    - TaskManager: Task management
    - WorkerPool: Worker pool management
    - ResultAggregator: Result aggregation
    - ErrorHandler: Error handling
    - PerformanceMonitor: Performance monitoring

Features:
    - Parallel order execution
    - Worker pool management
    - Task distribution
    - Result aggregation
    - Error handling
    - Performance monitoring
    - Resource management
    - Graceful degradation
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
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock
from queue import Queue, PriorityQueue

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
DEFAULT_WORKER_COUNT = 10
MAX_WORKER_COUNT = 50
TASK_QUEUE_SIZE = 1000
MAX_CONCURRENT_TASKS = 20
TASK_TIMEOUT = 30  # seconds
RESULT_AGGREGATION_TIMEOUT = 10  # seconds


@dataclass
class ParallelConfig:
    """Parallel execution configuration."""
    worker_count: int = DEFAULT_WORKER_COUNT
    max_worker_count: int = MAX_WORKER_COUNT
    task_queue_size: int = TASK_QUEUE_SIZE
    max_concurrent_tasks: int = MAX_CONCURRENT_TASKS
    task_timeout: int = TASK_TIMEOUT
    result_aggregation_timeout: int = RESULT_AGGREGATION_TIMEOUT
    parallel_execution: bool = True
    use_process_pool: bool = False
    require_all_tasks: bool = True
    graceful_degradation: bool = True
    auto_scale_workers: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParallelTask:
    """Parallel task."""
    task_id: str
    execution_id: str
    order: ExecutionOrder
    priority: int
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Order] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    retry_count: int = 0
    worker_id: Optional[int] = None


@dataclass
class ParallelResult:
    """Parallel execution result."""
    execution_id: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    pending_tasks: int
    results: List[Order]
    errors: List[str]
    total_profit: Decimal
    total_volume: Decimal
    total_gas: Decimal
    total_fees: Decimal
    execution_time_ms: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class ParallelExecutor(BaseExecutor):
    """
    Advanced Parallel Execution Engine.
    
    This class provides sophisticated parallel execution capabilities:
    1. Parallel order execution
    2. Worker pool management
    3. Task distribution
    4. Result aggregation
    5. Error handling
    6. Performance monitoring
    7. Resource management
    8. Graceful degradation
    
    Features:
    - Multi-threaded/process execution
    - Worker pool management
    - Task queue management
    - Priority-based scheduling
    - Result aggregation
    - Error handling
    - Performance monitoring
    - Resource management
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        parallel_config: Optional[ParallelConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the parallel executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            parallel_config: Parallel configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.parallel_config = parallel_config or ParallelConfig()
        
        # Task management
        self.tasks: Dict[str, ParallelTask] = {}
        self.task_queue: PriorityQueue = PriorityQueue(maxsize=self.parallel_config.task_queue_size)
        self.active_tasks: Set[str] = set()
        self.completed_tasks: Set[str] = set()
        
        # Results
        self.results: Dict[str, ParallelResult] = {}
        
        # Worker management
        self.workers: List[Dict[str, Any]] = []
        self.worker_pool: Optional[ThreadPoolExecutor] = None
        self.process_pool: Optional[ProcessPoolExecutor] = None
        
        # State management
        self._is_running = False
        self._is_paused = False
        self._worker_lock = Lock()
        self._task_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "tasks_total": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "tasks_cancelled": 0,
            "tasks_retried": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_task_time_ms": 0,
            "success_rate": Decimal("0"),
            "worker_utilization": Decimal("0"),
            "queue_size": 0,
            "active_workers": 0,
        })
        
        # Start workers
        self._init_workers()
        
        self.logger.info(f"ParallelExecutor initialized with {self.parallel_config.worker_count} workers")
    
    def _init_workers(self) -> None:
        """Initialize worker pool."""
        worker_count = min(
            self.parallel_config.worker_count,
            self.parallel_config.max_worker_count
        )
        
        if self.parallel_config.use_process_pool:
            self.process_pool = ProcessPoolExecutor(max_workers=worker_count)
        else:
            self.worker_pool = ThreadPoolExecutor(max_workers=worker_count)
        
        # Initialize workers
        for i in range(worker_count):
            self.workers.append({
                "id": i,
                "active": False,
                "current_task": None,
                "completed_tasks": 0,
                "total_time": 0,
                "last_active": datetime.utcnow(),
            })
        
        self.logger.info(f"Initialized {worker_count} workers")
    
    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        import uuid
        return f"task_{uuid.uuid4().hex[:12]}"
    
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
            
            # Check exchange
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return False, f"Exchange not found: {order.exchange}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def _execute_single_task(
        self,
        task: ParallelTask,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute a single task.
        
        Args:
            task: Parallel task
            
        Returns:
            Tuple of (order_result, error_message)
        """
        try:
            # Validate order
            is_valid, error = await self._validate_order(task.order)
            if not is_valid:
                return None, error
            
            # Get exchange
            exchange = self._get_exchange(task.order.exchange)
            if not exchange:
                return None, f"Exchange not found: {task.order.exchange}"
            
            # Place order
            result = await exchange.place_order(
                symbol=task.order.symbol,
                side=task.order.side,
                order_type=task.order.order_type,
                quantity=task.order.quantity,
                price=task.order.price,
                stop_price=task.order.stop_price,
                time_in_force=task.order.time_in_force,
                reduce_only=task.order.reduce_only,
                post_only=task.order.post_only,
                client_order_id=task.order.client_order_id,
                **task.order.extra_params,
            )
            
            if result:
                return result, None
            else:
                return None, "Order placement failed"
            
        except Exception as e:
            return None, str(e)
    
    async def _process_task(
        self,
        task: ParallelTask,
        worker_id: int,
    ) -> None:
        """
        Process a task on a worker.
        
        Args:
            task: Parallel task
            worker_id: Worker ID
        """
        task.start_time = datetime.utcnow()
        task.worker_id = worker_id
        task.status = ExecutionStatus.EXECUTING
        
        # Update worker status
        with self._worker_lock:
            if worker_id < len(self.workers):
                self.workers[worker_id]["active"] = True
                self.workers[worker_id]["current_task"] = task.task_id
        
        try:
            # Execute task
            result, error = await self._execute_single_task(task)
            
            task.end_time = datetime.utcnow()
            
            if error:
                task.status = ExecutionStatus.FAILED
                task.error = error
                self.metrics["tasks_failed"] += 1
            else:
                task.status = ExecutionStatus.COMPLETED
                task.result = result
                self.metrics["tasks_succeeded"] += 1
            
            # Update worker stats
            with self._worker_lock:
                if worker_id < len(self.workers):
                    worker = self.workers[worker_id]
                    worker["active"] = False
                    worker["current_task"] = None
                    worker["completed_tasks"] += 1
                    worker["total_time"] += (task.end_time - task.start_time).total_seconds()
                    worker["last_active"] = datetime.utcnow()
            
        except Exception as e:
            task.status = ExecutionStatus.FAILED
            task.error = str(e)
            task.end_time = datetime.utcnow()
            self.metrics["tasks_failed"] += 1
    
    async def _worker_loop(self, worker_id: int) -> None:
        """
        Worker loop for processing tasks.
        
        Args:
            worker_id: Worker ID
        """
        self.logger.debug(f"Worker {worker_id} started")
        
        while self._is_running and not self._is_paused:
            try:
                # Get next task from queue (with priority)
                try:
                    priority, task_id = self.task_queue.get(timeout=1)
                    task = self.tasks.get(task_id)
                    
                    if not task:
                        continue
                    
                    if task.status != ExecutionStatus.PENDING:
                        continue
                    
                    # Process task
                    await self._process_task(task, worker_id)
                    
                    # Update active tasks
                    with self._task_lock:
                        if task_id in self.active_tasks:
                            self.active_tasks.remove(task_id)
                        self.completed_tasks.add(task_id)
                    
                    self.metrics["tasks_total"] += 1
                    
                except Exception as e:
                    self.logger.debug(f"Worker {worker_id} error: {e}")
                    continue
                    
            except Exception as e:
                self.logger.error(f"Worker {worker_id} loop error: {e}")
                await asyncio.sleep(1)
        
        self.logger.debug(f"Worker {worker_id} stopped")
    
    def _start_workers(self) -> None:
        """Start all workers."""
        if not self._is_running:
            self._is_running = True
        
        # Start worker tasks
        for i in range(len(self.workers)):
            asyncio.create_task(self._worker_loop(i))
        
        self.logger.info(f"Started {len(self.workers)} workers")
    
    def _stop_workers(self) -> None:
        """Stop all workers."""
        self._is_running = False
        
        # Clear task queue
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except:
                break
        
        self.logger.info("Stopped workers")
    
    def _calculate_worker_utilization(self) -> Decimal:
        """
        Calculate worker utilization.
        
        Returns:
            Worker utilization (0-1)
        """
        active_workers = sum(1 for w in self.workers if w["active"])
        total_workers = len(self.workers)
        
        if total_workers == 0:
            return Decimal("0")
        
        return Decimal(str(active_workers / total_workers))
    
    async def _aggregate_results(
        self,
        tasks: Dict[str, ParallelTask],
        start_time: float,
    ) -> ParallelResult:
        """
        Aggregate task results.
        
        Args:
            tasks: Dictionary of tasks
            start_time: Start time
            
        Returns:
            ParallelResult
        """
        total_tasks = len(tasks)
        successful_tasks = sum(1 for t in tasks.values() if t.status == ExecutionStatus.COMPLETED)
        failed_tasks = sum(1 for t in tasks.values() if t.status == ExecutionStatus.FAILED)
        pending_tasks = sum(1 for t in tasks.values() if t.status == ExecutionStatus.PENDING)
        
        results = []
        errors = []
        total_profit = Decimal("0")
        total_volume = Decimal("0")
        total_gas = Decimal("0")
        total_fees = Decimal("0")
        
        for task in tasks.values():
            if task.result:
                results.append(task.result)
                # Calculate profit (simplified)
                profit = task.result.quantity * Decimal("0.01")  # 1% profit
                total_profit += profit
                total_volume += task.result.quantity * (task.result.price or Decimal("1"))
                total_gas += Decimal(str(task.result.gas_used or 0))
                total_fees += task.result.fee or Decimal("0")
            
            if task.error:
                errors.append(task.error)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return ParallelResult(
            execution_id=tasks[next(iter(tasks))].execution_id if tasks else "unknown",
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            pending_tasks=pending_tasks,
            results=results,
            errors=errors,
            total_profit=total_profit,
            total_volume=total_volume,
            total_gas=total_gas,
            total_fees=total_fees,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            metadata={
                "worker_count": len(self.workers),
                "active_workers": sum(1 for w in self.workers if w["active"]),
                "utilization": str(self._calculate_worker_utilization()),
            },
        )
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute an execution plan in parallel.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting parallel execution: {execution_id}")
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
            
            # Create tasks
            tasks = {}
            for order in plan.orders:
                task_id = self._generate_task_id()
                task = ParallelTask(
                    task_id=task_id,
                    execution_id=execution_id,
                    order=order,
                    priority=1,
                    status=ExecutionStatus.PENDING,
                )
                tasks[task_id] = task
                self.tasks[task_id] = task
                self.active_tasks.add(task_id)
                
                # Add to queue
                self.task_queue.put((task.priority, task_id))
            
            # Wait for tasks to complete
            timeout = self.parallel_config.task_timeout * len(tasks)
            await asyncio.sleep(0.1)  # Give workers time to start
            
            # Wait for all tasks to complete
            start_wait = time.time()
            while time.time() - start_wait < timeout:
                remaining = sum(1 for t in tasks.values() if t.status == ExecutionStatus.PENDING)
                if remaining == 0:
                    break
                await asyncio.sleep(0.1)
            
            # Aggregate results
            parallel_result = await self._aggregate_results(tasks, start_time)
            
            # Update metrics
            self.metrics["tasks_total"] += parallel_result.total_tasks
            self.metrics["tasks_succeeded"] += parallel_result.successful_tasks
            self.metrics["tasks_failed"] += parallel_result.failed_tasks
            
            if parallel_result.successful_tasks > 0:
                self.metrics["total_profit"] += parallel_result.total_profit
                self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            
            self.metrics["worker_utilization"] = self._calculate_worker_utilization()
            self.metrics["active_workers"] = sum(1 for w in self.workers if w["active"])
            self.metrics["queue_size"] = self.task_queue.qsize()
            
            # Create result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED if parallel_result.successful_tasks == parallel_result.total_tasks else ExecutionStatus.PARTIALLY_EXECUTED,
                orders=parallel_result.results,
                trades=[],
                positions=[],
                profit=parallel_result.total_profit,
                profit_percentage=(
                    parallel_result.total_profit / parallel_result.total_volume * Decimal("100")
                    if parallel_result.total_volume > 0 else Decimal("0")
                ),
                gas_cost=parallel_result.total_gas,
                fee_cost=parallel_result.total_fees,
                total_cost=parallel_result.total_volume,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                error=f"{parallel_result.failed_tasks} tasks failed" if parallel_result.failed_tasks > 0 else None,
                metadata={
                    "total_tasks": parallel_result.total_tasks,
                    "successful_tasks": parallel_result.successful_tasks,
                    "failed_tasks": parallel_result.failed_tasks,
                    "pending_tasks": parallel_result.pending_tasks,
                    "worker_count": len(self.workers),
                    "active_workers": self.metrics["active_workers"],
                    "utilization": str(self.metrics["worker_utilization"]),
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
                f"Parallel execution completed: {execution_id} "
                f"tasks: {parallel_result.successful_tasks}/{parallel_result.total_tasks}, "
                f"profit: ${float(result.profit):.2f}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Parallel execution failed: {error_msg}")
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
        
        with self._task_lock:
            for task_id, task in self.tasks.items():
                if task.execution_id == execution_id and task.status in [
                    ExecutionStatus.PENDING,
                    ExecutionStatus.EXECUTING,
                ]:
                    task.status = ExecutionStatus.CANCELLED
                    cancelled += 1
                    
                    # Try to cancel order if placed
                    if task.result:
                        try:
                            exchange = self._get_exchange(task.order.exchange)
                            if exchange:
                                await exchange.cancel_order(
                                    task.result.order_id,
                                    task.order.symbol,
                                )
                        except Exception:
                            pass
        
        self.metrics["tasks_cancelled"] += cancelled
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
        self.logger.info(f"Simulating parallel execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate tasks
        successful_tasks = len(plan.orders)
        total_profit = Decimal("10") * len(plan.orders)
        total_volume = Decimal("1000") * len(plan.orders)
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=[],
            trades=[],
            positions=[],
            profit=total_profit,
            profit_percentage=total_profit / total_volume * Decimal("100"),
            gas_cost=Decimal("0.001"),
            fee_cost=Decimal("0.001"),
            total_cost=total_volume,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            metadata={
                "simulated": True,
                "tasks": successful_tasks,
            },
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
            
            # Check if too many orders
            if len(plan.orders) > self.parallel_config.max_concurrent_tasks:
                return False, f"Too many tasks: {len(plan.orders)}"
            
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
                "task_count": len(plan.orders),
                "symbols": list(set(o.symbol for o in plan.orders)),
                "exchanges": list(set(o.exchange for o in plan.orders)),
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
                "task_count": 0,
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
    
    def get_tasks(self) -> Dict[str, ParallelTask]:
        """
        Get all tasks.
        
        Returns:
            Dictionary of task ID to ParallelTask
        """
        with self._task_lock:
            return self.tasks.copy()
    
    def get_workers(self) -> List[Dict[str, Any]]:
        """
        Get worker status.
        
        Returns:
            List of worker status dictionaries
        """
        with self._worker_lock:
            return self.workers.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **super().get_metrics(),
            "tasks_total": self.metrics["tasks_total"],
            "tasks_succeeded": self.metrics["tasks_succeeded"],
            "tasks_failed": self.metrics["tasks_failed"],
            "tasks_cancelled": self.metrics["tasks_cancelled"],
            "tasks_retried": self.metrics["tasks_retried"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "avg_task_time_ms": self.metrics["avg_task_time_ms"],
            "success_rate": float(self.metrics["success_rate"]),
            "worker_utilization": float(self.metrics["worker_utilization"]),
            "queue_size": self.metrics["queue_size"],
            "active_workers": self.metrics["active_workers"],
            "total_workers": len(self.workers),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "total_tasks": len(self.tasks),
        }


# Module exports
__all__ = [
    'ParallelExecutor',
    'ParallelConfig',
    'ParallelTask',
    'ParallelResult',
]
