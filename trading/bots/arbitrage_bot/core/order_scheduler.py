# trading/bots/arbitrage_bot/core/order_scheduler.py
# Nexus AI Trading System - Arbitrage Bot Order Scheduler Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Order Scheduler Module

This module provides advanced order scheduling and timing optimization
for the arbitrage bot system, including:

- Order timing optimization
- Execution scheduling
- Market timing analysis
- Order prioritization
- Batch processing
- Schedule coordination
- Time-based execution strategies
- Market condition-based scheduling
- Order queuing and batching
- Priority-based execution
- Deadline management
- SLA monitoring
- Scheduled order types
- Recurring orders
- Conditional execution

The order scheduler ensures optimal timing for arbitrage executions
to maximize profitability and minimize market impact.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeConnector
from trading.bots.arbitrage_bot.core.order_router import OrderRouter, RoutingRequest, RoutingResponse
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager
from trading.bots.arbitrage_bot.core.latency_monitor import LatencyMonitor, LatencySource
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SchedulePriority(str, Enum):
    """Schedule priority levels."""
    HIGH = "high"       # Execute as soon as possible
    NORMAL = "normal"   # Normal priority
    LOW = "low"         # Low priority
    BACKGROUND = "background"  # Background execution


class ScheduleStatus(str, Enum):
    """Schedule status."""
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class ScheduleType(str, Enum):
    """Schedule types."""
    ONE_TIME = "one_time"       # Single execution
    RECURRING = "recurring"     # Recurring execution
    CONDITIONAL = "conditional"  # Condition-based execution
    TIME_BASED = "time_based"   # Time-based execution
    MARKET_BASED = "market_based"  # Market condition-based


class ExecutionWindow(str, Enum):
    """Execution windows."""
    IMMEDIATE = "immediate"     # Execute immediately
    NEXT_MINUTE = "next_minute"  # Execute within next minute
    NEXT_HOUR = "next_hour"     # Execute within next hour
    NEXT_DAY = "next_day"       # Execute within next day
    CUSTOM = "custom"           # Custom window


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ScheduleConfig(BaseModel):
    """Schedule configuration."""
    max_concurrent: int = 10
    max_queue_size: int = 1000
    default_timeout: int = 60
    retry_count: int = 3
    retry_delay: int = 5
    batch_size: int = 10
    batch_window: int = 5  # seconds
    monitor_interval: int = 1  # seconds
    default_priority: SchedulePriority = SchedulePriority.NORMAL
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_concurrent', 'max_queue_size', 'default_timeout', 'retry_count', 'retry_delay')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class ScheduledOrder(BaseModel):
    """Scheduled order."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_type: ScheduleType
    priority: SchedulePriority = SchedulePriority.NORMAL
    
    # Order details
    routing_request: RoutingRequest
    execution_window: ExecutionWindow = ExecutionWindow.IMMEDIATE
    
    # Timing
    scheduled_time: Optional[datetime] = None
    earliest_time: Optional[datetime] = None
    latest_time: Optional[datetime] = None
    interval_seconds: Optional[int] = None
    max_executions: Optional[int] = None
    
    # Conditions
    conditions: Dict[str, Any] = Field(default_factory=dict)
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_volume: Optional[Decimal] = None
    min_liquidity: Optional[Decimal] = None
    require_confirmation: bool = False
    
    # Status
    status: ScheduleStatus = ScheduleStatus.PENDING
    execution_count: int = 0
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_recurring(self) -> bool:
        """Check if order is recurring."""
        return self.schedule_type == ScheduleType.RECURRING

    @property
    def is_conditional(self) -> bool:
        """Check if order is conditional."""
        return self.schedule_type == ScheduleType.CONDITIONAL

    @property
    def is_expired(self) -> bool:
        """Check if order has expired."""
        if self.latest_time and datetime.utcnow() > self.latest_time:
            return True
        if self.max_executions and self.execution_count >= self.max_executions:
            return True
        return False


class ScheduleExecution(BaseModel):
    """Schedule execution record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scheduled_order_id: str
    routing_response: Optional[RoutingResponse] = None
    status: ScheduleStatus
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduleQueueStatus(BaseModel):
    """Schedule queue status."""
    total_pending: int = 0
    total_queued: int = 0
    total_executing: int = 0
    total_completed: int = 0
    total_failed: int = 0
    queue_size: int = 0
    active_workers: int = 0
    oldest_pending: Optional[datetime] = None
    newest_pending: Optional[datetime] = None
    average_wait_time: float = 0.0
    throughput_per_minute: float = 0.0


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Scheduled orders
CREATE TABLE IF NOT EXISTS scheduled_orders (
    id VARCHAR(64) PRIMARY KEY,
    schedule_type VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    routing_request JSONB NOT NULL,
    execution_window VARCHAR(20) NOT NULL,
    scheduled_time TIMESTAMP,
    earliest_time TIMESTAMP,
    latest_time TIMESTAMP,
    interval_seconds INTEGER,
    max_executions INTEGER,
    conditions JSONB DEFAULT '{}',
    min_price DECIMAL(32, 16),
    max_price DECIMAL(32, 16),
    min_volume DECIMAL(32, 16),
    min_liquidity DECIMAL(32, 16),
    require_confirmation BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) NOT NULL,
    execution_count INTEGER DEFAULT 0,
    last_execution TIMESTAMP,
    next_execution TIMESTAMP,
    error_message TEXT,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_scheduled_orders_status (status),
    INDEX idx_scheduled_orders_priority (priority),
    INDEX idx_scheduled_orders_next_execution (next_execution),
    INDEX idx_scheduled_orders_created_at (created_at)
);

-- Schedule executions
CREATE TABLE IF NOT EXISTS schedule_executions (
    id VARCHAR(64) PRIMARY KEY,
    scheduled_order_id VARCHAR(64) NOT NULL,
    routing_response JSONB,
    status VARCHAR(20) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms FLOAT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    INDEX idx_schedule_executions_scheduled_order_id (scheduled_order_id),
    INDEX idx_schedule_executions_status (status),
    INDEX idx_schedule_executions_start_time (start_time)
);

-- Schedule queue
CREATE TABLE IF NOT EXISTS schedule_queue (
    id SERIAL PRIMARY KEY,
    scheduled_order_id VARCHAR(64) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dequeued_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'queued',
    INDEX idx_schedule_queue_scheduled_order_id (scheduled_order_id),
    INDEX idx_schedule_queue_priority (priority),
    INDEX idx_schedule_queue_enqueued_at (enqueued_at)
);
"""


# =============================================================================
# ORDER SCHEDULER CLASS
# =============================================================================

class OrderScheduler:
    """
    Advanced order scheduler for arbitrage bot.
    
    Features:
    - Order timing optimization
    - Execution scheduling
    - Market timing analysis
    - Order prioritization
    - Batch processing
    - Schedule coordination
    - Time-based execution strategies
    - Market condition-based scheduling
    - Order queuing and batching
    - Priority-based execution
    - Deadline management
    - SLA monitoring
    - Scheduled order types
    - Recurring orders
    - Conditional execution
    """
    
    def __init__(
        self,
        order_router: OrderRouter,
        market_data: MarketDataManager,
        latency_monitor: Optional[LatencyMonitor] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[ScheduleConfig] = None
    ):
        self.order_router = order_router
        self.market_data = market_data
        self.latency_monitor = latency_monitor
        self.redis = redis
        self.pool = pool
        self.config = config or ScheduleConfig()
        
        # Scheduled orders
        self._orders: Dict[str, ScheduledOrder] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # Active executions
        self._executing: Set[str] = set()
        self._executions: Dict[str, ScheduleExecution] = {}
        
        # Circuit breakers
        self._scheduler_cb = CircuitBreaker(
            name="order_scheduler",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Workers
        self._workers: List[asyncio.Task] = []
        self._num_workers = 5
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_skipped": 0
        }
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "execution_start": [],
            "execution_complete": [],
            "execution_failed": [],
            "order_scheduled": [],
            "order_cancelled": []
        }
        
        logger.info("OrderScheduler initialized")
    
    async def initialize(self):
        """Initialize the order scheduler."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load pending orders
        await self._load_pending_orders()
        
        # Start workers
        self._running = True
        for i in range(self._num_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        # Start monitor
        asyncio.create_task(self._monitor_loop())
        
        self._initialized = True
        logger.info("OrderScheduler initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # ORDER SCHEDULING
    # =========================================================================
    
    async def schedule_order(
        self,
        routing_request: RoutingRequest,
        schedule_type: ScheduleType = ScheduleType.ONE_TIME,
        scheduled_time: Optional[datetime] = None,
        earliest_time: Optional[datetime] = None,
        latest_time: Optional[datetime] = None,
        interval_seconds: Optional[int] = None,
        max_executions: Optional[int] = None,
        priority: SchedulePriority = SchedulePriority.NORMAL,
        execution_window: ExecutionWindow = ExecutionWindow.IMMEDIATE,
        conditions: Optional[Dict[str, Any]] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        min_volume: Optional[Decimal] = None,
        require_confirmation: bool = False,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScheduledOrder:
        """
        Schedule an order for execution.
        
        Args:
            routing_request: Routing request
            schedule_type: Type of schedule
            scheduled_time: Scheduled execution time
            earliest_time: Earliest execution time
            latest_time: Latest execution time
            interval_seconds: Interval for recurring orders
            max_executions: Maximum executions
            priority: Priority level
            execution_window: Execution window
            conditions: Execution conditions
            min_price: Minimum price condition
            max_price: Maximum price condition
            min_volume: Minimum volume condition
            require_confirmation: Require confirmation before execution
            tags: Tags for categorization
            metadata: Additional metadata
            
        Returns:
            ScheduledOrder
        """
        # Validate scheduling parameters
        if schedule_type == ScheduleType.RECURRING and not interval_seconds:
            raise ValueError("Interval required for recurring orders")
        
        if schedule_type == ScheduleType.ONE_TIME and scheduled_time and scheduled_time < datetime.utcnow():
            raise ValueError("Scheduled time cannot be in the past")
        
        # Create scheduled order
        order = ScheduledOrder(
            schedule_type=schedule_type,
            priority=priority,
            routing_request=routing_request,
            execution_window=execution_window,
            scheduled_time=scheduled_time,
            earliest_time=earliest_time,
            latest_time=latest_time,
            interval_seconds=interval_seconds,
            max_executions=max_executions,
            conditions=conditions or {},
            min_price=min_price,
            max_price=max_price,
            min_volume=min_volume,
            require_confirmation=require_confirmation,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Determine next execution
        order.next_execution = self._calculate_next_execution(order)
        
        # Save order
        self._orders[order.id] = order
        await self._save_order(order)
        
        # Queue for execution
        if order.next_execution and order.next_execution <= datetime.utcnow():
            await self._enqueue_order(order.id)
        
        # Notify callbacks
        await self._trigger_callbacks("order_scheduled", order)
        
        logger.info(
            f"Scheduled order {order.id} ({schedule_type.value}) "
            f"priority={priority.value} next={order.next_execution}"
        )
        
        return order
    
    async def cancel_scheduled_order(self, order_id: str) -> bool:
        """
        Cancel a scheduled order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        if order.status in [ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED]:
            return False
        
        order.status = ScheduleStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        
        await self._save_order(order)
        await self._trigger_callbacks("order_cancelled", order)
        
        logger.info(f"Cancelled scheduled order {order_id}")
        return True
    
    async def pause_scheduled_order(self, order_id: str) -> bool:
        """
        Pause a scheduled order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if paused successfully
        """
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        if order.status not in [ScheduleStatus.PENDING, ScheduleStatus.QUEUED]:
            return False
        
        order.status = ScheduleStatus.PENDING
        order.next_execution = None
        order.updated_at = datetime.utcnow()
        
        await self._save_order(order)
        
        logger.info(f"Paused scheduled order {order_id}")
        return True
    
    async def resume_scheduled_order(self, order_id: str) -> bool:
        """
        Resume a paused scheduled order.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if resumed successfully
        """
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        if order.status != ScheduleStatus.PENDING:
            return False
        
        order.status = ScheduleStatus.PENDING
        order.next_execution = self._calculate_next_execution(order)
        order.updated_at = datetime.utcnow()
        
        await self._save_order(order)
        
        if order.next_execution and order.next_execution <= datetime.utcnow():
            await self._enqueue_order(order.id)
        
        logger.info(f"Resumed scheduled order {order_id}")
        return True
    
    # =========================================================================
    # QUEUE MANAGEMENT
    # =========================================================================
    
    async def _enqueue_order(self, order_id: str):
        """Enqueue an order for execution."""
        if order_id not in self._orders:
            return
        
        order = self._orders[order_id]
        
        if order.status in [ScheduleStatus.QUEUED, ScheduleStatus.EXECUTING]:
            return
        
        # Check if order is expired
        if order.is_expired:
            order.status = ScheduleStatus.EXPIRED
            await self._save_order(order)
            return
        
        # Determine priority order (higher priority first)
        priority_value = {
            SchedulePriority.HIGH: 0,
            SchedulePriority.NORMAL: 1,
            SchedulePriority.LOW: 2,
            SchedulePriority.BACKGROUND: 3
        }.get(order.priority, 1)
        
        # Add to queue
        await self._queue.put((priority_value, order_id))
        order.status = ScheduleStatus.QUEUED
        order.updated_at = datetime.utcnow()
        
        await self._save_order(order)
        
        # Save to database queue
        if self.pool:
            await self._save_queue_entry(order_id, priority_value)
    
    async def _dequeue_order(self) -> Optional[ScheduledOrder]:
        """Dequeue an order for execution."""
        try:
            # Get from queue with timeout
            priority, order_id = await asyncio.wait_for(
                self._queue.get(),
                timeout=1.0
            )
            
            if order_id not in self._orders:
                return None
            
            order = self._orders[order_id]
            
            # Check if order is still valid
            if order.status == ScheduleStatus.CANCELLED:
                return None
            
            if order.is_expired:
                order.status = ScheduleStatus.EXPIRED
                await self._save_order(order)
                return None
            
            # Mark as executing
            order.status = ScheduleStatus.EXECUTING
            order.updated_at = datetime.utcnow()
            self._executing.add(order_id)
            
            await self._save_order(order)
            
            return order
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error dequeuing order: {e}")
            return None
    
    # =========================================================================
    # WORKER LOOP
    # =========================================================================
    
    async def _worker_loop(self, worker_id: int):
        """
        Worker loop for executing scheduled orders.
        
        Args:
            worker_id: Worker ID
        """
        logger.info(f"Scheduler worker {worker_id} started")
        
        while self._running:
            try:
                # Dequeue order
                order = await self._dequeue_order()
                
                if order is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Check if order should be executed
                if not await self._should_execute(order):
                    # Skip execution
                    order.status = ScheduleStatus.SKIPPED
                    self._executing.remove(order.id)
                    await self._save_order(order)
                    self._metrics["total_skipped"] += 1
                    
                    # Schedule next execution for recurring orders
                    if order.is_recurring:
                        await self._reschedule_order(order)
                    
                    continue
                
                # Execute order
                await self._execute_order(order)
                
                # Clean up
                self._executing.remove(order.id)
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Scheduler worker {worker_id} stopped")
    
    async def _execute_order(self, order: ScheduledOrder):
        """
        Execute a scheduled order.
        
        Args:
            order: Scheduled order
        """
        # Create execution record
        execution = ScheduleExecution(
            scheduled_order_id=order.id,
            status=ScheduleStatus.EXECUTING,
            start_time=datetime.utcnow()
        )
        self._executions[execution.id] = execution
        
        try:
            # Notify start
            await self._trigger_callbacks("execution_start", execution)
            
            # Execute routing request
            if self.latency_monitor:
                response, _ = await self.latency_monitor.measure_latency(
                    source=LatencySource.ORDER_PLACEMENT,
                    func=self.order_router.route_order,
                    request=order.routing_request,
                    exchange=order.routing_request.exchanges[0] if order.routing_request.exchanges else None,
                    operation="scheduled_execution"
                )
            else:
                response = await self.order_router.route_order(order.routing_request)
            
            execution.routing_response = response
            execution.status = ScheduleStatus.COMPLETED if response.is_successful else ScheduleStatus.FAILED
            
            if response.error_message:
                execution.error_message = response.error_message
            
            # Update order
            order.execution_count += 1
            order.last_execution = datetime.utcnow()
            order.status = ScheduleStatus.COMPLETED
            
            if order.is_successful:
                self._metrics["total_success"] += 1
            else:
                self._metrics["total_failed"] += 1
                if order.execution_count < self.config.retry_count:
                    # Retry later
                    await self._reschedule_order(order)
                    order.status = ScheduleStatus.PENDING
            
            self._metrics["total_processed"] += 1
            
            # Schedule next execution for recurring orders
            if order.is_recurring:
                await self._reschedule_order(order)
            
            # Notify completion
            await self._trigger_callbacks("execution_complete", execution)
            
        except Exception as e:
            logger.error(f"Error executing order {order.id}: {e}")
            
            execution.status = ScheduleStatus.FAILED
            execution.error_message = str(e)
            self._metrics["total_failed"] += 1
            
            order.status = ScheduleStatus.FAILED
            order.error_message = str(e)
            
            await self._trigger_callbacks("execution_failed", execution)
        
        finally:
            # Update execution
            execution.end_time = datetime.utcnow()
            execution.duration_ms = (execution.end_time - execution.start_time).total_seconds() * 1000
            
            # Save to database
            await self._save_execution(execution)
            await self._save_order(order)
    
    async def _should_execute(self, order: ScheduledOrder) -> bool:
        """
        Check if order should be executed.
        
        Args:
            order: Scheduled order
            
        Returns:
            True if should execute
        """
        # Check if order is conditional
        if order.is_conditional:
            # Check conditions
            conditions_met = await self._check_conditions(order)
            if not conditions_met:
                return False
        
        # Check price conditions
        if order.min_price or order.max_price:
            try:
                price = await self.market_data.get_price(
                    order.routing_request.exchanges[0] if order.routing_request.exchanges else "",
                    order.routing_request.symbol
                )
                
                if order.min_price and price.last < order.min_price:
                    logger.debug(f"Price {price.last} below min {order.min_price}")
                    return False
                
                if order.max_price and price.last > order.max_price:
                    logger.debug(f"Price {price.last} above max {order.max_price}")
                    return False
            except Exception as e:
                logger.error(f"Error checking price conditions: {e}")
                return False
        
        # Check volume conditions
        if order.min_volume:
            try:
                depth = await self.market_data.get_depth(
                    order.routing_request.exchanges[0] if order.routing_request.exchanges else "",
                    order.routing_request.symbol
                )
                total_volume = depth.total_bid_volume + depth.total_ask_volume
                if total_volume < order.min_volume:
                    logger.debug(f"Volume {total_volume} below min {order.min_volume}")
                    return False
            except Exception as e:
                logger.error(f"Error checking volume conditions: {e}")
                return False
        
        # Check if confirmation required
        if order.require_confirmation:
            # Wait for confirmation (would be implemented with external signal)
            return False
        
        return True
    
    async def _check_conditions(self, order: ScheduledOrder) -> bool:
        """
        Check if order conditions are met.
        
        Args:
            order: Scheduled order
            
        Returns:
            True if conditions are met
        """
        # This would implement complex condition checking
        # For now, return True if no conditions
        if not order.conditions:
            return True
        
        # Check market conditions
        for key, value in order.conditions.items():
            if key == "market_status":
                # Check market status
                pass
            elif key == "volatility":
                # Check volatility conditions
                pass
            elif key == "spread":
                # Check spread conditions
                pass
            elif key == "liquidity":
                # Check liquidity conditions
                pass
        
        return True
    
    async def _reschedule_order(self, order: ScheduledOrder):
        """
        Reschedule a recurring order.
        
        Args:
            order: Scheduled order
        """
        if not order.is_recurring:
            return
        
        # Calculate next execution time
        next_time = self._calculate_next_execution(order)
        order.next_execution = next_time
        order.status = ScheduleStatus.PENDING
        
        # Enqueue if next execution is due
        if next_time and next_time <= datetime.utcnow():
            await self._enqueue_order(order.id)
        
        logger.debug(f"Rescheduled order {order.id} for {next_time}")
    
    def _calculate_next_execution(self, order: ScheduledOrder) -> Optional[datetime]:
        """
        Calculate next execution time.
        
        Args:
            order: Scheduled order
            
        Returns:
            Next execution time
        """
        if order.schedule_type == ScheduleType.ONE_TIME:
            return order.scheduled_time
        
        if order.schedule_type == ScheduleType.RECURRING:
            if order.last_execution:
                return order.last_execution + timedelta(seconds=order.interval_seconds)
            else:
                return order.scheduled_time or datetime.utcnow()
        
        if order.schedule_type == ScheduleType.CONDITIONAL:
            # Conditional orders are evaluated continuously
            return datetime.utcnow()
        
        if order.schedule_type == ScheduleType.TIME_BASED:
            # Time-based orders execute at specific times
            return order.scheduled_time
        
        if order.schedule_type == ScheduleType.MARKET_BASED:
            # Market-based orders execute when conditions are met
            return datetime.utcnow()
        
        return None
    
    # =========================================================================
    # MONITOR LOOP
    # =========================================================================
    
    async def _monitor_loop(self):
        """Monitor loop for scheduling."""
        while self._running:
            try:
                await asyncio.sleep(self.config.monitor_interval)
                
                # Check for pending orders that need to be queued
                for order_id, order in list(self._orders.items()):
                    if order.status == ScheduleStatus.PENDING:
                        if order.next_execution and order.next_execution <= datetime.utcnow():
                            await self._enqueue_order(order_id)
                
                # Update queue status
                await self._update_queue_status()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)
    
    async def _update_queue_status(self):
        """Update queue status in Redis."""
        if not self.redis:
            return
        
        try:
            status = await self.get_queue_status()
            await self.redis.setex(
                "scheduler:queue_status",
                10,
                json.dumps(status.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Error updating queue status: {e}")
    
    # =========================================================================
    # STATUS AND METRICS
    # =========================================================================
    
    async def get_queue_status(self) -> ScheduleQueueStatus:
        """
        Get queue status.
        
        Returns:
            ScheduleQueueStatus
        """
        pending = 0
        queued = 0
        executing = 0
        completed = 0
        failed = 0
        
        for order in self._orders.values():
            if order.status == ScheduleStatus.PENDING:
                pending += 1
            elif order.status == ScheduleStatus.QUEUED:
                queued += 1
            elif order.status == ScheduleStatus.EXECUTING:
                executing += 1
            elif order.status == ScheduleStatus.COMPLETED:
                completed += 1
            elif order.status == ScheduleStatus.FAILED:
                failed += 1
        
        return ScheduleQueueStatus(
            total_pending=pending,
            total_queued=queued,
            total_executing=executing,
            total_completed=completed,
            total_failed=failed,
            queue_size=self._queue.qsize(),
            active_workers=len(self._workers),
            oldest_pending=min(
                (o.created_at for o in self._orders.values() 
                 if o.status == ScheduleStatus.PENDING),
                default=None
            ),
            newest_pending=max(
                (o.created_at for o in self._orders.values() 
                 if o.status == ScheduleStatus.PENDING),
                default=None
            )
        )
    
    async def get_order_status(self, order_id: str) -> Optional[ScheduledOrder]:
        """
        Get status of a scheduled order.
        
        Args:
            order_id: Order ID
            
        Returns:
            ScheduledOrder or None
        """
        return self._orders.get(order_id)
    
    async def get_execution_history(
        self,
        order_id: str,
        limit: int = 100
    ) -> List[ScheduleExecution]:
        """
        Get execution history for an order.
        
        Args:
            order_id: Order ID
            limit: Maximum number of executions
            
        Returns:
            List of ScheduleExecution
        """
        if not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM schedule_executions
                    WHERE scheduled_order_id = $1
                    ORDER BY start_time DESC
                    LIMIT $2
                    """,
                    order_id,
                    limit
                )
                
                executions = []
                for row in rows:
                    execution = ScheduleExecution(
                        id=row['id'],
                        scheduled_order_id=row['scheduled_order_id'],
                        status=ScheduleStatus(row['status']),
                        start_time=row['start_time'],
                        end_time=row['end_time'],
                        duration_ms=row['duration_ms'],
                        error_message=row['error_message'],
                        metadata=row['metadata'] or {}
                    )
                    if row['routing_response']:
                        execution.routing_response = RoutingResponse(**json.loads(row['routing_response']))
                    executions.append(execution)
                
                return executions
                
        except Exception as e:
            logger.error(f"Error getting execution history: {e}")
            return []
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    async def on(self, event: str, callback: Callable):
        """
        Register a callback for an event.
        
        Args:
            event: Event name ('execution_start', 'execution_complete', etc.)
            callback: Callback function
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    async def _trigger_callbacks(self, event: str, data: Any):
        """
        Trigger callbacks for an event.
        
        Args:
            event: Event name
            data: Event data
        """
        if event not in self._callbacks:
            return
        
        for callback in self._callbacks[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, order: ScheduledOrder):
        """Save scheduled order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO scheduled_orders (
                        id, schedule_type, priority, routing_request,
                        execution_window, scheduled_time, earliest_time,
                        latest_time, interval_seconds, max_executions,
                        conditions, min_price, max_price, min_volume,
                        min_liquidity, require_confirmation, status,
                        execution_count, last_execution, next_execution,
                        error_message, tags, metadata, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22, $23, $24)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        execution_count = EXCLUDED.execution_count,
                        last_execution = EXCLUDED.last_execution,
                        next_execution = EXCLUDED.next_execution,
                        error_message = EXCLUDED.error_message,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    """,
                    order.id,
                    order.schedule_type.value,
                    order.priority.value,
                    json.dumps(order.routing_request.dict(), default=str),
                    order.execution_window.value,
                    order.scheduled_time,
                    order.earliest_time,
                    order.latest_time,
                    order.interval_seconds,
                    order.max_executions,
                    json.dumps(order.conditions, default=str),
                    order.min_price,
                    order.max_price,
                    order.min_volume,
                    order.min_liquidity,
                    order.require_confirmation,
                    order.status.value,
                    order.execution_count,
                    order.last_execution,
                    order.next_execution,
                    order.error_message,
                    json.dumps(order.tags),
                    json.dumps(order.metadata, default=str),
                    order.updated_at
                )
        except Exception as e:
            logger.error(f"Error saving scheduled order: {e}")
    
    async def _save_execution(self, execution: ScheduleExecution):
        """Save schedule execution to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO schedule_executions (
                        id, scheduled_order_id, routing_response,
                        status, start_time, end_time, duration_ms,
                        error_message, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    execution.id,
                    execution.scheduled_order_id,
                    json.dumps(execution.routing_response.dict() if execution.routing_response else None, default=str),
                    execution.status.value,
                    execution.start_time,
                    execution.end_time,
                    execution.duration_ms,
                    execution.error_message,
                    json.dumps(execution.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving schedule execution: {e}")
    
    async def _save_queue_entry(self, order_id: str, priority: int):
        """Save queue entry to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO schedule_queue (
                        scheduled_order_id, priority, enqueued_at
                    ) VALUES ($1, $2, $3)
                    """,
                    order_id,
                    priority,
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving queue entry: {e}")
    
    async def _load_pending_orders(self):
        """Load pending orders from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM scheduled_orders
                    WHERE status IN ('pending', 'queued', 'executing')
                    ORDER BY priority, created_at
                    """
                )
                
                for row in rows:
                    try:
                        routing_request_data = json.loads(row['routing_request'])
                        order = ScheduledOrder(
                            id=row['id'],
                            schedule_type=ScheduleType(row['schedule_type']),
                            priority=SchedulePriority(row['priority']),
                            routing_request=RoutingRequest(**routing_request_data),
                            execution_window=ExecutionWindow(row['execution_window']),
                            scheduled_time=row['scheduled_time'],
                            earliest_time=row['earliest_time'],
                            latest_time=row['latest_time'],
                            interval_seconds=row['interval_seconds'],
                            max_executions=row['max_executions'],
                            conditions=row['conditions'] or {},
                            min_price=row['min_price'],
                            max_price=row['max_price'],
                            min_volume=row['min_volume'],
                            min_liquidity=row['min_liquidity'],
                            require_confirmation=row['require_confirmation'],
                            status=ScheduleStatus(row['status']),
                            execution_count=row['execution_count'],
                            last_execution=row['last_execution'],
                            next_execution=row['next_execution'],
                            error_message=row['error_message'],
                            tags=row['tags'] or [],
                            metadata=row['metadata'] or {},
                            created_at=row['created_at'],
                            updated_at=row['updated_at']
                        )
                        
                        self._orders[order.id] = order
                        
                        # Enqueue if needed
                        if order.status == ScheduleStatus.QUEUED:
                            priority_value = {
                                SchedulePriority.HIGH: 0,
                                SchedulePriority.NORMAL: 1,
                                SchedulePriority.LOW: 2,
                                SchedulePriority.BACKGROUND: 3
                            }.get(order.priority, 1)
                            await self._queue.put((priority_value, order.id))
                        
                    except Exception as e:
                        logger.error(f"Error loading scheduled order {row['id']}: {e}")
                
                logger.info(f"Loaded {len(self._orders)} pending orders")
                
        except Exception as e:
            logger.error(f"Error loading pending orders: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the order scheduler."""
        self._running = False
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Cancel pending orders
        for order_id, order in list(self._orders.items()):
            if order.status in [ScheduleStatus.PENDING, ScheduleStatus.QUEUED]:
                order.status = ScheduleStatus.CANCELLED
                await self._save_order(order)
        
        logger.info("OrderScheduler shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OrderScheduler',
    'SchedulePriority',
    'ScheduleStatus',
    'ScheduleType',
    'ExecutionWindow',
    'ScheduleConfig',
    'ScheduledOrder',
    'ScheduleExecution',
    'ScheduleQueueStatus'
]
