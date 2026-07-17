# trading/bots/ai_bot/strategies/strategy_executor.py
# NEXUS AI TRADING SYSTEM - Strategy Executor
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Strategy Executor for NEXUS AI Trading Bot.
Provides comprehensive strategy execution including:
- Strategy lifecycle management (start, stop, pause, resume)
- Multi-strategy orchestration
- Signal execution and routing
- Position management
- Performance tracking
- Resource management
- Error handling and recovery
- Event-driven execution
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyConfig, StrategyState
from trading.bots.ai_bot.execution.order_manager import OrderManager
from trading.bots.ai_bot.risk.risk_manager import RiskManager
from trading.bots.ai_bot.market_data.market_data_provider import MarketDataProvider
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.executor")


# ============================================================================
# Enums & Constants
# ============================================================================

class ExecutorState(str, Enum):
    """Executor states."""
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    RECOVERING = "recovering"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """Execution modes."""
    SEQUENTIAL = "sequential"      # Execute strategies one by one
    PARALLEL = "parallel"          # Execute strategies in parallel
    HYBRID = "hybrid"              # Hybrid execution
    PRIORITY = "priority"          # Priority-based execution


@dataclass
class StrategyInstance:
    """Strategy instance data."""
    strategy: BaseStrategy
    config: StrategyConfig
    priority: int = 0
    status: StrategyState = StrategyState.INITIALIZED
    last_execution: Optional[datetime] = None
    execution_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    performance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Execution context."""
    timestamp: datetime
    strategy: Optional[StrategyInstance] = None
    signal: Optional[Signal] = None
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Execution result."""
    success: bool
    strategy: str
    signal: Optional[Signal] = None
    order_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Strategy Executor
# ============================================================================

class StrategyExecutor:
    """
    Strategy Executor for NEXUS AI Trading Bot.
    Orchestrates strategy execution and signal processing.
    """

    def __init__(
        self,
        order_manager: OrderManager,
        risk_manager: RiskManager,
        market_data_provider: MarketDataProvider,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize strategy executor.

        Args:
            order_manager: Order management instance
            risk_manager: Risk management instance
            market_data_provider: Market data provider
            config: Configuration dictionary
        """
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.market_data_provider = market_data_provider
        self.config = config or {}

        # Strategy management
        self._strategies: Dict[str, StrategyInstance] = {}
        self._strategy_order: List[str] = []
        self._active_strategies: Set[str] = set()
        self._paused_strategies: Set[str] = set()

        # Execution state
        self._state = ExecutorState.INITIALIZED
        self._running = False
        self._paused = False
        self._lock = asyncio.Lock()

        # Execution mode
        self._mode = ExecutionMode(self.config.get("mode", "parallel"))

        # Signal processing
        self._signal_queue: asyncio.Queue = asyncio.Queue()
        self._signal_history: List[Dict[str, Any]] = []
        self._execution_history: List[ExecutionResult] = []

        # Performance tracking
        self._performance = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_signals": 0,
            "processed_signals": 0,
            "avg_execution_time_ms": 0.0,
            "by_strategy": defaultdict(lambda: {
                "executions": 0,
                "success": 0,
                "failed": 0,
                "avg_time": 0.0,
            }),
        }

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "signal": [],
            "execution": [],
            "strategy_start": [],
            "strategy_stop": [],
            "error": [],
            "state_change": [],
        }

        # Background tasks
        self._tasks: List[asyncio.Task] = []
        self._signal_processor_task: Optional[asyncio.Task] = None

        # Metrics
        self._metrics = {
            "strategies_loaded": 0,
            "strategies_active": 0,
            "signals_queued": 0,
            "signals_processed": 0,
            "execution_success_rate": 0.0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }

        # Performance timers
        self._last_metrics_update = datetime.utcnow()
        self._execution_start_time = datetime.utcnow()

        logger.info(
            "StrategyExecutor initialized",
            extra={
                "mode": self._mode.value,
                "config": self.config,
            }
        )

    # ========================================================================
    # Strategy Management
    # ========================================================================

    def register_strategy(
        self,
        name: str,
        strategy: BaseStrategy,
        config: StrategyConfig,
        priority: int = 0,
    ) -> bool:
        """
        Register a strategy.

        Args:
            name: Strategy name
            strategy: Strategy instance
            config: Strategy configuration
            priority: Strategy priority

        Returns:
            True if registered successfully
        """
        if name in self._strategies:
            logger.warning(f"Strategy {name} already registered")
            return False

        instance = StrategyInstance(
            strategy=strategy,
            config=config,
            priority=priority,
        )

        self._strategies[name] = instance
        self._strategy_order.append(name)

        # Sort strategies by priority
        self._strategy_order.sort(
            key=lambda x: self._strategies[x].priority,
            reverse=True,
        )

        logger.info(f"Strategy registered: {name}", extra={"priority": priority})

        # Register event handlers
        self._register_strategy_handlers(strategy)

        return True

    def unregister_strategy(self, name: str) -> bool:
        """
        Unregister a strategy.

        Args:
            name: Strategy name

        Returns:
            True if unregistered successfully
        """
        if name not in self._strategies:
            logger.warning(f"Strategy {name} not found")
            return False

        if name in self._active_strategies:
            logger.warning(f"Strategy {name} is active, stopping first")
            asyncio.create_task(self.stop_strategy(name))

        del self._strategies[name]
        self._strategy_order.remove(name)
        self._active_strategies.discard(name)
        self._paused_strategies.discard(name)

        logger.info(f"Strategy unregistered: {name}")
        return True

    async def start_strategy(self, name: str) -> bool:
        """
        Start a specific strategy.

        Args:
            name: Strategy name

        Returns:
            True if started successfully
        """
        if name not in self._strategies:
            logger.error(f"Strategy {name} not found")
            return False

        instance = self._strategies[name]

        if instance.status == StrategyState.RUNNING:
            logger.info(f"Strategy {name} already running")
            return True

        try:
            await instance.strategy.start()
            instance.status = StrategyState.RUNNING
            self._active_strategies.add(name)

            self._emit_event("strategy_start", {"name": name})

            logger.info(f"Strategy started: {name}")
            return True

        except Exception as e:
            logger.error(f"Error starting strategy {name}: {e}")
            instance.status = StrategyState.ERROR
            instance.last_error = str(e)
            self._emit_event("error", {"strategy": name, "error": str(e)})
            return False

    async def stop_strategy(self, name: str) -> bool:
        """
        Stop a specific strategy.

        Args:
            name: Strategy name

        Returns:
            True if stopped successfully
        """
        if name not in self._strategies:
            logger.error(f"Strategy {name} not found")
            return False

        instance = self._strategies[name]

        if instance.status == StrategyState.STOPPED:
            logger.info(f"Strategy {name} already stopped")
            return True

        try:
            await instance.strategy.stop()
            instance.status = StrategyState.STOPPED
            self._active_strategies.discard(name)
            self._paused_strategies.discard(name)

            self._emit_event("strategy_stop", {"name": name})

            logger.info(f"Strategy stopped: {name}")
            return True

        except Exception as e:
            logger.error(f"Error stopping strategy {name}: {e}")
            self._emit_event("error", {"strategy": name, "error": str(e)})
            return False

    async def pause_strategy(self, name: str) -> bool:
        """
        Pause a specific strategy.

        Args:
            name: Strategy name

        Returns:
            True if paused successfully
        """
        if name not in self._strategies:
            logger.error(f"Strategy {name} not found")
            return False

        instance = self._strategies[name]

        if instance.status != StrategyState.RUNNING:
            logger.info(f"Strategy {name} is not running")
            return False

        try:
            await instance.strategy.pause()
            instance.status = StrategyState.PAUSED
            self._paused_strategies.add(name)

            logger.info(f"Strategy paused: {name}")
            return True

        except Exception as e:
            logger.error(f"Error pausing strategy {name}: {e}")
            self._emit_event("error", {"strategy": name, "error": str(e)})
            return False

    async def resume_strategy(self, name: str) -> bool:
        """
        Resume a paused strategy.

        Args:
            name: Strategy name

        Returns:
            True if resumed successfully
        """
        if name not in self._strategies:
            logger.error(f"Strategy {name} not found")
            return False

        instance = self._strategies[name]

        if instance.status != StrategyState.PAUSED:
            logger.info(f"Strategy {name} is not paused")
            return False

        try:
            await instance.strategy.resume()
            instance.status = StrategyState.RUNNING
            self._paused_strategies.discard(name)

            logger.info(f"Strategy resumed: {name}")
            return True

        except Exception as e:
            logger.error(f"Error resuming strategy {name}: {e}")
            self._emit_event("error", {"strategy": name, "error": str(e)})
            return False

    # ========================================================================
    # Strategy Execution
    # ========================================================================

    async def execute(self) -> None:
        """
        Main execution loop.
        """
        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                # Get strategies to execute
                strategies = self._get_executable_strategies()

                if not strategies:
                    await asyncio.sleep(1)
                    continue

                # Execute strategies
                if self._mode == ExecutionMode.SEQUENTIAL:
                    await self._execute_sequential(strategies)
                elif self._mode == ExecutionMode.PARALLEL:
                    await self._execute_parallel(strategies)
                elif self._mode == ExecutionMode.PRIORITY:
                    await self._execute_priority(strategies)
                else:
                    await self._execute_hybrid(strategies)

                # Update metrics
                await self._update_metrics()

                # Process signal queue
                await self._process_signal_queue()

                # Sleep based on configuration
                await self._sleep_for_cycle()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Execution error: {e}")
                self._emit_event("error", {"error": str(e)})

                # Wait before retry
                await asyncio.sleep(5)

    def _get_executable_strategies(self) -> List[StrategyInstance]:
        """
        Get strategies ready for execution.

        Returns:
            List of StrategyInstance
        """
        strategies = []

        for name in self._strategy_order:
            instance = self._strategies.get(name)

            if not instance:
                continue

            if instance.status != StrategyState.RUNNING:
                continue

            if name in self._paused_strategies:
                continue

            strategies.append(instance)

        return strategies

    async def _execute_sequential(self, strategies: List[StrategyInstance]) -> None:
        """
        Execute strategies sequentially.

        Args:
            strategies: List of StrategyInstance
        """
        for instance in strategies:
            if not self._running:
                break

            try:
                await self._execute_strategy(instance)
            except Exception as e:
                logger.error(f"Error executing {instance.strategy.config.name}: {e}")
                self._emit_event("error", {
                    "strategy": instance.strategy.config.name,
                    "error": str(e),
                })

    async def _execute_parallel(self, strategies: List[StrategyInstance]) -> None:
        """
        Execute strategies in parallel.

        Args:
            strategies: List of StrategyInstance
        """
        tasks = []

        for instance in strategies:
            if not self._running:
                break

            tasks.append(self._execute_strategy(instance))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in parallel execution: {result}")
                    self._emit_event("error", {
                        "strategy": strategies[i].strategy.config.name,
                        "error": str(result),
                    })

    async def _execute_priority(self, strategies: List[StrategyInstance]) -> None:
        """
        Execute strategies by priority.

        Args:
            strategies: List of StrategyInstance
        """
        # Strategies are already sorted by priority
        for instance in strategies:
            if not self._running:
                break

            try:
                # Execute high priority strategies more frequently
                if instance.priority > 5:
                    await self._execute_strategy(instance)
                else:
                    # Lower priority strategies execute less frequently
                    if instance.execution_count % 2 == 0:
                        await self._execute_strategy(instance)

            except Exception as e:
                logger.error(f"Error executing {instance.strategy.config.name}: {e}")

    async def _execute_hybrid(self, strategies: List[StrategyInstance]) -> None:
        """
        Execute strategies with hybrid approach.

        Args:
            strategies: List of StrategyInstance
        """
        # Separate strategies by type
        high_priority = [s for s in strategies if s.priority > 5]
        low_priority = [s for s in strategies if s.priority <= 5]

        # Execute high priority sequentially
        for instance in high_priority:
            if not self._running:
                break
            await self._execute_strategy(instance)

        # Execute low priority in parallel
        if low_priority and self._running:
            tasks = [self._execute_strategy(instance) for instance in low_priority]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_strategy(self, instance: StrategyInstance) -> None:
        """
        Execute a single strategy.

        Args:
            instance: StrategyInstance
        """
        start_time = time.time()

        try:
            # Analyze
            analysis = await instance.strategy.analyze()

            # Process signals
            if analysis.get("signals"):
                for signal in analysis["signals"]:
                    await self._process_signal(signal, instance)

            # Update instance
            instance.last_execution = datetime.utcnow()
            instance.execution_count += 1

            # Track performance
            execution_time_ms = (time.time() - start_time) * 1000
            self._performance["by_strategy"][instance.strategy.config.name]["executions"] += 1
            self._performance["by_strategy"][instance.strategy.config.name]["avg_time"] = (
                (
                    self._performance["by_strategy"][instance.strategy.config.name]["avg_time"] *
                    (instance.execution_count - 1) +
                    execution_time_ms
                ) / instance.execution_count
            )

        except Exception as e:
            instance.error_count += 1
            instance.last_error = str(e)
            self._emit_event("error", {
                "strategy": instance.strategy.config.name,
                "error": str(e),
            })
            raise

    # ========================================================================
    # Signal Processing
    # ========================================================================

    async def _process_signal(self, signal: Signal, instance: StrategyInstance) -> None:
        """
        Process a trading signal.

        Args:
            signal: Trading signal
            instance: Strategy instance
        """
        self._performance["total_signals"] += 1

        # Validate signal
        if not await self._validate_signal(signal):
            logger.debug(f"Signal validation failed: {signal.symbol} {signal.type.value}")
            return

        # Add to queue for processing
        await self._signal_queue.put({
            "signal": signal,
            "instance": instance,
            "timestamp": datetime.utcnow(),
        })

        self._signal_history.append({
            "signal": signal,
            "timestamp": datetime.utcnow(),
            "strategy": instance.strategy.config.name,
            "status": "queued",
        })

        # Keep history limited
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-1000:]

    async def _process_signal_queue(self) -> None:
        """
        Process signals from the queue.
        """
        processed = 0

        while not self._signal_queue.empty() and processed < 10:
            try:
                item = await self._signal_queue.get()

                signal = item["signal"]
                instance = item["instance"]

                # Execute signal
                result = await instance.strategy.execute(signal)

                # Create execution result
                execution_result = ExecutionResult(
                    success=result.get("success", False),
                    strategy=instance.strategy.config.name,
                    signal=signal,
                    order_result=result,
                    execution_time_ms=result.get("execution_time_ms", 0),
                )

                # Track result
                self._execution_history.append(execution_result)
                self._performance["total_executions"] += 1

                if execution_result.success:
                    self._performance["successful_executions"] += 1
                    self._performance["by_strategy"][instance.strategy.config.name]["success"] += 1
                else:
                    self._performance["failed_executions"] += 1
                    self._performance["by_strategy"][instance.strategy.config.name]["failed"] += 1

                # Emit execution event
                self._emit_event("execution", execution_result)

                # Update signal history
                for entry in self._signal_history:
                    if entry["signal"] is signal:
                        entry["status"] = "executed"
                        entry["result"] = execution_result
                        break

                processed += 1

            except Exception as e:
                logger.error(f"Error processing signal: {e}")
                self._emit_event("error", {"error": str(e)})

    async def _validate_signal(self, signal: Signal) -> bool:
        """
        Validate a trading signal.

        Args:
            signal: Trading signal

        Returns:
            True if valid
        """
        # Check risk limits
        side = "buy" if signal.type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell"

        if not await self.risk_manager.check_order_limits(
            symbol=signal.symbol,
            side=side,
            quantity=signal.quantity,
            price=signal.price,
        ):
            return False

        # Check if symbol is active
        if signal.symbol not in self.config.get("active_symbols", []):
            return False

        return True

    # ========================================================================
    # Strategy Event Handling
    # ========================================================================

    def _register_strategy_handlers(self, strategy: BaseStrategy) -> None:
        """
        Register event handlers for a strategy.

        Args:
            strategy: Strategy instance
        """
        strategy.on("signal", self._handle_strategy_signal)
        strategy.on("trade", self._handle_strategy_trade)
        strategy.on("position", self._handle_strategy_position)
        strategy.on("error", self._handle_strategy_error)
        strategy.on("state_change", self._handle_strategy_state_change)
        strategy.on("heartbeat", self._handle_strategy_heartbeat)

    def _handle_strategy_signal(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy signal event.

        Args:
            data: Event data
        """
        signal = data.get("signal")
        if signal:
            self._emit_event("signal", signal)

    def _handle_strategy_trade(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy trade event.

        Args:
            data: Event data
        """
        self._emit_event("trade", data)

    def _handle_strategy_position(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy position event.

        Args:
            data: Event data
        """
        self._emit_event("position", data)

    def _handle_strategy_error(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy error event.

        Args:
            data: Event data
        """
        self._emit_event("error", {
            "strategy": data.get("strategy", "unknown"),
            "error": data.get("error"),
        })

    def _handle_strategy_state_change(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy state change event.

        Args:
            data: Event data
        """
        self._emit_event("state_change", data)

    def _handle_strategy_heartbeat(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy heartbeat event.

        Args:
            data: Event data
        """
        # Update strategy status
        strategy_name = data.get("strategy")
        if strategy_name and strategy_name in self._strategies:
            instance = self._strategies[strategy_name]
            instance.status = StrategyState.RUNNING

    # ========================================================================
    # Event System
    # ========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler function
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler function
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
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
    # Utility Methods
    # ========================================================================

    async def _sleep_for_cycle(self) -> None:
        """
        Sleep for the configured cycle duration.
        """
        cycle_duration = self.config.get("cycle_duration", 60)  # Default 60 seconds
        await asyncio.sleep(cycle_duration)

    async def _update_metrics(self) -> None:
        """
        Update performance metrics.
        """
        now = datetime.utcnow()

        # Update every 60 seconds
        if (now - self._last_metrics_update).seconds < 60:
            return

        # Calculate metrics
        total = self._performance["total_executions"]
        success = self._performance["successful_executions"]

        if total > 0:
            self._metrics["execution_success_rate"] = success / total

        # Update win rate
        if self._performance["by_strategy"]:
            total_profit = 0
            total_loss = 0
            total_wins = 0
            total_losses = 0

            for strategy_data in self._performance["by_strategy"].values():
                # Would need to get actual profit/loss data
                pass

            if total_losses > 0:
                self._metrics["win_rate"] = total_wins / (total_wins + total_losses)

        # Calculate Sharpe ratio
        if self._metrics["win_rate"] > 0:
            self._metrics["sharpe_ratio"] = (
                self._metrics["win_rate"] * 252 / (1 + self._metrics["max_drawdown"])
            )

        self._metrics["strategies_loaded"] = len(self._strategies)
        self._metrics["strategies_active"] = len(self._active_strategies)
        self._metrics["signals_queued"] = self._signal_queue.qsize()
        self._metrics["signals_processed"] = self._performance["processed_signals"]

        self._last_metrics_update = now

    # ========================================================================
    # Performance Tracking
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            "state": self._state.value,
            "running": self._running,
            "paused": self._paused,
            "mode": self._mode.value,
            "strategies": {
                "total": len(self._strategies),
                "active": len(self._active_strategies),
                "paused": len(self._paused_strategies),
            },
            "performance": self._performance,
            "metrics": self._metrics,
            "signal_queue_size": self._signal_queue.qsize(),
            "signal_history": len(self._signal_history),
            "execution_history": len(self._execution_history),
            "uptime_seconds": (datetime.utcnow() - self._execution_start_time).total_seconds(),
            "by_strategy": {
                name: {
                    "status": instance.status.value,
                    "execution_count": instance.execution_count,
                    "error_count": instance.error_count,
                    "priority": instance.priority,
                    "last_execution": instance.last_execution.isoformat() if instance.last_execution else None,
                    "performance": instance.performance,
                }
                for name, instance in self._strategies.items()
            },
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """
        Start the executor.
        """
        if self._state in [ExecutorState.RUNNING, ExecutorState.STARTING]:
            return

        self._state = ExecutorState.STARTING
        self._emit_event("state_change", {"state": self._state})

        try:
            # Start all strategies
            for name in self._strategy_order:
                await self.start_strategy(name)

            self._running = True
            self._state = ExecutorState.RUNNING
            self._execution_start_time = datetime.utcnow()

            # Start signal processor
            self._signal_processor_task = asyncio.create_task(self._process_signal_queue())

            # Start main execution loop
            await self.execute()

            self._emit_event("state_change", {"state": self._state})
            logger.info("StrategyExecutor started")

        except Exception as e:
            logger.error(f"Error starting executor: {e}")
            self._state = ExecutorState.ERROR
            self._emit_event("error", {"error": str(e)})
            raise

    async def stop(self) -> None:
        """
        Stop the executor.
        """
        if self._state in [ExecutorState.STOPPING, ExecutorState.STOPPED]:
            return

        self._state = ExecutorState.STOPPING
        self._emit_event("state_change", {"state": self._state})

        self._running = False

        # Stop signal processor
        if self._signal_processor_task:
            self._signal_processor_task.cancel()
            try:
                await self._signal_processor_task
            except asyncio.CancelledError:
                pass
            self._signal_processor_task = None

        # Stop all strategies
        for name in self._strategy_order:
            await self.stop_strategy(name)

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        self._state = ExecutorState.STOPPED
        self._emit_event("state_change", {"state": self._state})

        logger.info("StrategyExecutor stopped")

    async def pause(self) -> None:
        """
        Pause the executor.
        """
        if self._state != ExecutorState.RUNNING:
            return

        self._state = ExecutorState.PAUSING
        self._emit_event("state_change", {"state": self._state})

        self._paused = True

        # Pause all strategies
        for name in self._strategy_order:
            await self.pause_strategy(name)

        self._state = ExecutorState.PAUSED
        self._emit_event("state_change", {"state": self._state})

        logger.info("StrategyExecutor paused")

    async def resume(self) -> None:
        """
        Resume the executor.
        """
        if self._state != ExecutorState.PAUSED:
            return

        self._paused = False

        # Resume all strategies
        for name in self._strategy_order:
            await self.resume_strategy(name)

        self._state = ExecutorState.RUNNING
        self._emit_event("state_change", {"state": self._state})

        logger.info("StrategyExecutor resumed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# ============================================================================
# Factory Function
# ============================================================================

def create_strategy_executor(
    order_manager: OrderManager,
    risk_manager: RiskManager,
    market_data_provider: MarketDataProvider,
    config: Optional[Dict[str, Any]] = None,
) -> StrategyExecutor:
    """
    Factory function to create a StrategyExecutor instance.

    Args:
        order_manager: Order management instance
        risk_manager: Risk management instance
        market_data_provider: Market data provider
        config: Configuration dictionary

    Returns:
        StrategyExecutor instance
    """
    return StrategyExecutor(
        order_manager=order_manager,
        risk_manager=risk_manager,
        market_data_provider=market_data_provider,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the strategy executor
    pass
