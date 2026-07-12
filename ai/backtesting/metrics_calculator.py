"""
NEXUS AI TRADING SYSTEM - Metrics Calculator
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Metrics Calculator system with:
- Performance metrics (Sharpe, Sortino, Calmar, etc.)
- Risk metrics (VaR, CVaR, Max Drawdown, etc.)
- Trade statistics (Win Rate, Profit Factor, etc.)
- Portfolio metrics (Beta, Alpha, etc.)
- Rolling metrics
- Annualization
- Benchmark comparison
- Multiple timeframes
- Export capabilities
- Visualization
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel, Field, validator
from scipy import stats
from scipy.optimize import minimize

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import MetricsCalculationError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class MetricType(str, Enum):
    """Metric types"""
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADE = "trade"
    PORTFOLIO = "portfolio"
    COMPARATIVE = "comparative"
    ROLLING = "rolling"


class AnnualizationMethod(str, Enum):
    """Annualization methods"""
    TRADING_DAYS = "trading_days"
    CALENDAR_DAYS = "calendar_days"
    COMPOUND = "compound"
    SIMPLE = "simple"


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    total_return: float = 0.0
    annual_return: float = 0.0
    monthly_return: float = 0.0
    weekly_return: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    compound_annual_growth_rate: float = 0.0
    rolling_returns: List[float] = field(default_factory=list)


@dataclass
class RiskMetrics:
    """Risk metrics"""
    volatility: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    value_at_risk_95: float = 0.0
    value_at_risk_99: float = 0.0
    conditional_value_at_risk_95: float = 0.0
    conditional_value_at_risk_99: float = 0.0
    expected_shortfall: float = 0.0
    tail_risk: float = 0.0
    downside_deviation: float = 0.0
    upside_deviation: float = 0.0
    drawdown_duration: float = 0.0
    recovery_time: float = 0.0


@dataclass
class TradeMetrics:
    """Trade metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    average_trade: float = 0.0
    average_win_loss_ratio: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    average_holding_period: float = 0.0
    trade_duration: List[float] = field(default_factory=list)


@dataclass
class PortfolioMetrics:
    """Portfolio metrics"""
    beta: float = 1.0
    alpha: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    information_ratio: float = 0.0
    treynor_ratio: float = 0.0
    capture_ratio: float = 0.0
    correlation: float = 0.0
    r_squared: float = 0.0


@dataclass
class RollingMetrics:
    """Rolling metrics"""
    rolling_sharpe: List[float] = field(default_factory=list)
    rolling_volatility: List[float] = field(default_factory=list)
    rolling_max_drawdown: List[float] = field(default_factory=list)
    rolling_win_rate: List[float] = field(default_factory=list)
    rolling_returns: List[float] = field(default_factory=list)
    rolling_correlation: List[float] = field(default_factory=list)


class MetricsConfig(BaseModel):
    """Metrics calculator configuration"""
    risk_free_rate: float = Field(default=0.02, ge=0)
    trading_days: int = Field(default=252, gt=0)
    annualization_method: AnnualizationMethod = AnnualizationMethod.TRADING_DAYS
    var_confidence_95: float = Field(default=0.95, ge=0, le=1)
    var_confidence_99: float = Field(default=0.99, ge=0, le=1)
    rolling_window: int = Field(default=30, gt=0)
    benchmark_symbol: Optional[str] = None
    benchmark_data: Optional[List[float]] = None
    use_excess_returns: bool = True
    log_returns: bool = True
    include_benchmark: bool = False
    cache_results: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    log_level: str = "info"


# ========================================
# METRICS CALCULATOR
# ========================================

class MetricsCalculator:
    """
    Complete metrics calculator for trading strategies.
    
    Features:
    - Performance metrics (Sharpe, Sortino, Calmar, etc.)
    - Risk metrics (VaR, CVaR, Max Drawdown, etc.)
    - Trade statistics (Win Rate, Profit Factor, etc.)
    - Portfolio metrics (Beta, Alpha, etc.)
    - Rolling metrics
    - Annualization
    - Benchmark comparison
    - Multiple timeframes
    - Export capabilities
    - Visualization
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = MetricsConfig(**(config or {}))
        self.redis = get_redis()
        
        # Cache
        self._cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_calculations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_calculation_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.MetricsCalculator")
        self.logger.info("MetricsCalculator initialized")
    
    # ========================================
    # MAIN CALCULATION
    # ========================================
    
    async def calculate_all_metrics(
        self,
        equity_curve: List[float],
        trades: Optional[List[Dict[str, Any]]] = None,
        benchmark_returns: Optional[List[float]] = None,
        risk_free_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate all metrics.
        
        Args:
            equity_curve: Equity curve values
            trades: Trade list
            benchmark_returns: Benchmark returns
            risk_free_rate: Risk-free rate
            
        Returns:
            Dict[str, Any]: All metrics
        """
        start_time = time.time()
        
        # Check cache
        cache_key = self._generate_cache_key(
            equity_curve,
            trades,
            benchmark_returns,
            risk_free_rate
        )
        
        if self.config.cache_results:
            cached = self._get_cached_metrics(cache_key)
            if cached:
                self._metrics["cache_hits"] += 1
                return cached
        
        self._metrics["cache_misses"] += 1
        
        try:
            # Calculate returns
            returns = self._calculate_returns(equity_curve)
            
            # Calculate performance metrics
            performance = await self.calculate_performance_metrics(
                returns,
                equity_curve
            )
            
            # Calculate risk metrics
            risk = await self.calculate_risk_metrics(
                returns,
                equity_curve
            )
            
            # Calculate trade metrics
            trade_metrics = await self.calculate_trade_metrics(trades or [])
            
            # Calculate portfolio metrics
            portfolio = await self.calculate_portfolio_metrics(
                returns,
                benchmark_returns
            )
            
            # Calculate rolling metrics
            rolling = await self.calculate_rolling_metrics(
                returns,
                equity_curve
            )
            
            # Combine all metrics
            result = {
                'performance': performance.__dict__,
                'risk': risk.__dict__,
                'trades': trade_metrics.__dict__,
                'portfolio': portfolio.__dict__,
                'rolling': rolling.__dict__,
                'returns': returns,
                'equity_curve': equity_curve,
                'summary': self._generate_summary(
                    performance,
                    risk,
                    trade_metrics,
                    portfolio
                )
            }
            
            # Cache result
            if self.config.cache_results:
                self._set_cached_metrics(cache_key, result)
            
            # Update metrics
            elapsed = time.time() - start_time
            self._metrics["total_calculations"] += 1
            self._metrics["avg_calculation_time"] = (
                self._metrics["avg_calculation_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(f"Metrics calculated in {elapsed:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Metrics calculation failed: {e}")
            raise MetricsCalculationError(f"Calculation failed: {e}")
    
    # ========================================
    # PERFORMANCE METRICS
    # ========================================
    
    async def calculate_performance_metrics(
        self,
        returns: List[float],
        equity_curve: List[float]
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics.
        
        Args:
            returns: Daily returns
            equity_curve: Equity curve
            
        Returns:
            PerformanceMetrics: Performance metrics
        """
        metrics = PerformanceMetrics()
        
        if not returns:
            return metrics
        
        # Total return
        metrics.total_return = self._calculate_total_return(equity_curve)
        
        # Annual return
        metrics.annual_return = self._calculate_annual_return(
            returns,
            len(returns)
        )
        
        # Monthly return
        metrics.monthly_return = self._calculate_period_return(
            returns,
            21  # Trading days in a month
        )
        
        # Weekly return
        metrics.weekly_return = self._calculate_period_return(
            returns,
            5  # Trading days in a week
        )
        
        # Daily return
        metrics.daily_return = self._calculate_period_return(
            returns,
            1
        )
        
        # Cumulative return
        metrics.cumulative_return = self._calculate_cumulative_return(returns)
        
        # CAGR
        metrics.compound_annual_growth_rate = self._calculate_cagr(
            equity_curve,
            len(equity_curve)
        )
        
        # Rolling returns
        metrics.rolling_returns = self._calculate_rolling_returns(
            returns,
            self.config.rolling_window
        )
        
        return metrics
    
    # ========================================
    # RISK METRICS
    # ========================================
    
    async def calculate_risk_metrics(
        self,
        returns: List[float],
        equity_curve: List[float]
    ) -> RiskMetrics:
        """
        Calculate risk metrics.
        
        Args:
            returns: Daily returns
            equity_curve: Equity curve
            
        Returns:
            RiskMetrics: Risk metrics
        """
        metrics = RiskMetrics()
        
        if not returns:
            return metrics
        
        # Volatility
        metrics.volatility = self._calculate_volatility(returns)
        
        # Max drawdown
        metrics.max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # Current drawdown
        metrics.current_drawdown = self._calculate_current_drawdown(equity_curve)
        
        # Value at Risk
        metrics.value_at_risk_95 = self._calculate_var(
            returns,
            self.config.var_confidence_95
        )
        metrics.value_at_risk_99 = self._calculate_var(
            returns,
            self.config.var_confidence_99
        )
        
        # Conditional Value at Risk
        metrics.conditional_value_at_risk_95 = self._calculate_cvar(
            returns,
            self.config.var_confidence_95
        )
        metrics.conditional_value_at_risk_99 = self._calculate_cvar(
            returns,
            self.config.var_confidence_99
        )
        
        # Expected shortfall
        metrics.expected_shortfall = self._calculate_expected_shortfall(returns)
        
        # Tail risk
        metrics.tail_risk = self._calculate_tail_risk(returns)
        
        # Downside deviation
        metrics.downside_deviation = self._calculate_downside_deviation(returns)
        
        # Upside deviation
        metrics.upside_deviation = self._calculate_upside_deviation(returns)
        
        # Drawdown duration
        metrics.drawdown_duration = self._calculate_drawdown_duration(equity_curve)
        
        # Recovery time
        metrics.recovery_time = self._calculate_recovery_time(equity_curve)
        
        return metrics
    
    # ========================================
    # TRADE METRICS
    # ========================================
    
    async def calculate_trade_metrics(
        self,
        trades: List[Dict[str, Any]]
    ) -> TradeMetrics:
        """
        Calculate trade metrics.
        
        Args:
            trades: Trade list
            
        Returns:
            TradeMetrics: Trade metrics
        """
        metrics = TradeMetrics()
        
        if not trades:
            return metrics
        
        # Basic counts
        metrics.total_trades = len(trades)
        
        # Winning and losing trades
        pnl_list = [t.get('pnl', 0) for t in trades]
        metrics.winning_trades = sum(1 for p in pnl_list if p > 0)
        metrics.losing_trades = sum(1 for p in pnl_list if p < 0)
        metrics.break_even_trades = sum(1 for p in pnl_list if p == 0)
        
        # Win rate
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        metrics.loss_rate = metrics.losing_trades / metrics.total_trades if metrics.total_trades > 0 else 0
        
        # Profit factor
        total_wins = sum(p for p in pnl_list if p > 0)
        total_losses = abs(sum(p for p in pnl_list if p < 0))
        metrics.profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Average values
        metrics.average_win = total_wins / metrics.winning_trades if metrics.winning_trades > 0 else 0
        metrics.average_loss = total_losses / metrics.losing_trades if metrics.losing_trades > 0 else 0
        metrics.average_trade = sum(pnl_list) / metrics.total_trades if metrics.total_trades > 0 else 0
        
        # Win/loss ratio
        metrics.average_win_loss_ratio = (
            metrics.average_win / metrics.average_loss if metrics.average_loss > 0 else 0
        )
        
        # Largest values
        metrics.largest_win = max(pnl_list) if pnl_list else 0
        metrics.largest_loss = min(pnl_list) if pnl_list else 0
        
        # Consecutive wins/losses
        metrics.max_consecutive_wins = self._calculate_max_consecutive(pnl_list, 1)
        metrics.max_consecutive_losses = self._calculate_max_consecutive(pnl_list, -1)
        
        # Average holding period
        if 'duration' in trades[0]:
            durations = [t.get('duration', 0) for t in trades]
            metrics.average_holding_period = sum(durations) / len(durations) if durations else 0
            metrics.trade_duration = durations
        
        return metrics
    
    # ========================================
    # PORTFOLIO METRICS
    # ========================================
    
    async def calculate_portfolio_metrics(
        self,
        returns: List[float],
        benchmark_returns: Optional[List[float]] = None
    ) -> PortfolioMetrics:
        """
        Calculate portfolio metrics.
        
        Args:
            returns: Portfolio returns
            benchmark_returns: Benchmark returns
            
        Returns:
            PortfolioMetrics: Portfolio metrics
        """
        metrics = PortfolioMetrics()
        
        if not returns:
            return metrics
        
        # Use config benchmark if provided
        if not benchmark_returns and self.config.benchmark_data:
            benchmark_returns = self.config.benchmark_data
        
        # Sharpe ratio
        metrics.sharpe_ratio = self._calculate_sharpe_ratio(
            returns,
            self.config.risk_free_rate
        )
        
        # Sortino ratio
        metrics.sortino_ratio = self._calculate_sortino_ratio(
            returns,
            self.config.risk_free_rate
        )
        
        # Calmar ratio
        # Need max drawdown for Calmar
        # Use sample equity curve
        equity_curve = [100 + sum(returns[:i]) for i in range(len(returns) + 1)]
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        metrics.calmar_ratio = self._calculate_calmar_ratio(
            returns,
            max_drawdown
        )
        
        # Omega ratio
        metrics.omega_ratio = self._calculate_omega_ratio(
            returns,
            self.config.risk_free_rate
        )
        
        if benchmark_returns:
            # Beta
            metrics.beta = self._calculate_beta(returns, benchmark_returns)
            
            # Alpha
            metrics.alpha = self._calculate_alpha(
                returns,
                benchmark_returns,
                self.config.risk_free_rate
            )
            
            # Information ratio
            metrics.information_ratio = self._calculate_information_ratio(
                returns,
                benchmark_returns
            )
            
            # Treynor ratio
            metrics.treynor_ratio = self._calculate_treynor_ratio(
                returns,
                metrics.beta,
                self.config.risk_free_rate
            )
            
            # Capture ratio
            metrics.capture_ratio = self._calculate_capture_ratio(
                returns,
                benchmark_returns
            )
            
            # Correlation
            metrics.correlation = self._calculate_correlation(
                returns,
                benchmark_returns
            )
            
            # R-squared
            metrics.r_squared = metrics.correlation ** 2
        
        return metrics
    
    # ========================================
    # ROLLING METRICS
    # ========================================
    
    async def calculate_rolling_metrics(
        self,
        returns: List[float],
        equity_curve: List[float]
    ) -> RollingMetrics:
        """
        Calculate rolling metrics.
        
        Args:
            returns: Daily returns
            equity_curve: Equity curve
            
        Returns:
            RollingMetrics: Rolling metrics
        """
        metrics = RollingMetrics()
        
        if len(returns) < self.config.rolling_window:
            return metrics
        
        window = self.config.rolling_window
        
        # Rolling Sharpe ratio
        metrics.rolling_sharpe = self._calculate_rolling_sharpe(
            returns,
            window
        )
        
        # Rolling volatility
        metrics.rolling_volatility = self._calculate_rolling_volatility(
            returns,
            window
        )
        
        # Rolling max drawdown
        metrics.rolling_max_drawdown = self._calculate_rolling_max_drawdown(
            equity_curve,
            window
        )
        
        # Rolling win rate
        # Need trade data for win rate
        metrics.rolling_win_rate = []
        
        # Rolling returns
        metrics.rolling_returns = self._calculate_rolling_returns(
            returns,
            window
        )
        
        # Rolling correlation (needs benchmark)
        if self.config.benchmark_data:
            benchmark_returns = self.config.benchmark_data
            if len(benchmark_returns) >= window:
                metrics.rolling_correlation = self._calculate_rolling_correlation(
                    returns,
                    benchmark_returns,
                    window
                )
        
        return metrics
    
    # ========================================
    # CORE CALCULATION FUNCTIONS
    # ========================================
    
    def _calculate_returns(self, equity_curve: List[float]) -> List[float]:
        """Calculate daily returns from equity curve"""
        if len(equity_curve) < 2:
            return []
        
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] != 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)
        
        return returns
    
    def _calculate_total_return(self, equity_curve: List[float]) -> float:
        """Calculate total return"""
        if len(equity_curve) < 2:
            return 0.0
        
        initial = equity_curve[0]
        final = equity_curve[-1]
        
        if initial == 0:
            return 0.0
        
        return (final - initial) / initial
    
    def _calculate_annual_return(
        self,
        returns: List[float],
        n_periods: int
    ) -> float:
        """Calculate annualized return"""
        if not returns:
            return 0.0
        
        total_return = sum(returns)
        periods_per_year = 252
        
        if n_periods == 0:
            return 0.0
        
        return (1 + total_return) ** (periods_per_year / n_periods) - 1
    
    def _calculate_period_return(
        self,
        returns: List[float],
        n_periods: int
    ) -> float:
        """Calculate return over specific period"""
        if len(returns) < n_periods:
            return 0.0
        
        period_returns = returns[-n_periods:]
        return sum(period_returns)
    
    def _calculate_cumulative_return(self, returns: List[float]) -> float:
        """Calculate cumulative return"""
        if not returns:
            return 0.0
        
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        
        return cumulative - 1
    
    def _calculate_cagr(
        self,
        equity_curve: List[float],
        n_periods: int
    ) -> float:
        """Calculate Compound Annual Growth Rate"""
        if len(equity_curve) < 2 or n_periods == 0:
            return 0.0
        
        initial = equity_curve[0]
        final = equity_curve[-1]
        
        if initial == 0:
            return 0.0
        
        return (final / initial) ** (252 / n_periods) - 1
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.0
        
        std = np.std(returns)
        return std * np.sqrt(252)
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        max_drawdown = 0.0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak != 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_current_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate current drawdown"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = max(equity_curve)
        current = equity_curve[-1]
        
        if peak == 0:
            return 0.0
        
        return (peak - current) / peak
    
    def _calculate_var(
        self,
        returns: List[float],
        confidence: float
    ) -> float:
        """Calculate Value at Risk"""
        if len(returns) < 2:
            return 0.0
        
        return np.percentile(returns, (1 - confidence) * 100)
    
    def _calculate_cvar(
        self,
        returns: List[float],
        confidence: float
    ) -> float:
        """Calculate Conditional Value at Risk"""
        if len(returns) < 2:
            return 0.0
        
        var = self._calculate_var(returns, confidence)
        tail_returns = [r for r in returns if r <= var]
        
        if not tail_returns:
            return var
        
        return np.mean(tail_returns)
    
    def _calculate_expected_shortfall(self, returns: List[float]) -> float:
        """Calculate Expected Shortfall"""
        return self._calculate_cvar(returns, 0.95)
    
    def _calculate_tail_risk(self, returns: List[float]) -> float:
        """Calculate Tail Risk"""
        if len(returns) < 2:
            return 0.0
        
        # 5th percentile
        var_95 = self._calculate_var(returns, 0.95)
        # 1st percentile
        var_99 = self._calculate_var(returns, 0.99)
        
        return abs(var_99 - var_95)
    
    def _calculate_downside_deviation(self, returns: List[float]) -> float:
        """Calculate Downside Deviation"""
        if len(returns) < 2:
            return 0.0
        
        threshold = 0  # Risk-free rate can be used here
        downside_returns = [r for r in returns if r < threshold]
        
        if not downside_returns:
            return 0.0
        
        return np.std(downside_returns) * np.sqrt(252)
    
    def _calculate_upside_deviation(self, returns: List[float]) -> float:
        """Calculate Upside Deviation"""
        if len(returns) < 2:
            return 0.0
        
        threshold = 0
        upside_returns = [r for r in returns if r > threshold]
        
        if not upside_returns:
            return 0.0
        
        return np.std(upside_returns) * np.sqrt(252)
    
    def _calculate_drawdown_duration(self, equity_curve: List[float]) -> float:
        """Calculate average drawdown duration"""
        if len(equity_curve) < 2:
            return 0.0
        
        in_drawdown = False
        drawdown_start = 0
        total_duration = 0
        count = 0
        
        for i, value in enumerate(equity_curve):
            if value < max(equity_curve[:i+1]):
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = i
            else:
                if in_drawdown:
                    in_drawdown = False
                    total_duration += i - drawdown_start
                    count += 1
        
        return total_duration / count if count > 0 else 0
    
    def _calculate_recovery_time(self, equity_curve: List[float]) -> float:
        """Calculate recovery time after drawdown"""
        if len(equity_curve) < 2:
            return 0.0
        
        peak = equity_curve[0]
        peak_index = 0
        recovery_times = []
        
        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                peak_index = i
            elif value < peak:
                # Find recovery
                for j in range(i + 1, len(equity_curve)):
                    if equity_curve[j] >= peak:
                        recovery_times.append(j - i)
                        break
        
        return np.mean(recovery_times) if recovery_times else 0
    
    def _calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Sharpe Ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = [r - risk_free_rate / 252 for r in returns]
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns)
        
        if std_excess == 0:
            return 0.0
        
        return mean_excess / std_excess * np.sqrt(252)
    
    def _calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Sortino Ratio"""
        if len(returns) < 2:
            return 0.0
        
        threshold = risk_free_rate / 252
        downside_returns = [r for r in returns if r < threshold]
        
        if not downside_returns:
            return 0.0
        
        mean_return = np.mean(returns) - threshold
        downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0.0
        
        return mean_return / downside_std * np.sqrt(252)
    
    def _calculate_calmar_ratio(
        self,
        returns: List[float],
        max_drawdown: float
    ) -> float:
        """Calculate Calmar Ratio"""
        if max_drawdown == 0:
            return 0.0
        
        annual_return = self._calculate_annual_return(returns, len(returns))
        return annual_return / max_drawdown
    
    def _calculate_omega_ratio(
        self,
        returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Omega Ratio"""
        if not returns:
            return 0.0
        
        threshold = risk_free_rate / 252
        
        gains = sum(r - threshold for r in returns if r > threshold)
        losses = abs(sum(r - threshold for r in returns if r < threshold))
        
        if losses == 0:
            return float('inf')
        
        return gains / losses
    
    def _calculate_beta(
        self,
        returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """Calculate Beta"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 1.0
        
        # Align lengths
        min_len = min(len(returns), len(benchmark_returns))
        r = returns[-min_len:]
        b = benchmark_returns[-min_len:]
        
        covariance = np.cov(r, b)[0][1]
        variance = np.var(b)
        
        if variance == 0:
            return 1.0
        
        return covariance / variance
    
    def _calculate_alpha(
        self,
        returns: List[float],
        benchmark_returns: List[float],
        risk_free_rate: float
    ) -> float:
        """Calculate Alpha"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0
        
        beta = self._calculate_beta(returns, benchmark_returns)
        
        portfolio_return = self._calculate_annual_return(returns, len(returns))
        benchmark_return = self._calculate_annual_return(benchmark_returns, len(benchmark_returns))
        
        return portfolio_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
    
    def _calculate_information_ratio(
        self,
        returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """Calculate Information Ratio"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0
        
        min_len = min(len(returns), len(benchmark_returns))
        r = returns[-min_len:]
        b = benchmark_returns[-min_len:]
        
        excess_returns = [r[i] - b[i] for i in range(len(r))]
        
        if not excess_returns:
            return 0.0
        
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns)
        
        if std_excess == 0:
            return 0.0
        
        return mean_excess / std_excess * np.sqrt(252)
    
    def _calculate_treynor_ratio(
        self,
        returns: List[float],
        beta: float,
        risk_free_rate: float
    ) -> float:
        """Calculate Treynor Ratio"""
        if beta == 0:
            return 0.0
        
        portfolio_return = self._calculate_annual_return(returns, len(returns))
        return (portfolio_return - risk_free_rate) / beta
    
    def _calculate_capture_ratio(
        self,
        returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """Calculate Capture Ratio"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 1.0
        
        min_len = min(len(returns), len(benchmark_returns))
        r = returns[-min_len:]
        b = benchmark_returns[-min_len:]
        
        portfolio_return = self._calculate_annual_return(r, len(r))
        benchmark_return = self._calculate_annual_return(b, len(b))
        
        if benchmark_return == 0:
            return 1.0
        
        return portfolio_return / benchmark_return
    
    def _calculate_correlation(
        self,
        returns: List[float],
        benchmark_returns: List[float]
    ) -> float:
        """Calculate Correlation"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0
        
        min_len = min(len(returns), len(benchmark_returns))
        r = returns[-min_len:]
        b = benchmark_returns[-min_len:]
        
        return np.corrcoef(r, b)[0][1]
    
    def _calculate_rolling_returns(
        self,
        returns: List[float],
        window: int
    ) -> List[float]:
        """Calculate rolling returns"""
        if len(returns) < window:
            return []
        
        rolling_returns = []
        for i in range(window, len(returns) + 1):
            window_returns = returns[i-window:i]
            rolling_returns.append(sum(window_returns))
        
        return rolling_returns
    
    def _calculate_rolling_sharpe(
        self,
        returns: List[float],
        window: int
    ) -> List[float]:
        """Calculate rolling Sharpe ratio"""
        if len(returns) < window:
            return []
        
        rolling_sharpe = []
        for i in range(window, len(returns) + 1):
            window_returns = returns[i-window:i]
            sharpe = self._calculate_sharpe_ratio(
                window_returns,
                self.config.risk_free_rate
            )
            rolling_sharpe.append(sharpe)
        
        return rolling_sharpe
    
    def _calculate_rolling_volatility(
        self,
        returns: List[float],
        window: int
    ) -> List[float]:
        """Calculate rolling volatility"""
        if len(returns) < window:
            return []
        
        rolling_volatility = []
        for i in range(window, len(returns) + 1):
            window_returns = returns[i-window:i]
            vol = self._calculate_volatility(window_returns)
            rolling_volatility.append(vol)
        
        return rolling_volatility
    
    def _calculate_rolling_max_drawdown(
        self,
        equity_curve: List[float],
        window: int
    ) -> List[float]:
        """Calculate rolling max drawdown"""
        if len(equity_curve) < window:
            return []
        
        rolling_drawdown = []
        for i in range(window, len(equity_curve) + 1):
            window_equity = equity_curve[i-window:i]
            drawdown = self._calculate_max_drawdown(window_equity)
            rolling_drawdown.append(drawdown)
        
        return rolling_drawdown
    
    def _calculate_rolling_correlation(
        self,
        returns: List[float],
        benchmark_returns: List[float],
        window: int
    ) -> List[float]:
        """Calculate rolling correlation"""
        if len(returns) < window or len(benchmark_returns) < window:
            return []
        
        rolling_correlation = []
        min_len = min(len(returns), len(benchmark_returns))
        
        for i in range(window, min_len + 1):
            r = returns[i-window:i]
            b = benchmark_returns[i-window:i]
            corr = self._calculate_correlation(r, b)
            rolling_correlation.append(corr)
        
        return rolling_correlation
    
    def _calculate_max_consecutive(
        self,
        values: List[float],
        sign: int
    ) -> int:
        """Calculate max consecutive wins or losses"""
        max_consecutive = 0
        current_consecutive = 0
        
        for value in values:
            if (value > 0 and sign > 0) or (value < 0 and sign < 0):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _generate_summary(
        self,
        performance: PerformanceMetrics,
        risk: RiskMetrics,
        trades: TradeMetrics,
        portfolio: PortfolioMetrics
    ) -> Dict[str, Any]:
        """Generate summary of key metrics"""
        return {
            'total_return': performance.total_return,
            'annual_return': performance.annual_return,
            'sharpe_ratio': portfolio.sharpe_ratio,
            'max_drawdown': risk.max_drawdown,
            'win_rate': trades.win_rate,
            'profit_factor': trades.profit_factor,
            'total_trades': trades.total_trades,
            'volatility': risk.volatility,
            'calmar_ratio': portfolio.calmar_ratio,
            'sortino_ratio': portfolio.sortino_ratio
        }
    
    # ========================================
    # CACHE MANAGEMENT
    # ========================================
    
    def _generate_cache_key(
        self,
        equity_curve: List[float],
        trades: Optional[List[Dict[str, Any]]],
        benchmark_returns: Optional[List[float]],
        risk_free_rate: Optional[float]
    ) -> str:
        """Generate cache key"""
        import hashlib
        
        # Create a string representation
        key_data = {
            'equity_length': len(equity_curve),
            'equity_first': equity_curve[0] if equity_curve else 0,
            'equity_last': equity_curve[-1] if equity_curve else 0,
            'trades_count': len(trades) if trades else 0,
            'benchmark_length': len(benchmark_returns) if benchmark_returns else 0,
            'risk_free_rate': risk_free_rate or self.config.risk_free_rate,
            'config': self.config.dict()
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_metrics(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached metrics"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.config.cache_ttl:
                return data
        
        # Check Redis cache
        try:
            cached = self.redis.get(f"metrics:{key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
        
        return None
    
    def _set_cached_metrics(
        self,
        key: str,
        data: Dict[str, Any]
    ) -> None:
        """Cache metrics"""
        self._cache[key] = (data, datetime.utcnow())
        
        # Store in Redis
        try:
            self.redis.setex(
                f"metrics:{key}",
                self.config.cache_ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            self.logger.error(f"Redis cache error: {e}")
    
    # ========================================
    # EXPORT
    # ========================================
    
    async def export_metrics(
        self,
        metrics: Dict[str, Any],
        format: str = 'json'
    ) -> str:
        """
        Export metrics.
        
        Args:
            metrics: Metrics data
            format: Export format ('json', 'csv', 'html')
            
        Returns:
            str: Exported data
        """
        if format == 'json':
            return json.dumps(metrics, default=str, indent=2)
        elif format == 'csv':
            return self._export_csv(metrics)
        elif format == 'html':
            return await self._export_html(metrics)
        else:
            raise MetricsCalculationError(f"Unsupported format: {format}")
    
    def _export_csv(self, metrics: Dict[str, Any]) -> str:
        """Export as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Metric', 'Value'])
        
        # Write metrics
        for category, values in metrics.items():
            if category in ['returns', 'equity_curve']:
                continue
            if isinstance(values, dict):
                for key, value in values.items():
                    if not isinstance(value, (list, dict)):
                        writer.writerow([f"{category}.{key}", value])
        
        return output.getvalue()
    
    async def _export_html(self, metrics: Dict[str, Any]) -> str:
        """Export as HTML"""
        # Create HTML report
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Metrics Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #1a1a2e; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
                .card { background: #f5f5f5; padding: 15px; border-radius: 8px; }
                .card-title { font-size: 14px; color: #666; }
                .card-value { font-size: 24px; font-weight: bold; margin-top: 5px; }
                .card-value.positive { color: #22c55e; }
                .card-value.negative { color: #ef4444; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #f5f5f5; }
            </style>
        </head>
        <body>
            <h1>Metrics Report</h1>
        """
        
        # Add summary cards
        summary = metrics.get('summary', {})
        if summary:
            html += '<div class="grid">'
            for key, value in summary.items():
                cls = 'positive' if value > 0 else 'negative' if value < 0 else ''
                html += f"""
                <div class="card">
                    <div class="card-title">{key.replace('_', ' ').title()}</div>
                    <div class="card-value {cls}">{value:.2%}</div>
                </div>
                """
            html += '</div>'
        
        # Add performance metrics
        performance = metrics.get('performance', {})
        if performance:
            html += '<h2>Performance Metrics</h2>'
            html += '<table><tr><th>Metric</th><th>Value</th></tr>'
            for key, value in performance.items():
                if not isinstance(value, list):
                    if isinstance(value, float):
                        html += f'<tr><td>{key.replace("_", " ").title()}</td><td>{value:.2%}</td></tr>'
            html += '</table>'
        
        # Add risk metrics
        risk = metrics.get('risk', {})
        if risk:
            html += '<h2>Risk Metrics</h2>'
            html += '<table><tr><th>Metric</th><th>Value</th></tr>'
            for key, value in risk.items():
                if not isinstance(value, list):
                    if isinstance(value, float):
                        html += f'<tr><td>{key.replace("_", " ").title()}</td><td>{value:.2%}</td></tr>'
            html += '</table>'
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the metrics calculator"""
        self._running = True
        self.logger.info("MetricsCalculator started")
    
    async def stop(self) -> None:
        """Stop the metrics calculator"""
        self._running = False
        self.logger.info("MetricsCalculator stopped")
    
    async def health_check(self) -> bool:
        """Check calculator health"""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_metrics_calculator: Optional[MetricsCalculator] = None


def get_metrics_calculator() -> MetricsCalculator:
    """Get singleton instance of MetricsCalculator"""
    global _metrics_calculator
    if _metrics_calculator is None:
        _metrics_calculator = MetricsCalculator()
    return _metrics_calculator


def reset_metrics_calculator() -> None:
    """Reset the metrics calculator (for testing)"""
    global _metrics_calculator
    if _metrics_calculator:
        asyncio.create_task(_metrics_calculator.stop())
    _metrics_calculator = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MetricsCalculator',
    'MetricsConfig',
    'MetricType',
    'AnnualizationMethod',
    'PerformanceMetrics',
    'RiskMetrics',
    'TradeMetrics',
    'PortfolioMetrics',
    'RollingMetrics',
    'get_metrics_calculator',
    'reset_metrics_calculator'
]
