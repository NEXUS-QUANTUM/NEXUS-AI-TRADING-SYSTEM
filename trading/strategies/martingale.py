# trading/strategies/martingale.py
"""
NEXUS AI TRADING SYSTEM - Martingale Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements Martingale-based trading strategies including:
- Classic Martingale (double on loss)
- Anti-Martingale (increase on win)
- Fibonacci Martingale
- D'Alembert Martingale
- Kelly Criterion hybrid
- Risk-managed Martingale

The Martingale strategy is a progressive betting system that increases
position size after losses to recover previous losses with a single win.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import deque

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade, MarketData
from .base import BaseStrategy, StrategyConfig, Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class MartingaleType(str, Enum):
    """Types of Martingale strategies"""
    CLASSIC = "classic"              # Double on loss
    ANTI = "anti"                    # Increase on win
    FIBONACCI = "fibonacci"          # Fibonacci sequence progression
    D_ALEMBERT = "dalembert"         # Increment/decrement by 1 unit
    KELLY = "kelly"                  # Kelly Criterion-based sizing
    HYBRID = "hybrid"                # Combination of methods
    RISK_MANAGED = "risk_managed"    # Risk-limited progression


class MartingaleDirection(str, Enum):
    """Direction for Martingale"""
    LONG = "long"        # Only long positions
    SHORT = "short"      # Only short positions
    BOTH = "both"        # Both directions


@dataclass
class MartingaleConfig:
    """Configuration for Martingale strategy"""
    # Strategy type
    martingale_type: MartingaleType = MartingaleType.CLASSIC
    direction: MartingaleDirection = MartingaleDirection.BOTH
    
    # Base parameters
    base_position_size: float = 100.0
    min_position_size: float = 10.0
    max_position_size: float = 10000.0
    max_steps: int = 5
    
    # Progression parameters
    multiplier: float = 2.0  # For classic martingale
    increment_unit: float = 1.0  # For D'Alembert
    fibonacci_start: Tuple[int, int] = (1, 1)  # For Fibonacci
    
    # Risk management
    max_loss_per_trade: float = 1000.0
    max_consecutive_losses: int = 5
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_drawdown_pct: float = 0.10
    
    # Entry/Exit
    entry_conditions: List[str] = field(default_factory=list)
    exit_conditions: List[str] = field(default_factory=list)
    require_previous_loss: bool = True
    cooldown_after_win: int = 0  # seconds
    
    # Execution
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.GTC
    slippage_tolerance: float = 0.005


@dataclass
class MartingaleState:
    """Current state of the Martingale strategy"""
    symbol: str
    direction: MartingaleDirection
    current_step: int = 0
    current_position_size: float = 0.0
    base_position_size: float = 0.0
    
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_losses: int = 0
    total_wins: int = 0
    
    current_loss_streak: float = 0.0  # Total loss amount in current streak
    recovered: bool = False
    
    last_trade_result: Optional[float] = None
    last_trade_time: Optional[datetime] = None
    
    fibonacci_prev: int = 0
    fibonacci_curr: int = 1
    
    dalembert_counter: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# MARTINGALE STRATEGY
# ============================================================================

class MartingaleStrategy(BaseStrategy):
    """
    Martingale trading strategy with progressive position sizing.
    
    Increases position size after losses to recover previous losses
    with a single winning trade.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        martingale_config: Optional[MartingaleConfig] = None,
    ):
        """
        Initialize the Martingale strategy.
        
        Args:
            config: Strategy configuration
            martingale_config: Martingale-specific configuration
        """
        super().__init__(config)
        self.martingale_config = martingale_config or MartingaleConfig()
        
        # State management
        self._states: Dict[str, MartingaleState] = {}
        self._current_state: Optional[MartingaleState] = None
        
        # Trade history for this strategy
        self._trade_history: List[Trade] = []
        self._loss_streak_history: List[float] = []
        
        # Performance tracking
        self._martingale_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "streak_break_count": 0,
            "max_streak_reached": 0,
            "avg_position_size": 0.0,
            "max_position_used": 0.0,
            "recovery_rate": 0.0,
            "total_loss_streaks": 0,
            "successful_recoveries": 0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Cooldown tracking
        self._cooldown_until: Optional[datetime] = None
        
        self.logger = logger
    
    # ========================================================================
    # MARTINGALE CALCULATIONS
    # ========================================================================
    
    def calculate_next_position_size(
        self,
        state: MartingaleState,
        last_trade_pnl: Optional[float] = None,
        is_winning: Optional[bool] = None,
    ) -> float:
        """
        Calculate the next position size based on Martingale logic.
        
        Args:
            state: Current Martingale state
            last_trade_pnl: P&L of the last trade
            is_winning: Whether the last trade was winning
            
        Returns:
            float: Next position size
        """
        martingale_type = self.martingale_config.martingale_type
        
        # If no trade result, use base size
        if last_trade_pnl is None:
            return self.martingale_config.base_position_size
        
        # Determine if trade was winning
        if is_winning is None:
            is_winning = last_trade_pnl > 0
        
        # Classic Martingale
        if martingale_type == MartingaleType.CLASSIC:
            if is_winning:
                # Reset to base on win
                state.current_step = 0
                state.current_loss_streak = 0.0
                return self.martingale_config.base_position_size
            else:
                # Double on loss
                state.current_step += 1
                state.current_loss_streak += abs(last_trade_pnl)
                size = self.martingale_config.base_position_size * (2 ** state.current_step)
                return min(size, self.martingale_config.max_position_size)
        
        # Anti-Martingale
        elif martingale_type == MartingaleType.ANTI:
            if is_winning:
                # Increase on win
                state.current_step += 1
                size = self.martingale_config.base_position_size * (self.martingale_config.multiplier ** state.current_step)
                return min(size, self.martingale_config.max_position_size)
            else:
                # Reset on loss
                state.current_step = 0
                return self.martingale_config.base_position_size
        
        # Fibonacci Martingale
        elif martingale_type == MartingaleType.FIBONACCI:
            if is_winning:
                # Reset Fibonacci sequence on win
                state.fibonacci_prev = 0
                state.fibonacci_curr = 1
                state.current_step = 0
                return self.martingale_config.base_position_size
            else:
                # Move to next Fibonacci number on loss
                next_fib = state.fibonacci_prev + state.fibonacci_curr
                state.fibonacci_prev = state.fibonacci_curr
                state.fibonacci_curr = next_fib
                state.current_step += 1
                size = self.martingale_config.base_position_size * next_fib
                return min(size, self.martingale_config.max_position_size)
        
        # D'Alembert Martingale
        elif martingale_type == MartingaleType.D_ALEMBERT:
            if is_winning:
                # Decrease by 1 unit on win
                state.dalembert_counter -= 1
                state.dalembert_counter = max(0, state.dalembert_counter)
                size = self.martingale_config.base_position_size * (1 + state.dalembert_counter * self.martingale_config.increment_unit)
                return min(size, self.martingale_config.max_position_size)
            else:
                # Increase by 1 unit on loss
                state.dalembert_counter += 1
                size = self.martingale_config.base_position_size * (1 + state.dalembert_counter * self.martingale_config.increment_unit)
                return min(size, self.martingale_config.max_position_size)
        
        # Kelly Criterion hybrid
        elif martingale_type == MartingaleType.KELLY:
            # Calculate Kelly fraction based on historical performance
            win_rate = self._calculate_win_rate()
            avg_win = self._calculate_avg_win()
            avg_loss = self._calculate_avg_loss()
            
            kelly_fraction = self._calculate_kelly(win_rate, avg_win, avg_loss)
            
            if is_winning:
                # Reduce size on win (anti-Martingale effect)
                size = self.martingale_config.base_position_size * (1 - kelly_fraction * 0.5)
                return max(size, self.martingale_config.min_position_size)
            else:
                # Increase size on loss (Martingale effect)
                size = self.martingale_config.base_position_size * (1 + kelly_fraction)
                return min(size, self.martingale_config.max_position_size)
        
        # Risk-managed Martingale
        elif martingale_type == MartingaleType.RISK_MANAGED:
            if not is_winning:
                # Progressive increase with risk limits
                state.current_step += 1
                # Use smaller multiplier for risk management
                multiplier = 1 + (self.martingale_config.multiplier - 1) / 2
                size = self.martingale_config.base_position_size * (multiplier ** state.current_step)
                size = min(size, self.martingale_config.max_position_size)
                
                # Check if size exceeds risk limits
                if state.current_loss_streak + size > self.martingale_config.max_loss_per_trade:
                    # Reset to base if risk limit exceeded
                    self.logger.warning("Risk limit exceeded, resetting position size")
                    state.current_step = 0
                    return self.martingale_config.base_position_size
                
                return size
            else:
                # Reset on win
                state.current_step = 0
                state.current_loss_streak = 0.0
                return self.martingale_config.base_position_size
        
        # Hybrid Martingale
        elif martingale_type == MartingaleType.HYBRID:
            # Combine multiple methods
            if is_winning:
                # Reset on win
                state.current_step = 0
                state.fibonacci_prev = 0
                state.fibonacci_curr = 1
                state.dalembert_counter = 0
                return self.martingale_config.base_position_size
            else:
                # Use Fibonacci progression with multiplier cap
                next_fib = state.fibonacci_prev + state.fibonacci_curr
                state.fibonacci_prev = state.fibonacci_curr
                state.fibonacci_curr = next_fib
                state.current_step += 1
                
                # Cap multiplier
                multiplier = min(next_fib, 5)
                size = self.martingale_config.base_position_size * multiplier
                return min(size, self.martingale_config.max_position_size)
        
        # Default: classic Martingale
        else:
            if is_winning:
                state.current_step = 0
                return self.martingale_config.base_position_size
            else:
                state.current_step += 1
                size = self.martingale_config.base_position_size * (2 ** state.current_step)
                return min(size, self.martingale_config.max_position_size)
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate from trade history."""
        if not self._trade_history:
            return 0.5
        
        wins = sum(1 for t in self._trade_history if (t.pnl or 0) > 0)
        return wins / len(self._trade_history)
    
    def _calculate_avg_win(self) -> float:
        """Calculate average winning trade."""
        wins = [t.pnl for t in self._trade_history if (t.pnl or 0) > 0]
        if not wins:
            return 1.0
        return sum(wins) / len(wins)
    
    def _calculate_avg_loss(self) -> float:
        """Calculate average losing trade."""
        losses = [abs(t.pnl) for t in self._trade_history if (t.pnl or 0) < 0]
        if not losses:
            return 1.0
        return sum(losses) / len(losses)
    
    def _calculate_kelly(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly fraction.
        
        Args:
            win_rate: Win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            
        Returns:
            float: Kelly fraction (0-1)
        """
        if avg_loss == 0:
            return 0.0
        
        win_loss_ratio = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        
        # Use half-Kelly for safety
        return max(0, min(0.25, kelly * 0.5))
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on Martingale logic.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        symbol = self.config.symbol or market_data[0].symbol
        current_price = market_data[-1].close
        
        # Initialize state if needed
        if symbol not in self._states:
            self._states[symbol] = MartingaleState(
                symbol=symbol,
                direction=self.martingale_config.direction,
                base_position_size=self.martingale_config.base_position_size,
                current_position_size=self.martingale_config.base_position_size,
            )
        
        state = self._states[symbol]
        self._current_state = state
        
        # Check cooldown
        if self._cooldown_until and datetime.utcnow() < self._cooldown_until:
            return None
        
        # Check max steps
        if state.current_step >= self.martingale_config.max_steps:
            self.logger.warning(f"Max steps reached: {state.current_step}")
            return None
        
        # Check max consecutive losses
        if state.consecutive_losses >= self.martingale_config.max_consecutive_losses:
            self.logger.warning(f"Max consecutive losses reached: {state.consecutive_losses}")
            return None
        
        # Check drawdown
        if self.current_drawdown > self.martingale_config.max_drawdown_pct:
            self.logger.warning(f"Max drawdown exceeded: {self.current_drawdown:.2%}")
            return None
        
        # Determine direction
        direction = self._determine_direction(market_data, state)
        
        if direction is None:
            return None
        
        # Calculate position size
        position_size = self.calculate_next_position_size(state, state.last_trade_result)
        position_size = max(position_size, self.martingale_config.min_position_size)
        position_size = min(position_size, self.martingale_config.max_position_size)
        
        # Update state
        state.current_position_size = position_size
        
        # Calculate stop loss and take profit
        stop_loss = self._calculate_stop_loss(current_price, direction, position_size)
        take_profit = self._calculate_take_profit(current_price, direction, position_size)
        
        # Determine signal type
        if direction == OrderSide.BUY:
            signal_type = SignalType.BUY
        else:
            signal_type = SignalType.SELL
        
        # Determine signal strength
        strength = self._determine_signal_strength(state)
        
        # Create signal
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=self._calculate_confidence(state),
            price=current_price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                "martingale_type": self.martingale_config.martingale_type.value,
                "current_step": state.current_step,
                "consecutive_losses": state.consecutive_losses,
                "position_size": position_size,
                "loss_streak_amount": state.current_loss_streak,
                "direction": direction.value,
            },
        )
        
        self.logger.info(
            f"Martingale signal: {signal_type.value} {symbol} @ {current_price:.2f} "
            f"size: {position_size:.2f} (step: {state.current_step}, "
            f"losses: {state.consecutive_losses})"
        )
        
        return signal
    
    def _determine_direction(
        self,
        market_data: List[MarketData],
        state: MartingaleState,
    ) -> Optional[OrderSide]:
        """
        Determine trade direction based on market conditions.
        
        Args:
            market_data: Market data
            state: Martingale state
            
        Returns:
            Optional[OrderSide]: Trade direction or None
        """
        direction = self.martingale_config.direction
        
        if direction == MartingaleDirection.LONG:
            return OrderSide.BUY
        elif direction == MartingaleDirection.SHORT:
            return OrderSide.SELL
        elif direction == MartingaleDirection.BOTH:
            # Determine direction based on trend
            if len(market_data) < 10:
                return OrderSide.BUY
            
            # Simple trend detection
            prices = [c.close for c in market_data[-10:]]
            trend = prices[-1] - prices[0]
            
            # If in loss streak, go with trend
            if state.consecutive_losses > 2:
                return OrderSide.BUY if trend > 0 else OrderSide.SELL
            
            # Alternating direction
            if state.total_trades % 2 == 0:
                return OrderSide.BUY
            else:
                return OrderSide.SELL
        
        return OrderSide.BUY
    
    def _calculate_stop_loss(
        self,
        price: float,
        direction: OrderSide,
        position_size: float,
    ) -> float:
        """
        Calculate stop loss price.
        
        Args:
            price: Entry price
            direction: Trade direction
            position_size: Position size
            
        Returns:
            float: Stop loss price
        """
        stop_loss_pct = self.martingale_config.stop_loss_pct
        
        # Increase stop loss for larger positions (risk management)
        if position_size > self.martingale_config.base_position_size * 2:
            stop_loss_pct = min(stop_loss_pct * 1.5, 0.10)
        
        if direction == OrderSide.BUY:
            return price * (1 - stop_loss_pct)
        else:
            return price * (1 + stop_loss_pct)
    
    def _calculate_take_profit(
        self,
        price: float,
        direction: OrderSide,
        position_size: float,
    ) -> float:
        """
        Calculate take profit price.
        
        Args:
            price: Entry price
            direction: Trade direction
            position_size: Position size
            
        Returns:
            float: Take profit price
        """
        take_profit_pct = self.martingale_config.take_profit_pct
        
        # Adjust take profit based on step
        if self._current_state:
            step = self._current_state.current_step
            # Wider take profit for higher steps
            take_profit_pct *= (1 + step * 0.1)
        
        if direction == OrderSide.BUY:
            return price * (1 + take_profit_pct)
        else:
            return price * (1 - take_profit_pct)
    
    def _determine_signal_strength(self, state: MartingaleState) -> SignalStrength:
        """Determine signal strength based on state."""
        if state.consecutive_losses == 0:
            return SignalStrength.WEAK
        elif state.consecutive_losses <= 2:
            return SignalStrength.MEDIUM
        elif state.consecutive_losses <= 4:
            return SignalStrength.STRONG
        else:
            return SignalStrength.VERY_STRONG
    
    def _calculate_confidence(self, state: MartingaleState) -> float:
        """Calculate signal confidence."""
        # Higher confidence as losses increase (recovery expected)
        base_confidence = 0.6
        loss_bonus = min(state.consecutive_losses * 0.05, 0.3)
        
        # Reduce confidence if max steps are reached
        step_penalty = max(0, state.current_step / self.martingale_config.max_steps * 0.2)
        
        return min(1.0, base_confidence + loss_bonus - step_penalty)
    
    # ========================================================================
    # TRADE HANDLING
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Handle completed trade.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        async with self._lock:
            # Update trade history
            self._trade_history.append(trade)
            self._martingale_stats["total_trades"] += 1
            
            pnl = trade.pnl or 0.0
            
            # Update state based on trade result
            symbol = trade.symbol
            if symbol in self._states:
                state = self._states[symbol]
                state.last_trade_result = pnl
                state.last_trade_time = datetime.utcnow()
                
                if pnl > 0:
                    state.total_wins += 1
                    state.consecutive_wins += 1
                    state.consecutive_losses = 0
                    self._martingale_stats["winning_trades"] += 1
                    
                    # Check if this trade broke a loss streak
                    if state.current_loss_streak > 0:
                        recovered_amount = state.current_loss_streak + pnl
                        if recovered_amount >= 0:
                            self._martingale_stats["successful_recoveries"] += 1
                            state.recovered = True
                            self.logger.info(
                                f"Recovered from loss streak! "
                                f"Streak: ${state.current_loss_streak:.2f}, "
                                f"Recovery profit: ${recovered_amount:.2f}"
                            )
                        
                        # Track loss streak
                        self._loss_streak_history.append(state.current_loss_streak)
                        state.current_loss_streak = 0.0
                        self._martingale_stats["streak_break_count"] += 1
                    
                    # Update cooldown
                    if self.martingale_config.cooldown_after_win > 0:
                        self._cooldown_until = datetime.utcnow() + timedelta(
                            seconds=self.martingale_config.cooldown_after_win
                        )
                
                else:
                    state.total_losses += 1
                    state.consecutive_losses += 1
                    state.consecutive_wins = 0
                    state.current_loss_streak += abs(pnl)
                    self._martingale_stats["losing_trades"] += 1
                    
                    # Track max streak
                    if state.consecutive_losses > self._martingale_stats["max_streak_reached"]:
                        self._martingale_stats["max_streak_reached"] = state.consecutive_losses
                    
                    # Track total loss streaks
                    if state.consecutive_losses == 1:
                        self._martingale_stats["total_loss_streaks"] += 1
                
                # Update stats
                self._martingale_stats["avg_position_size"] = (
                    (self._martingale_stats["avg_position_size"] * (self._martingale_stats["total_trades"] - 1) +
                     state.current_position_size) / self._martingale_stats["total_trades"]
                )
                
                if state.current_position_size > self._martingale_stats["max_position_used"]:
                    self._martingale_stats["max_position_used"] = state.current_position_size
                
                # Calculate recovery rate
                if self._martingale_stats["total_loss_streaks"] > 0:
                    self._martingale_stats["recovery_rate"] = (
                        self._martingale_stats["successful_recoveries"] /
                        self._martingale_stats["total_loss_streaks"]
                    )
            
            # Log trade result
            self.logger.info(
                f"Martingale trade result: {trade.symbol} "
                f"P&L: ${pnl:.2f} | "
                f"Consecutive losses: {state.consecutive_losses} | "
                f"Step: {state.current_step}"
            )
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    async def on_position_update(self, position: Position) -> None:
        """
        Handle position update.
        
        Args:
            position: Updated position
        """
        await super().on_position_update(position)
        
        # Update state for this symbol
        if position.symbol in self._states:
            state = self._states[position.symbol]
            
            # Update position size if still open
            if position.quantity > 0:
                state.current_position_size = position.quantity
    
    # ========================================================================
    # STRATEGY RESET
    # ========================================================================
    
    def reset_strategy(self, symbol: Optional[str] = None) -> None:
        """
        Reset Martingale state.
        
        Args:
            symbol: Symbol to reset (None for all)
        """
        if symbol:
            if symbol in self._states:
                self._states[symbol] = MartingaleState(
                    symbol=symbol,
                    direction=self.martingale_config.direction,
                    base_position_size=self.martingale_config.base_position_size,
                    current_position_size=self.martingale_config.base_position_size,
                )
                self.logger.info(f"Reset Martingale state for {symbol}")
        else:
            for sym in self._states:
                self._states[sym] = MartingaleState(
                    symbol=sym,
                    direction=self.martingale_config.direction,
                    base_position_size=self.martingale_config.base_position_size,
                    current_position_size=self.martingale_config.base_position_size,
                )
            self.logger.info("Reset all Martingale states")
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_martingale_stats(self) -> Dict[str, Any]:
        """
        Get Martingale-specific statistics.
        
        Returns:
            Dict[str, Any]: Martingale statistics
        """
        states = {}
        for symbol, state in self._states.items():
            states[symbol] = {
                "current_step": state.current_step,
                "consecutive_losses": state.consecutive_losses,
                "consecutive_wins": state.consecutive_wins,
                "current_position_size": state.current_position_size,
                "current_loss_streak": state.current_loss_streak,
                "total_wins": state.total_wins,
                "total_losses": state.total_losses,
                "recovered": state.recovered,
                "fibonacci_curr": state.fibonacci_curr,
                "dalembert_counter": state.dalembert_counter,
            }
        
        return {
            **self._martingale_stats,
            "states": states,
            "loss_streak_history": self._loss_streak_history[-10:],
            "avg_loss_streak": (
                sum(self._loss_streak_history) / len(self._loss_streak_history)
                if self._loss_streak_history else 0
            ),
            "max_loss_streak": max(self._loss_streak_history) if self._loss_streak_history else 0,
            "martingale_type": self.martingale_config.martingale_type.value,
            "direction": self.martingale_config.direction.value,
            "max_steps": self.martingale_config.max_steps,
            "base_position_size": self.martingale_config.base_position_size,
            "current_win_rate": self._calculate_win_rate(),
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Martingale strategy started (type: {self.martingale_config.martingale_type.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Martingale strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "MartingaleType",
    "MartingaleDirection",
    "MartingaleConfig",
    "MartingaleState",
    "MartingaleStrategy",
]
