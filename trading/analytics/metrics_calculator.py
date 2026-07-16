"""
NEXUS AI TRADING SYSTEM - Metrics Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced trading metrics calculation with comprehensive performance,
risk, and statistical measures for strategy evaluation.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, skew, kurtosis, jarque_bera
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import warnings
import logging
from decimal import Decimal
from pathlib import Path
import json

from nexus.shared.types.trading import Trade, TradeDirection, TradeStatus
from nexus.shared.utilities.logger import Logger

logger = Logger(__name__)


class MetricCategory(Enum):
    """Categories of trading metrics"""
    PERFORMANCE = "performance"
    RISK = "risk"
    RISK_ADJUSTED = "risk_adjusted"
    STATISTICAL = "statistical"
    TRADE = "trade"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"
    CORRELATION = "correlation"
    MOMENTUM = "momentum"


@dataclass
class PerformanceMetrics:
    """Performance-related metrics"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    cumulative_return: List[float] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    yearly_returns: Dict[str, float] = field(default_factory=dict)
    best_month: Dict[str, Any] = field(default_factory=dict)
    worst_month: Dict[str, Any] = field(default_factory=dict)
    best_year: Dict[str, Any] = field(default_factory=dict)
    worst_year: Dict[str, Any] = field(default_factory=dict)
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "monthly_returns": self.monthly_returns,
            "yearly_returns": self.yearly_returns,
            "best_month": self.best_month,
            "worst_month": self.worst_month,
            "best_year": self.best_year,
            "worst_year": self.worst_year,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses
        }


@dataclass
class RiskMetrics:
    """Risk-related metrics"""
    # Value at Risk
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    
    # Volatility
    volatility_daily: float = 0.0
    volatility_weekly: float = 0.0
    volatility_monthly: float = 0.0
    volatility_annualized: float = 0.0
    
    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    average_drawdown: float = 0.0
    average_drawdown_duration: int = 0
    max_drawdown_date: Optional[datetime] = None
    recovery_date: Optional[datetime] = None
    
    # Risk ratios
    downside_deviation: float = 0.0
    upside_potential: float = 0.0
    risk_of_ruin: float = 0.0
    probability_of_loss: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "volatility_daily": self.volatility_daily,
            "volatility_weekly": self.volatility_weekly,
            "volatility_monthly": self.volatility_monthly,
            "volatility_annualized": self.volatility_annualized,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "average_drawdown": self.average_drawdown,
            "average_drawdown_duration": self.average_drawdown_duration,
            "max_drawdown_date": self.max_drawdown_date.isoformat() if self.max_drawdown_date else None,
            "recovery_date": self.recovery_date.isoformat() if self.recovery_date else None,
            "downside_deviation": self.downside_deviation,
            "upside_potential": self.upside_potential,
            "risk_of_ruin": self.risk_of_ruin,
            "probability_of_loss": self.probability_of_loss
        }


@dataclass
class RiskAdjustedMetrics:
    """Risk-adjusted performance metrics"""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    tail_ratio: float = 0.0
    pain_index: float = 0.0
    martin_ratio: float = 0.0
    ulcer_index: float = 0.0
    sterling_ratio: float = 0.0
    burke_ratio: float = 0.0
    gain_pain_ratio: float = 0.0
    recovery_factor: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "omega_ratio": self.omega_ratio,
            "tail_ratio": self.tail_ratio,
            "pain_index": self.pain_index,
            "martin_ratio": self.martin_ratio,
            "ulcer_index": self.ulcer_index,
            "sterling_ratio": self.sterling_ratio,
            "burke_ratio": self.burke_ratio,
            "gain_pain_ratio": self.gain_pain_ratio,
            "recovery_factor": self.recovery_factor
        }


@dataclass
class TradeMetrics:
    """Trade-level metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    win_rate: float = 0.0
    loss_rate: float = 0.0
    break_even_rate: float = 0.0
    
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    
    average_win: float = 0.0
    average_loss: float = 0.0
    average_trade: float = 0.0
    average_win_loss_ratio: float = 0.0
    
    max_win: float = 0.0
    max_loss: float = 0.0
    max_win_loss_ratio: float = 0.0
    
    expected_value: float = 0.0
    expectancy_ratio: float = 0.0
    
    average_trade_duration: float = 0.0
    average_holding_period: float = 0.0
    trade_frequency: float = 0.0
    
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_profit: float = 0.0
    short_profit: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate": self.win_rate,
            "loss_rate": self.loss_rate,
            "break_even_rate": self.break_even_rate,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "net_profit": self.net_profit,
            "profit_factor": self.profit_factor,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "average_trade": self.average_trade,
            "average_win_loss_ratio": self.average_win_loss_ratio,
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "max_win_loss_ratio": self.max_win_loss_ratio,
            "expected_value": self.expected_value,
            "expectancy_ratio": self.expectancy_ratio,
            "average_trade_duration": self.average_trade_duration,
            "average_holding_period": self.average_holding_period,
            "trade_frequency": self.trade_frequency,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
            "long_win_rate": self.long_win_rate,
            "short_win_rate": self.short_win_rate,
            "long_profit": self.long_profit,
            "short_profit": self.short_profit
        }


@dataclass
class StatisticalMetrics:
    """Statistical metrics for returns distribution"""
    mean_return: float = 0.0
    median_return: float = 0.0
    std_deviation: float = 0.0
    variance: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    # Distribution tests
    jarque_bera_stat: float = 0.0
    jarque_bera_pvalue: float = 0.0
    is_normal: bool = False
    
    # Confidence intervals
    ci_95_lower: float = 0.0
    ci_95_upper: float = 0.0
    ci_99_lower: float = 0.0
    ci_99_upper: float = 0.0
    
    # Percentiles
    percentile_1: float = 0.0
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_50: float = 0.0
    percentile_75: float = 0.0
    percentile_95: float = 0.0
    percentile_99: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "mean_return": self.mean_return,
            "median_return": self.median_return,
            "std_deviation": self.std_deviation,
            "variance": self.variance,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "jarque_bera_stat": self.jarque_bera_stat,
            "jarque_bera_pvalue": self.jarque_bera_pvalue,
            "is_normal": self.is_normal,
            "ci_95_lower": self.ci_95_lower,
            "ci_95_upper": self.ci_95_upper,
            "ci_99_lower": self.ci_99_lower,
            "ci_99_upper": self.ci_99_upper,
            "percentile_1": self.percentile_1,
            "percentile_5": self.percentile_5,
            "percentile_25": self.percentile_25,
            "percentile_50": self.percentile_50,
            "percentile_75": self.percentile_75,
            "percentile_95": self.percentile_95,
            "percentile_99": self.percentile_99
        }


@dataclass
class VolatilityMetrics:
    """Volatility-related metrics"""
    historical_volatility: float = 0.0
    implied_volatility: Optional[float] = None
    
    # Rolling volatility
    rolling_volatility_20: List[float] = field(default_factory=list)
    rolling_volatility_50: List[float] = field(default_factory=list)
    rolling_volatility_100: List[float] = field(default_factory=list)
    
    # Volatility of volatility
    vol_of_vol: float = 0.0
    volatility_skew: float = 0.0
    volatility_kurtosis: float = 0.0
    
    # Extreme volatility
    max_volatility: float = 0.0
    min_volatility: float = 0.0
    volatility_percentile: float = 0.0
    
    # Volatility regimes
    high_volatility_periods: int = 0
    low_volatility_periods: int = 0
    volatility_regime: str = "normal"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "historical_volatility": self.historical_volatility,
            "implied_volatility": self.implied_volatility,
            "vol_of_vol": self.vol_of_vol,
            "volatility_skew": self.volatility_skew,
            "volatility_kurtosis": self.volatility_kurtosis,
            "max_volatility": self.max_volatility,
            "min_volatility": self.min_volatility,
            "volatility_percentile": self.volatility_percentile,
            "high_volatility_periods": self.high_volatility_periods,
            "low_volatility_periods": self.low_volatility_periods,
            "volatility_regime": self.volatility_regime
        }


@dataclass
class DrawdownMetrics:
    """Drawdown-specific metrics"""
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    average_drawdown: float = 0.0
    average_drawdown_duration: int = 0
    median_drawdown: float = 0.0
    
    # Drawdown periods
    drawdown_periods: List[Dict[str, Any]] = field(default_factory=list)
    current_drawdown: float = 0.0
    current_drawdown_duration: int = 0
    
    # Drawdown distribution
    drawdown_percentiles: Dict[str, float] = field(default_factory=dict)
    max_drawdown_date: Optional[datetime] = None
    recovery_date: Optional[datetime] = None
    
    # Drawdown severity
    severe_drawdowns: int = 0
    moderate_drawdowns: int = 0
    mild_drawdowns: int = 0
    
    # Recovery metrics
    average_recovery_time: float = 0.0
    max_recovery_time: float = 0.0
    recovery_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "average_drawdown": self.average_drawdown,
            "average_drawdown_duration": self.average_drawdown_duration,
            "median_drawdown": self.median_drawdown,
            "current_drawdown": self.current_drawdown,
            "current_drawdown_duration": self.current_drawdown_duration,
            "severe_drawdowns": self.severe_drawdowns,
            "moderate_drawdowns": self.moderate_drawdowns,
            "mild_drawdowns": self.mild_drawdowns,
            "average_recovery_time": self.average_recovery_time,
            "max_recovery_time": self.max_recovery_time,
            "recovery_rate": self.recovery_rate,
            "max_drawdown_date": self.max_drawdown_date.isoformat() if self.max_drawdown_date else None,
            "recovery_date": self.recovery_date.isoformat() if self.recovery_date else None
        }


@dataclass
class CorrelationMetrics:
    """Correlation and dependency metrics"""
    # Market correlation
    beta_to_market: Optional[float] = None
    alpha_to_market: Optional[float] = None
    r_squared: Optional[float] = None
    
    # Asset correlations
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    average_correlation: float = 0.0
    
    # Factor exposures
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    
    # Diversification
    diversification_ratio: float = 0.0
    concentration_ratio: float = 0.0
    effective_number_of_bets: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "beta_to_market": self.beta_to_market,
            "alpha_to_market": self.alpha_to_market,
            "r_squared": self.r_squared,
            "average_correlation": self.average_correlation,
            "diversification_ratio": self.diversification_ratio,
            "concentration_ratio": self.concentration_ratio,
            "effective_number_of_bets": self.effective_number_of_bets
        }


@dataclass
class MomentumMetrics:
    """Momentum and trend metrics"""
    # Momentum indicators
    momentum_score: float = 0.0
    relative_strength: float = 0.0
    price_momentum: float = 0.0
    volume_momentum: float = 0.0
    
    # Trend indicators
    trend_strength: float = 0.0
    trend_direction: str = "neutral"
    adx_value: Optional[float] = None
    
    # Rate of change
    roc_1: float = 0.0
    roc_5: float = 0.0
    roc_10: float = 0.0
    roc_20: float = 0.0
    
    # Moving average metrics
    ma_difference: float = 0.0
    ma_cross_signal: str = "neutral"
    distance_from_ma: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "momentum_score": self.momentum_score,
            "relative_strength": self.relative_strength,
            "price_momentum": self.price_momentum,
            "volume_momentum": self.volume_momentum,
            "trend_strength": self.trend_strength,
            "trend_direction": self.trend_direction,
            "adx_value": self.adx_value,
            "roc_1": self.roc_1,
            "roc_5": self.roc_5,
            "roc_10": self.roc_10,
            "roc_20": self.roc_20,
            "ma_difference": self.ma_difference,
            "ma_cross_signal": self.ma_cross_signal,
            "distance_from_ma": self.distance_from_ma
        }


@dataclass
class CompleteMetrics:
    """Complete metrics collection"""
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    risk: RiskMetrics = field(default_factory=RiskMetrics)
    risk_adjusted: RiskAdjustedMetrics = field(default_factory=RiskAdjustedMetrics)
    trade: TradeMetrics = field(default_factory=TradeMetrics)
    statistical: StatisticalMetrics = field(default_factory=StatisticalMetrics)
    volatility: VolatilityMetrics = field(default_factory=VolatilityMetrics)
    drawdown: DrawdownMetrics = field(default_factory=DrawdownMetrics)
    correlation: CorrelationMetrics = field(default_factory=CorrelationMetrics)
    momentum: MomentumMetrics = field(default_factory=MomentumMetrics)
    
    # Overall scores
    overall_score: float = 0.0
    risk_score: float = 0.0
    performance_score: float = 0.0
    consistency_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "performance": self.performance.to_dict(),
            "risk": self.risk.to_dict(),
            "risk_adjusted": self.risk_adjusted.to_dict(),
            "trade": self.trade.to_dict(),
            "statistical": self.statistical.to_dict(),
            "volatility": self.volatility.to_dict(),
            "drawdown": self.drawdown.to_dict(),
            "correlation": self.correlation.to_dict(),
            "momentum": self.momentum.to_dict(),
            "overall_score": self.overall_score,
            "risk_score": self.risk_score,
            "performance_score": self.performance_score,
            "consistency_score": self.consistency_score
        }


class MetricsCalculator:
    """
    Advanced metrics calculator for trading strategies.
    Computes comprehensive performance, risk, and statistical metrics.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        annualization_factor: int = 252,
        confidence_level: float = 0.95
    ):
        """
        Initialize the metrics calculator.
        
        Args:
            risk_free_rate: Risk-free rate for calculations
            annualization_factor: Number of periods in a year
            confidence_level: Confidence level for VaR calculations
        """
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.confidence_level = confidence_level
        self._logger = Logger(__name__)
    
    def calculate_all_metrics(
        self,
        trades: List[Trade],
        returns: Optional[List[float]] = None,
        prices: Optional[List[float]] = None,
        benchmark_returns: Optional[List[float]] = None,
        initial_capital: float = 10000.0
    ) -> CompleteMetrics:
        """
        Calculate all available metrics.
        
        Args:
            trades: List of trades
            returns: List of period returns
            prices: List of prices for equity curve
            benchmark_returns: Benchmark returns for comparison
            initial_capital: Initial capital
            
        Returns:
            Complete metrics collection
        """
        metrics = CompleteMetrics()
        
        try:
            # Calculate trade metrics
            metrics.trade = self.calculate_trade_metrics(trades)
            
            # Calculate performance metrics
            metrics.performance = self.calculate_performance_metrics(
                trades, returns, prices, initial_capital
            )
            
            # Calculate risk metrics
            metrics.risk = self.calculate_risk_metrics(returns, prices)
            
            # Calculate risk-adjusted metrics
            metrics.risk_adjusted = self.calculate_risk_adjusted_metrics(
                returns, metrics.risk, metrics.performance
            )
            
            # Calculate statistical metrics
            metrics.statistical = self.calculate_statistical_metrics(returns)
            
            # Calculate volatility metrics
            metrics.volatility = self.calculate_volatility_metrics(returns)
            
            # Calculate drawdown metrics
            metrics.drawdown = self.calculate_drawdown_metrics(prices)
            
            # Calculate correlation metrics
            metrics.correlation = self.calculate_correlation_metrics(
                returns, benchmark_returns
            )
            
            # Calculate momentum metrics
            metrics.momentum = self.calculate_momentum_metrics(prices, returns)
            
            # Calculate overall scores
            metrics.overall_score = self.calculate_overall_score(metrics)
            metrics.risk_score = self.calculate_risk_score(metrics)
            metrics.performance_score = self.calculate_performance_score(metrics)
            metrics.consistency_score = self.calculate_consistency_score(metrics)
            
        except Exception as e:
            self._logger.error(f"Error calculating metrics: {str(e)}")
        
        return metrics
    
    def calculate_trade_metrics(self, trades: List[Trade]) -> TradeMetrics:
        """Calculate trade-level metrics."""
        metrics = TradeMetrics()
        
        if not trades:
            return metrics
        
        # Filter completed trades
        completed_trades = [t for t in trades if t.status == TradeStatus.COMPLETED]
        if not completed_trades:
            return metrics
        
        metrics.total_trades = len(completed_trades)
        
        # Win/Loss counts
        winning_trades = [t for t in completed_trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in completed_trades if t.pnl and t.pnl < 0]
        breakeven_trades = [t for t in completed_trades if t.pnl and t.pnl == 0]
        
        metrics.winning_trades = len(winning_trades)
        metrics.losing_trades = len(losing_trades)
        metrics.breakeven_trades = len(breakeven_trades)
        
        # Rates
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        metrics.loss_rate = metrics.losing_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        metrics.break_even_rate = metrics.breakeven_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        
        # PnL metrics
        profits = [t.pnl for t in winning_trades if t.pnl]
        losses = [t.pnl for t in losing_trades if t.pnl]
        
        metrics.gross_profit = sum(profits) if profits else 0
        metrics.gross_loss = abs(sum(losses)) if losses else 0
        metrics.net_profit = metrics.gross_profit - metrics.gross_loss
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss if metrics.gross_loss > 0 else float('inf')
        
        # Averages
        metrics.average_win = np.mean(profits) if profits else 0
        metrics.average_loss = np.mean(losses) if losses else 0
        metrics.average_trade = np.mean([t.pnl for t in completed_trades if t.pnl]) if completed_trades else 0
        metrics.average_win_loss_ratio = abs(metrics.average_win / metrics.average_loss) if metrics.average_loss != 0 else 0
        
        # Max values
        metrics.max_win = max(profits) if profits else 0
        metrics.max_loss = min(losses) if losses else 0
        metrics.max_win_loss_ratio = abs(metrics.max_win / metrics.max_loss) if metrics.max_loss != 0 else 0
        
        # Expected value
        metrics.expected_value = metrics.win_rate * metrics.average_win - metrics.loss_rate * abs(metrics.average_loss)
        metrics.expectancy_ratio = metrics.expected_value / abs(metrics.average_loss) if metrics.average_loss != 0 else 0
        
        # Trade duration
        durations = []
        for trade in completed_trades:
            if trade.entry_time and trade.exit_time:
                duration = (trade.exit_time - trade.entry_time).total_seconds()
                durations.append(duration)
        
        if durations:
            metrics.average_trade_duration = np.mean(durations)
            metrics.average_holding_period = metrics.average_trade_duration / 3600  # hours
        
        # Trade frequency
        if completed_trades:
            time_range = (completed_trades[-1].entry_time - completed_trades[0].entry_time).total_seconds() if completed_trades[-1].entry_time and completed_trades[0].entry_time else 1
            metrics.trade_frequency = metrics.total_trades / (time_range / 86400)  # trades per day
        
        # Direction analysis
        long_trades = [t for t in completed_trades if t.direction == TradeDirection.LONG]
        short_trades = [t for t in completed_trades if t.direction == TradeDirection.SHORT]
        
        metrics.long_trades = len(long_trades)
        metrics.short_trades = len(short_trades)
        
        long_wins = [t for t in long_trades if t.pnl and t.pnl > 0]
        short_wins = [t for t in short_trades if t.pnl and t.pnl > 0]
        
        metrics.long_win_rate = len(long_wins) / len(long_trades) if long_trades else 0
        metrics.short_win_rate = len(short_wins) / len(short_trades) if short_trades else 0
        
        metrics.long_profit = sum([t.pnl for t in long_trades if t.pnl]) if long_trades else 0
        metrics.short_profit = sum([t.pnl for t in short_trades if t.pnl]) if short_trades else 0
        
        return metrics
    
    def calculate_performance_metrics(
        self,
        trades: List[Trade],
        returns: Optional[List[float]] = None,
        prices: Optional[List[float]] = None,
        initial_capital: float = 10000.0
    ) -> PerformanceMetrics:
        """Calculate performance metrics."""
        metrics = PerformanceMetrics()
        
        # Use returns if provided, else calculate from trades
        if returns is None and prices is None and trades:
            returns = self._calculate_returns_from_trades(trades, initial_capital)
        
        if returns is None:
            return metrics
        
        returns_array = np.array(returns)
        
        # Total return
        metrics.total_return = (np.prod(1 + returns_array) - 1) if len(returns_array) > 0 else 0
        
        # Annualized return
        n_periods = len(returns_array)
        if n_periods > 0:
            metrics.annualized_return = (1 + metrics.total_return) ** (self.annualization_factor / n_periods) - 1
        
        # Cumulative returns
        metrics.cumulative_return = list(np.cumprod(1 + returns_array) - 1)
        
        # Monthly returns
        metrics.monthly_returns = self._calculate_period_returns(returns_array, 21)  # ~21 trading days per month
        
        # Yearly returns
        metrics.yearly_returns = self._calculate_period_returns(returns_array, self.annualization_factor)
        
        # Best/Worst month
        if metrics.monthly_returns:
            best_month = max(metrics.monthly_returns.items(), key=lambda x: x[1])
            worst_month = min(metrics.monthly_returns.items(), key=lambda x: x[1])
            metrics.best_month = {"period": best_month[0], "return": best_month[1]}
            metrics.worst_month = {"period": worst_month[0], "return": worst_month[1]}
        
        # Best/Worst year
        if metrics.yearly_returns:
            best_year = max(metrics.yearly_returns.items(), key=lambda x: x[1])
            worst_year = min(metrics.yearly_returns.items(), key=lambda x: x[1])
            metrics.best_year = {"period": best_year[0], "return": best_year[1]}
            metrics.worst_year = {"period": worst_year[0], "return": worst_year[1]}
        
        # Consecutive wins/losses
        if len(returns_array) > 0:
            win_series = (returns_array > 0).astype(int)
            loss_series = (returns_array < 0).astype(int)
            
            metrics.max_consecutive_wins = self._max_consecutive(win_series, 1)
            metrics.max_consecutive_losses = self._max_consecutive(loss_series, 1)
        
        return metrics
    
    def calculate_risk_metrics(
        self,
        returns: Optional[List[float]] = None,
        prices: Optional[List[float]] = None
    ) -> RiskMetrics:
        """Calculate risk metrics."""
        metrics = RiskMetrics()
        
        if returns is None:
            return metrics
        
        returns_array = np.array(returns)
        if len(returns_array) == 0:
            return metrics
        
        # Value at Risk
        metrics.var_95 = np.percentile(returns_array, 5)
        metrics.var_99 = np.percentile(returns_array, 1)
        
        # Conditional VaR (Expected Shortfall)
        metrics.cvar_95 = np.mean(returns_array[returns_array <= metrics.var_95]) if np.any(returns_array <= metrics.var_95) else 0
        metrics.cvar_99 = np.mean(returns_array[returns_array <= metrics.var_99]) if np.any(returns_array <= metrics.var_99) else 0
        
        # Volatility
        metrics.volatility_daily = np.std(returns_array)
        metrics.volatility_weekly = metrics.volatility_daily * np.sqrt(5)
        metrics.volatility_monthly = metrics.volatility_daily * np.sqrt(21)
        metrics.volatility_annualized = metrics.volatility_daily * np.sqrt(self.annualization_factor)
        
        # Drawdown
        if prices is not None and len(prices) > 0:
            drawdown_metrics = self.calculate_drawdown_metrics(prices)
            metrics.max_drawdown = drawdown_metrics.max_drawdown
            metrics.max_drawdown_duration = drawdown_metrics.max_drawdown_duration
            metrics.average_drawdown = drawdown_metrics.average_drawdown
            metrics.average_drawdown_duration = drawdown_metrics.average_drawdown_duration
            metrics.max_drawdown_date = drawdown_metrics.max_drawdown_date
            metrics.recovery_date = drawdown_metrics.recovery_date
        
        # Downside deviation
        downside_returns = returns_array[returns_array < 0]
        metrics.downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        
        # Upside potential
        upside_returns = returns_array[returns_array > 0]
        metrics.upside_potential = np.mean(upside_returns) if len(upside_returns) > 0 else 0
        
        # Risk of ruin
        metrics.risk_of_ruin = self._calculate_risk_of_ruin(returns_array)
        
        # Probability of loss
        metrics.probability_of_loss = np.mean(returns_array < 0)
        
        return metrics
    
    def calculate_risk_adjusted_metrics(
        self,
        returns: Optional[List[float]] = None,
        risk_metrics: Optional[RiskMetrics] = None,
        performance_metrics: Optional[PerformanceMetrics] = None
    ) -> RiskAdjustedMetrics:
        """Calculate risk-adjusted performance metrics."""
        metrics = RiskAdjustedMetrics()
        
        if returns is None:
            return metrics
        
        returns_array = np.array(returns)
        if len(returns_array) == 0:
            return metrics
        
        # Sharpe Ratio
        excess_returns = returns_array - self.risk_free_rate / self.annualization_factor
        metrics.sharpe_ratio = np.mean(excess_returns) / np.std(returns_array) * np.sqrt(self.annualization_factor) if np.std(returns_array) > 0 else 0
        
        # Sortino Ratio
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        metrics.sortino_ratio = np.mean(returns_array) / downside_deviation * np.sqrt(self.annualization_factor) if downside_deviation > 0 else 0
        
        # Calmar Ratio
        if risk_metrics and risk_metrics.max_drawdown > 0 and performance_metrics:
            metrics.calmar_ratio = performance_metrics.annualized_return / risk_metrics.max_drawdown
        
        # Omega Ratio
        threshold = 0
        gains = returns_array[returns_array > threshold]
        losses = returns_array[returns_array < threshold]
        metrics.omega_ratio = np.sum(gains) / np.abs(np.sum(losses)) if np.abs(np.sum(losses)) > 0 else float('inf')
        
        # Tail Ratio
        percentile_95 = np.percentile(returns_array, 95)
        percentile_5 = np.percentile(returns_array, 5)
        metrics.tail_ratio = np.abs(percentile_95 / percentile_5) if percentile_5 != 0 else 0
        
        # Pain Index
        if risk_metrics and risk_metrics.max_drawdown > 0:
            metrics.pain_index = risk_metrics.max_drawdown ** 2
        
        # Martin Ratio
        metrics.martin_ratio = metrics.sharpe_ratio / (1 + metrics.pain_index) if metrics.pain_index > 0 else metrics.sharpe_ratio
        
        # Ulcer Index
        metrics.ulcer_index = self._calculate_ulcer_index(returns_array)
        
        # Sterling Ratio
        if risk_metrics and risk_metrics.max_drawdown > 0:
            metrics.sterling_ratio = performance_metrics.annualized_return / (risk_metrics.max_drawdown - 0.1) if risk_metrics.max_drawdown > 0.1 else 0
        
        # Burke Ratio
        metrics.burke_ratio = metrics.sharpe_ratio / (1 + np.sqrt(metrics.pain_index)) if metrics.pain_index > 0 else metrics.sharpe_ratio
        
        # Gain Pain Ratio
        metrics.gain_pain_ratio = np.mean(returns_array[returns_array > 0]) / np.abs(np.mean(returns_array[returns_array < 0])) if np.any(returns_array < 0) else float('inf')
        
        # Recovery Factor
        if risk_metrics and risk_metrics.max_drawdown > 0 and performance_metrics:
            metrics.recovery_factor = performance_metrics.total_return / risk_metrics.max_drawdown
        
        return metrics
    
    def calculate_statistical_metrics(self, returns: Optional[List[float]] = None) -> StatisticalMetrics:
        """Calculate statistical metrics for returns distribution."""
        metrics = StatisticalMetrics()
        
        if returns is None or len(returns) == 0:
            return metrics
        
        returns_array = np.array(returns)
        
        # Basic statistics
        metrics.mean_return = np.mean(returns_array)
        metrics.median_return = np.median(returns_array)
        metrics.std_deviation = np.std(returns_array)
        metrics.variance = np.var(returns_array)
        metrics.skewness = skew(returns_array)
        metrics.kurtosis = kurtosis(returns_array)
        
        # Jarque-Bera test for normality
        if len(returns_array) > 1:
            jb_stat, jb_pvalue = jarque_bera(returns_array)
            metrics.jarque_bera_stat = jb_stat
            metrics.jarque_bera_pvalue = jb_pvalue
            metrics.is_normal = jb_pvalue > 0.05
        
        # Confidence intervals (assuming normal distribution)
        std_error = metrics.std_deviation / np.sqrt(len(returns_array))
        z_95 = norm.ppf(0.975)
        z_99 = norm.ppf(0.995)
        
        metrics.ci_95_lower = metrics.mean_return - z_95 * std_error
        metrics.ci_95_upper = metrics.mean_return + z_95 * std_error
        metrics.ci_99_lower = metrics.mean_return - z_99 * std_error
        metrics.ci_99_upper = metrics.mean_return + z_99 * std_error
        
        # Percentiles
        metrics.percentile_1 = np.percentile(returns_array, 1)
        metrics.percentile_5 = np.percentile(returns_array, 5)
        metrics.percentile_25 = np.percentile(returns_array, 25)
        metrics.percentile_50 = np.percentile(returns_array, 50)
        metrics.percentile_75 = np.percentile(returns_array, 75)
        metrics.percentile_95 = np.percentile(returns_array, 95)
        metrics.percentile_99 = np.percentile(returns_array, 99)
        
        return metrics
    
    def calculate_volatility_metrics(self, returns: Optional[List[float]] = None) -> VolatilityMetrics:
        """Calculate volatility-related metrics."""
        metrics = VolatilityMetrics()
        
        if returns is None or len(returns) < 20:
            return metrics
        
        returns_array = np.array(returns)
        
        # Historical volatility
        metrics.historical_volatility = np.std(returns_array) * np.sqrt(self.annualization_factor)
        
        # Rolling volatility
        for window in [20, 50, 100]:
            rolling_vol = []
            for i in range(window, len(returns_array)):
                vol = np.std(returns_array[i-window:i]) * np.sqrt(self.annualization_factor)
                rolling_vol.append(vol)
            
            if window == 20:
                metrics.rolling_volatility_20 = rolling_vol
            elif window == 50:
                metrics.rolling_volatility_50 = rolling_vol
            elif window == 100:
                metrics.rolling_volatility_100 = rolling_vol
        
        # Volatility of volatility
        if metrics.rolling_volatility_20:
            metrics.vol_of_vol = np.std(metrics.rolling_volatility_20)
            metrics.volatility_skew = skew(metrics.rolling_volatility_20)
            metrics.volatility_kurtosis = kurtosis(metrics.rolling_volatility_20)
            metrics.max_volatility = max(metrics.rolling_volatility_20)
            metrics.min_volatility = min(metrics.rolling_volatility_20)
            
            # Volatility percentile
            current_vol = metrics.historical_volatility
            metrics.volatility_percentile = sum(1 for v in metrics.rolling_volatility_20 if v < current_vol) / len(metrics.rolling_volatility_20)
        
        # Volatility regimes
        vol_threshold_high = np.mean(metrics.rolling_volatility_20) + np.std(metrics.rolling_volatility_20) if metrics.rolling_volatility_20 else 0
        vol_threshold_low = np.mean(metrics.rolling_volatility_20) - np.std(metrics.rolling_volatility_20) if metrics.rolling_volatility_20 else 0
        
        if metrics.rolling_volatility_20:
            metrics.high_volatility_periods = sum(1 for v in metrics.rolling_volatility_20 if v > vol_threshold_high)
            metrics.low_volatility_periods = sum(1 for v in metrics.rolling_volatility_20 if v < vol_threshold_low)
        
        # Volatility regime classification
        if metrics.volatility_percentile > 0.7:
            metrics.volatility_regime = "high"
        elif metrics.volatility_percentile < 0.3:
            metrics.volatility_regime = "low"
        else:
            metrics.volatility_regime = "normal"
        
        return metrics
    
    def calculate_drawdown_metrics(self, prices: Optional[List[float]] = None) -> DrawdownMetrics:
        """Calculate drawdown-specific metrics."""
        metrics = DrawdownMetrics()
        
        if prices is None or len(prices) < 2:
            return metrics
        
        prices_array = np.array(prices)
        
        # Calculate drawdown series
        running_max = np.maximum.accumulate(prices_array)
        drawdown_series = (running_max - prices_array) / running_max
        
        # Max drawdown
        metrics.max_drawdown = np.max(drawdown_series)
        
        # Current drawdown
        metrics.current_drawdown = drawdown_series[-1]
        
        # Average drawdown
        metrics.average_drawdown = np.mean(drawdown_series)
        metrics.median_drawdown = np.median(drawdown_series)
        
        # Drawdown periods
        in_drawdown = False
        start_idx = 0
        metrics.drawdown_periods = []
        
        for i, dd in enumerate(drawdown_series):
            if dd > 0.01:  # 1% threshold
                if not in_drawdown:
                    in_drawdown = True
                    start_idx = i
            else:
                if in_drawdown:
                    in_drawdown = False
                    duration = i - start_idx
                    metrics.drawdown_periods.append({
                        "start": start_idx,
                        "end": i,
                        "duration": duration,
                        "max_drawdown": np.max(drawdown_series[start_idx:i])
                    })
        
        # Drawdown durations
        durations = [p["duration"] for p in metrics.drawdown_periods]
        if durations:
            metrics.max_drawdown_duration = max(durations)
            metrics.average_drawdown_duration = int(np.mean(durations))
            metrics.current_drawdown_duration = durations[-1] if durations else 0
        
        # Drawdown percentiles
        if durations:
            metrics.drawdown_percentiles = {
                "25": np.percentile(durations, 25),
                "50": np.percentile(durations, 50),
                "75": np.percentile(durations, 75),
                "90": np.percentile(durations, 90),
                "95": np.percentile(durations, 95)
            }
        
        # Drawdown severity classification
        max_dd = metrics.max_drawdown
        if max_dd > 0.2:
            metrics.severe_drawdowns = sum(1 for p in metrics.drawdown_periods if p["max_drawdown"] > 0.2)
        elif max_dd > 0.1:
            metrics.moderate_drawdowns = sum(1 for p in metrics.drawdown_periods if 0.1 < p["max_drawdown"] <= 0.2)
        else:
            metrics.mild_drawdowns = sum(1 for p in metrics.drawdown_periods if p["max_drawdown"] <= 0.1)
        
        # Max drawdown date
        if metrics.max_drawdown > 0:
            max_dd_idx = np.argmax(drawdown_series)
            metrics.max_drawdown_date = datetime.now() - timedelta(days=len(prices) - max_dd_idx)
            
            # Find recovery date
            for i in range(max_dd_idx + 1, len(prices)):
                if prices_array[i] >= running_max[max_dd_idx]:
                    metrics.recovery_date = datetime.now() - timedelta(days=len(prices) - i)
                    break
        
        # Recovery metrics
        if metrics.drawdown_periods:
            recovery_times = []
            for p in metrics.drawdown_periods:
                start_idx = p["start"]
                end_idx = p["end"]
                recovery_time = end_idx - start_idx
                recovery_times.append(recovery_time)
            
            if recovery_times:
                metrics.average_recovery_time = np.mean(recovery_times)
                metrics.max_recovery_time = max(recovery_times)
                metrics.recovery_rate = len([t for t in recovery_times if t < 20]) / len(recovery_times)
        
        return metrics
    
    def calculate_correlation_metrics(
        self,
        returns: Optional[List[float]] = None,
        benchmark_returns: Optional[List[float]] = None
    ) -> CorrelationMetrics:
        """Calculate correlation and dependency metrics."""
        metrics = CorrelationMetrics()
        
        if returns is None or benchmark_returns is None:
            return metrics
        
        returns_array = np.array(returns)
        benchmark_array = np.array(benchmark_returns)
        
        if len(returns_array) != len(benchmark_array) or len(returns_array) == 0:
            return metrics
        
        # Beta to market
        cov_matrix = np.cov(returns_array, benchmark_array)
        if cov_matrix.shape == (2, 2) and cov_matrix[1, 1] > 0:
            metrics.beta_to_market = cov_matrix[0, 1] / cov_matrix[1, 1]
            
            # Alpha (intercept of regression)
            slope, intercept = np.polyfit(benchmark_array, returns_array, 1)
            metrics.alpha_to_market = intercept
            
            # R-squared
            correlation = np.corrcoef(returns_array, benchmark_array)[0, 1]
            metrics.r_squared = correlation ** 2
        
        return metrics
    
    def calculate_momentum_metrics(
        self,
        prices: Optional[List[float]] = None,
        returns: Optional[List[float]] = None
    ) -> MomentumMetrics:
        """Calculate momentum and trend metrics."""
        metrics = MomentumMetrics()
        
        if prices is None or len(prices) < 20:
            return metrics
        
        prices_array = np.array(prices)
        
        # Price momentum
        metrics.price_momentum = (prices_array[-1] / prices_array[0]) - 1 if prices_array[0] > 0 else 0
        
        # Rate of Change
        for period in [1, 5, 10, 20]:
            if len(prices_array) > period:
                roc = (prices_array[-1] / prices_array[-period-1]) - 1 if prices_array[-period-1] > 0 else 0
                if period == 1:
                    metrics.roc_1 = roc
                elif period == 5:
                    metrics.roc_5 = roc
                elif period == 10:
                    metrics.roc_10 = roc
                elif period == 20:
                    metrics.roc_20 = roc
        
        # Relative Strength
        metrics.relative_strength = self._calculate_relative_strength(prices_array)
        
        # Volume momentum (if available)
        # This would require volume data
        
        # Trend analysis
        if len(prices_array) >= 50:
            # Trend strength using linear regression
            x = np.arange(len(prices_array))
            slope, _ = np.polyfit(x, prices_array, 1)
            metrics.trend_strength = abs(slope / np.mean(prices_array)) if np.mean(prices_array) > 0 else 0
            
            # Trend direction
            sma_short = np.mean(prices_array[-20:])
            sma_long = np.mean(prices_array[-50:])
            
            if sma_short > sma_long * 1.01:
                metrics.trend_direction = "bullish"
                metrics.ma_cross_signal = "golden_cross"
            elif sma_short < sma_long * 0.99:
                metrics.trend_direction = "bearish"
                metrics.ma_cross_signal = "death_cross"
            else:
                metrics.trend_direction = "neutral"
            
            metrics.ma_difference = (sma_short - sma_long) / sma_long if sma_long > 0 else 0
            
            # Distance from moving average
            metrics.distance_from_ma = (prices_array[-1] / sma_short) - 1 if sma_short > 0 else 0
        
        # Combined momentum score
        metrics.momentum_score = (
            metrics.roc_20 * 0.3 +
            metrics.roc_10 * 0.25 +
            metrics.roc_5 * 0.2 +
            metrics.price_momentum * 0.15 +
            metrics.relative_strength * 0.1
        )
        
        return metrics
    
    def calculate_overall_score(self, metrics: CompleteMetrics) -> float:
        """Calculate overall strategy score."""
        scores = []
        
        # Sharpe ratio (20%)
        scores.append(min(metrics.risk_adjusted.sharpe_ratio / 2, 1) * 0.2)
        
        # Win rate (15%)
        scores.append(metrics.trade.win_rate * 0.15)
        
        # Profit factor (15%)
        scores.append(min(metrics.trade.profit_factor / 2, 1) * 0.15)
        
        # Calmar ratio (15%)
        scores.append(min(metrics.risk_adjusted.calmar_ratio / 2, 1) * 0.15)
        
        # Consistency (15%)
        scores.append(metrics.consistency_score * 0.15)
        
        # Risk score (10%)
        scores.append(metrics.risk_score * 0.10)
        
        # Performance score (10%)
        scores.append(metrics.performance_score * 0.10)
        
        return sum(scores)
    
    def calculate_risk_score(self, metrics: CompleteMetrics) -> float:
        """Calculate risk score."""
        scores = []
        
        # Max drawdown (30%)
        dd_score = 1 - min(metrics.drawdown.max_drawdown, 1)
        scores.append(dd_score * 0.3)
        
        # Sharpe ratio (30%)
        sr_score = min(metrics.risk_adjusted.sharpe_ratio / 2, 1)
        scores.append(sr_score * 0.3)
        
        # Risk of ruin (20%)
        ror_score = 1 - min(metrics.risk.risk_of_ruin, 1)
        scores.append(ror_score * 0.2)
        
        # Volatility (20%)
        vol_score = 1 - min(metrics.volatility.historical_volatility, 1)
        scores.append(vol_score * 0.2)
        
        return sum(scores)
    
    def calculate_performance_score(self, metrics: CompleteMetrics) -> float:
        """Calculate performance score."""
        scores = []
        
        # Annualized return (30%)
        ret_score = min(metrics.performance.annualized_return, 1)
        scores.append(ret_score * 0.3)
        
        # Win rate (25%)
        scores.append(metrics.trade.win_rate * 0.25)
        
        # Profit factor (25%)
        scores.append(min(metrics.trade.profit_factor / 2, 1) * 0.25)
        
        # Recovery factor (20%)
        rf_score = min(metrics.risk_adjusted.recovery_factor / 2, 1)
        scores.append(rf_score * 0.2)
        
        return sum(scores)
    
    def calculate_consistency_score(self, metrics: CompleteMetrics) -> float:
        """Calculate consistency score."""
        scores = []
        
        # Win rate consistency (30%)
        wr_score = metrics.trade.win_rate * 0.3
        
        # Monthly consistency (30%)
        if metrics.performance.monthly_returns:
            monthly_returns = list(metrics.performance.monthly_returns.values())
            positive_months = sum(1 for r in monthly_returns if r > 0)
            month_score = positive_months / len(monthly_returns) if monthly_returns else 0
            scores.append(month_score * 0.3)
        else:
            scores.append(0.3 * 0.3)
        
        # Win/loss consistency (20%)
        wl_ratio = metrics.trade.average_win_loss_ratio
        wl_score = min(wl_ratio / 2, 1)
        scores.append(wl_score * 0.2)
        
        # Drawdown consistency (20%)
        dd_score = 1 - min(metrics.drawdown.max_drawdown, 0.5)
        scores.append(dd_score * 0.2)
        
        return sum(scores)
    
    def _calculate_returns_from_trades(
        self,
        trades: List[Trade],
        initial_capital: float
    ) -> List[float]:
        """Calculate returns series from trades."""
        if not trades:
            return []
        
        # Sort trades by exit time
        sorted_trades = sorted(trades, key=lambda t: t.exit_time if t.exit_time else datetime.min)
        
        returns = []
        equity = initial_capital
        
        for trade in sorted_trades:
            if trade.pnl is not None:
                return_pct = trade.pnl / equity if equity > 0 else 0
                returns.append(return_pct)
                equity += trade.pnl
        
        return returns
    
    def _calculate_period_returns(
        self,
        returns: np.ndarray,
        periods_per_year: int
    ) -> Dict[str, float]:
        """Calculate period returns (monthly, yearly, etc.)."""
        period_returns = {}
        
        if len(returns) < periods_per_year:
            return period_returns
        
        n_periods = len(returns) // periods_per_year
        
        for i in range(n_periods):
            start = i * periods_per_year
            end = min((i + 1) * periods_per_year, len(returns))
            period_return = np.prod(1 + returns[start:end]) - 1
            period_returns[f"period_{i+1}"] = period_return
        
        return period_returns
    
    def _max_consecutive(self, series: np.ndarray, target: int) -> int:
        """Calculate maximum consecutive occurrences of a value."""
        max_count = 0
        current_count = 0
        
        for value in series:
            if value == target:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def _calculate_risk_of_ruin(self, returns: np.ndarray) -> float:
        """Calculate risk of ruin using Kelly criterion."""
        if len(returns) == 0:
            return 0
        
        win_rate = np.mean(returns > 0)
        avg_win = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0
        avg_loss = np.mean(returns[returns < 0]) if np.any(returns < 0) else 0
        
        if avg_loss == 0:
            return 0
        
        # Kelly fraction
        kelly_fraction = win_rate - (1 - win_rate) * (avg_win / abs(avg_loss))
        
        # Risk of ruin with 1% of capital
        if kelly_fraction > 0:
            risk_of_ruin = np.exp(-2 * kelly_fraction * 0.01)
        else:
            risk_of_ruin = 1.0
        
        return min(risk_of_ruin, 1.0)
    
    def _calculate_ulcer_index(self, returns: np.ndarray) -> float:
        """Calculate Ulcer Index (measure of downside risk)."""
        if len(returns) == 0:
            return 0
        
        # Calculate cumulative returns
        cumulative = np.cumprod(1 + returns)
        
        # Running maximum
        running_max = np.maximum.accumulate(cumulative)
        
        # Drawdown squared
        drawdown_squared = ((running_max - cumulative) / running_max) ** 2
        
        # Ulcer Index
        ulcer_index = np.sqrt(np.mean(drawdown_squared))
        
        return ulcer_index
    
    def _calculate_relative_strength(self, prices: np.ndarray) -> float:
        """Calculate relative strength of a security."""
        if len(prices) < 14:
            return 0
        
        # Calculate gains and losses
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Average gains and losses over 14 periods
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains)
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses)
        
        if avg_loss == 0:
            return 0
        
        # Relative strength
        rs = avg_gain / avg_loss
        
        # RSI (0-100)
        rsi = 100 - (100 / (1 + rs))
        
        # Normalize to -1 to 1
        return (rsi - 50) / 50


# Utility functions for quick metric calculations
def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Quick Sharpe ratio calculation."""
    if not returns:
        return 0
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / 252
    return np.mean(excess_returns) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0


def calculate_max_drawdown(prices: List[float]) -> float:
    """Quick max drawdown calculation."""
    if not prices:
        return 0
    prices_array = np.array(prices)
    running_max = np.maximum.accumulate(prices_array)
    drawdown = (running_max - prices_array) / running_max
    return np.max(drawdown)


def calculate_win_rate(trades: List[Trade]) -> float:
    """Quick win rate calculation."""
    if not trades:
        return 0
    winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
    return len(winning_trades) / len(trades) if trades else 0


def calculate_profit_factor(trades: List[Trade]) -> float:
    """Quick profit factor calculation."""
    if not trades:
        return 0
    gross_profit = sum([t.pnl for t in trades if t.pnl and t.pnl > 0])
    gross_loss = abs(sum([t.pnl for t in trades if t.pnl and t.pnl < 0]))
    return gross_profit / gross_loss if gross_loss > 0 else float('inf')


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Quick Sortino ratio calculation."""
    if not returns:
        return 0
    returns_array = np.array(returns)
    downside_returns = returns_array[returns_array < 0]
    downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
    return np.mean(returns_array) / downside_deviation * np.sqrt(252) if downside_deviation > 0 else 0


def calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    """Quick Calmar ratio calculation."""
    return annual_return / max_drawdown if max_drawdown > 0 else 0


def calculate_omega_ratio(returns: List[float], threshold: float = 0) -> float:
    """Quick Omega ratio calculation."""
    if not returns:
        return 0
    returns_array = np.array(returns)
    gains = returns_array[returns_array > threshold]
    losses = returns_array[returns_array < threshold]
    return np.sum(gains) / np.abs(np.sum(losses)) if np.abs(np.sum(losses)) > 0 else float('inf')


# Factory function
def create_metrics_calculator(
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
    confidence_level: float = 0.95
) -> MetricsCalculator:
    """
    Create a metrics calculator with default configuration.
    
    Args:
        risk_free_rate: Risk-free rate
        annualization_factor: Number of periods in a year
        confidence_level: Confidence level for VaR
        
    Returns:
        Configured MetricsCalculator instance
    """
    return MetricsCalculator(
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        confidence_level=confidence_level
    )
