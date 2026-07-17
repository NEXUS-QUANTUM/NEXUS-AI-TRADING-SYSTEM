"""
NEXUS AI TRADING SYSTEM - Drawdown Controller
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced drawdown control system for managing portfolio drawdowns,
implementing circuit breakers, and protecting capital during adverse market conditions.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
DRAWDOWN_COUNTER = Counter(
    "nexus_drawdown_events_total",
    "Total number of drawdown events",
    ["level", "action"],
)
DRAWDOWN_GAUGE = Gauge(
    "nexus_current_drawdown",
    "Current drawdown level",
    ["portfolio"],
)
DRAWDOWN_DURATION = Histogram(
    "nexus_drawdown_duration_seconds",
    "Duration of drawdown periods",
    ["portfolio"],
)


class DrawdownLevel(Enum):
    """Drawdown severity levels."""

    NORMAL = "normal"          # 0-5%
    WARNING = "warning"        # 5-10%
    ELEVATED = "elevated"      # 10-20%
    SEVERE = "severe"          # 20-30%
    CRITICAL = "critical"      # 30-50%
    EXTREME = "extreme"        # 50%+


class ActionType(Enum):
    """Types of drawdown actions."""

    NONE = "none"
    REDUCE_POSITION = "reduce_position"
    HALT_TRADING = "halt_trading"
    CLOSE_POSITIONS = "close_positions"
    LIQUIDATE = "liquidate"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class DrawdownConfig:
    """Configuration for drawdown control."""

    # Thresholds (in decimal, e.g., 0.1 = 10%)
    warning_threshold: float = 0.05
    elevated_threshold: float = 0.10
    severe_threshold: float = 0.20
    critical_threshold: float = 0.30
    extreme_threshold: float = 0.50

    # Action configurations
    warning_action: ActionType = ActionType.NONE
    elevated_action: ActionType = ActionType.REDUCE_POSITION
    severe_action: ActionType = ActionType.HALT_TRADING
    critical_action: ActionType = ActionType.CLOSE_POSITIONS
    extreme_action: ActionType = ActionType.EMERGENCY_STOP

    # Position reduction percentages
    warning_reduction: float = 0.0
    elevated_reduction: float = 0.25
    severe_reduction: float = 0.50
    critical_reduction: float = 0.75
    extreme_reduction: float = 1.0

    # Recovery thresholds
    recovery_threshold: float = 0.03
    recovery_action: ActionType = ActionType.NONE
    recovery_position_increase: float = 0.10

    # Monitoring
    check_interval_seconds: int = 60
    lookback_days: int = 30
    min_history_points: int = 20

    # Advanced settings
    use_rolling_window: bool = True
    rolling_window_days: int = 30
    use_peak_drawdown: bool = True
    use_relative_drawdown: bool = False
    use_high_water_mark: bool = True

    # Allowed symbols
    allowed_symbols: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "warning_threshold": self.warning_threshold,
            "elevated_threshold": self.elevated_threshold,
            "severe_threshold": self.severe_threshold,
            "critical_threshold": self.critical_threshold,
            "extreme_threshold": self.extreme_threshold,
            "warning_action": self.warning_action.value,
            "elevated_action": self.elevated_action.value,
            "severe_action": self.severe_action.value,
            "critical_action": self.critical_action.value,
            "extreme_action": self.extreme_action.value,
            "warning_reduction": self.warning_reduction,
            "elevated_reduction": self.elevated_reduction,
            "severe_reduction": self.severe_reduction,
            "critical_reduction": self.critical_reduction,
            "extreme_reduction": self.extreme_reduction,
            "recovery_threshold": self.recovery_threshold,
            "recovery_action": self.recovery_action.value,
            "recovery_position_increase": self.recovery_position_increase,
            "check_interval_seconds": self.check_interval_seconds,
            "lookback_days": self.lookback_days,
            "min_history_points": self.min_history_points,
            "use_rolling_window": self.use_rolling_window,
            "rolling_window_days": self.rolling_window_days,
            "use_peak_drawdown": self.use_peak_drawdown,
            "use_relative_drawdown": self.use_relative_drawdown,
            "use_high_water_mark": self.use_high_water_mark,
            "allowed_symbols": self.allowed_symbols,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrawdownConfig":
        """Create from dictionary."""
        return cls(
            warning_threshold=data.get("warning_threshold", 0.05),
            elevated_threshold=data.get("elevated_threshold", 0.10),
            severe_threshold=data.get("severe_threshold", 0.20),
            critical_threshold=data.get("critical_threshold", 0.30),
            extreme_threshold=data.get("extreme_threshold", 0.50),
            warning_action=ActionType(data.get("warning_action", "none")),
            elevated_action=ActionType(data.get("elevated_action", "reduce_position")),
            severe_action=ActionType(data.get("severe_action", "halt_trading")),
            critical_action=ActionType(data.get("critical_action", "close_positions")),
            extreme_action=ActionType(data.get("extreme_action", "emergency_stop")),
            warning_reduction=data.get("warning_reduction", 0.0),
            elevated_reduction=data.get("elevated_reduction", 0.25),
            severe_reduction=data.get("severe_reduction", 0.50),
            critical_reduction=data.get("critical_reduction", 0.75),
            extreme_reduction=data.get("extreme_reduction", 1.0),
            recovery_threshold=data.get("recovery_threshold", 0.03),
            recovery_action=ActionType(data.get("recovery_action", "none")),
            recovery_position_increase=data.get("recovery_position_increase", 0.10),
            check_interval_seconds=data.get("check_interval_seconds", 60),
            lookback_days=data.get("lookback_days", 30),
            min_history_points=data.get("min_history_points", 20),
            use_rolling_window=data.get("use_rolling_window", True),
            rolling_window_days=data.get("rolling_window_days", 30),
            use_peak_drawdown=data.get("use_peak_drawdown", True),
            use_relative_drawdown=data.get("use_relative_drawdown", False),
            use_high_water_mark=data.get("use_high_water_mark", True),
            allowed_symbols=data.get("allowed_symbols", []),
        )


@dataclass
class DrawdownState:
    """Current drawdown state."""

    current_drawdown: float = 0.0
    peak_drawdown: float = 0.0
    drawdown_level: DrawdownLevel = DrawdownLevel.NORMAL
    current_action: ActionType = ActionType.NONE
    position_reduction: float = 0.0
    drawdown_start_time: Optional[datetime] = None
    drawdown_end_time: Optional[datetime] = None
    high_water_mark: float = 0.0
    current_value: float = 0.0
    peak_value: float = 0.0
    recovery_value: Optional[float] = None
    recovery_threshold_reached: bool = False
    last_check_time: datetime = field(default_factory=datetime.utcnow)
    active_actions: List[ActionType] = field(default_factory=list)
    history: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_drawdown": self.current_drawdown,
            "peak_drawdown": self.peak_drawdown,
            "drawdown_level": self.drawdown_level.value,
            "current_action": self.current_action.value,
            "position_reduction": self.position_reduction,
            "drawdown_start_time": self.drawdown_start_time.isoformat() if self.drawdown_start_time else None,
            "drawdown_end_time": self.drawdown_end_time.isoformat() if self.drawdown_end_time else None,
            "high_water_mark": self.high_water_mark,
            "current_value": self.current_value,
            "peak_value": self.peak_value,
            "recovery_value": self.recovery_value,
            "recovery_threshold_reached": self.recovery_threshold_reached,
            "last_check_time": self.last_check_time.isoformat(),
            "active_actions": [a.value for a in self.active_actions],
            "history": self.history[-100:],  # Last 100 points
        }


class DrawdownController:
    """
    Advanced drawdown control system for managing portfolio drawdowns.
    """

    def __init__(
        self,
        config: Optional[Union[DrawdownConfig, Dict[str, Any]]] = None,
        portfolio_manager: Optional[Any] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the drawdown controller.

        Args:
            config: Drawdown configuration
            portfolio_manager: Portfolio manager instance
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        if isinstance(config, dict):
            self.config = DrawdownConfig.from_dict(config)
        elif isinstance(config, DrawdownConfig):
            self.config = config
        else:
            self.config = DrawdownConfig()

        self.portfolio_manager = portfolio_manager
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._state: Dict[str, DrawdownState] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._action_handlers: Dict[ActionType, Callable] = {}
        self._event_handlers: Dict[str, List[Callable]] = {
            "drawdown_triggered": [],
            "drawdown_recovered": [],
            "action_executed": [],
        }

        # Register default action handlers
        self._register_default_handlers()

        # Start monitoring
        self._start_monitoring()

        logger.info(f"DrawdownController initialized with config: {self.config.to_dict()}")

    def _register_default_handlers(self):
        """Register default action handlers."""
        self.register_action_handler(ActionType.NONE, self._handle_none)
        self.register_action_handler(ActionType.REDUCE_POSITION, self._handle_reduce_position)
        self.register_action_handler(ActionType.HALT_TRADING, self._handle_halt_trading)
        self.register_action_handler(ActionType.CLOSE_POSITIONS, self._handle_close_positions)
        self.register_action_handler(ActionType.LIQUIDATE, self._handle_liquidate)
        self.register_action_handler(ActionType.EMERGENCY_STOP, self._handle_emergency_stop)

    def register_action_handler(self, action_type: ActionType, handler: Callable):
        """
        Register an action handler.

        Args:
            action_type: Type of action
            handler: Handler function
        """
        self._action_handlers[action_type] = handler
        logger.info(f"Registered handler for action: {action_type.value}")

    def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler.

        Args:
            event_type: Type of event
            handler: Handler function
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)
            logger.info(f"Registered handler for event: {event_type}")

    def _start_monitoring(self):
        """Start the monitoring task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for monitoring drawdown."""
        while True:
            try:
                await self.check_drawdown()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def check_drawdown(
        self,
        portfolio_id: str = "default",
        current_value: Optional[float] = None,
    ) -> DrawdownState:
        """
        Check and update drawdown status.

        Args:
            portfolio_id: Portfolio identifier
            current_value: Current portfolio value

        Returns:
            Current drawdown state
        """
        async with self._lock:
            # Initialize state if not exists
            if portfolio_id not in self._state:
                self._state[portfolio_id] = DrawdownState()

            state = self._state[portfolio_id]
            state.last_check_time = datetime.utcnow()

            # Get current value
            if current_value is None and self.portfolio_manager:
                current_value = await self.portfolio_manager.get_portfolio_value(portfolio_id)

            if current_value is None:
                logger.warning(f"No current value available for portfolio {portfolio_id}")
                return state

            # Update current value
            state.current_value = current_value

            # Update peak value (high water mark)
            if state.use_high_water_mark:
                if current_value > state.peak_value:
                    state.peak_value = current_value

            # Calculate drawdown
            if state.peak_value > 0:
                drawdown = (state.peak_value - current_value) / state.peak_value
            else:
                drawdown = 0.0

            state.current_drawdown = drawdown

            # Update peak drawdown
            if drawdown > state.peak_drawdown:
                state.peak_drawdown = drawdown

            # Track drawdown history
            state.history.append(drawdown)
            if len(state.history) > self.config.min_history_points * 2:
                state.history = state.history[-self.config.min_history_points * 2:]

            # Determine drawdown level
            previous_level = state.drawdown_level
            state.drawdown_level = self._get_drawdown_level(drawdown)

            # Track drawdown duration
            if drawdown > 0:
                if state.drawdown_start_time is None:
                    state.drawdown_start_time = datetime.utcnow()
                    # Trigger event
                    await self._trigger_event("drawdown_started", portfolio_id, state)
            else:
                if state.drawdown_start_time is not None:
                    state.drawdown_end_time = datetime.utcnow()
                    duration = (state.drawdown_end_time - state.drawdown_start_time).total_seconds()
                    DRAWDOWN_DURATION.labels(portfolio=portfolio_id).observe(duration)
                    # Trigger event
                    await self._trigger_event("drawdown_recovered", portfolio_id, state)
                state.drawdown_start_time = None
                state.drawdown_end_time = None

            # Determine action
            action = self._get_action_for_level(state.drawdown_level)
            state.current_action = action

            # Update position reduction
            state.position_reduction = self._get_position_reduction(state.drawdown_level)

            # Execute action if changed
            if action != previous_level or state.active_actions:
                await self._execute_action(portfolio_id, state, action)

            # Update metrics
            DRAWDOWN_GAUGE.labels(portfolio=portfolio_id).set(drawdown * 100)
            DRAWDOWN_COUNTER.labels(
                level=state.drawdown_level.value,
                action=action.value,
            ).inc()

            # Check recovery
            await self._check_recovery(portfolio_id, state)

            return state

    def _get_drawdown_level(self, drawdown: float) -> DrawdownLevel:
        """
        Get drawdown level based on current drawdown.

        Args:
            drawdown: Current drawdown (0-1)

        Returns:
            Drawdown level
        """
        if drawdown >= self.config.extreme_threshold:
            return DrawdownLevel.EXTREME
        elif drawdown >= self.config.critical_threshold:
            return DrawdownLevel.CRITICAL
        elif drawdown >= self.config.severe_threshold:
            return DrawdownLevel.SEVERE
        elif drawdown >= self.config.elevated_threshold:
            return DrawdownLevel.ELEVATED
        elif drawdown >= self.config.warning_threshold:
            return DrawdownLevel.WARNING
        else:
            return DrawdownLevel.NORMAL

    def _get_action_for_level(self, level: DrawdownLevel) -> ActionType:
        """
        Get action for drawdown level.

        Args:
            level: Drawdown level

        Returns:
            Action to take
        """
        action_map = {
            DrawdownLevel.NORMAL: ActionType.NONE,
            DrawdownLevel.WARNING: self.config.warning_action,
            DrawdownLevel.ELEVATED: self.config.elevated_action,
            DrawdownLevel.SEVERE: self.config.severe_action,
            DrawdownLevel.CRITICAL: self.config.critical_action,
            DrawdownLevel.EXTREME: self.config.extreme_action,
        }
        return action_map.get(level, ActionType.NONE)

    def _get_position_reduction(self, level: DrawdownLevel) -> float:
        """
        Get position reduction percentage for drawdown level.

        Args:
            level: Drawdown level

        Returns:
            Position reduction (0-1)
        """
        reduction_map = {
            DrawdownLevel.NORMAL: 0.0,
            DrawdownLevel.WARNING: self.config.warning_reduction,
            DrawdownLevel.ELEVATED: self.config.elevated_reduction,
            DrawdownLevel.SEVERE: self.config.severe_reduction,
            DrawdownLevel.CRITICAL: self.config.critical_reduction,
            DrawdownLevel.EXTREME: self.config.extreme_reduction,
        }
        return reduction_map.get(level, 0.0)

    async def _execute_action(
        self,
        portfolio_id: str,
        state: DrawdownState,
        action: ActionType,
    ):
        """
        Execute drawdown action.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
            action: Action to execute
        """
        # Execute action
        if action != ActionType.NONE and action in self._action_handlers:
            try:
                handler = self._action_handlers[action]
                if asyncio.iscoroutinefunction(handler):
                    await handler(portfolio_id, state)
                else:
                    handler(portfolio_id, state)

                # Track active actions
                if action not in state.active_actions:
                    state.active_actions.append(action)

                # Trigger event
                await self._trigger_event("action_executed", portfolio_id, {
                    "action": action.value,
                    "drawdown": state.current_drawdown,
                    "level": state.drawdown_level.value,
                    "reduction": state.position_reduction,
                })

                logger.info(
                    f"Executed action {action.value} for portfolio {portfolio_id} "
                    f"(drawdown: {state.current_drawdown:.2%})"
                )

            except Exception as e:
                logger.error(f"Error executing action {action.value}: {e}")

    async def _check_recovery(self, portfolio_id: str, state: DrawdownState):
        """
        Check and handle recovery from drawdown.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if state.current_drawdown == 0:
            # Fully recovered
            if not state.recovery_threshold_reached:
                state.recovery_threshold_reached = True
                await self._trigger_event("full_recovery", portfolio_id, state)

        elif state.current_drawdown < self.config.recovery_threshold:
            # Recovery threshold reached
            if not state.recovery_threshold_reached:
                state.recovery_threshold_reached = True
                # Increase positions
                if self.config.recovery_action != ActionType.NONE:
                    await self._execute_action(portfolio_id, state, self.config.recovery_action)
                await self._trigger_event("recovery_threshold_reached", portfolio_id, state)

    async def _handle_none(self, portfolio_id: str, state: DrawdownState):
        """Handle NONE action."""
        # No action needed
        logger.debug(f"No action for portfolio {portfolio_id}")

    async def _handle_reduce_position(self, portfolio_id: str, state: DrawdownState):
        """
        Handle position reduction.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if self.portfolio_manager:
            reduction = state.position_reduction
            logger.info(f"Reducing positions by {reduction:.1%} for portfolio {portfolio_id}")

            try:
                await self.portfolio_manager.reduce_positions(
                    portfolio_id=portfolio_id,
                    reduction_percent=reduction,
                    allowed_symbols=self.config.allowed_symbols,
                )
            except Exception as e:
                logger.error(f"Error reducing positions: {e}")

    async def _handle_halt_trading(self, portfolio_id: str, state: DrawdownState):
        """
        Handle trading halt.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if self.portfolio_manager:
            logger.warning(f"Halting trading for portfolio {portfolio_id}")

            try:
                await self.portfolio_manager.halt_trading(portfolio_id)
            except Exception as e:
                logger.error(f"Error halting trading: {e}")

    async def _handle_close_positions(self, portfolio_id: str, state: DrawdownState):
        """
        Handle closing positions.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if self.portfolio_manager:
            logger.warning(f"Closing all positions for portfolio {portfolio_id}")

            try:
                await self.portfolio_manager.close_all_positions(portfolio_id)
            except Exception as e:
                logger.error(f"Error closing positions: {e}")

    async def _handle_liquidate(self, portfolio_id: str, state: DrawdownState):
        """
        Handle liquidation.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if self.portfolio_manager:
            logger.critical(f"Liquidating portfolio {portfolio_id}")

            try:
                await self.portfolio_manager.liquidate(portfolio_id)
            except Exception as e:
                logger.error(f"Error liquidating: {e}")

    async def _handle_emergency_stop(self, portfolio_id: str, state: DrawdownState):
        """
        Handle emergency stop.

        Args:
            portfolio_id: Portfolio identifier
            state: Current drawdown state
        """
        if self.portfolio_manager:
            logger.critical(f"EMERGENCY STOP for portfolio {portfolio_id}")

            try:
                await self.portfolio_manager.emergency_stop(portfolio_id)
            except Exception as e:
                logger.error(f"Error in emergency stop: {e}")

    async def _trigger_event(self, event_type: str, portfolio_id: str, data: Any):
        """
        Trigger event handlers.

        Args:
            event_type: Type of event
            portfolio_id: Portfolio identifier
            data: Event data
        """
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(portfolio_id, data)
                else:
                    handler(portfolio_id, data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    async def get_drawdown_state(
        self,
        portfolio_id: str = "default",
    ) -> Optional[DrawdownState]:
        """
        Get current drawdown state.

        Args:
            portfolio_id: Portfolio identifier

        Returns:
            Drawdown state or None
        """
        async with self._lock:
            return self._state.get(portfolio_id)

    async def get_drawdown_history(
        self,
        portfolio_id: str = "default",
        limit: int = 100,
    ) -> List[float]:
        """
        Get drawdown history.

        Args:
            portfolio_id: Portfolio identifier
            limit: Maximum number of points

        Returns:
            List of drawdown values
        """
        async with self._lock:
            state = self._state.get(portfolio_id)
            if state:
                return state.history[-limit:]
            return []

    async def get_drawdown_statistics(
        self,
        portfolio_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Get drawdown statistics.

        Args:
            portfolio_id: Portfolio identifier

        Returns:
            Drawdown statistics
        """
        async with self._lock:
            state = self._state.get(portfolio_id)

            if not state or not state.history:
                return {
                    "current_drawdown": 0.0,
                    "peak_drawdown": 0.0,
                    "drawdown_level": "unknown",
                    "drawdown_count": 0,
                    "avg_drawdown": 0.0,
                    "max_drawdown": 0.0,
                    "avg_drawdown_duration_seconds": 0.0,
                }

            # Count drawdown periods
            drawdown_periods = []
            in_drawdown = False
            start_idx = 0

            for i, dd in enumerate(state.history):
                if dd > 0 and not in_drawdown:
                    in_drawdown = True
                    start_idx = i
                elif dd == 0 and in_drawdown:
                    in_drawdown = False
                    drawdown_periods.append(i - start_idx)

            if in_drawdown:
                drawdown_periods.append(len(state.history) - start_idx)

            # Calculate statistics
            stats = {
                "current_drawdown": state.current_drawdown,
                "peak_drawdown": state.peak_drawdown,
                "drawdown_level": state.drawdown_level.value,
                "drawdown_count": len(drawdown_periods),
                "avg_drawdown": np.mean(state.history) if state.history else 0.0,
                "max_drawdown": np.max(state.history) if state.history else 0.0,
                "avg_drawdown_duration_seconds": np.mean(drawdown_periods) * self.config.check_interval_seconds if drawdown_periods else 0.0,
            }

            return stats

    async def reset_drawdown_state(self, portfolio_id: str = "default"):
        """
        Reset drawdown state.

        Args:
            portfolio_id: Portfolio identifier
        """
        async with self._lock:
            if portfolio_id in self._state:
                self._state[portfolio_id] = DrawdownState()
                logger.info(f"Reset drawdown state for portfolio {portfolio_id}")

    async def update_config(self, config: Union[DrawdownConfig, Dict[str, Any]]):
        """
        Update drawdown configuration.

        Args:
            config: New configuration
        """
        if isinstance(config, dict):
            self.config = DrawdownConfig.from_dict(config)
        else:
            self.config = config

        logger.info(f"Drawdown configuration updated: {self.config.to_dict()}")

    async def simulate_drawdown(
        self,
        portfolio_id: str,
        drawdown_scenario: List[float],
        initial_value: float = 100000.0,
    ) -> Dict[str, Any]:
        """
        Simulate drawdown scenario.

        Args:
            portfolio_id: Portfolio identifier
            drawdown_scenario: List of drawdown values
            initial_value: Initial portfolio value

        Returns:
            Simulation results
        """
        results = {
            "portfolio_id": portfolio_id,
            "initial_value": initial_value,
            "simulation": [],
            "actions_taken": [],
            "final_value": initial_value,
            "max_drawdown": 0.0,
        }

        current_value = initial_value
        peak_value = initial_value

        for i, dd in enumerate(drawdown_scenario):
            # Calculate value
            current_value = peak_value * (1 - dd)

            # Update peak
            if current_value > peak_value:
                peak_value = current_value

            # Check drawdown level
            level = self._get_drawdown_level(dd)
            action = self._get_action_for_level(level)

            # Record simulation point
            results["simulation"].append({
                "step": i,
                "drawdown": dd,
                "value": current_value,
                "level": level.value,
                "action": action.value,
            })

            # Record action
            if action != ActionType.NONE:
                results["actions_taken"].append({
                    "step": i,
                    "drawdown": dd,
                    "action": action.value,
                })

            # Update max drawdown
            if dd > results["max_drawdown"]:
                results["max_drawdown"] = dd

        results["final_value"] = current_value

        return results

    async def shutdown(self):
        """Shutdown the drawdown controller."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("DrawdownController shut down")


# Export singleton
drawdown_controller = DrawdownController()
