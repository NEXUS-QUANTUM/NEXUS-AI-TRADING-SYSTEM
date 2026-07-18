# trading/risk-management/drawdown_controller.py
"""
NEXUS AI TRADING SYSTEM - Drawdown Controller
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements drawdown control mechanisms to protect
trading capital from excessive losses. It monitors equity drawdowns
and takes corrective actions when drawdown thresholds are exceeded.

Key Features:
- Maximum drawdown monitoring
- Daily drawdown limits
- Position-level drawdown control
- Progressive position reduction
- Auto-recovery mechanisms
- Alerting and logging
- Performance tracking
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import deque, defaultdict

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import Position, Trade, MarketData
from shared.types.portfolio import Portfolio

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class DrawdownLevel(str, Enum):
    """Drawdown severity levels"""
    NORMAL = "normal"              # No action needed
    WARNING = "warning"            # Monitor closely
    REDUCE = "reduce"              # Reduce position sizes
    HALT = "halt"                  # Stop new trades
    EMERGENCY = "emergency"        # Close all positions
    RECOVERING = "recovering"      # Recovery mode


class DrawdownAction(str, Enum):
    """Actions to take on drawdown"""
    NONE = "none"
    MONITOR = "monitor"
    REDUCE_POSITIONS = "reduce_positions"
    HALT_TRADING = "halt_trading"
    CLOSE_POSITIONS = "close_positions"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    REBALANCE = "rebalance"


@dataclass
class DrawdownConfig:
    """Configuration for drawdown control"""
    # Maximum drawdown limits
    max_drawdown_pct: float = 0.10  # 10%
    max_daily_drawdown_pct: float = 0.05  # 5%
    max_position_drawdown_pct: float = 0.03  # 3%
    max_monthly_drawdown_pct: float = 0.15  # 15%
    
    # Action thresholds
    warning_threshold: float = 0.5  # 50% of max
    reduce_threshold: float = 0.7  # 70% of max
    halt_threshold: float = 0.85  # 85% of max
    emergency_threshold: float = 0.95  # 95% of max
    
    # Position reduction factors
    reduction_factor_warning: float = 0.8
    reduction_factor_reduce: float = 0.5
    reduction_factor_halt: float = 0.1
    
    # Recovery parameters
    recovery_threshold: float = 0.3  # 30% of max
    recovery_increment: float = 0.1  # 10% per step
    recovery_interval: int = 60  # seconds
    auto_recovery: bool = True
    
    # Position closure
    close_positions_on_emergency: bool = True
    close_orders_on_emergency: bool = True
    close_partial_on_reduce: bool = False
    partial_close_pct: float = 0.5  # 50% of position
    
    # Monitoring
    monitor_interval: int = 10  # seconds
    track_daily: bool = True
    track_monthly: bool = True
    track_per_position: bool = True
    
    # Alerts
    enable_alerts: bool = True
    alert_cooldown: int = 300  # seconds


@dataclass
class DrawdownMetrics:
    """Drawdown metrics"""
    current_drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    max_drawdown_pct: float = 0.0
    drawdown_duration: float = 0.0  # seconds
    
    daily_drawdown_pct: float = 0.0
    daily_peak_equity: float = 0.0
    daily_start_equity: float = 0.0
    
    monthly_drawdown_pct: float = 0.0
    monthly_peak_equity: float = 0.0
    
    position_drawdowns: Dict[str, float] = field(default_factory=dict)
    recovery_progress: float = 0.0
    is_in_recovery: bool = False
    
    level: DrawdownLevel = DrawdownLevel.NORMAL
    action_taken: DrawdownAction = DrawdownAction.NONE
    last_action_time: Optional[datetime] = None
    last_alert_time: Optional[datetime] = None


# ============================================================================
# DRAWDOWN CONTROLLER
# ============================================================================

class DrawdownController:
    """
    Controls and monitors drawdown to protect trading capital.
    
    Features:
    - Multiple drawdown thresholds
    - Progressive actions
    - Position reduction
    - Auto-recovery
    - Alerting
    - Performance tracking
    """
    
    def __init__(
        self,
        config: Optional[DrawdownConfig] = None,
        initial_equity: float = 100000.0,
    ):
        """
        Initialize the drawdown controller.
        
        Args:
            config: Drawdown configuration
            initial_equity: Initial equity value
        """
        self.config = config or DrawdownConfig()
        self.metrics = DrawdownMetrics()
        
        # Equity tracking
        self._equity_history: List[float] = [initial_equity]
        self._daily_equity: List[float] = [initial_equity]
        self._monthly_equity: Dict[str, List[float]] = defaultdict(list)
        self._position_entries: Dict[str, float] = {}
        
        # Performance tracking
        self._performance_history: deque = deque(maxlen=1000)
        self._drawdown_events: List[Dict[str, Any]] = []
        
        # State
        self._is_initialized = False
        self._last_check_time = datetime.utcnow()
        self._current_date = datetime.utcnow().date()
        self._current_month = datetime.utcnow().strftime("%Y-%m")
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_drawdown_callbacks: List[Callable[[DrawdownLevel, Dict[str, Any]], Awaitable[None]]] = []
        self._on_action_callbacks: List[Callable[[DrawdownAction, Dict[str, Any]], Awaitable[None]]] = []
        self._on_recovery_callbacks: List[Callable[[float], Awaitable[None]]] = []
        
        # Initialize metrics
        self._update_metrics(initial_equity)
        
        self.logger = logger
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_drawdown(
        self,
        callback: Callable[[DrawdownLevel, Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register callback for drawdown events."""
        self._on_drawdown_callbacks.append(callback)
    
    def on_action(
        self,
        callback: Callable[[DrawdownAction, Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register callback for action events."""
        self._on_action_callbacks.append(callback)
    
    def on_recovery(
        self,
        callback: Callable[[float], Awaitable[None]],
    ) -> None:
        """Register callback for recovery events."""
        self._on_recovery_callbacks.append(callback)
    
    async def _trigger_drawdown_callbacks(self, level: DrawdownLevel, data: Dict[str, Any]) -> None:
        """Trigger drawdown callbacks."""
        for callback in self._on_drawdown_callbacks:
            try:
                await callback(level, data)
            except Exception as e:
                self.logger.error(f"Error in drawdown callback: {e}")
    
    async def _trigger_action_callbacks(self, action: DrawdownAction, data: Dict[str, Any]) -> None:
        """Trigger action callbacks."""
        for callback in self._on_action_callbacks:
            try:
                await callback(action, data)
            except Exception as e:
                self.logger.error(f"Error in action callback: {e}")
    
    async def _trigger_recovery_callbacks(self, progress: float) -> None:
        """Trigger recovery callbacks."""
        for callback in self._on_recovery_callbacks:
            try:
                await callback(progress)
            except Exception as e:
                self.logger.error(f"Error in recovery callback: {e}")
    
    # ========================================================================
    # CORE OPERATIONS
    # ========================================================================
    
    async def update_equity(self, equity: float) -> DrawdownLevel:
        """
        Update current equity and check drawdown.
        
        Args:
            equity: Current equity value
            
        Returns:
            DrawdownLevel: Current drawdown level
        """
        async with self._lock:
            self._equity_history.append(equity)
            
            # Update daily tracking
            if self.config.track_daily:
                today = datetime.utcnow().date()
                if today != self._current_date:
                    self._current_date = today
                    self._daily_equity = [equity]
                    self.metrics.daily_peak_equity = equity
                    self.metrics.daily_start_equity = equity
                    self.metrics.daily_drawdown_pct = 0.0
                else:
                    self._daily_equity.append(equity)
            
            # Update monthly tracking
            if self.config.track_monthly:
                month = datetime.utcnow().strftime("%Y-%m")
                if month != self._current_month:
                    self._current_month = month
                    self._monthly_equity[month] = [equity]
                    self.metrics.monthly_peak_equity = equity
                    self.metrics.monthly_drawdown_pct = 0.0
                else:
                    self._monthly_equity[month].append(equity)
            
            # Update metrics
            self._update_metrics(equity)
            
            # Check drawdown
            level, action = await self._check_drawdown(equity)
            
            # Check for recovery
            if self.metrics.is_in_recovery:
                await self._check_recovery(equity)
            
            self._last_check_time = datetime.utcnow()
            
            return level
    
    async def update_position(self, position: Position) -> None:
        """
        Update position tracking for drawdown.
        
        Args:
            position: Position to update
        """
        async with self._lock:
            if not self.config.track_per_position:
                return
            
            symbol = position.symbol
            
            # Track entry price for drawdown calculation
            if symbol not in self._position_entries:
                self._position_entries[symbol] = position.entry_price
            
            # Calculate position drawdown
            if position.entry_price > 0:
                pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100
                if position.side == OrderSide.SELL:
                    pnl_pct = -pnl_pct
                
                # Update metrics
                if pnl_pct < 0:
                    self.metrics.position_drawdowns[symbol] = abs(pnl_pct)
                else:
                    self.metrics.position_drawdowns.pop(symbol, None)
    
    def _update_metrics(self, equity: float) -> None:
        """
        Update drawdown metrics.
        
        Args:
            equity: Current equity
        """
        # Peak equity
        if not self.metrics.peak_equity or equity > self.metrics.peak_equity:
            self.metrics.peak_equity = equity
        
        # Current equity
        self.metrics.current_equity = equity
        
        # Current drawdown
        if self.metrics.peak_equity > 0:
            self.metrics.current_drawdown_pct = (
                (self.metrics.peak_equity - equity) / self.metrics.peak_equity
            )
        
        # Max drawdown
        if self.metrics.current_drawdown_pct > self.metrics.max_drawdown_pct:
            self.metrics.max_drawdown_pct = self.metrics.current_drawdown_pct
        
        # Drawdown duration
        if self.metrics.current_drawdown_pct > 0:
            if not self.metrics.drawdown_duration:
                self.metrics.drawdown_duration = 0
            self.metrics.drawdown_duration += (
                datetime.utcnow() - self._last_check_time
            ).total_seconds()
        else:
            self.metrics.drawdown_duration = 0
        
        # Daily drawdown
        if self.config.track_daily and self._daily_equity:
            if not self.metrics.daily_peak_equity:
                self.metrics.daily_peak_equity = max(self._daily_equity)
            if not self.metrics.daily_start_equity:
                self.metrics.daily_start_equity = self._daily_equity[0]
            
            if self.metrics.daily_peak_equity > 0:
                self.metrics.daily_drawdown_pct = (
                    (self.metrics.daily_peak_equity - equity) / self.metrics.daily_peak_equity
                )
        
        # Monthly drawdown
        if self.config.track_monthly and self._monthly_equity.get(self._current_month):
            month_data = self._monthly_equity[self._current_month]
            peak = max(month_data) if month_data else equity
            if peak > 0:
                self.metrics.monthly_drawdown_pct = (peak - equity) / peak
    
    async def _check_drawdown(self, equity: float) -> Tuple[DrawdownLevel, DrawdownAction]:
        """
        Check drawdown and determine action.
        
        Args:
            equity: Current equity
            
        Returns:
            Tuple[DrawdownLevel, DrawdownAction]: Drawdown level and action
        """
        # Calculate thresholds
        max_dd = self.config.max_drawdown_pct
        current_dd = self.metrics.current_drawdown_pct
        
        # Determine level
        if current_dd <= 0:
            level = DrawdownLevel.NORMAL
            action = DrawdownAction.NONE
        elif current_dd >= max_dd * self.config.emergency_threshold:
            level = DrawdownLevel.EMERGENCY
            action = DrawdownAction.EMERGENCY_SHUTDOWN
        elif current_dd >= max_dd * self.config.halt_threshold:
            level = DrawdownLevel.HALT
            action = DrawdownAction.HALT_TRADING
        elif current_dd >= max_dd * self.config.reduce_threshold:
            level = DrawdownLevel.REDUCE
            action = DrawdownAction.REDUCE_POSITIONS
        elif current_dd >= max_dd * self.config.warning_threshold:
            level = DrawdownLevel.WARNING
            action = DrawdownAction.MONITOR
        else:
            level = DrawdownLevel.NORMAL
            action = DrawdownAction.NONE
        
        # Update metrics
        self.metrics.level = level
        self.metrics.action_taken = action
        
        # Log and trigger callbacks
        if level != DrawdownLevel.NORMAL:
            data = {
                "equity": equity,
                "drawdown_pct": current_dd,
                "max_drawdown_pct": max_dd,
                "level": level.value,
                "action": action.value,
            }
            
            await self._trigger_drawdown_callbacks(level, data)
            await self._trigger_action_callbacks(action, data)
            
            self._drawdown_events.append({
                "timestamp": datetime.utcnow(),
                "level": level.value,
                "action": action.value,
                "drawdown_pct": current_dd,
                "equity": equity,
            })
        
        return level, action
    
    async def _check_recovery(self, equity: float) -> None:
        """
        Check if recovery is possible.
        
        Args:
            equity: Current equity
        """
        if not self.config.auto_recovery:
            return
        
        max_dd = self.config.max_drawdown_pct
        current_dd = self.metrics.current_drawdown_pct
        
        # Recovery threshold
        if current_dd <= max_dd * self.config.recovery_threshold:
            # Start recovery
            self.metrics.is_in_recovery = True
            self.metrics.recovery_progress = 0.0
            
            await self._trigger_recovery_callbacks(0.0)
            
            self.logger.info("Drawdown recovery initiated")
        
        # Progress recovery
        if self.metrics.is_in_recovery:
            # Calculate progress
            target = max_dd * self.config.recovery_threshold
            if target > 0:
                progress = 1 - (current_dd / target)
                self.metrics.recovery_progress = min(1.0, max(0.0, progress))
                
                if progress >= 1.0:
                    # Full recovery
                    self.metrics.is_in_recovery = False
                    self.metrics.recovery_progress = 1.0
                    
                    await self._trigger_recovery_callbacks(1.0)
                    
                    self.logger.info("Drawdown fully recovered")
                elif progress % self.config.recovery_increment < 0.01:
                    # Incremental recovery
                    await self._trigger_recovery_callbacks(progress)
    
    # ========================================================================
    # POSITION SIZING ADJUSTMENTS
    # ========================================================================
    
    def get_position_size_multiplier(self) -> float:
        """
        Get position size multiplier based on current drawdown.
        
        Returns:
            float: Position size multiplier (0-1)
        """
        level = self.metrics.level
        
        if level == DrawdownLevel.NORMAL:
            return 1.0
        elif level == DrawdownLevel.WARNING:
            return self.config.reduction_factor_warning
        elif level == DrawdownLevel.REDUCE:
            return self.config.reduction_factor_reduce
        elif level == DrawdownLevel.HALT:
            return self.config.reduction_factor_halt
        elif level == DrawdownLevel.EMERGENCY:
            return 0.0
        elif level == DrawdownLevel.RECOVERING:
            # Gradual increase during recovery
            progress = self.metrics.recovery_progress
            return 0.5 + 0.5 * progress
        
        return 1.0
    
    def get_max_position_size(self, base_max: float) -> float:
        """
        Get adjusted max position size.
        
        Args:
            base_max: Base maximum position size
            
        Returns:
            float: Adjusted max position size
        """
        multiplier = self.get_position_size_multiplier()
        return base_max * multiplier
    
    def should_allow_new_trades(self) -> bool:
        """
        Check if new trades should be allowed.
        
        Returns:
            bool: True if new trades allowed
        """
        level = self.metrics.level
        return level not in [DrawdownLevel.HALT, DrawdownLevel.EMERGENCY]
    
    def should_close_positions(self) -> bool:
        """
        Check if positions should be closed.
        
        Returns:
            bool: True if positions should be closed
        """
        return self.metrics.level == DrawdownLevel.EMERGENCY
    
    def should_reduce_positions(self) -> bool:
        """
        Check if positions should be reduced.
        
        Returns:
            bool: True if positions should be reduced
        """
        return self.metrics.level in [DrawdownLevel.REDUCE, DrawdownLevel.HALT]
    
    # ========================================================================
    # POSITION CLOSURE HELPERS
    # ========================================================================
    
    def get_positions_to_close(self, positions: List[Position]) -> List[Position]:
        """
        Get positions that should be closed.
        
        Args:
            positions: Current positions
            
        Returns:
            List[Position]: Positions to close
        """
        if not self.should_close_positions():
            return []
        
        if self.config.close_positions_on_emergency:
            return positions
        
        return []
    
    def get_positions_to_reduce(self, positions: List[Position]) -> List[Tuple[Position, float]]:
        """
        Get positions to reduce and their target sizes.
        
        Args:
            positions: Current positions
            
        Returns:
            List[Tuple[Position, float]]: (Position, target_quantity)
        """
        if not self.should_reduce_positions():
            return []
        
        if not self.config.close_partial_on_reduce:
            return []
        
        reductions = []
        pct = self.config.partial_close_pct
        
        for position in positions:
            target_quantity = position.quantity * (1 - pct)
            reductions.append((position, target_quantity))
        
        return reductions
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current drawdown metrics.
        
        Returns:
            Dict[str, Any]: Metrics
        """
        return {
            "current_equity": self.metrics.current_equity,
            "peak_equity": self.metrics.peak_equity,
            "current_drawdown_pct": self.metrics.current_drawdown_pct,
            "max_drawdown_pct": self.metrics.max_drawdown_pct,
            "drawdown_duration": self.metrics.drawdown_duration,
            "daily_drawdown_pct": self.metrics.daily_drawdown_pct,
            "monthly_drawdown_pct": self.metrics.monthly_drawdown_pct,
            "level": self.metrics.level.value,
            "action": self.metrics.action_taken.value,
            "is_in_recovery": self.metrics.is_in_recovery,
            "recovery_progress": self.metrics.recovery_progress,
            "position_drawdowns": self.metrics.position_drawdowns,
            "position_size_multiplier": self.get_position_size_multiplier(),
            "allow_new_trades": self.should_allow_new_trades(),
            "should_close_positions": self.should_close_positions(),
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get drawdown summary.
        
        Returns:
            Dict[str, Any]: Summary
        """
        return {
            "current_drawdown": self.metrics.current_drawdown_pct,
            "max_drawdown": self.metrics.max_drawdown_pct,
            "level": self.metrics.level.value,
            "action": self.metrics.action_taken.value,
            "equity": {
                "current": self.metrics.current_equity,
                "peak": self.metrics.peak_equity,
            },
            "recovery": {
                "in_progress": self.metrics.is_in_recovery,
                "progress": self.metrics.recovery_progress,
            },
            "limits": {
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "warning_threshold": self.config.warning_threshold,
                "reduce_threshold": self.config.reduce_threshold,
                "halt_threshold": self.config.halt_threshold,
                "emergency_threshold": self.config.emergency_threshold,
            },
            "events": len(self._drawdown_events),
        }
    
    def get_position_multipliers(self) -> Dict[str, float]:
        """
        Get position size multipliers for each position.
        
        Returns:
            Dict[str, float]: Position multipliers
        """
        multipliers = {}
        for symbol, drawdown in self.metrics.position_drawdowns.items():
            if drawdown > self.config.max_position_drawdown_pct:
                # Reduce position size based on position drawdown
                ratio = self.config.max_position_drawdown_pct / drawdown
                multipliers[symbol] = min(1.0, ratio)
            else:
                multipliers[symbol] = 1.0
        
        return multipliers
    
    # ========================================================================
    # RESET AND CLEANUP
    # ========================================================================
    
    async def reset(self) -> None:
        """Reset drawdown controller state."""
        async with self._lock:
            self.metrics = DrawdownMetrics()
            self._equity_history = [self.metrics.current_equity or 100000.0]
            self._daily_equity = [self.metrics.current_equity or 100000.0]
            self._monthly_equity.clear()
            self._position_entries.clear()
            self._drawdown_events.clear()
            self._is_initialized = False
            self._last_check_time = datetime.utcnow()
            self._current_date = datetime.utcnow().date()
            self._current_month = datetime.utcnow().strftime("%Y-%m")
            
            self.logger.info("Drawdown controller reset")
    
    def get_equity_history(self, limit: int = 100) -> List[float]:
        """
        Get equity history.
        
        Args:
            limit: Maximum number of entries
            
        Returns:
            List[float]: Equity history
        """
        if limit > 0:
            return self._equity_history[-limit:]
        return self._equity_history
    
    def get_drawdown_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get drawdown events.
        
        Args:
            limit: Maximum number of events
            
        Returns:
            List[Dict[str, Any]]: Drawdown events
        """
        if limit > 0:
            return self._drawdown_events[-limit:]
        return self._drawdown_events


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "DrawdownLevel",
    "DrawdownAction",
    
    # Models
    "DrawdownConfig",
    "DrawdownMetrics",
    
    # Controller
    "DrawdownController",
]
