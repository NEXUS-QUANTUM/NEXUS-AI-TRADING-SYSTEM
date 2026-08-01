"""
NEXUS AI TRADING SYSTEM
Hedge Bot Risk-Reward Manager

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: trading/bots/hedge_bot/hedge_bot_risk_reward_manager.py
Description: Advanced risk-reward management for hedge bot positions
             with real-time risk assessment and dynamic position sizing.
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from decimal import Decimal

import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async, RetryConfig
from shared.utilities.cache import cache_result, CacheConfig
from trading.bots.hedge_bot.core.position_sizer import PositionSizer
from trading.bots.hedge_bot.core.stop_loss_manager import StopLossManager
from trading.bots.hedge_bot.core.take_profit_manager import TakeProfitManager

# Initialize logger
logger = get_logger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class RiskRewardType(str, Enum):
    """Types of risk-reward strategies."""
    FIXED_RATIO = "fixed_ratio"
    DYNAMIC = "dynamic"
    KELLY_CRITERION = "kelly_criterion"
    OPTIMAL_F = "optimal_f"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    MARTINGALE = "martingale"
    ANTI_MARTINGALE = "anti_martingale"
    PYRAMIDING = "pyramiding"
    SCALING = "scaling"
    ADAPTIVE = "adaptive"
    AI_DRIVEN = "ai_driven"
    REGIME_BASED = "regime_based"


class RiskLevel(str, Enum):
    """Risk levels for position sizing."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EXTREME = "extreme"
    CUSTOM = "custom"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class RiskRewardConfig:
    """Configuration for risk-reward management."""
    risk_reward_type: RiskRewardType = RiskRewardType.DYNAMIC
    risk_level: RiskLevel = RiskLevel.MODERATE
    max_risk_per_trade: float = 0.02  # 2% of portfolio
    max_risk_per_day: float = 0.05    # 5% of portfolio
    max_risk_per_week: float = 0.10   # 10% of portfolio
    max_drawdown: float = 0.20        # 20% max drawdown
    min_reward_ratio: float = 1.5     # Minimum risk-reward ratio
    target_reward_ratio: float = 2.0  # Target risk-reward ratio
    max_leverage: float = 10.0        # Maximum leverage
    kelly_fraction: float = 0.25      # Fraction of Kelly criterion
    volatility_lookback: int = 20     # Days for volatility calculation
    correlation_lookback: int = 60    # Days for correlation
    max_correlation: float = 0.7      # Maximum allowed correlation
    position_sizing_method: str = "fixed_fractional"
    adaptive_threshold: float = 0.1   # Threshold for adaptive sizing


@dataclass
class RiskRewardMetrics:
    """Risk-reward metrics for a position."""
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    position_size: float
    leverage: float
    expected_value: float
    win_probability: float
    expected_risk: float
    expected_reward: float
    sharpe_contribution: float
    var_contribution: float
    risk_adjusted_return: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PositionRiskReward:
    """Risk-reward profile for a specific position."""
    symbol: str
    side: PositionSide
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    unrealized_pnl: float
    realized_pnl: float
    risk_reward_ratio: float
    current_risk_reward_ratio: float
    trailing_stop: Optional[float] = None
    breakeven_stop: Optional[float] = None
    partial_take_profit_levels: List[float] = field(default_factory=list)
    partial_take_profit_sizes: List[float] = field(default_factory=list)
    scaling_levels: List[float] = field(default_factory=list)
    scaling_sizes: List[float] = field(default_factory=list)


@dataclass
class RiskRewardDecision:
    """Risk-reward decision for a trade."""
    action: str  # enter, exit, hold, scale_in, scale_out
    position_size: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    confidence: float
    reasoning: str
    metrics: RiskRewardMetrics
    expected_pnl: float
    probability_of_success: float
    expected_shortfall: float
    optimal_position_size: float
    adjusted_position_size: float


@dataclass
class RiskRewardStats:
    """Statistical summary of risk-reward performance."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    average_risk_reward: float
    average_holding_period: float
    max_consecutive_losses: int
    max_drawdown: float
    recovery_factor: float
    risk_adjusted_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    kelly_percentage: float
    optimal_f: float
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# RISK-REWARD MANAGER CLASS
# ============================================================================

class RiskRewardManager:
    """
    Advanced risk-reward management for hedge bot positions.
    
    Features:
    - Dynamic risk-reward ratio calculation
    - Kelly Criterion and Optimal F sizing
    - Volatility-adjusted position sizing
    - Adaptive risk management
    - AI-driven risk-reward optimization
    - Regime-based risk adjustments
    - Pyramiding and scaling strategies
    - Partial take profit management
    - Trailing stop management
    - Risk-reward statistics and analytics
    """
    
    def __init__(
        self,
        config: RiskRewardConfig,
        position_sizer: Optional[PositionSizer] = None,
        stop_loss_manager: Optional[StopLossManager] = None,
        take_profit_manager: Optional[TakeProfitManager] = None,
    ):
        """
        Initialize the risk-reward manager.
        
        Args:
            config: Risk-reward configuration
            position_sizer: Position sizer instance
            stop_loss_manager: Stop loss manager instance
            take_profit_manager: Take profit manager instance
        """
        self.config = config
        self.position_sizer = position_sizer or PositionSizer({})
        self.stop_loss_manager = stop_loss_manager or StopLossManager({})
        self.take_profit_manager = take_profit_manager or TakeProfitManager({})
        
        # State
        self.positions: Dict[str, PositionRiskReward] = {}
        self.metrics_cache: Dict[str, RiskRewardMetrics] = {}
        self.stats: RiskRewardStats = RiskRewardStats(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            average_win=0.0,
            average_loss=0.0,
            profit_factor=0.0,
            average_risk_reward=0.0,
            average_holding_period=0.0,
            max_consecutive_losses=0,
            max_drawdown=0.0,
            recovery_factor=0.0,
            risk_adjusted_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            kelly_percentage=0.0,
            optimal_f=0.0,
        )
        
        # History
        self.trade_history: List[Dict[str, Any]] = []
        self.performance_history: List[Dict[str, float]] = []
        
        # Market data cache
        self._market_data_cache: Dict[str, pd.DataFrame] = {}
        self._volatility_cache: Dict[str, float] = {}
        self._correlation_cache: Dict[str, float] = {}
        
        # Initialize AI model (placeholder)
        self._ai_model = None
        
        logger.info("RiskRewardManager initialized successfully")
    
    # ========================================================================
    # POSITION SIZING
    # ========================================================================
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        portfolio_value: float,
        volatility: Optional[float] = None,
        correlation: Optional[float] = None,
        win_probability: Optional[float] = None,
        side: PositionSide = PositionSide.LONG,
    ) -> Dict[str, float]:
        """
        Calculate optimal position size based on risk-reward parameters.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            portfolio_value: Total portfolio value
            volatility: Asset volatility (optional)
            correlation: Portfolio correlation (optional)
            win_probability: Probability of winning (optional)
            side: Position side
            
        Returns:
            Position size with details
        """
        # Calculate risk per unit
        if side == PositionSide.LONG:
            risk_per_unit = entry_price - stop_loss
            reward_per_unit = take_profit - entry_price
        else:
            risk_per_unit = stop_loss - entry_price
            reward_per_unit = entry_price - take_profit
        
        # Validate
        if risk_per_unit <= 0 or reward_per_unit <= 0:
            logger.warning(f"Invalid risk/reward for {symbol}")
            return {
                "position_size": 0,
                "risk_amount": 0,
                "reward_amount": 0,
                "risk_reward_ratio": 0,
                "max_position_size": 0,
                "adjusted_position_size": 0,
            }
        
        # Calculate raw risk-reward ratio
        raw_risk_reward = reward_per_unit / risk_per_unit
        
        # Get volatility if not provided
        if volatility is None:
            volatility = self._get_volatility(symbol)
        
        # Get correlation if not provided
        if correlation is None:
            correlation = self._get_correlation(symbol)
        
        # Get win probability if not provided
        if win_probability is None:
            win_probability = self._estimate_win_probability(symbol)
        
        # Determine sizing method
        sizing_method = self.config.position_sizing_method
        
        # Calculate position sizes using different methods
        sizes = {}
        
        # 1. Fixed Fractional (Kelly-based)
        kelly_fraction = self._calculate_kelly_fraction(
            win_probability,
            raw_risk_reward,
        )
        sizes["fixed_fractional"] = self._calculate_fixed_fractional(
            portfolio_value,
            risk_per_unit,
            kelly_fraction,
            entry_price,
        )
        
        # 2. Volatility Adjusted
        sizes["volatility_adjusted"] = self._calculate_volatility_adjusted(
            portfolio_value,
            risk_per_unit,
            volatility,
            entry_price,
        )
        
        # 3. Risk Based
        max_risk_amount = portfolio_value * self.config.max_risk_per_trade
        sizes["risk_based"] = self._calculate_risk_based(
            max_risk_amount,
            risk_per_unit,
            entry_price,
        )
        
        # 4. Optimal F
        optimal_f = self._calculate_optimal_f(
            self.trade_history,
            raw_risk_reward,
        )
        sizes["optimal_f"] = self._calculate_optimal_f_position(
            portfolio_value,
            risk_per_unit,
            optimal_f,
            entry_price,
        )
        
        # 5. Kelly Criterion
        sizes["kelly"] = self._calculate_kelly_position(
            portfolio_value,
            risk_per_unit,
            win_probability,
            raw_risk_reward,
            entry_price,
        )
        
        # 6. Regime Based
        regime = self._detect_market_regime()
        sizes["regime_based"] = self._calculate_regime_based(
            portfolio_value,
            risk_per_unit,
            regime,
            entry_price,
        )
        
        # 7. AI Driven (if available)
        if self._ai_model:
            sizes["ai_driven"] = self._calculate_ai_driven(
                symbol,
                entry_price,
                stop_loss,
                take_profit,
                portfolio_value,
                volatility,
                correlation,
                win_probability,
            )
        
        # Select the appropriate size based on configuration
        selected_size = self._select_position_size(sizes, sizing_method)
        
        # Apply risk limits
        adjusted_size = self._apply_risk_limits(
            selected_size,
            portfolio_value,
            symbol,
            side,
        )
        
        # Calculate metrics
        risk_amount = adjusted_size * risk_per_unit
        reward_amount = adjusted_size * reward_per_unit
        
        # Calculate expected value
        expected_value = (win_probability * reward_amount) - ((1 - win_probability) * risk_amount)
        
        return {
            "position_size": adjusted_size,
            "risk_amount": risk_amount,
            "reward_amount": reward_amount,
            "risk_reward_ratio": raw_risk_reward,
            "max_position_size": selected_size,
            "adjusted_position_size": adjusted_size,
            "kelly_fraction": kelly_fraction,
            "optimal_f": optimal_f,
            "win_probability": win_probability,
            "volatility": volatility,
            "correlation": correlation,
            "expected_value": expected_value,
            "sizes": sizes,
            "selected_method": sizing_method,
            "regime": regime,
        }
    
    def _calculate_fixed_fractional(
        self,
        portfolio_value: float,
        risk_per_unit: float,
        kelly_fraction: float,
        entry_price: float,
    ) -> float:
        """Calculate fixed fractional position size."""
        if risk_per_unit <= 0:
            return 0
        
        # Kelly fraction with safety factor
        fraction = min(kelly_fraction * self.config.kelly_fraction, 0.25)
        risk_amount = portfolio_value * fraction
        
        return risk_amount / risk_per_unit
    
    def _calculate_volatility_adjusted(
        self,
        portfolio_value: float,
        risk_per_unit: float,
        volatility: float,
        entry_price: float,
    ) -> float:
        """Calculate volatility-adjusted position size."""
        if risk_per_unit <= 0 or volatility <= 0:
            return 0
        
        # Base risk amount
        base_risk = portfolio_value * self.config.max_risk_per_trade
        
        # Adjust for volatility
        avg_volatility = 0.02  # Average daily volatility (2%)
        volatility_adjustment = avg_volatility / volatility
        volatility_adjustment = max(0.5, min(2.0, volatility_adjustment))
        
        adjusted_risk = base_risk * volatility_adjustment
        
        return adjusted_risk / risk_per_unit
    
    def _calculate_risk_based(
        self,
        max_risk_amount: float,
        risk_per_unit: float,
        entry_price: float,
    ) -> float:
        """Calculate risk-based position size."""
        if risk_per_unit <= 0:
            return 0
        
        return max_risk_amount / risk_per_unit
    
    def _calculate_optimal_f_position(
        self,
        portfolio_value: float,
        risk_per_unit: float,
        optimal_f: float,
        entry_price: float,
    ) -> float:
        """Calculate position size using Optimal F."""
        if risk_per_unit <= 0 or optimal_f <= 0:
            return 0
        
        risk_amount = portfolio_value * optimal_f
        return risk_amount / risk_per_unit
    
    def _calculate_kelly_position(
        self,
        portfolio_value: float,
        risk_per_unit: float,
        win_probability: float,
        risk_reward_ratio: float,
        entry_price: float,
    ) -> float:
        """Calculate position size using Kelly Criterion."""
        if risk_per_unit <= 0:
            return 0
        
        # Kelly formula: f* = (p * b - q) / b
        # where p = win probability, q = loss probability, b = odds ratio
        q = 1 - win_probability
        kelly = (win_probability * risk_reward_ratio - q) / risk_reward_ratio
        
        # Apply Kelly fraction
        kelly = max(0, min(kelly * self.config.kelly_fraction, 0.25))
        risk_amount = portfolio_value * kelly
        
        return risk_amount / risk_per_unit
    
    def _calculate_regime_based(
        self,
        portfolio_value: float,
        risk_per_unit: float,
        regime: str,
        entry_price: float,
    ) -> float:
        """Calculate regime-based position size."""
        if risk_per_unit <= 0:
            return 0
        
        # Regime multipliers
        regime_multipliers = {
            "bull": 1.2,
            "bear": 0.6,
            "sideways": 0.8,
            "high_volatility": 0.5,
            "low_volatility": 1.5,
            "crash": 0.2,
            "recovery": 1.1,
            "risk_on": 1.3,
            "risk_off": 0.4,
        }
        
        multiplier = regime_multipliers.get(regime, 1.0)
        base_risk = portfolio_value * self.config.max_risk_per_trade * multiplier
        
        return base_risk / risk_per_unit
    
    def _calculate_ai_driven(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        portfolio_value: float,
        volatility: float,
        correlation: float,
        win_probability: float,
    ) -> float:
        """Calculate AI-driven position size."""
        # Placeholder - would use actual AI model
        # This is a simplified implementation
        if not self._ai_model:
            return self._calculate_fixed_fractional(
                portfolio_value,
                entry_price - stop_loss if stop_loss < entry_price else stop_loss - entry_price,
                0.25,
                entry_price,
            )
        
        # Mock AI prediction
        confidence_score = 0.7 + (win_probability - 0.5) * 0.5
        volatility_score = 1.0 / (1 + volatility)
        correlation_score = 1.0 - abs(correlation)
        
        ai_multiplier = confidence_score * volatility_score * correlation_score
        ai_multiplier = max(0.2, min(2.0, ai_multiplier))
        
        base_size = self._calculate_fixed_fractional(
            portfolio_value,
            entry_price - stop_loss if stop_loss < entry_price else stop_loss - entry_price,
            0.25,
            entry_price,
        )
        
        return base_size * ai_multiplier
    
    def _select_position_size(
        self,
        sizes: Dict[str, float],
        method: str,
    ) -> float:
        """Select position size based on method."""
        if method in sizes:
            return sizes[method]
        
        # Fallback to minimum of all methods
        valid_sizes = [v for v in sizes.values() if v > 0]
        if valid_sizes:
            return min(valid_sizes)
        
        return 0
    
    def _apply_risk_limits(
        self,
        position_size: float,
        portfolio_value: float,
        symbol: str,
        side: PositionSide,
    ) -> float:
        """Apply risk limits to position size."""
        if position_size <= 0:
            return 0
        
        # Max risk per trade
        max_risk = portfolio_value * self.config.max_risk_per_trade
        
        # Check existing positions
        total_risk = self._get_total_risk()
        available_risk = max_risk - total_risk
        
        if available_risk <= 0:
            return 0
        
        # Apply correlation adjustment
        if symbol in self.positions:
            correlation = self._get_correlation(symbol)
            if correlation > self.config.max_correlation:
                available_risk *= (1 - correlation)
        
        # Check daily and weekly limits
        daily_risk_used = self._get_daily_risk_used()
        weekly_risk_used = self._get_weekly_risk_used()
        
        max_daily_risk = portfolio_value * self.config.max_risk_per_day
        max_weekly_risk = portfolio_value * self.config.max_risk_per_week
        
        daily_available = max(0, max_daily_risk - daily_risk_used)
        weekly_available = max(0, max_weekly_risk - weekly_risk_used)
        
        available_risk = min(available_risk, daily_available, weekly_available)
        
        # Calculate adjusted position size
        risk_per_unit = self._get_risk_per_unit(symbol, side)
        if risk_per_unit <= 0:
            return 0
        
        adjusted_size = available_risk / risk_per_unit
        
        # Check leverage limit
        leverage = (adjusted_size * self._get_current_price(symbol)) / portfolio_value
        if leverage > self.config.max_leverage:
            adjusted_size = (self.config.max_leverage * portfolio_value) / self._get_current_price(symbol)
        
        return max(0, adjusted_size)
    
    def _get_total_risk(self) -> float:
        """Get total risk of all open positions."""
        total_risk = 0
        for position in self.positions.values():
            risk_per_unit = abs(position.entry_price - position.stop_loss)
            total_risk += position.position_size * risk_per_unit
        return total_risk
    
    def _get_daily_risk_used(self) -> float:
        """Get risk used today."""
        today = datetime.now().date()
        daily_risk = 0
        
        for trade in self.trade_history:
            if trade.get("timestamp", datetime.now()).date() == today:
                if trade.get("result") == "loss":
                    daily_risk += abs(trade.get("pnl", 0))
        
        return daily_risk
    
    def _get_weekly_risk_used(self) -> float:
        """Get risk used this week."""
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        weekly_risk = 0
        
        for trade in self.trade_history:
            if trade.get("timestamp", datetime.now()) >= week_start:
                if trade.get("result") == "loss":
                    weekly_risk += abs(trade.get("pnl", 0))
        
        return weekly_risk
    
    def _get_risk_per_unit(self, symbol: str, side: PositionSide) -> float:
        """Get risk per unit for a symbol."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            return abs(pos.entry_price - pos.stop_loss)
        
        # Default risk per unit (1% of price)
        price = self._get_current_price(symbol)
        return price * 0.01
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        # Placeholder - would get from market data service
        if symbol in self.positions:
            return self.positions[symbol].current_price
        return 100.0  # Default
    
    # ========================================================================
    # KELLY CRITERION AND OPTIMAL F
    # ========================================================================
    
    def _calculate_kelly_fraction(
        self,
        win_probability: float,
        risk_reward_ratio: float,
    ) -> float:
        """Calculate Kelly fraction."""
        if risk_reward_ratio <= 0:
            return 0
        
        q = 1 - win_probability
        kelly = (win_probability * risk_reward_ratio - q) / risk_reward_ratio
        
        # Apply constraints
        kelly = max(0, min(kelly, 0.5))
        
        return kelly
    
    def _calculate_optimal_f(
        self,
        trade_history: List[Dict[str, Any]],
        risk_reward_ratio: float,
    ) -> float:
        """Calculate Optimal F."""
        if not trade_history:
            return 0.1  # Default
        
        # Extract trade results
        results = []
        for trade in trade_history[-100:]:  # Last 100 trades
            if "pnl" in trade:
                results.append(trade["pnl"])
        
        if not results:
            return 0.1
        
        # Calculate optimal f using brute force
        best_f = 0
        best_twr = 0
        
        for f in np.arange(0.01, 0.5, 0.01):
            twr = 1
            for result in results:
                if result < 0:
                    twr *= (1 - f)
                else:
                    twr *= (1 + f * (result / abs(min(results, key=abs))))
            
            if twr > best_twr:
                best_twr = twr
                best_f = f
        
        return max(0.05, min(best_f, 0.3))
    
    # ========================================================================
    # RISK-REWARD OPTIMIZATION
    # ========================================================================
    
    def optimize_risk_reward(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        portfolio_value: float,
        market_data: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Optimize risk-reward ratio for a trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            portfolio_value: Total portfolio value
            market_data: Market data for optimization
            
        Returns:
            Optimized risk-reward parameters
        """
        if market_data is None:
            market_data = self._get_market_data(symbol)
        
        # Calculate base metrics
        risk_per_unit = abs(entry_price - stop_loss)
        reward_per_unit = abs(take_profit - entry_price)
        raw_ratio = reward_per_unit / risk_per_unit if risk_per_unit > 0 else 0
        
        # Get volatility
        volatility = self._get_volatility(symbol)
        
        # Optimize stop loss
        optimized_stop = self._optimize_stop_loss(
            symbol,
            entry_price,
            market_data,
            volatility,
        )
        
        # Optimize take profit
        optimized_take = self._optimize_take_profit(
            symbol,
            entry_price,
            market_data,
            volatility,
        )
        
        # Calculate optimized ratio
        opt_risk = abs(entry_price - optimized_stop)
        opt_reward = abs(optimized_take - entry_price)
        opt_ratio = opt_reward / opt_risk if opt_risk > 0 else 0
        
        # Compare and select best
        if opt_ratio > raw_ratio:
            use_stop = optimized_stop
            use_take = optimized_take
            use_ratio = opt_ratio
        else:
            use_stop = stop_loss
            use_take = take_profit
            use_ratio = raw_ratio
        
        # Calculate position size
        position_result = self.calculate_position_size(
            symbol,
            entry_price,
            use_stop,
            use_take,
            portfolio_value,
            volatility,
            None,
            None,
        )
        
        return {
            "entry_price": entry_price,
            "stop_loss": use_stop,
            "take_profit": use_take,
            "risk_reward_ratio": use_ratio,
            "position_size": position_result["position_size"],
            "risk_amount": position_result["risk_amount"],
            "reward_amount": position_result["reward_amount"],
            "volatility": volatility,
            "optimized_stop": optimized_stop,
            "optimized_take": optimized_take,
            "original_stop": stop_loss,
            "original_take": take_profit,
            "original_ratio": raw_ratio,
            "improvement": (use_ratio - raw_ratio) / raw_ratio if raw_ratio > 0 else 0,
        }
    
    def _optimize_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        market_data: pd.DataFrame,
        volatility: float,
    ) -> float:
        """Optimize stop loss level."""
        if market_data.empty:
            return entry_price * 0.98  # 2% stop
        
        # Calculate ATR
        atr = self._calculate_atr(market_data, 14)
        
        # Calculate support levels
        support = self._calculate_support_levels(market_data, entry_price)
        
        # Use ATR-based stop with support validation
        atr_stop = entry_price - atr * 1.5
        
        # Find nearest support below entry
        support_levels = [s for s in support if s < entry_price]
        if support_levels:
            nearest_support = max(support_levels)
            # Use the more conservative of ATR stop and support
            stop_loss = max(atr_stop, nearest_support)
        else:
            stop_loss = atr_stop
        
        # Adjust for volatility
        volatility_multiplier = 1 + (volatility - 0.02) * 5
        volatility_multiplier = max(0.8, min(1.5, volatility_multiplier))
        
        stop_loss = entry_price - (entry_price - stop_loss) * volatility_multiplier
        
        return max(entry_price * 0.95, min(entry_price * 0.99, stop_loss))
    
    def _optimize_take_profit(
        self,
        symbol: str,
        entry_price: float,
        market_data: pd.DataFrame,
        volatility: float,
    ) -> float:
        """Optimize take profit level."""
        if market_data.empty:
            return entry_price * 1.04  # 4% target
        
        # Calculate resistance levels
        resistance = self._calculate_resistance_levels(market_data, entry_price)
        
        # Use volatility-based target
        vol_target = entry_price + entry_price * volatility * 2
        
        # Find nearest resistance above entry
        resistance_levels = [r for r in resistance if r > entry_price]
        if resistance_levels:
            nearest_resistance = min(resistance_levels)
            # Use the more conservative of volatility target and resistance
            take_profit = min(vol_target, nearest_resistance)
        else:
            take_profit = vol_target
        
        # Adjust for volatility
        volatility_multiplier = 1 + (volatility - 0.02) * 3
        volatility_multiplier = max(0.8, min(1.5, volatility_multiplier))
        
        take_profit = entry_price + (take_profit - entry_price) * volatility_multiplier
        
        return max(entry_price * 1.01, min(entry_price * 1.15, take_profit))
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if data.empty or len(data) < period:
            return 0.02  # Default 2%
        
        high = data['high'] if 'high' in data.columns else data['close'] * 1.01
        low = data['low'] if 'low' in data.columns else data['close'] * 0.99
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        
        return atr / close.iloc[-1]  # Return as percentage
    
    def _calculate_support_levels(
        self,
        data: pd.DataFrame,
        current_price: float,
    ) -> List[float]:
        """Calculate support levels."""
        if data.empty:
            return []
        
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        
        # Find pivot lows
        pivots = []
        for i in range(2, len(close) - 2):
            if (close.iloc[i] < close.iloc[i-1] and 
                close.iloc[i] < close.iloc[i-2] and
                close.iloc[i] < close.iloc[i+1] and
                close.iloc[i] < close.iloc[i+2]):
                pivots.append(close.iloc[i])
        
        # Return unique support levels within 5% of current price
        supports = []
        for pivot in pivots:
            if 0.95 * current_price < pivot < 1.05 * current_price:
                supports.append(pivot)
        
        return sorted(supports)
    
    def _calculate_resistance_levels(
        self,
        data: pd.DataFrame,
        current_price: float,
    ) -> List[float]:
        """Calculate resistance levels."""
        if data.empty:
            return []
        
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        
        # Find pivot highs
        pivots = []
        for i in range(2, len(close) - 2):
            if (close.iloc[i] > close.iloc[i-1] and 
                close.iloc[i] > close.iloc[i-2] and
                close.iloc[i] > close.iloc[i+1] and
                close.iloc[i] > close.iloc[i+2]):
                pivots.append(close.iloc[i])
        
        # Return unique resistance levels within 5% of current price
        resistances = []
        for pivot in pivots:
            if 0.95 * current_price < pivot < 1.05 * current_price:
                resistances.append(pivot)
        
        return sorted(resistances)
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
        side: PositionSide,
        position_size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        trailing_stop: Optional[float] = None,
    ) -> PositionRiskReward:
        """
        Update or create a position with risk-reward management.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            side: Position side
            position_size: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            trailing_stop: Trailing stop price
            
        Returns:
            Updated position
        """
        # Calculate PNL
        if side == PositionSide.LONG:
            unrealized_pnl = (current_price - entry_price) * position_size
        else:
            unrealized_pnl = (entry_price - current_price) * position_size
        
        # Calculate risk-reward ratio
        risk_per_unit = abs(entry_price - stop_loss)
        if side == PositionSide.LONG:
            reward_per_unit = take_profit - entry_price
        else:
            reward_per_unit = entry_price - take_profit
        
        risk_reward_ratio = reward_per_unit / risk_per_unit if risk_per_unit > 0 else 0
        
        # Calculate current risk-reward ratio
        if side == PositionSide.LONG:
            current_risk = current_price - stop_loss
            current_reward = take_profit - current_price
        else:
            current_risk = stop_loss - current_price
            current_reward = current_price - take_profit
        
        current_risk_reward = current_reward / current_risk if current_risk > 0 else 0
        
        # Update or create position
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price
            position.unrealized_pnl = unrealized_pnl
            position.current_risk_reward_ratio = current_risk_reward
            
            # Update trailing stop
            if trailing_stop:
                if position.trailing_stop is None or trailing_stop > position.trailing_stop:
                    position.trailing_stop = trailing_stop
            
            # Check breakeven stop
            if unrealized_pnl > 0 and position.breakeven_stop is None:
                position.breakeven_stop = entry_price
            
        else:
            position = PositionRiskReward(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=position_size,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=0.0,
                risk_reward_ratio=risk_reward_ratio,
                current_risk_reward_ratio=current_risk_reward,
                trailing_stop=trailing_stop,
                breakeven_stop=entry_price if unrealized_pnl > 0 else None,
            )
            self.positions[symbol] = position
        
        # Update metrics cache
        self._update_metrics_cache(symbol, position)
        
        return position
    
    def _update_metrics_cache(
        self,
        symbol: str,
        position: PositionRiskReward,
    ) -> None:
        """Update metrics cache for a position."""
        risk_per_unit = abs(position.entry_price - position.stop_loss)
        
        if position.side == PositionSide.LONG:
            reward_per_unit = position.take_profit - position.entry_price
        else:
            reward_per_unit = position.entry_price - position.take_profit
        
        self.metrics_cache[symbol] = RiskRewardMetrics(
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            risk_amount=position.position_size * risk_per_unit,
            reward_amount=position.position_size * reward_per_unit,
            risk_reward_ratio=position.risk_reward_ratio,
            position_size=position.position_size,
            leverage=(position.position_size * position.entry_price) / 100000,  # Assuming 100k portfolio
            expected_value=position.unrealized_pnl * position.current_risk_reward_ratio,
            win_probability=self._estimate_win_probability(symbol),
            expected_risk=risk_per_unit * position.position_size,
            expected_reward=reward_per_unit * position.position_size,
            sharpe_contribution=position.unrealized_pnl / (position.position_size * position.entry_price),
            var_contribution=risk_per_unit / position.entry_price,
            risk_adjusted_return=position.unrealized_pnl / risk_per_unit if risk_per_unit > 0 else 0,
        )
    
    def get_position_decision(
        self,
        symbol: str,
        current_price: float,
        portfolio_value: float,
    ) -> RiskRewardDecision:
        """
        Get risk-reward decision for a position.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            portfolio_value: Total portfolio value
            
        Returns:
            Risk-reward decision
        """
        if symbol not in self.positions:
            return self._get_empty_decision("No position found")
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # Calculate metrics
        if position.side == PositionSide.LONG:
            risk_to_stop = (current_price - position.stop_loss) / position.entry_price
            reward_to_target = (position.take_profit - current_price) / position.entry_price
        else:
            risk_to_stop = (position.stop_loss - current_price) / position.entry_price
            reward_to_target = (current_price - position.take_profit) / position.entry_price
        
        current_ratio = reward_to_target / risk_to_stop if risk_to_stop > 0 else 0
        
        # Decision logic
        decision = RiskRewardDecision(
            action="hold",
            position_size=position.position_size,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            risk_reward_ratio=current_ratio,
            confidence=0.5,
            reasoning="Holding position",
            metrics=self.metrics_cache.get(symbol, RiskRewardMetrics(
                entry_price=0,
                stop_loss=0,
                take_profit=0,
                risk_amount=0,
                reward_amount=0,
                risk_reward_ratio=0,
                position_size=0,
                leverage=0,
                expected_value=0,
                win_probability=0,
                expected_risk=0,
                expected_reward=0,
                sharpe_contribution=0,
                var_contribution=0,
                risk_adjusted_return=0,
            )),
            expected_pnl=position.unrealized_pnl,
            probability_of_success=self._estimate_win_probability(symbol),
            expected_shortfall=position.position_size * abs(position.entry_price - position.stop_loss),
            optimal_position_size=self.calculate_position_size(
                symbol,
                current_price,
                position.stop_loss,
                position.take_profit,
                portfolio_value,
            )["position_size"],
            adjusted_position_size=position.position_size,
        )
        
        # Check for trailing stop update
        if position.trailing_stop:
            if position.side == PositionSide.LONG:
                if current_price > position.trailing_stop:
                    new_trailing = max(position.trailing_stop, current_price * 0.98)
                    if new_trailing > position.trailing_stop:
                        position.trailing_stop = new_trailing
                        decision.stop_loss = new_trailing
                        decision.action = "update_stop"
                        decision.reasoning = f"Trailing stop updated to {new_trailing:.2f}"
            else:
                if current_price < position.trailing_stop:
                    new_trailing = min(position.trailing_stop, current_price * 1.02)
                    if new_trailing < position.trailing_stop:
                        position.trailing_stop = new_trailing
                        decision.stop_loss = new_trailing
                        decision.action = "update_stop"
                        decision.reasoning = f"Trailing stop updated to {new_trailing:.2f}"
        
        # Check for take profit adjustment
        if position.unrealized_pnl > 0:
            # Consider partial take profit
            if position.unrealized_pnl > position.position_size * position.entry_price * 0.05:
                # Take partial profits
                take_profit_size = position.position_size * 0.25
                decision.position_size = position.position_size - take_profit_size
                decision.action = "partial_take_profit"
                decision.reasoning = f"Taking partial profit of {take_profit_size:.2f} units"
                decision.confidence = 0.7
        
        # Check for scaling
        if position.unrealized_pnl < 0 and position.side == PositionSide.LONG:
            if current_price > position.entry_price * 0.98:
                # Consider scaling in
                scale_size = position.position_size * 0.5
                decision.position_size = position.position_size + scale_size
                decision.action = "scale_in"
                decision.reasoning = f"Scaling in with {scale_size:.2f} units"
                decision.confidence = 0.6
        
        # Check for exit conditions
        if current_ratio < self.config.min_reward_ratio:
            if position.unrealized_pnl > 0:
                # Exit on weakening ratio
                decision.action = "exit"
                decision.reasoning = f"Risk-reward ratio {current_ratio:.2f} below minimum {self.config.min_reward_ratio}"
                decision.confidence = 0.8
            else:
                # Tighten stop
                new_stop = current_price * 0.995 if position.side == PositionSide.LONG else current_price * 1.005
                decision.stop_loss = new_stop
                decision.action = "tighten_stop"
                decision.reasoning = f"Tightening stop to {new_stop:.2f} due to poor risk-reward"
                decision.confidence = 0.7
        
        return decision
    
    def _get_empty_decision(self, reason: str) -> RiskRewardDecision:
        """Get an empty decision."""
        return RiskRewardDecision(
            action="no_action",
            position_size=0,
            stop_loss=0,
            take_profit=0,
            risk_reward_ratio=0,
            confidence=0,
            reasoning=reason,
            metrics=RiskRewardMetrics(
                entry_price=0,
                stop_loss=0,
                take_profit=0,
                risk_amount=0,
                reward_amount=0,
                risk_reward_ratio=0,
                position_size=0,
                leverage=0,
                expected_value=0,
                win_probability=0,
                expected_risk=0,
                expected_reward=0,
                sharpe_contribution=0,
                var_contribution=0,
                risk_adjusted_return=0,
            ),
            expected_pnl=0,
            probability_of_success=0,
            expected_shortfall=0,
            optimal_position_size=0,
            adjusted_position_size=0,
        )
    
    # ========================================================================
    # RISK-REWARD STATISTICS
    # ========================================================================
    
    def update_stats(self, trade: Dict[str, Any]) -> None:
        """
        Update risk-reward statistics with a new trade.
        
        Args:
            trade: Trade data
        """
        self.trade_history.append(trade)
        
        # Update counts
        self.stats.total_trades += 1
        if trade.get("result") == "win":
            self.stats.winning_trades += 1
            self.stats.average_win = (
                (self.stats.average_win * (self.stats.winning_trades - 1) + trade.get("pnl", 0)) /
                self.stats.winning_trades
            )
        else:
            self.stats.losing_trades += 1
            self.stats.average_loss = (
                (self.stats.average_loss * (self.stats.losing_trades - 1) + abs(trade.get("pnl", 0))) /
                self.stats.losing_trades
            )
        
        # Calculate win rate
        self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades if self.stats.total_trades > 0 else 0
        
        # Calculate profit factor
        total_wins = self.stats.winning_trades * self.stats.average_win
        total_losses = self.stats.losing_trades * self.stats.average_loss
        self.stats.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Update average risk-reward
        if "risk_reward_ratio" in trade:
            current_avg = self.stats.average_risk_reward
            self.stats.average_risk_reward = (
                (current_avg * (self.stats.total_trades - 1) + trade["risk_reward_ratio"]) /
                self.stats.total_trades
            )
        
        # Update max consecutive losses
        if trade.get("result") == "loss":
            self.stats.max_consecutive_losses += 1
        else:
            self.stats.max_consecutive_losses = 0
        
        # Update max drawdown
        if "drawdown" in trade:
            self.stats.max_drawdown = max(self.stats.max_drawdown, trade.get("drawdown", 0))
        
        # Calculate Kelly percentage
        if self.stats.total_trades > 10:
            self.stats.kelly_percentage = self._calculate_kelly_fraction(
                self.stats.win_rate,
                self.stats.average_risk_reward,
            )
        
        # Calculate Optimal F
        if self.stats.total_trades > 20:
            self.stats.optimal_f = self._calculate_optimal_f(
                self.trade_history,
                self.stats.average_risk_reward,
            )
        
        # Update performance history
        self.performance_history.append({
            "timestamp": datetime.now().isoformat(),
            "total_trades": self.stats.total_trades,
            "win_rate": self.stats.win_rate,
            "profit_factor": self.stats.profit_factor,
            "average_risk_reward": self.stats.average_risk_reward,
            "max_drawdown": self.stats.max_drawdown,
        })
        
        logger.info(f"Updated stats: Win Rate={self.stats.win_rate:.2%}, "
                   f"Profit Factor={self.stats.profit_factor:.2f}, "
                   f"Avg R/R={self.stats.average_risk_reward:.2f}")
    
    def get_stats(self) -> RiskRewardStats:
        """Get current risk-reward statistics."""
        return self.stats
    
    # ========================================================================
    # VOLATILITY AND CORRELATION
    # ========================================================================
    
    def _get_volatility(self, symbol: str) -> float:
        """Get volatility for a symbol."""
        if symbol in self._volatility_cache:
            return self._volatility_cache[symbol]
        
        # Get market data
        data = self._get_market_data(symbol)
        if data.empty:
            return 0.02  # Default 2%
        
        # Calculate volatility
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        returns = close.pct_change().dropna()
        
        if len(returns) < 2:
            return 0.02
        
        volatility = returns.std() * np.sqrt(252)  # Annualized
        self._volatility_cache[symbol] = volatility
        
        return volatility
    
    def _get_correlation(self, symbol: str) -> float:
        """Get correlation with portfolio."""
        if symbol in self._correlation_cache:
            return self._correlation_cache[symbol]
        
        # Get market data
        data = self._get_market_data(symbol)
        if data.empty:
            return 0.0
        
        # Calculate correlation with market (use first symbol as market)
        market_symbol = "SPY"  # Default market proxy
        market_data = self._get_market_data(market_symbol)
        
        if market_data.empty or len(data) < 2 or len(market_data) < 2:
            return 0.0
        
        # Align data
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        market_close = market_data['close'] if 'close' in market_data.columns else market_data.iloc[:, 0]
        
        returns = close.pct_change().dropna()
        market_returns = market_close.pct_change().dropna()
        
        # Align indices
        common_idx = returns.index.intersection(market_returns.index)
        if len(common_idx) < 5:
            return 0.0
        
        returns = returns.loc[common_idx]
        market_returns = market_returns.loc[common_idx]
        
        correlation = returns.corr(market_returns)
        self._correlation_cache[symbol] = correlation
        
        return correlation
    
    def _get_market_data(self, symbol: str) -> pd.DataFrame:
        """Get market data for a symbol."""
        # Placeholder - would get from market data service
        if symbol in self._market_data_cache:
            return self._market_data_cache[symbol]
        
        # Generate mock data
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, 100)))
        
        data = pd.DataFrame({
            'open': close * (1 + np.random.normal(0, 0.005, 100)),
            'high': close * (1 + np.random.normal(0.01, 0.01, 100)),
            'low': close * (1 - np.random.normal(0.01, 0.01, 100)),
            'close': close,
            'volume': np.random.lognormal(10, 2, 100),
        }, index=dates)
        
        self._market_data_cache[symbol] = data
        return data
    
    def _estimate_win_probability(self, symbol: str) -> float:
        """Estimate win probability for a symbol."""
        # Placeholder - would use AI or historical analysis
        if self.stats.total_trades > 10:
            return self.stats.win_rate
        return 0.5  # Default
    
    # ========================================================================
    # MARKET REGIME DETECTION
    # ========================================================================
    
    def _detect_market_regime(self) -> str:
        """Detect current market regime."""
        # Placeholder - would use market data service
        # For now, return based on simple logic
        data = self._get_market_data("SPY")
        if data.empty:
            return "sideways"
        
        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]
        returns = close.pct_change().dropna()
        
        if len(returns) < 20:
            return "sideways"
        
        volatility = returns.std() * np.sqrt(252)
        trend = close.iloc[-1] / close.iloc[-20] - 1
        
        if volatility > 0.3:
            return "high_volatility"
        elif volatility < 0.1:
            return "low_volatility"
        elif trend > 0.05:
            return "bull"
        elif trend < -0.05:
            return "bear"
        else:
            return "sideways"
    
    # ========================================================================
    # CLEANUP AND MANAGEMENT
    # ========================================================================
    
    def close_position(self, symbol: str, final_price: float) -> Dict[str, Any]:
        """
        Close a position and record final PNL.
        
        Args:
            symbol: Trading symbol
            final_price: Final price
            
        Returns:
            Trade record
        """
        if symbol not in self.positions:
            return {"error": "Position not found"}
        
        position = self.positions[symbol]
        
        # Calculate final PNL
        if position.side == PositionSide.LONG:
            pnl = (final_price - position.entry_price) * position.position_size
        else:
            pnl = (position.entry_price - final_price) * position.position_size
        
        # Determine result
        result = "win" if pnl > 0 else "loss"
        
        # Create trade record
        trade = {
            "symbol": symbol,
            "side": position.side.value,
            "entry_price": position.entry_price,
            "exit_price": final_price,
            "position_size": position.position_size,
            "pnl": pnl,
            "result": result,
            "risk_reward_ratio": position.risk_reward_ratio,
            "holding_period": (datetime.now() - position.entry_price).days,  # Approximation
            "timestamp": datetime.now(),
            "drawdown": position.max_drawdown if hasattr(position, 'max_drawdown') else 0,
        }
        
        # Update stats
        self.update_stats(trade)
        
        # Remove position
        del self.positions[symbol]
        
        return trade
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of all positions.
        
        Returns:
            Position summary
        """
        total_value = 0
        total_risk = 0
        total_reward = 0
        
        for position in self.positions.values():
            total_value += position.position_size * position.current_price
            total_risk += position.position_size * abs(position.entry_price - position.stop_loss)
            total_reward += position.position_size * abs(position.take_profit - position.entry_price)
        
        return {
            "total_positions": len(self.positions),
            "total_value": total_value,
            "total_risk": total_risk,
            "total_reward": total_reward,
            "average_risk_reward": total_reward / total_risk if total_risk > 0 else 0,
            "risk_percentage": total_risk / 100000,  # Assuming 100k portfolio
            "positions": {
                symbol: {
                    "side": pos.side.value,
                    "size": pos.position_size,
                    "entry": pos.entry_price,
                    "current": pos.current_price,
                    "stop": pos.stop_loss,
                    "target": pos.take_profit,
                    "pnl": pos.unrealized_pnl,
                    "risk_reward": pos.current_risk_reward_ratio,
                    "trailing_stop": pos.trailing_stop,
                }
                for symbol, pos in self.positions.items()
            }
        }
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._market_data_cache.clear()
        self._volatility_cache.clear()
        self._correlation_cache.clear()
        self.metrics_cache.clear()
        logger.info("Cache cleared")
    
    def reset_stats(self) -> None:
        """Reset all statistics."""
        self.stats = RiskRewardStats(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            average_win=0.0,
            average_loss=0.0,
            profit_factor=0.0,
            average_risk_reward=0.0,
            average_holding_period=0.0,
            max_consecutive_losses=0,
            max_drawdown=0.0,
            recovery_factor=0.0,
            risk_adjusted_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            kelly_percentage=0.0,
            optimal_f=0.0,
        )
        self.trade_history.clear()
        self.performance_history.clear()
        logger.info("Stats reset")


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_risk_reward_manager(
    config: Optional[Dict[str, Any]] = None,
    position_sizer: Optional[PositionSizer] = None,
    stop_loss_manager: Optional[StopLossManager] = None,
    take_profit_manager: Optional[TakeProfitManager] = None,
) -> RiskRewardManager:
    """
    Factory function to create a RiskRewardManager.
    
    Args:
        config: Configuration dictionary
        position_sizer: Position sizer instance
        stop_loss_manager: Stop loss manager instance
        take_profit_manager: Take profit manager instance
        
    Returns:
        Configured RiskRewardManager
    """
    if config is None:
        config = {}
    
    risk_config = RiskRewardConfig(
        risk_reward_type=RiskRewardType(config.get("risk_reward_type", "dynamic")),
        risk_level=RiskLevel(config.get("risk_level", "moderate")),
        max_risk_per_trade=config.get("max_risk_per_trade", 0.02),
        max_risk_per_day=config.get("max_risk_per_day", 0.05),
        max_risk_per_week=config.get("max_risk_per_week", 0.10),
        max_drawdown=config.get("max_drawdown", 0.20),
        min_reward_ratio=config.get("min_reward_ratio", 1.5),
        target_reward_ratio=config.get("target_reward_ratio", 2.0),
        max_leverage=config.get("max_leverage", 10.0),
        kelly_fraction=config.get("kelly_fraction", 0.25),
        volatility_lookback=config.get("volatility_lookback", 20),
        correlation_lookback=config.get("correlation_lookback", 60),
        max_correlation=config.get("max_correlation", 0.7),
        position_sizing_method=config.get("position_sizing_method", "fixed_fractional"),
        adaptive_threshold=config.get("adaptive_threshold", 0.1),
    )
    
    return RiskRewardManager(
        config=risk_config,
        position_sizer=position_sizer,
        stop_loss_manager=stop_loss_manager,
        take_profit_manager=take_profit_manager,
    )
