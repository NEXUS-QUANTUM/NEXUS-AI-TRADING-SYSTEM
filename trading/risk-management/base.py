# trading/risk-management/base.py
"""
NEXUS AI TRADING SYSTEM - Risk Management Base Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides the core risk management framework for the
NEXUS AI Trading System. It defines the base classes and interfaces
for all risk management components including position sizing,
stop-loss management, drawdown control, and portfolio risk.

Key Features:
- Position sizing algorithms
- Stop-loss and take-profit management
- Drawdown control
- Portfolio risk limits
- Risk factor calculations
- Monte Carlo simulations
"""

import asyncio
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import deque, defaultdict

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade, MarketData
from shared.types.portfolio import Portfolio, AccountBalance

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class RiskLevel(str, Enum):
    """Risk levels for position sizing"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class StopLossType(str, Enum):
    """Types of stop-loss orders"""
    FIXED = "fixed"
    TRAILING = "trailing"
    VOLATILITY = "volatility"
    ATR = "atr"
    SUPPORT_RESISTANCE = "support_resistance"
    DYNAMIC = "dynamic"


class TakeProfitType(str, Enum):
    """Types of take-profit orders"""
    FIXED = "fixed"
    RISK_REWARD = "risk_reward"
    TRAILING = "trailing"
    DYNAMIC = "dynamic"


@dataclass
class PositionSizingConfig:
    """Configuration for position sizing"""
    # Risk per trade
    risk_per_trade: float = 0.01  # 1% of account
    max_risk_per_trade: float = 0.02  # 2% max
    
    # Position limits
    max_position_size: float = 100000.0
    min_position_size: float = 10.0
    max_positions: int = 5
    max_exposure: float = 0.5  # 50% of portfolio
    
    # Risk level
    risk_level: RiskLevel = RiskLevel.MODERATE
    
    # Kelly Criterion
    use_kelly: bool = False
    kelly_fraction: float = 0.5  # Half-Kelly
    
    # Volatility adjustment
    adjust_to_volatility: bool = True
    volatility_lookback: int = 20
    
    # Correlation adjustment
    adjust_to_correlation: bool = False
    correlation_threshold: float = 0.7


@dataclass
class StopLossConfig:
    """Configuration for stop-loss"""
    stop_loss_type: StopLossType = StopLossType.FIXED
    fixed_pct: float = 0.02  # 2% for fixed stop
    trailing_pct: float = 0.02  # 2% for trailing
    atr_multiplier: float = 2.0
    atr_period: int = 14
    volatility_multiplier: float = 1.5
    min_stop_pct: float = 0.005  # 0.5% min
    max_stop_pct: float = 0.10  # 10% max
    
    # Dynamic adjustment
    dynamic_adjust: bool = True
    adjustment_factor: float = 0.5
    max_adjustment: float = 2.0


@dataclass
class TakeProfitConfig:
    """Configuration for take-profit"""
    take_profit_type: TakeProfitType = TakeProfitType.RISK_REWARD
    risk_reward_ratio: float = 2.0
    min_risk_reward: float = 1.5
    max_risk_reward: float = 5.0
    fixed_pct: float = 0.04  # 4% for fixed TP
    dynamic_multiplier: float = 1.5
    
    # Partial take profits
    enable_partial: bool = True
    partial_levels: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.5, 0.5),  # 50% at 0.5x risk
        (0.3, 1.0),  # 30% at 1.0x risk
        (0.2, 2.0),  # 20% at 2.0x risk
    ])


@dataclass
class DrawdownConfig:
    """Configuration for drawdown control"""
    max_drawdown_pct: float = 0.10  # 10% max drawdown
    max_daily_drawdown: float = 0.05  # 5% daily
    max_position_drawdown: float = 0.03  # 3% per position
    auto_reduce_on_drawdown: bool = True
    reduction_factor: float = 0.5  # 50% reduction
    recovery_period: int = 10  # days to recover


@dataclass
class RiskMetrics:
    """Risk metrics for a position or portfolio"""
    # Position risk
    position_risk: float = 0.0
    stop_loss_distance: float = 0.0
    risk_reward_ratio: float = 0.0
    
    # Portfolio risk
    portfolio_exposure: float = 0.0
    portfolio_risk: float = 0.0
    correlation_risk: float = 0.0
    
    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    
    # Value at Risk
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    
    # Returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0


# ============================================================================
# RISK MANAGER BASE CLASS
# ============================================================================

class RiskManager(ABC):
    """
    Abstract base class for risk management.
    
    All risk management components must inherit from this class and
    implement the required methods for position sizing, stop-loss,
    take-profit, and drawdown management.
    """
    
    def __init__(
        self,
        position_sizing_config: Optional[PositionSizingConfig] = None,
        stop_loss_config: Optional[StopLossConfig] = None,
        take_profit_config: Optional[TakeProfitConfig] = None,
        drawdown_config: Optional[DrawdownConfig] = None,
    ):
        """
        Initialize the risk manager.
        
        Args:
            position_sizing_config: Position sizing configuration
            stop_loss_config: Stop-loss configuration
            take_profit_config: Take-profit configuration
            drawdown_config: Drawdown configuration
        """
        self.position_sizing_config = position_sizing_config or PositionSizingConfig()
        self.stop_loss_config = stop_loss_config or StopLossConfig()
        self.take_profit_config = take_profit_config or TakeProfitConfig()
        self.drawdown_config = drawdown_config or DrawdownConfig()
        
        # State
        self._positions: Dict[str, Position] = {}
        self._closed_trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._drawdown_curve: List[float] = []
        
        # Performance history
        self._performance_history: deque = deque(maxlen=1000)
        self._daily_pnl: Dict[str, float] = defaultdict(float)
        self._last_date: Optional[str] = None
        
        # Metrics
        self._metrics = RiskMetrics()
        
        self.logger = logger
    
    # ========================================================================
    # ABSTRACT METHODS
    # ========================================================================
    
    @abstractmethod
    def calculate_position_size(
        self,
        symbol: str,
        price: float,
        account_balance: float,
        stop_loss: Optional[float] = None,
        risk_percent: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate position size for a trade.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            account_balance: Current account balance
            stop_loss: Stop loss price (optional)
            risk_percent: Risk percentage (optional)
            context: Additional context
            
        Returns:
            float: Position size
        """
        pass
    
    @abstractmethod
    def calculate_stop_loss(
        self,
        symbol: str,
        price: float,
        side: OrderSide,
        position_size: float,
        market_data: Optional[List[MarketData]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate stop loss price.
        
        Args:
            symbol: Trading symbol
            price: Entry price
            side: Trade side
            position_size: Position size
            market_data: Market data for calculation
            context: Additional context
            
        Returns:
            float: Stop loss price
        """
        pass
    
    @abstractmethod
    def calculate_take_profit(
        self,
        symbol: str,
        price: float,
        side: OrderSide,
        stop_loss: float,
        position_size: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Union[float, List[Tuple[float, float]]]:
        """
        Calculate take profit price(s).
        
        Args:
            symbol: Trading symbol
            price: Entry price
            side: Trade side
            stop_loss: Stop loss price
            position_size: Position size
            context: Additional context
            
        Returns:
            Union[float, List[Tuple[float, float]]]: TP price(s) with quantities
        """
        pass
    
    # ========================================================================
    # VIRTUAL METHODS
    # ========================================================================
    
    def update_position(self, position: Position) -> None:
        """
        Update position state.
        
        Args:
            position: Position to update
        """
        self._positions[position.symbol] = position
    
    def remove_position(self, symbol: str) -> Optional[Position]:
        """
        Remove a position.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Optional[Position]: Removed position
        """
        return self._positions.pop(symbol, None)
    
    def update_account_balance(self, balance: float) -> None:
        """
        Update account balance.
        
        Args:
            balance: Current account balance
        """
        self._equity_curve.append(balance)
        self._update_drawdown(balance)
    
    def record_trade(self, trade: Trade) -> None:
        """
        Record a completed trade.
        
        Args:
            trade: Completed trade
        """
        self._closed_trades.append(trade)
        self._performance_history.append(trade)
        
        # Update daily P&L
        date = trade.exit_time.strftime("%Y-%m-%d") if trade.exit_time else datetime.utcnow().strftime("%Y-%m-%d")
        if self._last_date is None:
            self._last_date = date
        
        if date != self._last_date:
            # Reset daily P&L
            self._daily_pnl.clear()
            self._last_date = date
        
        self._daily_pnl[date] += trade.pnl or 0.0
    
    # ========================================================================
    # RISK CALCULATIONS
    # ========================================================================
    
    def calculate_var(
        self,
        returns: List[float],
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate Value at Risk.
        
        Args:
            returns: List of returns
            confidence: Confidence level (0-1)
            
        Returns:
            float: Value at Risk
        """
        if not returns:
            return 0.0
        
        return np.percentile(returns, (1 - confidence) * 100)
    
    def calculate_cvar(
        self,
        returns: List[float],
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).
        
        Args:
            returns: List of returns
            confidence: Confidence level (0-1)
            
        Returns:
            float: CVaR
        """
        if not returns:
            return 0.0
        
        var = self.calculate_var(returns, confidence)
        return np.mean([r for r in returns if r <= var])
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02,
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            float: Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming daily returns)
        annualized_return = avg_return * 252
        annualized_std = std_return * np.sqrt(252)
        
        return (annualized_return - risk_free_rate) / annualized_std
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02,
    ) -> float:
        """
        Calculate Sortino ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            float: Sortino ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        
        # Calculate downside deviation
        downside = [r for r in returns if r < 0]
        if not downside:
            return 0.0
        
        downside_std = np.std(downside)
        if downside_std == 0:
            return 0.0
        
        # Annualize
        annualized_return = avg_return * 252
        annualized_downside = downside_std * np.sqrt(252)
        
        return (annualized_return - risk_free_rate) / annualized_downside
    
    def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """
        Calculate maximum drawdown.
        
        Args:
            equity_curve: List of equity values
            
        Returns:
            float: Maximum drawdown
        """
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        
        max_drawdown = 0.0
        peak = equity_curve[0]
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def calculate_correlation(self, returns1: List[float], returns2: List[float]) -> float:
        """
        Calculate correlation between two return series.
        
        Args:
            returns1: First return series
            returns2: Second return series
            
        Returns:
            float: Correlation coefficient
        """
        if len(returns1) != len(returns2) or len(returns1) < 2:
            return 0.0
        
        return np.corrcoef(returns1, returns2)[0, 1]
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _update_drawdown(self, equity: float) -> None:
        """
        Update drawdown metrics.
        
        Args:
            equity: Current equity
        """
        if not self._equity_curve:
            self._metrics.current_drawdown = 0.0
            self._metrics.max_drawdown = 0.0
            return
        
        peak = max(self._equity_curve)
        if equity > peak:
            self._metrics.current_drawdown = 0.0
        else:
            self._metrics.current_drawdown = (peak - equity) / peak
        
        if self._metrics.current_drawdown > self._metrics.max_drawdown:
            self._metrics.max_drawdown = self._metrics.current_drawdown
        
        self._drawdown_curve.append(self._metrics.current_drawdown)
    
    def _get_risk_multiplier(self) -> float:
        """
        Get risk multiplier based on current drawdown.
        
        Returns:
            float: Risk multiplier
        """
        if not self.drawdown_config.auto_reduce_on_drawdown:
            return 1.0
        
        current_dd = self._metrics.current_drawdown
        max_dd = self.drawdown_config.max_drawdown_pct
        
        if current_dd == 0:
            return 1.0
        
        if current_dd > max_dd * 0.8:
            return self.drawdown_config.reduction_factor
        elif current_dd > max_dd * 0.5:
            return 0.7
        
        return 1.0
    
    def _get_volatility_adjustment(self, market_data: Optional[List[MarketData]]) -> float:
        """
        Get volatility adjustment factor.
        
        Args:
            market_data: Market data
            
        Returns:
            float: Volatility adjustment factor
        """
        if not self.position_sizing_config.adjust_to_volatility:
            return 1.0
        
        if not market_data or len(market_data) < self.position_sizing_config.volatility_lookback:
            return 1.0
        
        # Calculate recent volatility
        prices = [d.close for d in market_data[-self.position_sizing_config.volatility_lookback:]]
        returns = []
        
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return 1.0
        
        volatility = np.std(returns)
        
        # Normalize volatility
        # Assuming average volatility of 0.02 (2%)
        avg_volatility = 0.02
        if volatility > 0:
            adjustment = avg_volatility / volatility
            adjustment = max(0.5, min(2.0, adjustment))
        else:
            adjustment = 1.0
        
        return adjustment
    
    def _get_risk_level_multiplier(self) -> float:
        """
        Get risk level multiplier.
        
        Returns:
            float: Risk level multiplier
        """
        multipliers = {
            RiskLevel.CONSERVATIVE: 0.5,
            RiskLevel.MODERATE: 1.0,
            RiskLevel.AGGRESSIVE: 1.5,
            RiskLevel.VERY_AGGRESSIVE: 2.0,
        }
        return multipliers.get(self.position_sizing_config.risk_level, 1.0)
    
    # ========================================================================
    # POSITION SIZING METHODS
    # ========================================================================
    
    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Calculate Kelly Criterion fraction.
        
        Args:
            win_rate: Win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            
        Returns:
            float: Kelly fraction
        """
        if avg_loss == 0:
            return 0.0
        
        win_loss_ratio = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        
        # Apply Kelly fraction
        kelly *= self.position_sizing_config.kelly_fraction
        
        # Cap at 25%
        return max(0, min(0.25, kelly))
    
    def calculate_correlation_adjustment(
        self,
        symbol: str,
        existing_positions: Dict[str, Position],
    ) -> float:
        """
        Calculate correlation adjustment for position sizing.
        
        Args:
            symbol: New symbol
            existing_positions: Existing positions
            
        Returns:
            float: Correlation adjustment factor
        """
        if not self.position_sizing_config.adjust_to_correlation:
            return 1.0
        
        # This would require historical return data for correlation
        # For now, return 1.0
        return 1.0
    
    # ========================================================================
    # STOP-LOSS METHODS
    # ========================================================================
    
    def calculate_atr(
        self,
        market_data: List[MarketData],
        period: int = 14,
    ) -> float:
        """
        Calculate Average True Range.
        
        Args:
            market_data: Market data
            period: ATR period
            
        Returns:
            float: ATR value
        """
        if len(market_data) < period + 1:
            return 0.0
        
        highs = [d.high for d in market_data]
        lows = [d.low for d in market_data]
        closes = [d.close for d in market_data]
        
        tr_list = []
        for i in range(1, min(len(market_data), period + 1)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1]),
            )
            tr_list.append(tr)
        
        if not tr_list:
            return 0.0
        
        return sum(tr_list) / len(tr_list)
    
    def calculate_volatility_stop(
        self,
        price: float,
        side: OrderSide,
        market_data: List[MarketData],
        multiplier: float = 1.5,
    ) -> float:
        """
        Calculate volatility-based stop loss.
        
        Args:
            price: Entry price
            side: Trade side
            market_data: Market data
            multiplier: Volatility multiplier
            
        Returns:
            float: Stop loss price
        """
        if not market_data:
            return self.calculate_fixed_stop(price, side)
        
        # Calculate volatility
        returns = []
        for i in range(1, min(len(market_data), 20)):
            if market_data[i-1].close > 0:
                returns.append((market_data[i].close - market_data[i-1].close) / market_data[i-1].close)
        
        if not returns:
            return self.calculate_fixed_stop(price, side)
        
        volatility = np.std(returns)
        stop_distance = price * volatility * multiplier
        
        # Apply limits
        min_distance = price * self.stop_loss_config.min_stop_pct
        max_distance = price * self.stop_loss_config.max_stop_pct
        stop_distance = max(min_distance, min(max_distance, stop_distance))
        
        if side == OrderSide.BUY:
            return price - stop_distance
        else:
            return price + stop_distance
    
    def calculate_fixed_stop(
        self,
        price: float,
        side: OrderSide,
        pct: Optional[float] = None,
    ) -> float:
        """
        Calculate fixed percentage stop loss.
        
        Args:
            price: Entry price
            side: Trade side
            pct: Stop percentage
            
        Returns:
            float: Stop loss price
        """
        pct = pct or self.stop_loss_config.fixed_pct
        
        if side == OrderSide.BUY:
            return price * (1 - pct)
        else:
            return price * (1 + pct)
    
    # ========================================================================
    # TAKE-PROFIT METHODS
    # ========================================================================
    
    def calculate_risk_reward_tp(
        self,
        price: float,
        side: OrderSide,
        stop_loss: float,
        ratio: float,
    ) -> float:
        """
        Calculate risk-reward take profit.
        
        Args:
            price: Entry price
            side: Trade side
            stop_loss: Stop loss price
            ratio: Risk-reward ratio
            
        Returns:
            float: Take profit price
        """
        if side == OrderSide.BUY:
            risk = price - stop_loss
            return price + risk * ratio
        else:
            risk = stop_loss - price
            return price - risk * ratio
    
    def calculate_partial_take_profits(
        self,
        price: float,
        side: OrderSide,
        stop_loss: float,
        levels: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """
        Calculate partial take profit levels.
        
        Args:
            price: Entry price
            side: Trade side
            stop_loss: Stop loss price
            levels: List of (percentage, quantity) tuples
            
        Returns:
            List[Tuple[float, float]]: (price, quantity) for each level
        """
        result = []
        
        for pct, qty in levels:
            if side == OrderSide.BUY:
                risk = price - stop_loss
                tp_price = price + risk * pct
            else:
                risk = stop_loss - price
                tp_price = price - risk * pct
            
            result.append((tp_price, qty))
        
        return result
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def get_risk_metrics(self) -> RiskMetrics:
        """
        Get current risk metrics.
        
        Returns:
            RiskMetrics: Current risk metrics
        """
        return self._metrics
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Get risk summary.
        
        Returns:
            Dict[str, Any]: Risk summary
        """
        total_exposure = sum(p.quantity * p.entry_price for p in self._positions.values())
        total_value = self._equity_curve[-1] if self._equity_curve else 0
        
        return {
            "positions": len(self._positions),
            "total_exposure": total_exposure,
            "portfolio_value": total_value,
            "exposure_ratio": total_exposure / total_value if total_value > 0 else 0,
            "current_drawdown": self._metrics.current_drawdown,
            "max_drawdown": self._metrics.max_drawdown,
            "var_95": self._metrics.var_95,
            "var_99": self._metrics.var_99,
            "sharpe_ratio": self._metrics.sharpe_ratio,
            "sortino_ratio": self._metrics.sortino_ratio,
            "calmar_ratio": self._metrics.calmar_ratio,
            "total_trades": len(self._closed_trades),
            "win_rate": self._calculate_win_rate(),
        }
    
    def _calculate_win_rate(self) -> float:
        """
        Calculate win rate.
        
        Returns:
            float: Win rate percentage
        """
        if not self._closed_trades:
            return 0.0
        
        wins = sum(1 for t in self._closed_trades if (t.pnl or 0) > 0)
        return (wins / len(self._closed_trades)) * 100


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "RiskLevel",
    "StopLossType",
    "TakeProfitType",
    
    # Configurations
    "PositionSizingConfig",
    "StopLossConfig",
    "TakeProfitConfig",
    "DrawdownConfig",
    
    # Models
    "RiskMetrics",
    
    # Base class
    "RiskManager",
]
