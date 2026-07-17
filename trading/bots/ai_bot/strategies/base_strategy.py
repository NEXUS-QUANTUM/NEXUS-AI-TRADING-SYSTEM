# trading/bots/ai_bot/strategies/base_strategy.py
# NEXUS AI TRADING SYSTEM - Base Trading Strategy Framework
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Base Trading Strategy Framework for NEXUS AI Trading Bot.
Provides the foundation for all trading strategies including:
- Strategy lifecycle management (start, stop, pause, resume)
- Signal generation and processing
- Risk management integration
- Performance tracking and metrics
- Configuration management
- Event handling and callbacks
- Logging and error handling
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# NEXUS Imports
from trading.bots.ai_bot.execution.order_manager import OrderManager
from trading.bots.ai_bot.risk.risk_manager import RiskManager
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy")


# ============================================================================
# Enums & Constants
# ============================================================================

class StrategyState(str, Enum):
    """Strategy states."""
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class StrategyType(str, Enum):
    """Strategy types."""
    TRENDING = "trending"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    SCALPING = "scalping"
    GRID = "grid"
    AI = "ai"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


class SignalType(str, Enum):
    """Signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


class SignalStrength(str, Enum):
    """Signal strength."""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    name: str
    type: StrategyType
    symbols: List[str]
    timeframe: str
    initial_capital: float
    max_position_size: float
    max_positions: int
    min_confidence: float = 0.6
    risk_per_trade: float = 0.02
    max_drawdown: float = 0.1
    use_stop_loss: bool = True
    use_take_profit: bool = True
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.04
    trailing_stop: bool = False
    trailing_stop_percent: float = 0.015
    min_volume: float = 1000.0
    min_spread: float = 0.0001
    max_slippage: float = 0.005
    execution_timeout_seconds: int = 30
    concurrent_executions: int = 1
    enable_logging: bool = True
    enable_metrics: bool = True
    enable_telemetry: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    type: SignalType
    strength: SignalStrength
    confidence: float
    price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    expiry_time: Optional[datetime] = None


@dataclass
class Position:
    """Trading position."""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "open"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyMetrics:
    """Strategy metrics."""
    name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    total_volume: float = 0.0
    total_fees: float = 0.0
    avg_trade_duration: float = 0.0
    avg_hold_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# Base Strategy Class
# ============================================================================

class BaseStrategy(ABC):
    """
    Base Trading Strategy Framework.
    Provides core functionality for all trading strategies.
    """

    def __init__(
        self,
        config: StrategyConfig,
        risk_manager: RiskManager,
        order_manager: OrderManager,
    ):
        """
        Initialize base strategy.

        Args:
            config: Strategy configuration
            risk_manager: Risk management instance
            order_manager: Order management instance
        """
        self.config = config
        self.risk_manager = risk_manager
        self.order_manager = order_manager

        # State management
        self._state = StrategyState.INITIALIZED
        self._running = False
        self._paused = False
        self._lock = asyncio.Lock()

        # Position tracking
        self._positions: Dict[str, Position] = {}
        self._order_history: List[Dict[str, Any]] = []
        self._trade_history: List[Dict[str, Any]] = []

        # Signal tracking
        self._signals: List[Signal] = []
        self._signal_history: List[Signal] = []
        self._active_signals: Dict[str, Signal] = {}

        # Performance metrics
        self._metrics = StrategyMetrics(name=config.name)
        self._performance: Dict[str, Any] = {}
        self._last_metrics_update = datetime.utcnow()

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "signal": [],
            "trade": [],
            "position": [],
            "error": [],
            "state_change": [],
        }

        # Monitoring
        self._last_heartbeat = datetime.utcnow()
        self._heartbeat_interval = 60  # seconds

        # Performance counters
        self._counter = {
            "signals_generated": 0,
            "signals_executed": 0,
            "trades_completed": 0,
            "errors": 0,
            "warnings": 0,
        }

        logger.info(
            f"Strategy initialized: {config.name}",
            extra={
                "type": config.type.value,
                "symbols": config.symbols,
                "timeframe": config.timeframe,
            }
        )

    # ========================================================================
    # Abstract Methods
    # ========================================================================

    @abstractmethod
    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze market data and generate signals.

        Returns:
            Analysis results including signals
        """
        pass

    @abstractmethod
    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """
        Execute a trading signal.

        Args:
            signal: Trading signal

        Returns:
            Execution results
        """
        pass

    # ========================================================================
    # Core Strategy Methods
    # ========================================================================

    async def run(self) -> None:
        """
        Main strategy loop.
        """
        while self._running:
            try:
                if self._paused:
                    await asyncio.sleep(1)
                    continue

                # Run analysis
                analysis = await self.analyze()

                # Process signals
                if analysis.get("signals"):
                    for signal in analysis["signals"]:
                        await self._process_signal(signal)

                # Update metrics
                await self._update_metrics()

                # Heartbeat
                await self._heartbeat()

                # Sleep based on timeframe
                await self._sleep_for_timeframe()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Strategy error: {e}")
                self._counter["errors"] += 1
                self._emit_event("error", {"error": str(e)})

                # Wait before retry
                await asyncio.sleep(5)

    async def _process_signal(self, signal: Signal) -> None:
        """
        Process a trading signal.

        Args:
            signal: Trading signal
        """
        try:
            self._counter["signals_generated"] += 1

            # Validate signal
            if not await self._validate_signal(signal):
                return

            # Check if symbol already has position
            if signal.symbol in self._positions:
                await self._handle_position_signal(signal)
                return

            # Check risk limits
            if not await self.risk_manager.check_order_limits(
                symbol=signal.symbol,
                side="buy" if signal.type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell",
                quantity=signal.quantity,
                price=signal.price,
            ):
                return

            # Execute signal
            result = await self.execute(signal)

            if result.get("success"):
                self._counter["signals_executed"] += 1

                # Store position if opened
                if result.get("position"):
                    self._positions[signal.symbol] = result["position"]

                # Store trade
                if result.get("trade"):
                    self._trade_history.append(result["trade"])

                self._emit_event("signal", {"signal": signal, "result": result})
            else:
                logger.warning(f"Signal execution failed: {result.get('error')}")
                self._emit_event("error", {"signal": signal, "error": result.get("error")})

        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            self._counter["errors"] += 1

    async def _validate_signal(self, signal: Signal) -> bool:
        """
        Validate a signal.

        Args:
            signal: Trading signal

        Returns:
            True if valid
        """
        # Check confidence
        if signal.confidence < self.config.min_confidence:
            logger.debug(f"Signal confidence too low: {signal.confidence}")
            return False

        # Check if expired
        if signal.expiry_time and signal.expiry_time < datetime.utcnow():
            logger.debug("Signal expired")
            return False

        # Check if already processed
        if signal.id in self._active_signals:
            logger.debug("Signal already processed")
            return False

        # Check symbol
        if signal.symbol not in self.config.symbols:
            logger.warning(f"Symbol not in config: {signal.symbol}")
            return False

        return True

    async def _handle_position_signal(self, signal: Signal) -> None:
        """
        Handle signal for a symbol with an existing position.

        Args:
            signal: Trading signal
        """
        position = self._positions.get(signal.symbol)
        if not position:
            return

        # Check if signal is for exit
        if signal.type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT, SignalType.STOP_LOSS]:
            await self._close_position(position)
            return

        # Check if signal is for taking profit
        if signal.type == SignalType.TAKE_PROFIT:
            if position.unrealized_pnl > 0:
                await self._take_profit(position)
            return

    async def _close_position(self, position: Position) -> Dict[str, Any]:
        """
        Close a position.

        Args:
            position: Position to close

        Returns:
            Close result
        """
        try:
            result = await self.order_manager.close_position(
                symbol=position.symbol,
                side=position.side,
                quantity=position.quantity,
            )

            if result.get("success"):
                position.status = "closed"
                self._counter["trades_completed"] += 1
                self._emit_event("position", {"position": position, "action": "close"})

            return result

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}

    async def _take_profit(self, position: Position) -> Dict[str, Any]:
        """
        Take profit on a position.

        Args:
            position: Position to take profit on

        Returns:
            Take profit result
        """
        # Calculate profit amount
        profit_amount = position.unrealized_pnl

        # Close partial or full position
        # For now, close full position
        return await self._close_position(position)

    async def _update_metrics(self) -> None:
        """
        Update strategy metrics.
        """
        now = datetime.utcnow()

        # Update metrics every minute
        if (now - self._last_metrics_update).seconds < 60:
            return

        # Calculate metrics
        trades = self._trade_history
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

        self._metrics.total_trades = len(trades)
        self._metrics.winning_trades = len(winning_trades)
        self._metrics.losing_trades = len(losing_trades)

        if self._metrics.total_trades > 0:
            self._metrics.win_rate = len(winning_trades) / len(trades)

            total_wins = sum(t.get("pnl", 0) for t in winning_trades)
            total_losses = abs(sum(t.get("pnl", 0) for t in losing_trades))

            if len(winning_trades) > 0:
                self._metrics.average_win = total_wins / len(winning_trades)

            if len(losing_trades) > 0:
                self._metrics.average_loss = total_losses / len(losing_trades)

            if total_losses > 0:
                self._metrics.profit_factor = total_wins / total_losses
            else:
                self._metrics.profit_factor = total_wins

            self._metrics.total_pnl = total_wins - total_losses

        self._last_metrics_update = now

    async def _heartbeat(self) -> None:
        """
        Send heartbeat.
        """
        now = datetime.utcnow()
        if (now - self._last_heartbeat).seconds >= self._heartbeat_interval:
            self._last_heartbeat = now
            self._emit_event("heartbeat", {
                "state": self._state.value,
                "positions": len(self._positions),
                "trades": len(self._trade_history),
                "signals": len(self._signals),
            })

    async def _sleep_for_timeframe(self) -> None:
        """
        Sleep based on the configured timeframe.
        """
        timeframe_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }

        sleep_seconds = timeframe_map.get(self.config.timeframe, 60)
        await asyncio.sleep(sleep_seconds)

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
    # State Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy."""
        if self._state in [StrategyState.RUNNING, StrategyState.STARTING]:
            return

        self._state = StrategyState.STARTING
        self._emit_event("state_change", {"state": self._state})

        try:
            await self._on_start()
            self._running = True
            self._state = StrategyState.RUNNING
            self._emit_event("state_change", {"state": self._state})

            # Run main loop
            await self.run()

        except Exception as e:
            logger.error(f"Error starting strategy: {e}")
            self._state = StrategyState.ERROR
            self._emit_event("error", {"error": str(e)})

    async def stop(self) -> None:
        """Stop the strategy."""
        if self._state in [StrategyState.STOPPING, StrategyState.STOPPED]:
            return

        self._state = StrategyState.STOPPING
        self._emit_event("state_change", {"state": self._state})

        try:
            self._running = False
            await self._on_stop()
            self._state = StrategyState.STOPPED
            self._emit_event("state_change", {"state": self._state})

        except Exception as e:
            logger.error(f"Error stopping strategy: {e}")
            self._state = StrategyState.ERROR
            self._emit_event("error", {"error": str(e)})

    async def pause(self) -> None:
        """Pause the strategy."""
        if self._state != StrategyState.RUNNING:
            return

        self._state = StrategyState.PAUSING
        self._emit_event("state_change", {"state": self._state})

        self._paused = True
        self._state = StrategyState.PAUSED
        self._emit_event("state_change", {"state": self._state})

    async def resume(self) -> None:
        """Resume the strategy."""
        if self._state != StrategyState.PAUSED:
            return

        self._paused = False
        self._state = StrategyState.RUNNING
        self._emit_event("state_change", {"state": self._state})

    # ========================================================================
    # Hook Methods
    # ========================================================================

    async def _on_start(self) -> None:
        """Called when strategy starts."""
        pass

    async def _on_stop(self) -> None:
        """Called when strategy stops."""
        pass

    async def _on_pause(self) -> None:
        """Called when strategy pauses."""
        pass

    async def _on_resume(self) -> None:
        """Called when strategy resumes."""
        pass

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_state(self) -> StrategyState:
        """Get current strategy state."""
        return self._state

    def get_metrics(self) -> StrategyMetrics:
        """Get strategy metrics."""
        return self._metrics

    def get_performance(self) -> Dict[str, Any]:
        """Get performance data."""
        return {
            "metrics": self._metrics.__dict__,
            "positions": len(self._positions),
            "trades": len(self._trade_history),
            "signals": len(self._signals),
            "counters": self._counter,
            "state": self._state.value,
            "uptime": (datetime.utcnow() - self._last_heartbeat).seconds,
        }

    def get_positions(self) -> Dict[str, Position]:
        """Get current positions."""
        return self._positions

    def get_signals(self) -> List[Signal]:
        """Get recent signals."""
        return self._signals[-100:]

    def get_trades(self) -> List[Dict[str, Any]]:
        """Get trade history."""
        return self._trade_history

    def _calculate_position_size(self, price: float) -> float:
        """
        Calculate position size based on risk.

        Args:
            price: Entry price

        Returns:
            Position size
        """
        risk_amount = self.config.initial_capital * self.config.risk_per_trade
        stop_loss_amount = price * self.config.stop_loss_percent

        if stop_loss_amount > 0:
            return risk_amount / stop_loss_amount

        return self.config.max_position_size

    def _generate_signal_id(self) -> str:
        """
        Generate a unique signal ID.

        Returns:
            Signal ID
        """
        return f"sig_{int(time.time() * 1000)}_{self._counter['signals_generated']}"

    def _log(self, level: str, message: str, **kwargs) -> None:
        """
        Log a message.

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional log data
        """
        if not self.config.enable_logging:
            return

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{self.config.name}] {message}", extra=kwargs)


# ============================================================================
# Factory Function
# ============================================================================

def create_base_strategy(
    config: StrategyConfig,
    risk_manager: RiskManager,
    order_manager: OrderManager,
) -> BaseStrategy:
    """
    Factory function to create a BaseStrategy instance.
    This should be overridden by specific strategy factories.

    Args:
        config: Strategy configuration
        risk_manager: Risk management instance
        order_manager: Order management instance

    Returns:
        BaseStrategy instance
    """
    # This is a placeholder - should be implemented by specific strategies
    raise NotImplementedError("Use specific strategy factory")


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the base strategy
    pass
