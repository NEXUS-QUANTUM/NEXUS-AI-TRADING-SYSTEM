"""
NEXUS AI TRADING SYSTEM - Order Executor Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/order_executor.py
Version: 1.0.0
Description: Advanced order execution engine with full API integration
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, Tuple
from enum import Enum
from collections import deque

from pydantic import BaseModel, Field, ConfigDict

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.helpers.trading_helpers import (
    calculate_percentage_change,
    calculate_price_distance,
    round_to_tick_size,
    calculate_smart_order_routing
)
from shared.constants.trading_constants import (
    MAX_EXECUTION_RETRIES,
    EXECUTION_TIMEOUT,
    MIN_ORDER_SIZE,
    MAX_ORDER_SPLIT
)
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


class ExecutionType(str, Enum):
    """Types of execution strategies"""
    MARKET = "market"                  # Market order execution
    LIMIT = "limit"                    # Limit order execution
    STOP = "stop"                      # Stop order execution
    ICEBERG = "iceberg"                # Iceberg order execution
    TWAP = "twap"                      # Time-Weighted Average Price
    VWAP = "vwap"                      # Volume-Weighted Average Price
    POV = "pov"                        # Percentage of Volume
    ADAPTIVE = "adaptive"              # Adaptive execution
    SMART = "smart"                    # Smart order routing
    ARBITRAGE = "arbitrage"            # Arbitrage execution
    HEDGE = "hedge"                    # Hedge execution
    SCALING = "scaling"                # Scaling execution


class ExecutionPriority(str, Enum):
    """Execution priority levels"""
    SPEED = "speed"                    # Prioritize speed
    PRICE = "price"                    # Prioritize price
    BALANCED = "balanced"              # Balanced approach
    COST = "cost"                      # Prioritize cost reduction
    IMPACT = "impact"                  # Minimize market impact


class ExecutionMode(str, Enum):
    """Execution modes"""
    SYNC = "sync"                      # Synchronous execution
    ASYNC = "async"                    # Asynchronous execution
    BATCH = "batch"                    # Batch execution
    STREAMING = "streaming"            # Streaming execution
    ADAPTIVE = "adaptive"              # Adaptive mode selection


class ExecutionResult(BaseModel):
    """Execution result"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    order_id: str = Field(..., description="Order ID")
    executed_price: float = Field(..., description="Average execution price")
    executed_size: float = Field(..., description="Total executed size")
    status: OrderStatus = Field(..., description="Execution status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Execution timestamp")
    
    # Fill details
    fills: List[Dict[str, Any]] = Field(default_factory=list, description="Individual fills")
    fill_count: int = Field(0, description="Number of fills")
    
    # Performance metrics
    execution_time: float = Field(0.0, description="Execution time in seconds")
    slippage: float = Field(0.0, description="Slippage from intended price")
    spread_cost: float = Field(0.0, description="Spread cost")
    fees: float = Field(0.0, description="Total fees")
    
    # Routing
    route: str = Field("", description="Execution route")
    venue: str = Field("", description="Execution venue")
    
    # Additional data
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    error: Optional[str] = Field(None, description="Error message if any")


class ExecutionConfig(BaseModel):
    """Configuration for order execution"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    execution_type: ExecutionType = Field(default=ExecutionType.SMART)
    execution_priority: ExecutionPriority = Field(default=ExecutionPriority.BALANCED)
    mode: ExecutionMode = Field(default=ExecutionMode.ADAPTIVE)
    
    # Order parameters
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    size: float = Field(..., description="Order size")
    price: Optional[float] = Field(None, description="Limit price")
    stop_price: Optional[float] = Field(None, description="Stop price")
    order_type: OrderType = Field(default=OrderType.LIMIT)
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    
    # Time settings
    start_time: Optional[datetime] = Field(None, description="Execution start time")
    end_time: Optional[datetime] = Field(None, description="Execution end time")
    timeout: float = Field(EXECUTION_TIMEOUT, description="Execution timeout in seconds")
    max_execution_time: Optional[float] = Field(None, description="Maximum execution time")
    
    # Risk settings
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    max_spread: float = Field(0.005, description="Maximum allowed spread")
    min_fill_size: float = Field(MIN_ORDER_SIZE, description="Minimum fill size")
    max_order_size: float = Field(MAX_ORDER_SPLIT, description="Maximum order size per fill")
    
    # Smart routing
    venues: List[str] = Field(default_factory=list, description="Preferred venues")
    exclude_venues: List[str] = Field(default_factory=list, description="Excluded venues")
    routing_strategy: str = Field("best_price", description="Routing strategy")
    
    # Iceberg settings
    iceberg_display_size: Optional[float] = Field(None, description="Iceberg display size")
    iceberg_refresh_rate: float = Field(1.0, description="Iceberg refresh rate in seconds")
    
    # TWAP settings
    twap_interval: float = Field(10.0, description="TWAP interval in seconds")
    twap_pieces: int = Field(10, description="Number of TWAP pieces")
    twap_duration: float = Field(60.0, description="TWAP duration in seconds")
    
    # VWAP settings
    vwap_window: int = Field(20, description="VWAP window")
    vwap_participation: float = Field(0.1, description="VWAP participation rate")
    
    # POV settings
    pov_target: float = Field(0.1, description="Target percentage of volume")
    pov_min_participation: float = Field(0.05, description="Minimum participation")
    pov_max_participation: float = Field(0.2, description="Maximum participation")
    
    # Adaptive settings
    adaptive_sensitivity: float = Field(0.5, description="Adaptive sensitivity")
    adaptive_update_interval: float = Field(1.0, description="Update interval")
    
    # Retry settings
    max_retries: int = Field(MAX_EXECUTION_RETRIES, description="Maximum retries")
    retry_delay: float = Field(0.5, description="Retry delay in seconds")
    retry_backoff: float = Field(2.0, description="Retry backoff multiplier")
    
    # Validation
    validate_price: bool = Field(True, description="Validate price")
    validate_size: bool = Field(True, description="Validate size")
    validate_venue: bool = Field(True, description="Validate venue")


class ExecutionMetrics(BaseModel):
    """Execution performance metrics"""
    total_orders: int = Field(0, description="Total orders executed")
    successful_orders: int = Field(0, description="Successful orders")
    failed_orders: int = Field(0, description="Failed orders")
    partial_orders: int = Field(0, description="Partially filled orders")
    
    total_volume: float = Field(0.0, description="Total volume executed")
    total_value: float = Field(0.0, description="Total value executed")
    total_fees: float = Field(0.0, description="Total fees paid")
    
    average_execution_time: float = Field(0.0, description="Average execution time")
    average_slippage: float = Field(0.0, description="Average slippage")
    average_spread: float = Field(0.0, description="Average spread")
    
    fill_rate: float = Field(0.0, description="Fill rate percentage")
    success_rate: float = Field(0.0, description="Success rate percentage")


class OrderExecutor:
    """
    Advanced order execution engine with full API integration.
    
    Features:
    - Multiple execution strategies (Market, Limit, TWAP, VWAP, Iceberg, etc.)
    - Smart order routing
    - Adaptive execution
    - Risk management
    - Performance metrics
    - Retry and recovery
    - Circuit breaker protection
    - Real-time monitoring
    """

    def __init__(
        self,
        broker: BrokerInterface,
        default_config: Optional[ExecutionConfig] = None,
        max_concurrent: int = 10,
        enable_monitoring: bool = True
    ):
        """
        Initialize the order executor.

        Args:
            broker: Broker interface for order execution
            default_config: Default execution configuration
            max_concurrent: Maximum concurrent executions
            enable_monitoring: Enable performance monitoring
        """
        self._broker = broker
        self._default_config = default_config or ExecutionConfig(
            symbol="",
            side=OrderSide.BUY,
            size=0
        )
        self._max_concurrent = max_concurrent
        self._enable_monitoring = enable_monitoring

        # Active executions
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        self._execution_history: List[ExecutionResult] = []
        self._execution_queue: asyncio.Queue = asyncio.Queue()

        # Performance tracking
        self._metrics = ExecutionMetrics()
        self._execution_times: deque = deque(maxlen=100)
        self._slippage_values: deque = deque(maxlen=100)

        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Control flags
        self._running = False
        self._initialized = False

        # Tasks
        self._execution_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None

        logger.info(f"Initialized OrderExecutor with max_concurrent={max_concurrent}")

    async def initialize(self) -> bool:
        """
        Initialize the order executor.

        Returns:
            bool: True if initialized successfully
        """
        if self._initialized:
            return True

        try:
            # Initialize broker connection
            if hasattr(self._broker, 'initialize'):
                await self._broker.initialize()

            # Start execution worker
            self._running = True
            self._execution_task = asyncio.create_task(self._process_queue())

            # Start monitoring
            if self._enable_monitoring:
                self._monitoring_task = asyncio.create_task(self._monitor_executions())

            self._initialized = True
            logger.info("OrderExecutor initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize OrderExecutor: {e}")
            return False

    async def shutdown(self):
        """Shutdown the order executor gracefully."""
        self._running = False

        if self._execution_task:
            self._execution_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()

        # Wait for active executions to complete
        if self._active_executions:
            logger.info(f"Waiting for {len(self._active_executions)} active executions to complete")
            timeout = 30
            start = time.time()
            while self._active_executions and (time.time() - start) < timeout:
                await asyncio.sleep(0.5)

        logger.info("OrderExecutor shut down")

    # ==================== Main Execution Methods ====================

    async def execute(
        self,
        config: Optional[ExecutionConfig] = None,
        callback: Optional[Callable[[ExecutionResult], Awaitable[None]]] = None
    ) -> ExecutionResult:
        """
        Execute an order.

        Args:
            config: Execution configuration (uses default if not provided)
            callback: Optional callback for execution updates

        Returns:
            ExecutionResult: Execution result
        """
        config = config or self._default_config

        # Validate configuration
        if config.validate_price and config.price is None and config.order_type != OrderType.MARKET:
            raise ValueError("Price required for non-market orders")

        if config.validate_size and config.size <= 0:
            raise ValueError("Order size must be positive")

        if config.validate_venue and config.venues and not config.venues:
            raise ValueError("No venues available")

        # Create execution context
        execution_id = f"exec_{datetime.utcnow().timestamp()}_{config.symbol}"
        context = {
            'id': execution_id,
            'config': config,
            'callback': callback,
            'status': 'pending',
            'start_time': datetime.utcnow(),
            'attempts': 0,
            'results': []
        }

        # Add to active executions
        self._active_executions[execution_id] = context

        try:
            # Execute with retry
            result = await self._execute_with_retry(context)

            # Update metrics
            await self._update_metrics(result)

            # Callback
            if callback:
                await callback(result)

            return result

        except Exception as e:
            logger.error(f"Execution failed for {execution_id}: {e}")
            result = ExecutionResult(
                order_id=execution_id,
                executed_price=0,
                executed_size=0,
                status=OrderStatus.REJECTED,
                error=str(e)
            )
            return result

        finally:
            # Remove from active executions
            self._active_executions.pop(execution_id, None)

    async def execute_batch(
        self,
        configs: List[ExecutionConfig],
        parallel: bool = False
    ) -> List[ExecutionResult]:
        """
        Execute multiple orders in batch.

        Args:
            configs: List of execution configurations
            parallel: Execute in parallel if True, otherwise sequential

        Returns:
            List[ExecutionResult]: Execution results
        """
        if parallel:
            # Execute in parallel with concurrency limit
            tasks = []
            for config in configs:
                tasks.append(self.execute(config))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    final_results.append(ExecutionResult(
                        order_id="",
                        executed_price=0,
                        executed_size=0,
                        status=OrderStatus.REJECTED,
                        error=str(result)
                    ))
                else:
                    final_results.append(result)

            return final_results

        else:
            # Execute sequentially
            results = []
            for config in configs:
                result = await self.execute(config)
                results.append(result)

            return results

    async def execute_async(
        self,
        config: ExecutionConfig,
        callback: Optional[Callable[[ExecutionResult], Awaitable[None]]] = None
    ) -> str:
        """
        Execute an order asynchronously (non-blocking).

        Args:
            config: Execution configuration
            callback: Optional callback

        Returns:
            str: Execution ID for tracking
        """
        # Queue the execution
        await self._execution_queue.put({
            'config': config,
            'callback': callback
        })

        return f"queued_{datetime.utcnow().timestamp()}"

    # ==================== Execution Strategies ====================

    async def _execute_with_retry(self, context: Dict[str, Any]) -> ExecutionResult:
        """Execute with retry logic."""
        config = context['config']
        attempts = 0
        last_error = None

        while attempts < config.max_retries:
            try:
                # Check circuit breaker
                venue = config.venues[0] if config.venues else "default"
                if venue in self._circuit_breakers:
                    if not self._circuit_breakers[venue].is_available():
                        logger.warning(f"Circuit breaker open for {venue}")
                        await asyncio.sleep(config.retry_delay)
                        continue

                # Execute based on strategy
                result = await self._execute_strategy(config)

                if result.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                    return result

                # Handle partial fills
                if result.status == OrderStatus.PARTIALLY_FILLED:
                    # Check if we should continue
                    if result.executed_size / config.size > 0.5:
                        return result
                    # Otherwise retry with remaining size
                    config.size = config.size - result.executed_size
                    attempts += 1
                    continue

                # Check for specific errors
                if result.error:
                    if "insufficient_balance" in result.error.lower():
                        # Don't retry for balance issues
                        return result

                attempts += 1
                await asyncio.sleep(config.retry_delay * (config.retry_backoff ** attempts))

            except Exception as e:
                last_error = e
                logger.warning(f"Execution attempt {attempts + 1} failed: {e}")
                attempts += 1
                await asyncio.sleep(config.retry_delay * (config.retry_backoff ** attempts))

        # All retries exhausted
        return ExecutionResult(
            order_id=context['id'],
            executed_price=0,
            executed_size=0,
            status=OrderStatus.REJECTED,
            error=f"All retries exhausted: {last_error}"
        )

    async def _execute_strategy(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute based on strategy type."""
        if config.execution_type == ExecutionType.MARKET:
            return await self._execute_market(config)

        elif config.execution_type == ExecutionType.LIMIT:
            return await self._execute_limit(config)

        elif config.execution_type == ExecutionType.STOP:
            return await self._execute_stop(config)

        elif config.execution_type == ExecutionType.ICEBERG:
            return await self._execute_iceberg(config)

        elif config.execution_type == ExecutionType.TWAP:
            return await self._execute_twap(config)

        elif config.execution_type == ExecutionType.VWAP:
            return await self._execute_vwap(config)

        elif config.execution_type == ExecutionType.POV:
            return await self._execute_pov(config)

        elif config.execution_type == ExecutionType.ADAPTIVE:
            return await self._execute_adaptive(config)

        elif config.execution_type == ExecutionType.SMART:
            return await self._execute_smart(config)

        elif config.execution_type == ExecutionType.ARBITRAGE:
            return await self._execute_arbitrage(config)

        elif config.execution_type == ExecutionType.HEDGE:
            return await self._execute_hedge(config)

        elif config.execution_type == ExecutionType.SCALING:
            return await self._execute_scaling(config)

        else:
            raise ValueError(f"Unknown execution type: {config.execution_type}")

    # ==================== Strategy Implementations ====================

    async def _execute_market(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute market order."""
        start_time = time.time()

        try:
            result = await self._broker.place_order(
                symbol=config.symbol,
                side=config.side,
                order_type=OrderType.MARKET,
                quantity=config.size,
                time_in_force=config.time_in_force
            )

            execution_time = time.time() - start_time

            return ExecutionResult(
                order_id=result.get('order_id', ''),
                executed_price=result.get('price', 0),
                executed_size=result.get('filled_quantity', config.size),
                status=OrderStatus.FILLED,
                execution_time=execution_time,
                fills=result.get('fills', []),
                fill_count=len(result.get('fills', [])),
                fees=result.get('fees', 0),
                venue=result.get('venue', 'market')
            )

        except Exception as e:
            raise

    async def _execute_limit(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute limit order."""
        start_time = time.time()

        if config.price is None:
            raise ValueError("Price required for limit order")

        try:
            result = await self._broker.place_order(
                symbol=config.symbol,
                side=config.side,
                order_type=OrderType.LIMIT,
                quantity=config.size,
                price=config.price,
                time_in_force=config.time_in_force
            )

            execution_time = time.time() - start_time

            # Calculate slippage
            slippage = abs(config.price - result.get('price', config.price)) / config.price

            return ExecutionResult(
                order_id=result.get('order_id', ''),
                executed_price=result.get('price', config.price),
                executed_size=result.get('filled_quantity', config.size),
                status=OrderStatus.FILLED,
                execution_time=execution_time,
                slippage=slippage,
                fills=result.get('fills', []),
                fill_count=len(result.get('fills', [])),
                fees=result.get('fees', 0),
                venue=result.get('venue', 'limit')
            )

        except Exception as e:
            raise

    async def _execute_stop(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute stop order."""
        start_time = time.time()

        if config.stop_price is None:
            raise ValueError("Stop price required for stop order")

        try:
            order_type = OrderType.STOP if config.order_type == OrderType.MARKET else OrderType.STOP_LIMIT
            params = {
                'symbol': config.symbol,
                'side': config.side,
                'order_type': order_type,
                'quantity': config.size,
                'stop_price': config.stop_price,
                'time_in_force': config.time_in_force
            }

            if config.price:
                params['price'] = config.price

            result = await self._broker.place_order(**params)

            execution_time = time.time() - start_time

            return ExecutionResult(
                order_id=result.get('order_id', ''),
                executed_price=result.get('price', config.stop_price),
                executed_size=result.get('filled_quantity', config.size),
                status=OrderStatus.FILLED,
                execution_time=execution_time,
                fills=result.get('fills', []),
                fill_count=len(result.get('fills', [])),
                fees=result.get('fees', 0),
                venue=result.get('venue', 'stop')
            )

        except Exception as e:
            raise

    async def _execute_iceberg(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute iceberg order."""
        start_time = time.time()

        display_size = config.iceberg_display_size or config.size * 0.1
        remaining = config.size
        total_filled = 0
        total_price = 0
        fills = []

        while remaining > 0 and (time.time() - start_time) < config.max_execution_time:
            order_size = min(display_size, remaining)

            try:
                # Place limit order
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.LIMIT,
                    quantity=order_size,
                    price=config.price,
                    time_in_force=TimeInForce.IOC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', config.price)
                    fills.append(result)

                remaining -= filled

                # Check if we should stop
                if filled == 0:
                    # No fills, maybe wait
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"Iceberg order error: {e}")

            await asyncio.sleep(config.iceberg_refresh_rate)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else config.price

        return ExecutionResult(
            order_id=f"iceberg_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='iceberg'
        )

    async def _execute_twap(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute TWAP order."""
        start_time = time.time()

        piece_size = config.size / config.twap_pieces
        total_filled = 0
        total_price = 0
        fills = []

        for i in range(config.twap_pieces):
            try:
                # Place order
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.MARKET if config.order_type == OrderType.MARKET else OrderType.LIMIT,
                    quantity=piece_size,
                    price=config.price,
                    time_in_force=TimeInForce.IOC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', config.price)
                    fills.append(result)

            except Exception as e:
                logger.warning(f"TWAP order {i} error: {e}")

            # Wait for next piece
            await asyncio.sleep(config.twap_interval)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else config.price

        return ExecutionResult(
            order_id=f"twap_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='twap'
        )

    async def _execute_vwap(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute VWAP order."""
        start_time = time.time()

        # Get volume profile
        volume_profile = await self._get_volume_profile(config.symbol, config.vwap_window)

        # Calculate target volumes per interval
        total_volume = sum(volume_profile.values())
        pieces = config.twap_pieces

        total_filled = 0
        total_price = 0
        fills = []

        for i, (time_key, volume) in enumerate(volume_profile.items()):
            if i >= pieces:
                break

            target_size = config.size * (volume / total_volume)

            try:
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.LIMIT,
                    quantity=target_size,
                    price=config.price,
                    time_in_force=TimeInForce.IOC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', config.price)
                    fills.append(result)

            except Exception as e:
                logger.warning(f"VWAP order {i} error: {e}")

            await asyncio.sleep(config.twap_interval)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else config.price

        return ExecutionResult(
            order_id=f"vwap_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='vwap'
        )

    async def _execute_pov(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute Percentage of Volume order."""
        start_time = time.time()

        total_filled = 0
        total_price = 0
        fills = []

        while total_filled < config.size and (time.time() - start_time) < config.max_execution_time:
            # Get current volume
            volume = await self._get_recent_volume(config.symbol)
            target_participation = min(
                config.pov_max_participation,
                max(config.pov_min_participation, config.pov_target)
            )

            order_size = volume * target_participation

            try:
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.MARKET,
                    quantity=order_size,
                    time_in_force=TimeInForce.IOC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', 0)
                    fills.append(result)

            except Exception as e:
                logger.warning(f"POV order error: {e}")

            await asyncio.sleep(1)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else 0

        return ExecutionResult(
            order_id=f"pov_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='pov'
        )

    async def _execute_adaptive(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute adaptive order."""
        start_time = time.time()

        # Get market conditions
        spread = await self._get_current_spread(config.symbol)
        volatility = await self._get_current_volatility(config.symbol)

        # Adjust strategy based on conditions
        if spread > config.max_spread:
            # Wide spread, use limit orders
            order_type = OrderType.LIMIT
        elif volatility > 0.01:
            # High volatility, use market orders
            order_type = OrderType.MARKET
        else:
            # Normal conditions, use limit
            order_type = OrderType.LIMIT

        total_filled = 0
        total_price = 0
        fills = []

        # Execute with adaptive sizing
        remaining = config.size
        while remaining > 0 and (time.time() - start_time) < config.max_execution_time:
            # Adaptive sizing based on market impact
            order_size = min(remaining, config.size * 0.1)

            # Check if we should adjust price
            if order_type == OrderType.LIMIT:
                # Use adaptive price
                if config.side == OrderSide.BUY:
                    price = config.price * (1 - volatility * config.adaptive_sensitivity)
                else:
                    price = config.price * (1 + volatility * config.adaptive_sensitivity)
            else:
                price = None

            try:
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=order_type,
                    quantity=order_size,
                    price=price,
                    time_in_force=TimeInForce.IOC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', 0)
                    fills.append(result)
                    remaining -= filled

            except Exception as e:
                logger.warning(f"Adaptive order error: {e}")

            # Update market conditions
            await asyncio.sleep(config.adaptive_update_interval)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else config.price

        return ExecutionResult(
            order_id=f"adaptive_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='adaptive'
        )

    async def _execute_smart(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute smart order routing."""
        start_time = time.time()

        # Get available venues
        venues = await self._get_available_venues(config.symbol)

        # Filter venues
        if config.venues:
            venues = [v for v in venues if v in config.venues]
        if config.exclude_venues:
            venues = [v for v in venues if v not in config.exclude_venues]

        if not venues:
            raise ValueError("No venues available")

        # Get best prices
        best_prices = await self._get_best_prices(config.symbol, venues)

        # Sort venues by price
        if config.side == OrderSide.BUY:
            sorted_venues = sorted(best_prices.items(), key=lambda x: x[1])
        else:
            sorted_venues = sorted(best_prices.items(), key=lambda x: x[1], reverse=True)

        total_filled = 0
        total_price = 0
        fills = []

        for venue, price in sorted_venues:
            if total_filled >= config.size:
                break

            order_size = min(config.size - total_filled, config.max_order_size)

            try:
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.LIMIT,
                    quantity=order_size,
                    price=price,
                    time_in_force=TimeInForce.IOC,
                    venue=venue
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', price)
                    fills.append(result)

            except Exception as e:
                logger.warning(f"Smart order on {venue} failed: {e}")

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else 0

        return ExecutionResult(
            order_id=f"smart_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            route='smart_routing',
            venue='multi_venue'
        )

    async def _execute_arbitrage(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute arbitrage order."""
        start_time = time.time()

        # Get prices from multiple venues
        venues = await self._get_available_venues(config.symbol)
        prices = await self._get_best_prices(config.symbol, venues)

        if len(prices) < 2:
            raise ValueError("Need at least 2 venues for arbitrage")

        # Find arbitrage opportunity
        if config.side == OrderSide.BUY:
            # Buy from cheapest venue
            cheapest_venue = min(prices.items(), key=lambda x: x[1])
            # Sell on most expensive venue (if we have the asset)
            most_expensive_venue = max(prices.items(), key=lambda x: x[1])
        else:
            # Sell on most expensive venue
            most_expensive_venue = max(prices.items(), key=lambda x: x[1])
            # Buy on cheapest venue (if we have the asset)
            cheapest_venue = min(prices.items(), key=lambda x: x[1])

        total_filled = 0
        total_price = 0
        fills = []

        try:
            # Execute on primary venue
            result = await self._broker.place_order(
                symbol=config.symbol,
                side=config.side,
                order_type=OrderType.MARKET,
                quantity=config.size,
                venue=cheapest_venue if config.side == OrderSide.BUY else most_expensive_venue
            )

            filled = result.get('filled_quantity', 0)
            if filled > 0:
                total_filled += filled
                total_price += filled * result.get('price', 0)
                fills.append(result)

            # Execute hedge on secondary venue
            if total_filled > 0:
                hedge_side = OrderSide.SELL if config.side == OrderSide.BUY else OrderSide.BUY
                hedge_result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=hedge_side,
                    order_type=OrderType.MARKET,
                    quantity=total_filled,
                    venue=most_expensive_venue if config.side == OrderSide.BUY else cheapest_venue
                )
                fills.append(hedge_result)

        except Exception as e:
            logger.error(f"Arbitrage execution failed: {e}")

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else 0

        return ExecutionResult(
            order_id=f"arb_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            route='arbitrage',
            venue='multi_venue'
        )

    async def _execute_hedge(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute hedge order."""
        # Similar to arbitrage but with correlated assets
        # This is a simplified implementation
        return await self._execute_market(config)

    async def _execute_scaling(self, config: ExecutionConfig) -> ExecutionResult:
        """Execute scaling order."""
        start_time = time.time()

        # Split into multiple orders
        num_orders = config.twap_pieces
        piece_size = config.size / num_orders

        total_filled = 0
        total_price = 0
        fills = []

        price_range = 0.02  # 2% price range
        step = price_range / num_orders

        for i in range(num_orders):
            if config.side == OrderSide.BUY:
                price = config.price * (1 - step * i)
            else:
                price = config.price * (1 + step * i)

            try:
                result = await self._broker.place_order(
                    symbol=config.symbol,
                    side=config.side,
                    order_type=OrderType.LIMIT,
                    quantity=piece_size,
                    price=price,
                    time_in_force=TimeInForce.GTC
                )

                filled = result.get('filled_quantity', 0)
                if filled > 0:
                    total_filled += filled
                    total_price += filled * result.get('price', price)
                    fills.append(result)

            except Exception as e:
                logger.warning(f"Scaling order {i} error: {e}")

            await asyncio.sleep(config.twap_interval)

        execution_time = time.time() - start_time
        avg_price = total_price / total_filled if total_filled > 0 else config.price

        return ExecutionResult(
            order_id=f"scale_{config.symbol}_{int(start_time)}",
            executed_price=avg_price,
            executed_size=total_filled,
            status=OrderStatus.FILLED if total_filled >= config.size else OrderStatus.PARTIALLY_FILLED,
            execution_time=execution_time,
            fills=fills,
            fill_count=len(fills),
            fees=sum(f.get('fees', 0) for f in fills),
            venue='scaling'
        )

    # ==================== Queue Processing ====================

    async def _process_queue(self):
        """Process execution queue."""
        while self._running:
            try:
                item = await self._execution_queue.get()

                # Execute with semaphore
                async with self._semaphore:
                    result = await self.execute(item['config'])

                    if item.get('callback'):
                        await item['callback'](result)

                self._execution_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing queue: {e}")

    async def _monitor_executions(self):
        """Monitor active executions."""
        while self._running:
            try:
                # Check for stale executions
                now = datetime.utcnow()
                stale_ids = []

                for exec_id, context in self._active_executions.items():
                    if context['status'] == 'pending':
                        elapsed = (now - context['start_time']).total_seconds()
                        if elapsed > context['config'].timeout:
                            stale_ids.append(exec_id)

                # Cancel stale executions
                for exec_id in stale_ids:
                    context = self._active_executions[exec_id]
                    context['status'] = 'timeout'
                    logger.warning(f"Execution {exec_id} timed out")

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring executions: {e}")

    # ==================== Market Data Helpers ====================

    async def _get_volume_profile(self, symbol: str, window: int) -> Dict[str, float]:
        """Get volume profile for VWAP execution."""
        # Simplified implementation
        # In production, this would fetch historical volume data
        return {f"interval_{i}": 1.0 / window for i in range(window)}

    async def _get_recent_volume(self, symbol: str) -> float:
        """Get recent trading volume."""
        # Simplified implementation
        return 1000.0

    async def _get_current_spread(self, symbol: str) -> float:
        """Get current spread."""
        # Simplified implementation
        return 0.001

    async def _get_current_volatility(self, symbol: str) -> float:
        """Get current volatility."""
        # Simplified implementation
        return 0.01

    async def _get_available_venues(self, symbol: str) -> List[str]:
        """Get available venues for a symbol."""
        # Simplified implementation
        return ['primary', 'secondary']

    async def _get_best_prices(self, symbol: str, venues: List[str]) -> Dict[str, float]:
        """Get best prices from venues."""
        # Simplified implementation
        base_price = 100.0
        return {venue: base_price * (1 + i * 0.001) for i, venue in enumerate(venues)}

    # ==================== Metrics Management ====================

    async def _update_metrics(self, result: ExecutionResult):
        """Update execution metrics."""
        self._metrics.total_orders += 1

        if result.status == OrderStatus.FILLED:
            self._metrics.successful_orders += 1
        elif result.status == OrderStatus.PARTIALLY_FILLED:
            self._metrics.partial_orders += 1
        else:
            self._metrics.failed_orders += 1

        self._metrics.total_volume += result.executed_size
        self._metrics.total_value += result.executed_price * result.executed_size
        self._metrics.total_fees += result.fees

        self._execution_times.append(result.execution_time)
        self._slippage_values.append(result.slippage)

        if self._execution_times:
            self._metrics.average_execution_time = sum(self._execution_times) / len(self._execution_times)

        if self._slippage_values:
            self._metrics.average_slippage = sum(self._slippage_values) / len(self._slippage_values)

        total_completed = self._metrics.successful_orders + self._metrics.failed_orders
        if total_completed > 0:
            self._metrics.success_rate = self._metrics.successful_orders / total_completed * 100

        if self._metrics.total_orders > 0:
            self._metrics.fill_rate = self._metrics.successful_orders / self._metrics.total_orders * 100

    async def get_metrics(self) -> ExecutionMetrics:
        """Get execution metrics."""
        return self._metrics

    async def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        return {
            'metrics': self._metrics.model_dump(),
            'active_executions': len(self._active_executions),
            'queue_size': self._execution_queue.qsize(),
            'execution_times': list(self._execution_times),
            'slippage_values': list(self._slippage_values)
        }

    # ==================== Utility Methods ====================

    async def cancel_all(self) -> int:
        """Cancel all executions."""
        cancelled = 0

        # Cancel active executions
        for exec_id, context in self._active_executions.items():
            if context['status'] == 'pending':
                context['status'] = 'cancelled'
                cancelled += 1

        # Clear queue
        while not self._execution_queue.empty():
            try:
                self._execution_queue.get_nowait()
                self._execution_queue.task_done()
                cancelled += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Cancelled {cancelled} executions")
        return cancelled

    async def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            'running': self._running,
            'initialized': self._initialized,
            'active_executions': len(self._active_executions),
            'queue_size': self._execution_queue.qsize(),
            'max_concurrent': self._max_concurrent,
            'execution_history': len(self._execution_history)
        }

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
