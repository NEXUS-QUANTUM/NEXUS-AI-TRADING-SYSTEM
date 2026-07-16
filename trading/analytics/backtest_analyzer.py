"""
NEXUS AI TRADING SYSTEM - Backtest Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced backtest analysis with comprehensive performance metrics,
risk analysis, and visualization capabilities.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, skew, kurtosis, jarque_bera
import warnings
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dataclasses_json import dataclass_json

from nexus.shared.types.trading import (
    Trade, TradeDirection, TradeStatus, 
    OrderType, OrderStatus, Position
)
from nexus.shared.helpers.trading_helpers import (
    calculate_returns, calculate_drawdown, calculate_sharpe_ratio,
    calculate_calmar_ratio, calculate_sortino_ratio, calculate_omega_ratio,
    calculate_win_rate, calculate_profit_factor, calculate_average_trade,
    calculate_max_consecutive_losses, calculate_recovery_factor
)
from nexus.trading.analytics.metrics_calculator import MetricsCalculator
from nexus.trading.analytics.visualizer import Visualizer
from nexus.shared.utilities.logger import Logger

logger = Logger(__name__)


class RiskMetricType(Enum):
    """Types of risk metrics"""
    VAR = "var"
    CVAR = "cvar"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    CALMAR = "calmar"
    OMEGA = "omega"
    TAIL_RATIO = "tail_ratio"
    PAIN_INDEX = "pain_index"
    MARTIN_RATIO = "martin_ratio"


@dataclass_json
@dataclass
class BacktestConfig:
    """Configuration for backtest analysis"""
    # Analysis parameters
    risk_free_rate: float = 0.02
    confidence_level: float = 0.95
    var_method: str = "historical"  # historical, parametric, monte_carlo
    
    # Benchmark parameters
    benchmark_symbol: Optional[str] = None
    benchmark_data: Optional[pd.Series] = None
    
    # Advanced metrics
    calculate_rolling_metrics: bool = True
    rolling_window: int = 252  # trading days
    calculate_annualized_metrics: bool = True
    annualization_factor: int = 252
    
    # Monte Carlo parameters
    monte_carlo_simulations: int = 10000
    monte_carlo_days: int = 252
    
    # Risk management
    max_leverage: float = 10.0
    max_position_size: float = 1.0
    max_correlation: float = 0.8
    
    # Output options
    generate_charts: bool = True
    generate_report: bool = True
    save_results: bool = True
    output_dir: str = "data/exports/backtest_results"
    
    # Parallel processing
    use_parallel: bool = True
    max_workers: int = 4


@dataclass_json
@dataclass
class TradeAnalytics:
    """Advanced trade-level analytics"""
    # Basic metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    # Win rates
    win_rate: float = 0.0
    win_rate_by_direction: Dict[str, float] = field(default_factory=dict)
    
    # PnL metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    
    # Average metrics
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    avg_trade_duration: float = 0.0
    
    # Extreme metrics
    max_win: float = 0.0
    max_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_running_loss: float = 0.0
    
    # Distribution metrics
    pnl_skew: float = 0.0
    pnl_kurtosis: float = 0.0
    pnl_jarque_bera: Dict[str, float] = field(default_factory=dict)
    
    # Direction analysis
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0
    long_pnl: float = 0.0
    short_pnl: float = 0.0
    
    # Time analysis
    trades_by_hour: Dict[int, int] = field(default_factory=dict)
    trades_by_day: Dict[str, int] = field(default_factory=dict)
    trades_by_month: Dict[str, int] = field(default_factory=dict)
    
    # Performance over time
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    yearly_returns: Dict[str, float] = field(default_factory=dict)
    
    # Statistical significance
    t_statistic: float = 0.0
    p_value: float = 0.0
    is_statistically_significant: bool = False
    
    # Equity curve analysis
    equity_curve_volatility: float = 0.0
    equity_curve_skew: float = 0.0
    equity_curve_kurtosis: float = 0.0


@dataclass_json
@dataclass
class RiskAnalytics:
    """Comprehensive risk analytics"""
    # Value at Risk
    var_95: float = 0.0  # 95% VaR
    var_99: float = 0.0  # 99% VaR
    cvar_95: float = 0.0  # 95% CVaR
    cvar_99: float = 0.0  # 99% CVaR
    
    # VaR breakdown
    var_historical: float = 0.0
    var_parametric: float = 0.0
    var_monte_carlo: float = 0.0
    
    # Drawdown metrics
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    avg_drawdown: float = 0.0
    avg_drawdown_duration: int = 0
    max_drawdown_date: Optional[datetime] = None
    max_drawdown_recovery_date: Optional[datetime] = None
    
    # Drawdown segmentation
    drawdown_periods: List[Dict[str, Any]] = field(default_factory=list)
    drawdown_distribution: Dict[str, float] = field(default_factory=dict)
    
    # Volatility metrics
    volatility_annualized: float = 0.0
    volatility_monthly: float = 0.0
    volatility_weekly: float = 0.0
    volatility_daily: float = 0.0
    volatility_rolling: List[float] = field(default_factory=list)
    
    # Risk ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    tail_ratio: float = 0.0
    pain_index: float = 0.0
    martin_ratio: float = 0.0
    
    # Risk exposure
    max_exposure: float = 0.0
    avg_exposure: float = 0.0
    exposure_by_asset: Dict[str, float] = field(default_factory=dict)
    leverage_used: float = 0.0
    
    # Risk of ruin
    risk_of_ruin: float = 0.0
    probability_of_loss: float = 0.0
    
    # Stress testing
    stress_test_results: Dict[str, float] = field(default_factory=dict)
    scenario_analysis: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Correlation metrics
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    beta_to_market: Optional[float] = None
    alpha_to_market: Optional[float] = None


@dataclass_json
@dataclass
class PerformanceAnalytics:
    """Comprehensive performance analytics"""
    # Basic returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    monthly_return_avg: float = 0.0
    daily_return_avg: float = 0.0
    
    # Cumulative returns
    cumulative_return: List[float] = field(default_factory=list)
    cumulative_dates: List[datetime] = field(default_factory=list)
    
    # Annual returns
    annual_returns: Dict[str, float] = field(default_factory=dict)
    best_year: Dict[str, Any] = field(default_factory=dict)
    worst_year: Dict[str, Any] = field(default_factory=dict)
    
    # Monthly returns
    monthly_returns_matrix: Dict[str, Dict[int, float]] = field(default_factory=dict)
    
    # Rolling metrics
    rolling_returns: List[float] = field(default_factory=list)
    rolling_sharpe: List[float] = field(default_factory=list)
    rolling_volatility: List[float] = field(default_factory=list)
    rolling_drawdown: List[float] = field(default_factory=list)
    
    # Benchmark comparison
    benchmark_return: Optional[float] = None
    benchmark_annualized_return: Optional[float] = None
    benchmark_volatility: Optional[float] = None
    relative_return: Optional[float] = None
    information_ratio: Optional[float] = None
    
    # Performance metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    recovery_factor: float = 0.0
    payoff_ratio: float = 0.0
    
    # Peak performance
    best_trade: Dict[str, Any] = field(default_factory=dict)
    worst_trade: Dict[str, Any] = field(default_factory=dict)
    best_month: Dict[str, Any] = field(default_factory=dict)
    worst_month: Dict[str, Any] = field(default_factory=dict)
    
    # Consistency metrics
    consistency_score: float = 0.0
    positive_months: int = 0
    negative_months: int = 0
    win_months_ratio: float = 0.0


@dataclass_json
@dataclass
class BacktestAnalysisResult:
    """Complete backtest analysis result"""
    # Basic information
    strategy_name: str = ""
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    analysis_duration: float = 0.0
    
    # Core analytics
    trade_analytics: TradeAnalytics = field(default_factory=TradeAnalytics)
    risk_analytics: RiskAnalytics = field(default_factory=RiskAnalytics)
    performance_analytics: PerformanceAnalytics = field(default_factory=PerformanceAnalytics)
    
    # Combined metrics
    overall_score: float = 0.0
    risk_adjusted_return: float = 0.0
    quality_score: float = 0.0
    
    # Raw data
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    returns_series: List[float] = field(default_factory=list)
    
    # Summaries
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Visualization references
    chart_paths: Dict[str, str] = field(default_factory=dict)
    report_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy_name": self.strategy_name,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "analysis_duration": self.analysis_duration,
            "trade_analytics": self.trade_analytics.to_dict(),
            "risk_analytics": self.risk_analytics.to_dict(),
            "performance_analytics": self.performance_analytics.to_dict(),
            "overall_score": self.overall_score,
            "risk_adjusted_return": self.risk_adjusted_return,
            "quality_score": self.quality_score,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "warnings": self.warnings
        }


class BacktestAnalyzer:
    """
    Advanced backtest analyzer with comprehensive analytics capabilities.
    Provides deep performance, risk, and trade analysis with statistical rigor.
    """
    
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        executor: Optional[ThreadPoolExecutor] = None
    ):
        """
        Initialize the backtest analyzer.
        
        Args:
            config: Configuration for analysis
            executor: Thread pool executor for parallel processing
        """
        self.config = config or BacktestConfig()
        self.executor = executor or ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._metrics_calculator = MetricsCalculator()
        self._visualizer = Visualizer()
        self._logger = Logger(__name__)
        
    async def analyze_trades(
        self,
        trades: List[Trade],
        initial_capital: float = 10000.0,
        benchmark_returns: Optional[List[float]] = None
    ) -> BacktestAnalysisResult:
        """
        Perform comprehensive backtest analysis on a list of trades.
        
        Args:
            trades: List of trades to analyze
            initial_capital: Initial capital for the strategy
            benchmark_returns: Benchmark returns for comparison
            
        Returns:
            Complete backtest analysis result
        """
        start_time = datetime.now()
        
        self._logger.info(f"Starting backtest analysis on {len(trades)} trades")
        
        try:
            # Convert trades to DataFrame for analysis
            df_trades = self._trades_to_dataframe(trades)
            
            # Calculate equity curve and returns
            equity_curve = self._calculate_equity_curve(df_trades, initial_capital)
            returns_series = self._calculate_returns_series(equity_curve)
            drawdown_curve = self._calculate_drawdown_curve(equity_curve)
            
            # Run analytics in parallel
            tasks = [
                self._analyze_trades_async(df_trades),
                self._analyze_risk_async(returns_series, drawdown_curve, equity_curve),
                self._analyze_performance_async(returns_series, equity_curve, benchmark_returns)
            ]
            
            trade_analytics, risk_analytics, performance_analytics = await asyncio.gather(*tasks)
            
            # Calculate combined metrics
            overall_score = self._calculate_overall_score(
                trade_analytics, risk_analytics, performance_analytics
            )
            
            risk_adjusted_return = self._calculate_risk_adjusted_return(
                performance_analytics, risk_analytics
            )
            
            quality_score = self._calculate_quality_score(
                trade_analytics, risk_analytics, performance_analytics
            )
            
            # Generate summary
            summary = self._generate_summary(
                trade_analytics, risk_analytics, performance_analytics
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                trade_analytics, risk_analytics, performance_analytics
            )
            
            # Generate warnings
            warnings = self._generate_warnings(
                trade_analytics, risk_analytics, performance_analytics
            )
            
            # Create result
            result = BacktestAnalysisResult(
                strategy_name=self._extract_strategy_name(trades),
                analysis_timestamp=datetime.now(),
                analysis_duration=(datetime.now() - start_time).total_seconds(),
                trade_analytics=trade_analytics,
                risk_analytics=risk_analytics,
                performance_analytics=performance_analytics,
                overall_score=overall_score,
                risk_adjusted_return=risk_adjusted_return,
                quality_score=quality_score,
                trades=trades,
                equity_curve=equity_curve,
                drawdown_curve=drawdown_curve,
                returns_series=returns_series,
                summary=summary,
                recommendations=recommendations,
                warnings=warnings
            )
            
            # Generate charts if requested
            if self.config.generate_charts:
                result.chart_paths = await self._generate_charts(result)
            
            # Generate report if requested
            if self.config.generate_report:
                result.report_path = await self._generate_report(result)
            
            # Save results if requested
            if self.config.save_results:
                await self._save_results(result)
            
            self._logger.info(f"Backtest analysis completed in {result.analysis_duration:.2f}s")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error in backtest analysis: {str(e)}")
            raise
    
    def _trades_to_dataframe(self, trades: List[Trade]) -> pd.DataFrame:
        """Convert trades to pandas DataFrame with proper types."""
        if not trades:
            return pd.DataFrame()
            
        data = []
        for trade in trades:
            entry_price = trade.entry_price if trade.entry_price else 0
            exit_price = trade.exit_price if trade.exit_price else entry_price
            pnl = trade.pnl if trade.pnl else 0
            
            data.append({
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "volume": trade.volume,
                "direction": trade.direction.value,
                "pnl": pnl,
                "pnl_percent": pnl / (entry_price * trade.volume) if entry_price > 0 else 0,
                "status": trade.status.value,
                "strategy": trade.strategy if hasattr(trade, 'strategy') else "default",
                "symbol": trade.symbol
            })
            
        df = pd.DataFrame(data)
        
        # Convert time columns
        if "entry_time" in df.columns:
            df["entry_time"] = pd.to_datetime(df["entry_time"])
        if "exit_time" in df.columns:
            df["exit_time"] = pd.to_datetime(df["exit_time"])
            
        return df
    
    def _calculate_equity_curve(
        self,
        df_trades: pd.DataFrame,
        initial_capital: float
    ) -> List[float]:
        """Calculate equity curve from trades."""
        if df_trades.empty:
            return [initial_capital]
            
        # Sort trades by entry time
        df_sorted = df_trades.sort_values("entry_time")
        
        equity = [initial_capital]
        current_equity = initial_capital
        
        for _, trade in df_sorted.iterrows():
            current_equity += trade["pnl"]
            equity.append(current_equity)
            
        return equity
    
    def _calculate_returns_series(self, equity_curve: List[float]) -> List[float]:
        """Calculate returns series from equity curve."""
        if len(equity_curve) < 2:
            return [0.0]
            
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] != 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)
                
        return returns
    
    def _calculate_drawdown_curve(self, equity_curve: List[float]) -> List[float]:
        """Calculate drawdown curve from equity curve."""
        if not equity_curve:
            return []
            
        running_max = equity_curve[0]
        drawdowns = []
        
        for equity in equity_curve:
            if equity > running_max:
                running_max = equity
            drawdown = (running_max - equity) / running_max if running_max > 0 else 0
            drawdowns.append(drawdown)
            
        return drawdowns
    
    async def _analyze_trades_async(self, df_trades: pd.DataFrame) -> TradeAnalytics:
        """Analyze trade-level metrics asynchronously."""
        if df_trades.empty:
            return TradeAnalytics()
            
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._analyze_trades_sync,
            df_trades
        )
    
    def _analyze_trades_sync(self, df_trades: pd.DataFrame) -> TradeAnalytics:
        """Synchronous trade analysis."""
        analytics = TradeAnalytics()
        
        # Filter completed trades
        df_completed = df_trades[df_trades["status"] == TradeStatus.COMPLETED.value]
        
        if df_completed.empty:
            return analytics
            
        # Basic metrics
        analytics.total_trades = len(df_completed)
        analytics.winning_trades = len(df_completed[df_completed["pnl"] > 0])
        analytics.losing_trades = len(df_completed[df_completed["pnl"] < 0])
        analytics.breakeven_trades = len(df_completed[df_completed["pnl"] == 0])
        
        # Win rate
        analytics.win_rate = analytics.winning_trades / analytics.total_trades
        
        # PnL metrics
        analytics.gross_profit = df_completed[df_completed["pnl"] > 0]["pnl"].sum()
        analytics.gross_loss = df_completed[df_completed["pnl"] < 0]["pnl"].sum()
        analytics.net_profit = analytics.gross_profit + analytics.gross_loss
        analytics.profit_factor = abs(analytics.gross_profit / analytics.gross_loss) if analytics.gross_loss != 0 else float('inf')
        
        # Average metrics
        analytics.avg_trade = df_completed["pnl"].mean()
        analytics.avg_win = df_completed[df_completed["pnl"] > 0]["pnl"].mean() if analytics.winning_trades > 0 else 0
        analytics.avg_loss = df_completed[df_completed["pnl"] < 0]["pnl"].mean() if analytics.losing_trades > 0 else 0
        
        # Calculate trade durations
        df_completed["duration"] = (df_completed["exit_time"] - df_completed["entry_time"]).dt.total_seconds()
        analytics.avg_trade_duration = df_completed["duration"].mean() if not df_completed.empty else 0
        
        # Extreme metrics
        analytics.max_win = df_completed["pnl"].max() if not df_completed.empty else 0
        analytics.max_loss = df_completed["pnl"].min() if not df_completed.empty else 0
        
        # Consecutive wins/losses
        win_series = (df_completed["pnl"] > 0).astype(int)
        analytics.max_consecutive_wins = self._max_consecutive(win_series, 1)
        analytics.max_consecutive_losses = self._max_consecutive(win_series, 0)
        
        # Running loss
        running_loss = 0
        max_running_loss = 0
        for pnl in df_completed["pnl"]:
            if pnl < 0:
                running_loss += pnl
                max_running_loss = min(max_running_loss, running_loss)
            else:
                running_loss = 0
        analytics.max_running_loss = max_running_loss
        
        # Distribution metrics
        pnl_values = df_completed["pnl"].values
        analytics.pnl_skew = skew(pnl_values) if len(pnl_values) > 0 else 0
        analytics.pnl_kurtosis = kurtosis(pnl_values) if len(pnl_values) > 0 else 0
        
        # Jarque-Bera test for normality
        if len(pnl_values) > 0:
            jb_stat, jb_pvalue = jarque_bera(pnl_values)
            analytics.pnl_jarque_bera = {"statistic": jb_stat, "p_value": jb_pvalue}
        
        # Direction analysis
        df_long = df_completed[df_completed["direction"] == TradeDirection.LONG.value]
        df_short = df_completed[df_completed["direction"] == TradeDirection.SHORT.value]
        
        analytics.long_trades = len(df_long)
        analytics.short_trades = len(df_short)
        analytics.long_win_rate = len(df_long[df_long["pnl"] > 0]) / len(df_long) if len(df_long) > 0 else 0
        analytics.short_win_rate = len(df_short[df_short["pnl"] > 0]) / len(df_short) if len(df_short) > 0 else 0
        analytics.long_pnl = df_long["pnl"].sum() if not df_long.empty else 0
        analytics.short_pnl = df_short["pnl"].sum() if not df_short.empty else 0
        
        analytics.win_rate_by_direction = {
            "long": analytics.long_win_rate,
            "short": analytics.short_win_rate
        }
        
        # Time analysis
        if "entry_time" in df_completed.columns:
            analytics.trades_by_hour = df_completed["entry_time"].dt.hour.value_counts().to_dict()
            analytics.trades_by_day = df_completed["entry_time"].dt.day_name().value_counts().to_dict()
            analytics.trades_by_month = df_completed["entry_time"].dt.strftime("%Y-%m").value_counts().to_dict()
            
            # Monthly returns
            df_completed["month"] = df_completed["entry_time"].dt.strftime("%Y-%m")
            analytics.monthly_returns = df_completed.groupby("month")["pnl"].sum().to_dict()
            
            # Yearly returns
            df_completed["year"] = df_completed["entry_time"].dt.year
            analytics.yearly_returns = df_completed.groupby("year")["pnl"].sum().to_dict()
        
        # Statistical significance
        if len(pnl_values) > 1:
            t_stat, p_val = stats.ttest_1samp(pnl_values, 0)
            analytics.t_statistic = t_stat
            analytics.p_value = p_val
            analytics.is_statistically_significant = p_val < 0.05
        
        # Equity curve analysis
        cumulative_pnl = df_completed["pnl"].cumsum()
        analytics.equity_curve_volatility = cumulative_pnl.std() if len(cumulative_pnl) > 0 else 0
        if len(cumulative_pnl) > 0:
            analytics.equity_curve_skew = skew(cumulative_pnl)
            analytics.equity_curve_kurtosis = kurtosis(cumulative_pnl)
        
        return analytics
    
    def _max_consecutive(self, series: pd.Series, target_value: int) -> int:
        """Calculate maximum consecutive occurrences of a value."""
        max_count = 0
        current_count = 0
        
        for value in series:
            if value == target_value:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
                
        return max_count
    
    async def _analyze_risk_async(
        self,
        returns_series: List[float],
        drawdown_curve: List[float],
        equity_curve: List[float]
    ) -> RiskAnalytics:
        """Analyze risk metrics asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._analyze_risk_sync,
            returns_series,
            drawdown_curve,
            equity_curve
        )
    
    def _analyze_risk_sync(
        self,
        returns_series: List[float],
        drawdown_curve: List[float],
        equity_curve: List[float]
    ) -> RiskAnalytics:
        """Synchronous risk analysis."""
        analytics = RiskAnalytics()
        
        if not returns_series:
            return analytics
            
        returns_array = np.array(returns_series)
        
        # VaR calculations
        analytics.var_95 = np.percentile(returns_array, 5)
        analytics.var_99 = np.percentile(returns_array, 1)
        
        # CVaR (Expected Shortfall)
        analytics.cvar_95 = returns_array[returns_array <= analytics.var_95].mean() if len(returns_array[returns_array <= analytics.var_95]) > 0 else 0
        analytics.cvar_99 = returns_array[returns_array <= analytics.var_99].mean() if len(returns_array[returns_array <= analytics.var_99]) > 0 else 0
        
        # VaR by method
        analytics.var_historical = analytics.var_95
        analytics.var_parametric = self._calculate_parametric_var(returns_array, 0.95)
        analytics.var_monte_carlo = self._calculate_monte_carlo_var(returns_array, 0.95)
        
        # Drawdown metrics
        if drawdown_curve:
            analytics.max_drawdown = max(drawdown_curve)
            analytics.avg_drawdown = np.mean(drawdown_curve)
            
            # Drawdown duration
            in_drawdown = False
            current_duration = 0
            total_duration = 0
            num_periods = 0
            
            for dd in drawdown_curve:
                if dd > 0.01:  # 1% threshold
                    if not in_drawdown:
                        in_drawdown = True
                        current_duration = 0
                    current_duration += 1
                else:
                    if in_drawdown:
                        in_drawdown = False
                        total_duration += current_duration
                        num_periods += 1
                        
            analytics.max_drawdown_duration = current_duration if in_drawdown else 0
            analytics.avg_drawdown_duration = total_duration / num_periods if num_periods > 0 else 0
            
            # Find max drawdown period
            max_dd = 0
            max_dd_idx = 0
            for i, dd in enumerate(drawdown_curve):
                if dd > max_dd:
                    max_dd = dd
                    max_dd_idx = i
                    
            if max_dd_idx > 0 and max_dd_idx < len(equity_curve):
                analytics.max_drawdown_date = datetime.now() - timedelta(days=max_dd_idx)
                # Find recovery
                for j in range(max_dd_idx, len(equity_curve)):
                    if equity_curve[j] >= equity_curve[max_dd_idx] * (1 - max_dd):
                        analytics.max_drawdown_recovery_date = datetime.now() - timedelta(days=j)
                        break
        
        # Volatility metrics
        analytics.volatility_daily = returns_array.std()
        analytics.volatility_weekly = returns_array.std() * np.sqrt(5)
        analytics.volatility_monthly = returns_array.std() * np.sqrt(21)
        analytics.volatility_annualized = returns_array.std() * np.sqrt(252)
        
        # Rolling volatility
        if len(returns_series) > 20:
            analytics.volatility_rolling = [
                np.std(returns_series[max(0, i-20):i]) 
                for i in range(20, len(returns_series) + 1)
            ]
        
        # Risk ratios
        avg_return = np.mean(returns_array) * 252  # annualized
        risk_free = self.config.risk_free_rate
        
        analytics.sharpe_ratio = (avg_return - risk_free) / analytics.volatility_annualized if analytics.volatility_annualized > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        analytics.sortino_ratio = (avg_return - risk_free) / downside_deviation if downside_deviation > 0 else 0
        
        # Calmar ratio (return / max drawdown)
        analytics.calmar_ratio = avg_return / analytics.max_drawdown if analytics.max_drawdown > 0 else 0
        
        # Omega ratio
        threshold = 0
        analytics.omega_ratio = self._calculate_omega_ratio(returns_array, threshold)
        
        # Tail ratio
        analytics.tail_ratio = self._calculate_tail_ratio(returns_array)
        
        # Pain index
        analytics.pain_index = self._calculate_pain_index(drawdown_curve)
        
        # Martin ratio
        analytics.martin_ratio = self._calculate_martin_ratio(returns_array, drawdown_curve)
        
        # Risk of ruin
        analytics.risk_of_ruin = self._calculate_risk_of_ruin(returns_array)
        analytics.probability_of_loss = np.mean(returns_array < 0)
        
        # Stress testing
        analytics.stress_test_results = self._stress_test(returns_array)
        
        # Scenario analysis
        analytics.scenario_analysis = self._scenario_analysis(returns_array, equity_curve)
        
        return analytics
    
    def _calculate_parametric_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate parametric VaR assuming normal distribution."""
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_score = norm.ppf(1 - confidence)
        return mu + z_score * sigma
    
    def _calculate_monte_carlo_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate VaR using Monte Carlo simulation."""
        if len(returns) < 2:
            return 0
            
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        # Generate random scenarios
        scenarios = np.random.normal(mu, sigma, self.config.monte_carlo_simulations)
        return np.percentile(scenarios, (1 - confidence) * 100)
    
    def _calculate_omega_ratio(self, returns: np.ndarray, threshold: float) -> float:
        """Calculate Omega ratio."""
        gains = returns[returns > threshold]
        losses = returns[returns < threshold]
        
        if len(losses) == 0 or np.abs(losses.sum()) == 0:
            return float('inf')
            
        return gains.sum() / np.abs(losses.sum())
    
    def _calculate_tail_ratio(self, returns: np.ndarray) -> float:
        """Calculate tail ratio (95th percentile / 5th percentile)."""
        percentile_95 = np.percentile(returns, 95)
        percentile_5 = np.percentile(returns, 5)
        
        if percentile_5 == 0:
            return 0
            
        return np.abs(percentile_95 / percentile_5)
    
    def _calculate_pain_index(self, drawdown_curve: List[float]) -> float:
        """Calculate Pain Index (average of squared drawdowns)."""
        if not drawdown_curve:
            return 0
            
        squared_drawdowns = [dd ** 2 for dd in drawdown_curve]
        return np.mean(squared_drawdowns)
    
    def _calculate_martin_ratio(self, returns: np.ndarray, drawdown_curve: List[float]) -> float:
        """Calculate Martin ratio (return / pain index)."""
        avg_return = np.mean(returns) * 252  # annualized
        pain_index = self._calculate_pain_index(drawdown_curve)
        
        return avg_return / pain_index if pain_index > 0 else 0
    
    def _calculate_risk_of_ruin(self, returns: np.ndarray) -> float:
        """Calculate risk of ruin."""
        # Using Kelly criterion approximation
        win_rate = np.mean(returns > 0)
        avg_win = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0
        avg_loss = np.mean(returns[returns < 0]) if np.any(returns < 0) else 0
        
        if avg_loss == 0:
            return 0
            
        kelly_fraction = win_rate - (1 - win_rate) * (avg_win / abs(avg_loss))
        
        # Risk of ruin with 1% of capital
        if kelly_fraction > 0:
            risk_of_ruin = np.exp(-2 * kelly_fraction * 0.01)  # 1% of capital
        else:
            risk_of_ruin = 1.0
            
        return min(risk_of_ruin, 1.0)
    
    def _stress_test(self, returns: np.ndarray) -> Dict[str, float]:
        """Perform stress testing on returns."""
        results = {}
        
        # Historical shocks
        scenarios = {
            "crash_2008": -0.05,  # 5% daily loss
            "crash_2020": -0.12,  # 12% daily loss
            "flash_crash": -0.20,  # 20% daily loss
            "bear_market": -0.02,  # 2% daily loss for 30 days
        }
        
        for scenario, shock in scenarios.items():
            # Apply shock to returns
            stressed_returns = returns.copy()
            # Simulate shock impact
            if isinstance(shock, float):
                # Single day shock
                stressed_returns[-1] = shock
            elif isinstance(shock, tuple):
                # Multi-day shock
                start_idx = len(returns) - shock[1]
                stressed_returns[start_idx:] = shock[0]
            
            # Calculate impact
            impact = np.sum(stressed_returns) - np.sum(returns)
            results[scenario] = impact
            
        return results
    
    def _scenario_analysis(
        self,
        returns: np.ndarray,
        equity_curve: List[float]
    ) -> Dict[str, Dict[str, float]]:
        """Perform scenario analysis."""
        scenarios = {}
        
        # Bull market scenario
        bull_returns = returns[returns > np.percentile(returns, 50)]
        if len(bull_returns) > 0:
            scenarios["bull_market"] = {
                "return": np.mean(bull_returns) * 252,
                "volatility": np.std(bull_returns) * np.sqrt(252),
                "sharpe": (np.mean(bull_returns) * 252 - self.config.risk_free_rate) / (np.std(bull_returns) * np.sqrt(252) if np.std(bull_returns) > 0 else 1)
            }
        
        # Bear market scenario
        bear_returns = returns[returns <= np.percentile(returns, 50)]
        if len(bear_returns) > 0:
            scenarios["bear_market"] = {
                "return": np.mean(bear_returns) * 252,
                "volatility": np.std(bear_returns) * np.sqrt(252),
                "sharpe": (np.mean(bear_returns) * 252 - self.config.risk_free_rate) / (np.std(bear_returns) * np.sqrt(252) if np.std(bear_returns) > 0 else 1)
            }
        
        # High volatility scenario
        high_vol_returns = returns[np.abs(returns) > np.std(returns) * 1.5]
        if len(high_vol_returns) > 0:
            scenarios["high_volatility"] = {
                "return": np.mean(high_vol_returns) * 252,
                "volatility": np.std(high_vol_returns) * np.sqrt(252),
                "sharpe": (np.mean(high_vol_returns) * 252 - self.config.risk_free_rate) / (np.std(high_vol_returns) * np.sqrt(252) if np.std(high_vol_returns) > 0 else 1)
            }
        
        return scenarios
    
    async def _analyze_performance_async(
        self,
        returns_series: List[float],
        equity_curve: List[float],
        benchmark_returns: Optional[List[float]] = None
    ) -> PerformanceAnalytics:
        """Analyze performance metrics asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._analyze_performance_sync,
            returns_series,
            equity_curve,
            benchmark_returns
        )
    
    def _analyze_performance_sync(
        self,
        returns_series: List[float],
        equity_curve: List[float],
        benchmark_returns: Optional[List[float]] = None
    ) -> PerformanceAnalytics:
        """Synchronous performance analysis."""
        analytics = PerformanceAnalytics()
        
        if not returns_series or len(equity_curve) < 2:
            return analytics
            
        returns_array = np.array(returns_series)
        equity_array = np.array(equity_curve)
        
        # Basic returns
        analytics.total_return = (equity_array[-1] / equity_array[0]) - 1 if equity_array[0] > 0 else 0
        n_years = len(returns_series) / 252
        analytics.annualized_return = (1 + analytics.total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        analytics.daily_return_avg = np.mean(returns_array)
        analytics.monthly_return_avg = np.mean(returns_array) * 21
        
        # Cumulative returns
        cumulative_returns = np.cumprod(1 + returns_array) - 1
        analytics.cumulative_return = cumulative_returns.tolist()
        analytics.cumulative_dates = [datetime.now() - timedelta(days=i) for i in range(len(cumulative_returns))]
        
        # Annual returns
        analytics.annual_returns = self._calculate_annual_returns(returns_series)
        
        # Best and worst year
        if analytics.annual_returns:
            best_year = max(analytics.annual_returns.items(), key=lambda x: x[1])
            worst_year = min(analytics.annual_returns.items(), key=lambda x: x[1])
            analytics.best_year = {"year": best_year[0], "return": best_year[1]}
            analytics.worst_year = {"year": worst_year[0], "return": worst_year[1]}
        
        # Monthly returns matrix
        analytics.monthly_returns_matrix = self._calculate_monthly_returns_matrix(returns_series)
        
        # Rolling metrics
        if len(returns_series) > 20:
            analytics.rolling_returns = [
                np.mean(returns_series[max(0, i-20):i]) * 252
                for i in range(20, len(returns_series) + 1)
            ]
            
            analytics.rolling_sharpe = [
                (np.mean(returns_series[max(0, i-20):i]) * 252 - self.config.risk_free_rate) /
                (np.std(returns_series[max(0, i-20):i]) * np.sqrt(252) if np.std(returns_series[max(0, i-20):i]) > 0 else 1)
                for i in range(20, len(returns_series) + 1)
            ]
            
            analytics.rolling_volatility = [
                np.std(returns_series[max(0, i-20):i]) * np.sqrt(252)
                for i in range(20, len(returns_series) + 1)
            ]
        
        # Benchmark comparison
        if benchmark_returns:
            benchmark_array = np.array(benchmark_returns)
            analytics.benchmark_return = (np.cumprod(1 + benchmark_array)[-1] - 1) if len(benchmark_array) > 0 else 0
            analytics.benchmark_annualized_return = (1 + analytics.benchmark_return) ** (1 / n_years) - 1 if n_years > 0 else 0
            analytics.benchmark_volatility = benchmark_array.std() * np.sqrt(252)
            
            # Relative return (alpha)
            analytics.relative_return = analytics.annualized_return - (analytics.benchmark_annualized_return or 0)
            
            # Information ratio
            active_returns = returns_array - benchmark_array
            if len(active_returns) > 0 and active_returns.std() > 0:
                analytics.information_ratio = (analytics.annualized_return - (analytics.benchmark_annualized_return or 0)) / active_returns.std()
        
        # Win rate (from returns)
        analytics.win_rate = np.mean(returns_array > 0)
        
        # Profit factor (from returns)
        positive_returns = returns_array[returns_array > 0]
        negative_returns = returns_array[returns_array < 0]
        analytics.profit_factor = positive_returns.sum() / abs(negative_returns.sum()) if negative_returns.sum() != 0 else float('inf')
        
        # Recovery factor
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        analytics.recovery_factor = analytics.annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Payoff ratio
        avg_win = np.mean(positive_returns) if len(positive_returns) > 0 else 0
        avg_loss = np.mean(negative_returns) if len(negative_returns) > 0 else 0
        analytics.payoff_ratio = avg_win / abs(avg_loss) if avg_loss != 0 else 0
        
        # Best and worst trade
        if len(returns_series) > 0:
            best_idx = np.argmax(returns_array)
            worst_idx = np.argmin(returns_array)
            analytics.best_trade = {"date": datetime.now() - timedelta(days=len(returns_series) - best_idx), "return": returns_array[best_idx]}
            analytics.worst_trade = {"date": datetime.now() - timedelta(days=len(returns_series) - worst_idx), "return": returns_array[worst_idx]}
        
        # Monthly consistency
        monthly_returns = self._get_monthly_returns(returns_series)
        analytics.positive_months = sum(1 for r in monthly_returns if r > 0)
        analytics.negative_months = sum(1 for r in monthly_returns if r < 0)
        analytics.win_months_ratio = analytics.positive_months / len(monthly_returns) if len(monthly_returns) > 0 else 0
        
        # Consistency score (based on win rate and win/loss ratio)
        analytics.consistency_score = self._calculate_consistency_score(analytics)
        
        return analytics
    
    def _calculate_annual_returns(self, returns_series: List[float]) -> Dict[str, float]:
        """Calculate annual returns from daily returns."""
        if not returns_series:
            return {}
            
        # Group by year
        annual_returns = {}
        # Simulate years (assuming 252 trading days per year)
        num_years = len(returns_series) // 252
        
        for year_idx in range(num_years):
            start_idx = year_idx * 252
            end_idx = min((year_idx + 1) * 252, len(returns_series))
            year_returns = returns_series[start_idx:end_idx]
            if year_returns:
                year_ret = np.cumprod(1 + np.array(year_returns))[-1] - 1
                annual_returns[str(year_idx)] = year_ret
                
        return annual_returns
    
    def _calculate_monthly_returns_matrix(self, returns_series: List[float]) -> Dict[str, Dict[int, float]]:
        """Calculate monthly returns matrix."""
        monthly_returns = {}
        
        if not returns_series:
            return monthly_returns
            
        # Simulate months (assuming 21 trading days per month)
        num_months = len(returns_series) // 21
        
        for month_idx in range(num_months):
            start_idx = month_idx * 21
            end_idx = min((month_idx + 1) * 21, len(returns_series))
            month_returns = returns_series[start_idx:end_idx]
            if month_returns:
                month_ret = np.cumprod(1 + np.array(month_returns))[-1] - 1
                year = str(month_idx // 12 + 2020)  # Approximate year
                month = month_idx % 12 + 1
                
                if year not in monthly_returns:
                    monthly_returns[year] = {}
                monthly_returns[year][month] = month_ret
                
        return monthly_returns
    
    def _get_monthly_returns(self, returns_series: List[float]) -> List[float]:
        """Get monthly returns from daily returns."""
        monthly_returns = []
        
        if not returns_series:
            return monthly_returns
            
        # Simulate months (assuming 21 trading days per month)
        num_months = len(returns_series) // 21
        
        for month_idx in range(num_months):
            start_idx = month_idx * 21
            end_idx = min((month_idx + 1) * 21, len(returns_series))
            month_returns = returns_series[start_idx:end_idx]
            if month_returns:
                month_ret = np.cumprod(1 + np.array(month_returns))[-1] - 1
                monthly_returns.append(month_ret)
                
        return monthly_returns
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown from equity curve."""
        if len(equity_curve) < 2:
            return 0
            
        running_max = equity_curve[0]
        max_drawdown = 0
        
        for equity in equity_curve[1:]:
            if equity > running_max:
                running_max = equity
            drawdown = (running_max - equity) / running_max if running_max > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
            
        return max_drawdown
    
    def _calculate_consistency_score(self, analytics: PerformanceAnalytics) -> float:
        """Calculate consistency score based on win rate and win/loss ratio."""
        # Score based on win rate (30%)
        win_rate_score = analytics.win_rate * 0.3
        
        # Score based on win/loss ratio (30%)
        win_loss_ratio = analytics.payoff_ratio
        win_loss_score = min(win_loss_ratio / 2, 1) * 0.3
        
        # Score based on monthly consistency (20%)
        monthly_score = analytics.win_months_ratio * 0.2
        
        # Score based on Sharpe ratio (20%)
        sharpe_score = min(analytics.sharpe_ratio / 2, 1) * 0.2
        
        return min(win_rate_score + win_loss_score + monthly_score + sharpe_score, 1.0)
    
    def _calculate_overall_score(
        self,
        trade_analytics: TradeAnalytics,
        risk_analytics: RiskAnalytics,
        performance_analytics: PerformanceAnalytics
    ) -> float:
        """Calculate overall strategy score."""
        scores = []
        
        # Win rate score (20%)
        scores.append(trade_analytics.win_rate * 0.2)
        
        # Profit factor score (20%)
        pf = min(trade_analytics.profit_factor / 2, 1)
        scores.append(pf * 0.2)
        
        # Sharpe ratio score (20%)
        sr = min(risk_analytics.sharpe_ratio / 2, 1)
        scores.append(sr * 0.2)
        
        # Calmar ratio score (20%)
        cr = min(risk_analytics.calmar_ratio / 2, 1)
        scores.append(cr * 0.2)
        
        # Consistency score (20%)
        scores.append(performance_analytics.consistency_score * 0.2)
        
        return sum(scores)
    
    def _calculate_risk_adjusted_return(
        self,
        performance_analytics: PerformanceAnalytics,
        risk_analytics: RiskAnalytics
    ) -> float:
        """Calculate risk-adjusted return metric."""
        if risk_analytics.max_drawdown > 0:
            return performance_analytics.annualized_return / risk_analytics.max_drawdown
        return 0
    
    def _calculate_quality_score(
        self,
        trade_analytics: TradeAnalytics,
        risk_analytics: RiskAnalytics,
        performance_analytics: PerformanceAnalytics
    ) -> float:
        """Calculate overall quality score."""
        # Quality score based on multiple factors
        factors = []
        
        # High win rate with good risk-reward
        if trade_analytics.win_rate > 0.5 and trade_analytics.profit_factor > 1.5:
            factors.append(1.0)
        elif trade_analytics.win_rate > 0.4 and trade_analytics.profit_factor > 1.2:
            factors.append(0.7)
        else:
            factors.append(0.3)
        
        # Good risk management
        if risk_analytics.max_drawdown < 0.15 and risk_analytics.sharpe_ratio > 1:
            factors.append(1.0)
        elif risk_analytics.max_drawdown < 0.25 and risk_analytics.sharpe_ratio > 0.5:
            factors.append(0.7)
        else:
            factors.append(0.3)
        
        # Consistent performance
        if performance_analytics.consistency_score > 0.7:
            factors.append(1.0)
        elif performance_analytics.consistency_score > 0.5:
            factors.append(0.7)
        else:
            factors.append(0.3)
        
        return np.mean(factors)
    
    def _generate_summary(
        self,
        trade_analytics: TradeAnalytics,
        risk_analytics: RiskAnalytics,
        performance_analytics: PerformanceAnalytics
    ) -> Dict[str, Any]:
        """Generate summary of analysis results."""
        return {
            "total_trades": trade_analytics.total_trades,
            "win_rate": trade_analytics.win_rate,
            "profit_factor": trade_analytics.profit_factor,
            "total_return": performance_analytics.total_return,
            "annualized_return": performance_analytics.annualized_return,
            "max_drawdown": risk_analytics.max_drawdown,
            "sharpe_ratio": risk_analytics.sharpe_ratio,
            "calmar_ratio": risk_analytics.calmar_ratio,
            "overall_score": self._calculate_overall_score(trade_analytics, risk_analytics, performance_analytics),
            "quality_score": self._calculate_quality_score(trade_analytics, risk_analytics, performance_analytics)
        }
    
    def _generate_recommendations(
        self,
        trade_analytics: TradeAnalytics,
        risk_analytics: RiskAnalytics,
        performance_analytics: PerformanceAnalytics
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Win rate recommendations
        if trade_analytics.win_rate < 0.4:
            recommendations.append("Consider improving entry/exit signals to increase win rate above 40%")
        elif trade_analytics.win_rate < 0.5:
            recommendations.append("Focus on improving trade selection quality to increase win rate")
        
        # Profit factor recommendations
        if trade_analytics.profit_factor < 1.2:
            recommendations.append("Improve risk-reward ratio by cutting losses earlier or letting winners run")
        elif trade_analytics.profit_factor < 1.5:
            recommendations.append("Consider optimizing position sizing to improve profit factor")
        
        # Drawdown recommendations
        if risk_analytics.max_drawdown > 0.2:
            recommendations.append("Implement stricter stop-loss levels to reduce maximum drawdown")
        elif risk_analytics.max_drawdown > 0.15:
            recommendations.append("Consider adding diversification to reduce drawdown risk")
        
        # Sharpe ratio recommendations
        if risk_analytics.sharpe_ratio < 0.5:
            recommendations.append("Reduce volatility or increase returns to improve Sharpe ratio")
        elif risk_analytics.sharpe_ratio < 1:
            recommendations.append("Consider risk-adjusting position sizes to improve risk-adjusted returns")
        
        # Consistency recommendations
        if performance_analytics.consistency_score < 0.5:
            recommendations.append("Work on maintaining consistent performance across different market conditions")
        
        # Directional bias recommendations
        if trade_analytics.long_win_rate < 0.3 and trade_analytics.short_win_rate > 0.5:
            recommendations.append("Consider focusing on short positions as long trades show low win rate")
        elif trade_analytics.short_win_rate < 0.3 and trade_analytics.long_win_rate > 0.5:
            recommendations.append("Consider focusing on long positions as short trades show low win rate")
        
        # Risk management recommendations
        if risk_analytics.risk_of_ruin > 0.2:
            recommendations.append(f"Risk of ruin is {risk_analytics.risk_of_ruin:.2%}. Consider reducing position size")
        
        return recommendations
    
    def _generate_warnings(
        self,
        trade_analytics: TradeAnalytics,
        risk_analytics: RiskAnalytics,
        performance_analytics: PerformanceAnalytics
    ) -> List[str]:
        """Generate warnings based on analysis."""
        warnings = []
        
        # Insufficient data
        if trade_analytics.total_trades < 30:
            warnings.append(f"Only {trade_analytics.total_trades} trades. Consider more data for reliable analysis")
        
        # Risk warnings
        if risk_analytics.max_drawdown > 0.3:
            warnings.append(f"Maximum drawdown of {risk_analytics.max_drawdown:.2%} is high. Review risk management")
        
        if risk_analytics.risk_of_ruin > 0.3:
            warnings.append(f"Risk of ruin is {risk_analytics.risk_of_ruin:.2%}. High probability of account depletion")
        
        # Performance warnings
        if performance_analytics.annualized_return < 0:
            warnings.append("Strategy is losing money. Consider fundamental changes")
        
        if performance_analytics.win_months_ratio < 0.4:
            warnings.append(f"Only {performance_analytics.win_months_ratio:.2%} of months are profitable")
        
        # Statistical warnings
        if trade_analytics.total_trades > 30:
            if trade_analytics.p_value > 0.05:
                warnings.append("Strategy returns are not statistically significant (p > 0.05)")
        
        # Extreme metrics
        if trade_analytics.max_consecutive_losses > 5:
            warnings.append(f"Max consecutive losses: {trade_analytics.max_consecutive_losses}. High streak risk")
        
        if abs(trade_analytics.pnl_skew) > 2:
            warnings.append(f"PnL distribution is highly skewed ({trade_analytics.pnl_skew:.2f})")
        
        if trade_analytics.pnl_kurtosis > 3:
            warnings.append(f"PnL distribution shows extreme events (kurtosis: {trade_analytics.pnl_kurtosis:.2f})")
        
        return warnings
    
    async def _generate_charts(self, result: BacktestAnalysisResult) -> Dict[str, str]:
        """Generate visualization charts."""
        chart_paths = {}
        
        try:
            # Create subplot with multiple charts
            fig = make_subplots(
                rows=4, cols=2,
                subplot_titles=(
                    "Equity Curve", "Drawdown",
                    "Monthly Returns", "Return Distribution",
                    "Rolling Sharpe Ratio", "Risk Metrics",
                    "Trade Analysis", "Performance Summary"
                ),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                      [{"secondary_y": False}, {"secondary_y": True}],
                      [{"secondary_y": False}, {"secondary_y": False}],
                      [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # 1. Equity Curve
            if result.equity_curve:
                fig.add_trace(
                    go.Scatter(
                        y=result.equity_curve,
                        name="Equity",
                        line=dict(color="blue", width=2),
                        hovertemplate="Equity: $%{y:.2f}<extra></extra>"
                    ),
                    row=1, col=1
                )
            
            # 2. Drawdown
            if result.drawdown_curve:
                fig.add_trace(
                    go.Scatter(
                        y=result.drawdown_curve,
                        name="Drawdown",
                        fill='tozeroy',
                        line=dict(color="red", width=2),
                        hovertemplate="Drawdown: %{y:.2%}<extra></extra>"
                    ),
                    row=1, col=2
                )
            
            # 3. Monthly Returns Heatmap
            monthly_returns = result.performance_analytics.monthly_returns_matrix
            if monthly_returns:
                months = list(range(1, 13))
                years = list(monthly_returns.keys())
                z_values = []
                for year in years:
                    year_data = monthly_returns[year]
                    row_values = [year_data.get(month, 0) for month in months]
                    z_values.append(row_values)
                
                fig.add_trace(
                    go.Heatmap(
                        z=z_values,
                        x=months,
                        y=years,
                        colorscale="RdYlGn",
                        name="Monthly Returns",
                        hovertemplate="Year %{y}<br>Month %{x}<br>Return: %{z:.2%}<extra></extra>"
                    ),
                    row=2, col=1
                )
            
            # 4. Return Distribution
            if result.returns_series:
                fig.add_trace(
                    go.Histogram(
                        x=result.returns_series,
                        nbinsx=50,
                        name="Returns",
                        hovertemplate="Return: %{x:.2%}<br>Count: %{y}<extra></extra>"
                    ),
                    row=2, col=2
                )
                
                # Add normal distribution curve
                mu = np.mean(result.returns_series)
                sigma = np.std(result.returns_series)
                x = np.linspace(mu - 4*sigma, mu + 4*sigma, 100)
                y = stats.norm.pdf(x, mu, sigma)
                fig.add_trace(
                    go.Scatter(
                        x=x, y=y,
                        name="Normal",
                        line=dict(color="black", dash="dash"),
                        hovertemplate="x: %{x:.4f}<br>y: %{y:.2f}<extra></extra>"
                    ),
                    row=2, col=2
                )
            
            # 5. Rolling Sharpe Ratio
            if result.performance_analytics.rolling_sharpe:
                fig.add_trace(
                    go.Scatter(
                        y=result.performance_analytics.rolling_sharpe,
                        name="Rolling Sharpe",
                        line=dict(color="green", width=2),
                        hovertemplate="Sharpe: %{y:.2f}<extra></extra>"
                    ),
                    row=3, col=1
                )
                fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)
            
            # 6. Risk Metrics
            risk_metrics = [
                ("VaR 95%", result.risk_analytics.var_95 * 100),
                ("CVaR 95%", result.risk_analytics.cvar_95 * 100),
                ("Max DD", result.risk_analytics.max_drawdown * 100),
                ("Sharpe", result.risk_analytics.sharpe_ratio),
                ("Sortino", result.risk_analytics.sortino_ratio),
                ("Calmar", result.risk_analytics.calmar_ratio)
            ]
            
            names, values = zip(*risk_metrics)
            fig.add_trace(
                go.Bar(
                    x=names,
                    y=values,
                    name="Risk Metrics",
                    hovertemplate="%{x}: %{y:.2f}<extra></extra>"
                ),
                row=3, col=2
            )
            
            # 7. Trade Analysis
            if result.trade_analytics:
                trade_metrics = [
                    ("Win Rate", result.trade_analytics.win_rate * 100),
                    ("Profit Factor", result.trade_analytics.profit_factor),
                    ("Avg Win", result.trade_analytics.avg_win),
                    ("Avg Loss", result.trade_analytics.avg_loss),
                    ("Max Win", result.trade_analytics.max_win),
                    ("Max Loss", result.trade_analytics.max_loss)
                ]
                
                names2, values2 = zip(*trade_metrics)
                fig.add_trace(
                    go.Bar(
                        x=names2,
                        y=values2,
                        name="Trade Metrics",
                        hovertemplate="%{x}: %{y:.2f}<extra></extra>"
                    ),
                    row=4, col=1
                )
            
            # 8. Performance Summary
            summary_text = (
                f"Total Return: {result.performance_analytics.total_return:.2%}<br>"
                f"Annualized Return: {result.performance_analytics.annualized_return:.2%}<br>"
                f"Sharpe Ratio: {result.risk_analytics.sharpe_ratio:.2f}<br>"
                f"Max Drawdown: {result.risk_analytics.max_drawdown:.2%}<br>"
                f"Win Rate: {result.trade_analytics.win_rate:.2%}<br>"
                f"Profit Factor: {result.trade_analytics.profit_factor:.2f}<br>"
                f"Total Trades: {result.trade_analytics.total_trades}<br>"
                f"Overall Score: {result.overall_score:.2%}"
            )
            
            fig.add_annotation(
                text=summary_text,
                xref="x domain",
                yref="y domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=10),
                bgcolor="white",
                borderpad=10,
                row=4, col=2
            )
            
            # Update layout
            fig.update_layout(
                height=1200,
                width=1800,
                showlegend=True,
                title_text=f"Backtest Analysis - {result.strategy_name}",
                template="plotly_white",
                font=dict(family="Arial", size=12),
                barmode='group'
            )
            
            # Update axes
            fig.update_xaxes(title_text="Day", row=1, col=1)
            fig.update_xaxes(title_text="Day", row=1, col=2)
            fig.update_xaxes(title_text="Month", row=2, col=1)
            fig.update_xaxes(title_text="Return", row=2, col=2)
            fig.update_xaxes(title_text="Period", row=3, col=1)
            fig.update_xaxes(title_text="Metric", row=3, col=2)
            fig.update_xaxes(title_text="Metric", row=4, col=1)
            
            fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
            fig.update_yaxes(title_text="Drawdown (%)", row=1, col=2)
            fig.update_yaxes(title_text="Year", row=2, col=1)
            fig.update_yaxes(title_text="Frequency", row=2, col=2)
            fig.update_yaxes(title_text="Sharpe Ratio", row=3, col=1)
            fig.update_yaxes(title_text="Value", row=3, col=2)
            fig.update_yaxes(title_text="Value", row=4, col=1)
            
            # Save chart
            chart_path = Path(self.config.output_dir) / f"{result.strategy_name}_analysis.html"
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            fig.write_html(str(chart_path))
            chart_paths["analysis"] = str(chart_path)
            
        except Exception as e:
            self._logger.error(f"Error generating charts: {str(e)}")
        
        return chart_paths
    
    async def _generate_report(self, result: BacktestAnalysisResult) -> Optional[str]:
        """Generate comprehensive HTML report."""
        try:
            # Create report HTML
            html_content = self._create_report_html(result)
            
            # Save report
            report_path = Path(self.config.output_dir) / f"{result.strategy_name}_report.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            return str(report_path)
            
        except Exception as e:
            self._logger.error(f"Error generating report: {str(e)}")
            return None
    
    def _create_report_html(self, result: BacktestAnalysisResult) -> str:
        """Create comprehensive HTML report."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Backtest Report - {result.strategy_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ border-bottom: 2px solid #2196F3; padding-bottom: 10px; margin-bottom: 20px; }}
                .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #2196F3; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
                .section {{ margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
                .section h2 {{ color: #2196F3; margin-top: 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #2196F3; color: white; }}
                tr:hover {{ background: #f5f5f5; }}
                .positive {{ color: #4CAF50; }}
                .negative {{ color: #f44336; }}
                .warning {{ color: #ff9800; }}
                .recommendation {{ background: #e3f2fd; padding: 10px; border-left: 4px solid #2196F3; margin: 5px 0; }}
                .chart-container {{ margin: 20px 0; text-align: center; }}
                .summary-box {{ background: #e8f5e9; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Backtest Analysis Report</h1>
                    <p><strong>Strategy:</strong> {result.strategy_name}</p>
                    <p><strong>Analysis Date:</strong> {result.analysis_timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p><strong>Analysis Duration:</strong> {result.analysis_duration:.2f} seconds</p>
                </div>
                
                <div class="summary-box">
                    <h3>Overall Summary</h3>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-value">{result.performance_analytics.total_return:.2%}</div>
                            <div class="metric-label">Total Return</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{result.performance_analytics.annualized_return:.2%}</div>
                            <div class="metric-label">Annualized Return</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{result.risk_analytics.sharpe_ratio:.2f}</div>
                            <div class="metric-label">Sharpe Ratio</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{result.risk_analytics.max_drawdown:.2%}</div>
                            <div class="metric-label">Max Drawdown</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{result.trade_analytics.win_rate:.2%}</div>
                            <div class="metric-label">Win Rate</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{result.overall_score:.2%}</div>
                            <div class="metric-label">Overall Score</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>Performance Metrics</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Benchmark</th>
                            <th>Status</th>
                        </tr>
                        <tr>
                            <td>Total Return</td>
                            <td>{result.performance_analytics.total_return:.2%}</td>
                            <td>{result.performance_analytics.benchmark_return:.2% if result.performance_analytics.benchmark_return is not None else 'N/A'}</td>
                            <td class="{('positive' if result.performance_analytics.total_return > 0 else 'negative')}">
                                {('✅' if result.performance_analytics.total_return > 0 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Annualized Return</td>
                            <td>{result.performance_analytics.annualized_return:.2%}</td>
                            <td>{result.performance_analytics.benchmark_annualized_return:.2% if result.performance_analytics.benchmark_annualized_return is not None else 'N/A'}</td>
                            <td class="{('positive' if result.performance_analytics.annualized_return > 0 else 'negative')}">
                                {('✅' if result.performance_analytics.annualized_return > 0 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Sharpe Ratio</td>
                            <td>{result.risk_analytics.sharpe_ratio:.2f}</td>
                            <td>1.0</td>
                            <td class="{('positive' if result.risk_analytics.sharpe_ratio > 1 else 'negative')}">
                                {('✅' if result.risk_analytics.sharpe_ratio > 1 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Sortino Ratio</td>
                            <td>{result.risk_analytics.sortino_ratio:.2f}</td>
                            <td>1.0</td>
                            <td class="{('positive' if result.risk_analytics.sortino_ratio > 1 else 'negative')}">
                                {('✅' if result.risk_analytics.sortino_ratio > 1 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Calmar Ratio</td>
                            <td>{result.risk_analytics.calmar_ratio:.2f}</td>
                            <td>1.0</td>
                            <td class="{('positive' if result.risk_analytics.calmar_ratio > 1 else 'negative')}">
                                {('✅' if result.risk_analytics.calmar_ratio > 1 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Max Drawdown</td>
                            <td>{result.risk_analytics.max_drawdown:.2%}</td>
                            <td>15%</td>
                            <td class="{('positive' if result.risk_analytics.max_drawdown < 0.15 else 'negative')}">
                                {('✅' if result.risk_analytics.max_drawdown < 0.15 else '❌')}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div class="section">
                    <h2>Trade Analytics</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Direction</th>
                            <th>Status</th>
                        </tr>
                        <tr>
                            <td>Total Trades</td>
                            <td>{result.trade_analytics.total_trades}</td>
                            <td>-</td>
                            <td>{'✅' if result.trade_analytics.total_trades > 30 else '⚠️'}</td>
                        </tr>
                        <tr>
                            <td>Win Rate</td>
                            <td>{result.trade_analytics.win_rate:.2%}</td>
                            <td>{result.trade_analytics.long_win_rate:.2%} (L) / {result.trade_analytics.short_win_rate:.2%} (S)</td>
                            <td class="{('positive' if result.trade_analytics.win_rate > 0.5 else 'negative')}">
                                {('✅' if result.trade_analytics.win_rate > 0.5 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Profit Factor</td>
                            <td>{result.trade_analytics.profit_factor:.2f}</td>
                            <td>-</td>
                            <td class="{('positive' if result.trade_analytics.profit_factor > 1.5 else 'negative')}">
                                {('✅' if result.trade_analytics.profit_factor > 1.5 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Avg Win / Avg Loss</td>
                            <td>{result.trade_analytics.avg_win:.2f} / {result.trade_analytics.avg_loss:.2f}</td>
                            <td>{result.trade_analytics.avg_win/abs(result.trade_analytics.avg_loss) if result.trade_analytics.avg_loss != 0 else 0:.2f} Ratio</td>
                            <td class="{('positive' if result.trade_analytics.avg_win/abs(result.trade_analytics.avg_loss) > 1.5 if result.trade_analytics.avg_loss != 0 else False else 'negative')}">
                                {('✅' if result.trade_analytics.avg_win/abs(result.trade_analytics.avg_loss) > 1.5 if result.trade_analytics.avg_loss != 0 else False else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Max Consecutive Losses</td>
                            <td>{result.trade_analytics.max_consecutive_losses}</td>
                            <td>-</td>
                            <td class="{('positive' if result.trade_analytics.max_consecutive_losses < 5 else 'negative')}">
                                {('✅' if result.trade_analytics.max_consecutive_losses < 5 else '⚠️')}
                            </td>
                        </tr>
                        <tr>
                            <td>Avg Trade Duration</td>
                            <td>{result.trade_analytics.avg_trade_duration:.0f} seconds</td>
                            <td>-</td>
                            <td>-</td>
                        </tr>
                    </table>
                </div>
                
                <div class="section">
                    <h2>Risk Metrics</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Threshold</th>
                            <th>Status</th>
                        </tr>
                        <tr>
                            <td>VaR 95%</td>
                            <td>{result.risk_analytics.var_95:.2%}</td>
                            <td>10%</td>
                            <td class="{('positive' if abs(result.risk_analytics.var_95) < 0.1 else 'negative')}">
                                {('✅' if abs(result.risk_analytics.var_95) < 0.1 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>CVaR 95%</td>
                            <td>{result.risk_analytics.cvar_95:.2%}</td>
                            <td>15%</td>
                            <td class="{('positive' if abs(result.risk_analytics.cvar_95) < 0.15 else 'negative')}">
                                {('✅' if abs(result.risk_analytics.cvar_95) < 0.15 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Volatility (Annual)</td>
                            <td>{result.risk_analytics.volatility_annualized:.2%}</td>
                            <td>30%</td>
                            <td class="{('positive' if result.risk_analytics.volatility_annualized < 0.3 else 'negative')}">
                                {('✅' if result.risk_analytics.volatility_annualized < 0.3 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Risk of Ruin</td>
                            <td>{result.risk_analytics.risk_of_ruin:.2%}</td>
                            <td>5%</td>
                            <td class="{('positive' if result.risk_analytics.risk_of_ruin < 0.05 else 'negative')}">
                                {('✅' if result.risk_analytics.risk_of_ruin < 0.05 else '⚠️')}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div class="section">
                    <h2>Recommendations</h2>
                    {''.join(f'<div class="recommendation">💡 {rec}</div>' for rec in result.recommendations)}
                    {'' if result.recommendations else '<p>✅ No specific recommendations at this time.</p>'}
                </div>
                
                <div class="section">
                    <h2>Warnings</h2>
                    {''.join(f'<div class="recommendation" style="border-left-color: #ff9800;">⚠️ {warning}</div>' for warning in result.warnings)}
                    {'' if result.warnings else '<p>✅ No warnings detected.</p>'}
                </div>
                
                <div class="section">
                    <h2>Additional Metrics</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
                        <tr>
                            <td>Consistency Score</td>
                            <td>{result.performance_analytics.consistency_score:.2%}</td>
                        </tr>
                        <tr>
                            <td>Quality Score</td>
                            <td>{result.quality_score:.2%}</td>
                        </tr>
                        <tr>
                            <td>Win Months Ratio</td>
                            <td>{result.performance_analytics.win_months_ratio:.2%}</td>
                        </tr>
                        <tr>
                            <td>Recovery Factor</td>
                            <td>{result.performance_analytics.recovery_factor:.2f}</td>
                        </tr>
                        <tr>
                            <td>Statistical Significance</td>
                            <td>{'✅' if result.trade_analytics.is_statistically_significant else '❌'} (p={result.trade_analytics.p_value:.4f})</td>
                        </tr>
                    </table>
                </div>
                
                {f'''
                <div class="section">
                    <h2>Analysis Charts</h2>
                    <div class="chart-container">
                        <iframe src="{Path(result.chart_paths['analysis']).name}" width="100%" height="1200" frameborder="0"></iframe>
                    </div>
                </div>
                ''' if result.chart_paths.get('analysis') else ''}
                
                <div style="text-align: center; padding: 20px; color: #666; border-top: 1px solid #ddd; margin-top: 20px;">
                    <p>Generated by NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD</p>
                    <p>All Rights Reserved</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def _save_results(self, result: BacktestAnalysisResult) -> None:
        """Save analysis results to files."""
        try:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save JSON results
            json_path = output_dir / f"{result.strategy_name}_analysis.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, default=str)
                
            # Save CSV of trades
            if result.trades:
                csv_path = output_dir / f"{result.strategy_name}_trades.csv"
                df_trades = self._trades_to_dataframe(result.trades)
                df_trades.to_csv(csv_path, index=False)
                
            self._logger.info(f"Results saved to {output_dir}")
            
        except Exception as e:
            self._logger.error(f"Error saving results: {str(e)}")
    
    def _extract_strategy_name(self, trades: List[Trade]) -> str:
        """Extract strategy name from trades."""
        if not trades:
            return "unknown_strategy"
            
        strategy_names = set()
        for trade in trades:
            if hasattr(trade, 'strategy') and trade.strategy:
                strategy_names.add(trade.strategy)
                
        return "_".join(strategy_names) if strategy_names else "unknown_strategy"
    
    async def compare_strategies(
        self,
        results: List[BacktestAnalysisResult]
    ) -> Dict[str, Any]:
        """
        Compare multiple strategy backtest results.
        
        Args:
            results: List of backtest analysis results
            
        Returns:
            Comparison dictionary
        """
        if not results:
            return {}
            
        comparison = {
            "strategies": [],
            "metrics_comparison": {},
            "ranking": []
        }
        
        for result in results:
            strategy_data = {
                "name": result.strategy_name,
                "total_return": result.performance_analytics.total_return,
                "annualized_return": result.performance_analytics.annualized_return,
                "sharpe_ratio": result.risk_analytics.sharpe_ratio,
                "max_drawdown": result.risk_analytics.max_drawdown,
                "win_rate": result.trade_analytics.win_rate,
                "profit_factor": result.trade_analytics.profit_factor,
                "overall_score": result.overall_score,
                "quality_score": result.quality_score
            }
            comparison["strategies"].append(strategy_data)
        
        # Create comparison table
        metrics = ["total_return", "annualized_return", "sharpe_ratio", "max_drawdown", "win_rate", "profit_factor", "overall_score"]
        comparison["metrics_comparison"] = {
            metric: {
                "best": max([s[metric] for s in comparison["strategies"]]),
                "worst": min([s[metric] for s in comparison["strategies"]]),
                "average": sum([s[metric] for s in comparison["strategies"]]) / len(comparison["strategies"])
            }
            for metric in metrics
        }
        
        # Rank strategies by overall score
        comparison["ranking"] = sorted(
            comparison["strategies"],
            key=lambda x: x["overall_score"],
            reverse=True
        )
        
        return comparison


# Factory function for easy initialization
def create_backtest_analyzer(
    risk_free_rate: float = 0.02,
    generate_charts: bool = True,
    generate_report: bool = True
) -> BacktestAnalyzer:
    """
    Create a backtest analyzer with default configuration.
    
    Args:
        risk_free_rate: Risk-free rate for calculations
        generate_charts: Whether to generate charts
        generate_report: Whether to generate reports
        
    Returns:
        Configured BacktestAnalyzer instance
    """
    config = BacktestConfig(
        risk_free_rate=risk_free_rate,
        generate_charts=generate_charts,
        generate_report=generate_report
    )
    return BacktestAnalyzer(config)
