"""
NEXUS AI TRADING SYSTEM - Performance Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced performance analysis with comprehensive benchmarking,
attribution analysis, and performance decomposition capabilities.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, skew, kurtosis
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import warnings
import logging
from pathlib import Path
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nexus.shared.types.trading import Trade, TradeDirection, TradeStatus
from nexus.shared.utilities.logger import Logger
from nexus.trading.analytics.metrics_calculator import (
    MetricsCalculator, CompleteMetrics, 
    PerformanceMetrics, RiskMetrics, RiskAdjustedMetrics
)

logger = Logger(__name__)


class BenchmarkType(Enum):
    """Types of benchmarks"""
    S_AND_P_500 = "s&p_500"
    NASDAQ = "nasdaq"
    DOW_JONES = "dow_jones"
    CRYPTO_INDEX = "crypto_index"
    BOND_INDEX = "bond_index"
    CUSTOM = "custom"


class AttributionType(Enum):
    """Types of performance attribution"""
    SECTOR = "sector"
    ASSET_CLASS = "asset_class"
    STRATEGY = "strategy"
    FACTOR = "factor"
    TIMING = "timing"
    SELECTION = "selection"
    INTERACTION = "interaction"


@dataclass
class PerformanceAttribution:
    """Performance attribution results"""
    total_return: float = 0.0
    selection_return: float = 0.0
    timing_return: float = 0.0
    interaction_return: float = 0.0
    allocation_return: float = 0.0
    
    # Factor attribution
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    
    # Sector attribution
    sector_contributions: Dict[str, float] = field(default_factory=dict)
    sector_weights: Dict[str, float] = field(default_factory=dict)
    
    # Strategy attribution
    strategy_contributions: Dict[str, float] = field(default_factory=dict)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    
    # Timing analysis
    market_timing_ability: float = 0.0
    stock_selection_ability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return": self.total_return,
            "selection_return": self.selection_return,
            "timing_return": self.timing_return,
            "interaction_return": self.interaction_return,
            "allocation_return": self.allocation_return,
            "factor_contributions": self.factor_contributions,
            "factor_exposures": self.factor_exposures,
            "sector_contributions": self.sector_contributions,
            "sector_weights": self.sector_weights,
            "strategy_contributions": self.strategy_contributions,
            "strategy_weights": self.strategy_weights,
            "market_timing_ability": self.market_timing_ability,
            "stock_selection_ability": self.stock_selection_ability
        }


@dataclass
class BenchmarkComparison:
    """Benchmark comparison results"""
    strategy_returns: List[float] = field(default_factory=list)
    benchmark_returns: List[float] = field(default_factory=list)
    
    # Return comparison
    strategy_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    relative_return: float = 0.0
    
    # Risk comparison
    strategy_volatility: float = 0.0
    benchmark_volatility: float = 0.0
    relative_volatility: float = 0.0
    
    # Risk-adjusted comparison
    strategy_sharpe: float = 0.0
    benchmark_sharpe: float = 0.0
    relative_sharpe: float = 0.0
    
    # Alpha/Beta
    alpha: float = 0.0
    beta: float = 0.0
    r_squared: float = 0.0
    
    # Tracking error
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    
    # Performance ratios
    upside_capture: float = 0.0
    downside_capture: float = 0.0
    capture_ratio: float = 0.0
    
    # Win rates
    strategy_win_rate: float = 0.0
    benchmark_win_rate: float = 0.0
    relative_win_rate: float = 0.0
    
    # Up/down periods
    up_periods_won: int = 0
    down_periods_won: int = 0
    up_periods_total: int = 0
    down_periods_total: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy_return": self.strategy_return,
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
            "relative_return": self.relative_return,
            "strategy_volatility": self.strategy_volatility,
            "benchmark_volatility": self.benchmark_volatility,
            "relative_volatility": self.relative_volatility,
            "strategy_sharpe": self.strategy_sharpe,
            "benchmark_sharpe": self.benchmark_sharpe,
            "relative_sharpe": self.relative_sharpe,
            "alpha": self.alpha,
            "beta": self.beta,
            "r_squared": self.r_squared,
            "tracking_error": self.tracking_error,
            "information_ratio": self.information_ratio,
            "upside_capture": self.upside_capture,
            "downside_capture": self.downside_capture,
            "capture_ratio": self.capture_ratio,
            "strategy_win_rate": self.strategy_win_rate,
            "benchmark_win_rate": self.benchmark_win_rate,
            "relative_win_rate": self.relative_win_rate,
            "up_periods_won": self.up_periods_won,
            "down_periods_won": self.down_periods_won,
            "up_periods_total": self.up_periods_total,
            "down_periods_total": self.down_periods_total
        }


@dataclass
class PerformanceDecomposition:
    """Performance decomposition results"""
    # Return decomposition
    risk_free_return: float = 0.0
    market_return: float = 0.0
    size_return: float = 0.0
    value_return: float = 0.0
    momentum_return: float = 0.0
    quality_return: float = 0.0
    volatility_return: float = 0.0
    alpha_return: float = 0.0
    
    # Risk decomposition
    market_risk: float = 0.0
    specific_risk: float = 0.0
    total_risk: float = 0.0
    
    # Factor exposures
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    factor_returns: Dict[str, float] = field(default_factory=dict)
    
    # Style analysis
    style_weights: Dict[str, float] = field(default_factory=dict)
    style_exposures: Dict[str, float] = field(default_factory=dict)
    
    # Timing analysis
    market_timing: float = 0.0
    volatility_timing: float = 0.0
    factor_timing: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "risk_free_return": self.risk_free_return,
            "market_return": self.market_return,
            "size_return": self.size_return,
            "value_return": self.value_return,
            "momentum_return": self.momentum_return,
            "quality_return": self.quality_return,
            "volatility_return": self.volatility_return,
            "alpha_return": self.alpha_return,
            "market_risk": self.market_risk,
            "specific_risk": self.specific_risk,
            "total_risk": self.total_risk,
            "factor_exposures": self.factor_exposures,
            "factor_returns": self.factor_returns,
            "style_weights": self.style_weights,
            "style_exposures": self.style_exposures,
            "market_timing": self.market_timing,
            "volatility_timing": self.volatility_timing,
            "factor_timing": self.factor_timing
        }


@dataclass
class PerformanceReport:
    """Complete performance report"""
    # Core metrics
    metrics: CompleteMetrics = field(default_factory=CompleteMetrics)
    
    # Benchmark comparison
    benchmark: Optional[BenchmarkComparison] = None
    
    # Attribution
    attribution: Optional[PerformanceAttribution] = None
    
    # Decomposition
    decomposition: Optional[PerformanceDecomposition] = None
    
    # Summary
    summary: Dict[str, Any] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Visualization
    chart_paths: Dict[str, str] = field(default_factory=dict)
    
    # Raw data
    returns: List[float] = field(default_factory=list)
    benchmark_returns: Optional[List[float]] = None
    prices: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "metrics": self.metrics.to_dict(),
            "benchmark": self.benchmark.to_dict() if self.benchmark else None,
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "decomposition": self.decomposition.to_dict() if self.decomposition else None,
            "summary": self.summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations
        }


class PerformanceAnalyzer:
    """
    Advanced performance analyzer with comprehensive performance analysis,
    benchmarking, attribution, and decomposition capabilities.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        annualization_factor: int = 252,
        confidence_level: float = 0.95
    ):
        """
        Initialize the performance analyzer.
        
        Args:
            risk_free_rate: Risk-free rate for calculations
            annualization_factor: Number of periods in a year
            confidence_level: Confidence level for calculations
        """
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.confidence_level = confidence_level
        self._metrics_calculator = MetricsCalculator(
            risk_free_rate=risk_free_rate,
            annualization_factor=annualization_factor,
            confidence_level=confidence_level
        )
        self._logger = Logger(__name__)
    
    def analyze_performance(
        self,
        trades: List[Trade],
        prices: Optional[List[float]] = None,
        returns: Optional[List[float]] = None,
        benchmark_returns: Optional[List[float]] = None,
        benchmark_name: Optional[str] = None,
        initial_capital: float = 10000.0
    ) -> PerformanceReport:
        """
        Perform comprehensive performance analysis.
        
        Args:
            trades: List of trades
            prices: Price series for equity curve
            returns: Return series
            benchmark_returns: Benchmark return series
            benchmark_name: Name of the benchmark
            initial_capital: Initial capital
            
        Returns:
            Complete performance report
        """
        self._logger.info("Starting performance analysis")
        
        try:
            # Calculate metrics
            metrics = self._metrics_calculator.calculate_all_metrics(
                trades=trades,
                returns=returns,
                prices=prices,
                benchmark_returns=benchmark_returns,
                initial_capital=initial_capital
            )
            
            # Create report
            report = PerformanceReport(
                metrics=metrics,
                returns=returns or [],
                prices=prices or [],
                benchmark_returns=benchmark_returns
            )
            
            # Benchmark comparison
            if benchmark_returns is not None:
                report.benchmark = self.compare_to_benchmark(
                    returns or [],
                    benchmark_returns,
                    benchmark_name or "Benchmark"
                )
            
            # Performance attribution
            if trades and prices:
                report.attribution = self.calculate_attribution(trades, prices)
            
            # Performance decomposition
            if returns is not None and benchmark_returns is not None:
                report.decomposition = self.decompose_performance(
                    returns, benchmark_returns
                )
            
            # Generate summary
            report.summary = self.generate_summary(report)
            
            # Identify strengths and weaknesses
            report.strengths = self.identify_strengths(report)
            report.weaknesses = self.identify_weaknesses(report)
            
            # Generate recommendations
            report.recommendations = self.generate_recommendations(report)
            
            self._logger.info("Performance analysis completed")
            
            return report
            
        except Exception as e:
            self._logger.error(f"Error in performance analysis: {str(e)}")
            raise
    
    def compare_to_benchmark(
        self,
        strategy_returns: List[float],
        benchmark_returns: List[float],
        benchmark_name: str = "Benchmark"
    ) -> BenchmarkComparison:
        """
        Compare strategy performance to a benchmark.
        
        Args:
            strategy_returns: Strategy return series
            benchmark_returns: Benchmark return series
            benchmark_name: Name of the benchmark
            
        Returns:
            Benchmark comparison results
        """
        comparison = BenchmarkComparison()
        
        if not strategy_returns or not benchmark_returns:
            return comparison
        
        strategy_array = np.array(strategy_returns)
        benchmark_array = np.array(benchmark_returns)
        
        # Align lengths
        min_len = min(len(strategy_array), len(benchmark_array))
        strategy_array = strategy_array[-min_len:]
        benchmark_array = benchmark_array[-min_len:]
        
        comparison.strategy_returns = strategy_array.tolist()
        comparison.benchmark_returns = benchmark_array.tolist()
        
        # Return comparison
        comparison.strategy_return = np.prod(1 + strategy_array) - 1
        comparison.benchmark_return = np.prod(1 + benchmark_array) - 1
        comparison.excess_return = comparison.strategy_return - comparison.benchmark_return
        comparison.relative_return = (1 + comparison.strategy_return) / (1 + comparison.benchmark_return) - 1 if (1 + comparison.benchmark_return) > 0 else 0
        
        # Risk comparison
        comparison.strategy_volatility = np.std(strategy_array) * np.sqrt(self.annualization_factor)
        comparison.benchmark_volatility = np.std(benchmark_array) * np.sqrt(self.annualization_factor)
        comparison.relative_volatility = comparison.strategy_volatility / comparison.benchmark_volatility if comparison.benchmark_volatility > 0 else 0
        
        # Risk-adjusted comparison
        excess_returns_strat = strategy_array - self.risk_free_rate / self.annualization_factor
        excess_returns_bench = benchmark_array - self.risk_free_rate / self.annualization_factor
        
        comparison.strategy_sharpe = np.mean(excess_returns_strat) / np.std(strategy_array) * np.sqrt(self.annualization_factor) if np.std(strategy_array) > 0 else 0
        comparison.benchmark_sharpe = np.mean(excess_returns_bench) / np.std(benchmark_array) * np.sqrt(self.annualization_factor) if np.std(benchmark_array) > 0 else 0
        comparison.relative_sharpe = comparison.strategy_sharpe - comparison.benchmark_sharpe
        
        # Alpha/Beta
        if len(strategy_array) > 1:
            beta, alpha = np.polyfit(benchmark_array, strategy_array, 1)
            comparison.beta = beta
            comparison.alpha = alpha * self.annualization_factor  # Annualized alpha
            
            # R-squared
            correlation = np.corrcoef(strategy_array, benchmark_array)[0, 1]
            comparison.r_squared = correlation ** 2
        
        # Tracking error and information ratio
        active_returns = strategy_array - benchmark_array
        comparison.tracking_error = np.std(active_returns) * np.sqrt(self.annualization_factor) if len(active_returns) > 0 else 0
        comparison.information_ratio = np.mean(active_returns) / np.std(active_returns) * np.sqrt(self.annualization_factor) if np.std(active_returns) > 0 else 0
        
        # Capture ratios
        positive_bench = benchmark_array > 0
        negative_bench = benchmark_array < 0
        
        if np.any(positive_bench):
            strategy_up = np.mean(strategy_array[positive_bench]) * self.annualization_factor if np.any(positive_bench) else 0
            benchmark_up = np.mean(benchmark_array[positive_bench]) * self.annualization_factor if np.any(positive_bench) else 0
            comparison.upside_capture = (strategy_up / benchmark_up) * 100 if benchmark_up != 0 else 0
        
        if np.any(negative_bench):
            strategy_down = np.mean(strategy_array[negative_bench]) * self.annualization_factor if np.any(negative_bench) else 0
            benchmark_down = np.mean(benchmark_array[negative_bench]) * self.annualization_factor if np.any(negative_bench) else 0
            comparison.downside_capture = (strategy_down / benchmark_down) * 100 if benchmark_down != 0 else 0
        
        comparison.capture_ratio = comparison.upside_capture / comparison.downside_capture if comparison.downside_capture != 0 else 0
        
        # Win rates
        comparison.strategy_win_rate = np.mean(strategy_array > 0)
        comparison.benchmark_win_rate = np.mean(benchmark_array > 0)
        
        # Relative win rate
        combined_returns = pd.DataFrame({
            'strategy': strategy_array,
            'benchmark': benchmark_array
        })
        
        # Up/Down periods
        combined_returns['strategy_win'] = combined_returns['strategy'] > 0
        combined_returns['benchmark_win'] = combined_returns['benchmark'] > 0
        combined_returns['benchmark_up'] = combined_returns['benchmark'] > 0
        combined_returns['benchmark_down'] = combined_returns['benchmark'] < 0
        
        comparison.up_periods_total = np.sum(combined_returns['benchmark_up'])
        comparison.down_periods_total = np.sum(combined_returns['benchmark_down'])
        
        comparison.up_periods_won = np.sum(
            combined_returns['benchmark_up'] & combined_returns['strategy_win'] & 
            (combined_returns['strategy'] > combined_returns['benchmark'])
        )
        
        comparison.down_periods_won = np.sum(
            combined_returns['benchmark_down'] & combined_returns['strategy_win'] & 
            (combined_returns['strategy'] > combined_returns['benchmark'])
        )
        
        comparison.relative_win_rate = np.mean(strategy_array > benchmark_array)
        
        return comparison
    
    def calculate_attribution(
        self,
        trades: List[Trade],
        prices: List[float],
        sectors: Optional[Dict[str, str]] = None,
        strategies: Optional[Dict[str, str]] = None
    ) -> PerformanceAttribution:
        """
        Calculate performance attribution.
        
        Args:
            trades: List of trades
            prices: Price series
            sectors: Trade ID to sector mapping
            strategies: Trade ID to strategy mapping
            
        Returns:
            Performance attribution results
        """
        attribution = PerformanceAttribution()
        
        if not trades:
            return attribution
        
        # Total return
        total_return = (prices[-1] / prices[0]) - 1 if prices and prices[0] > 0 else 0
        attribution.total_return = total_return
        
        # Calculate by strategy
        if strategies:
            strategy_returns = {}
            strategy_weights = {}
            
            for trade in trades:
                strategy_name = strategies.get(strategy_name, "default")
                if strategy_name not in strategy_returns:
                    strategy_returns[strategy_name] = []
                    strategy_weights[strategy_name] = 0
                
                if trade.pnl:
                    strategy_returns[strategy_name].append(trade.pnl)
                    strategy_weights[strategy_name] += abs(trade.volume)
            
            for strategy, returns in strategy_returns.items():
                if returns:
                    total_pnl = sum(returns)
                    total_weight = strategy_weights[strategy]
                    if total_weight > 0:
                        attribution.strategy_contributions[strategy] = total_pnl / total_weight
            
            total_weight = sum(strategy_weights.values())
            if total_weight > 0:
                for strategy in attribution.strategy_contributions:
                    attribution.strategy_weights[strategy] = strategy_weights[strategy] / total_weight
        
        # Calculate by sector
        if sectors:
            sector_returns = {}
            sector_weights = {}
            
            for trade in trades:
                sector_name = sectors.get(trade.id, "other")
                if sector_name not in sector_returns:
                    sector_returns[sector_name] = []
                    sector_weights[sector_name] = 0
                
                if trade.pnl:
                    sector_returns[sector_name].append(trade.pnl)
                    sector_weights[sector_name] += abs(trade.volume)
            
            for sector, returns in sector_returns.items():
                if returns:
                    total_pnl = sum(returns)
                    total_weight = sector_weights[sector]
                    if total_weight > 0:
                        attribution.sector_contributions[sector] = total_pnl / total_weight
            
            total_weight = sum(sector_weights.values())
            if total_weight > 0:
                for sector in attribution.sector_contributions:
                    attribution.sector_weights[sector] = sector_weights[sector] / total_weight
        
        # Selection and timing ability
        # Using Treynor-Mazuy model
        if len(prices) > 20:
            returns = np.diff(prices) / prices[:-1]
            market_returns = self._get_market_returns(len(returns))
            
            if len(returns) == len(market_returns):
                # Run regression
                X = np.column_stack([np.ones(len(returns)), market_returns, market_returns ** 2])
                beta, _ = np.linalg.lstsq(X, returns, rcond=None)[0]
                
                attribution.market_timing_ability = beta[2]  # Timing coefficient
                attribution.stock_selection_ability = beta[0] * self.annualization_factor  # Selection coefficient
        
        return attribution
    
    def decompose_performance(
        self,
        returns: List[float],
        benchmark_returns: List[float],
        factors: Optional[Dict[str, List[float]]] = None
    ) -> PerformanceDecomposition:
        """
        Decompose performance into factors.
        
        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns
            factors: Additional factor returns
            
        Returns:
            Performance decomposition results
        """
        decomposition = PerformanceDecomposition()
        
        if not returns:
            return decomposition
        
        returns_array = np.array(returns)
        
        # Basic decomposition
        decomposition.risk_free_return = self.risk_free_rate / self.annualization_factor
        
        # Market return
        if benchmark_returns:
            benchmark_array = np.array(benchmark_returns)
            if len(benchmark_array) == len(returns_array):
                decomposition.market_return = np.mean(benchmark_array)
                
                # Calculate alpha
                beta, alpha = np.polyfit(benchmark_array, returns_array, 1)
                decomposition.alpha_return = alpha * self.annualization_factor
        
        # Factor decomposition
        if factors:
            factor_returns_list = list(factors.keys())
            factor_matrix = np.column_stack([factors[f] for f in factor_returns_list])
            
            # Run regression
            X = np.column_stack([np.ones(len(returns_array)), factor_matrix])
            coeffs, _, _, _ = np.linalg.lstsq(X, returns_array, rcond=None)
            
            for i, factor in enumerate(factor_returns_list):
                decomposition.factor_exposures[factor] = coeffs[i + 1]
                decomposition.factor_returns[factor] = np.mean(factors[factor])
        
        # Style analysis
        style_factors = {
            'growth': self._get_growth_returns(len(returns)),
            'value': self._get_value_returns(len(returns)),
            'momentum': self._get_momentum_returns(len(returns)),
            'quality': self._get_quality_returns(len(returns))
        }
        
        # Optimize style weights
        def objective(weights, returns, factors):
            portfolio_returns = np.dot(factors, weights)
            return -np.corrcoef(returns, portfolio_returns)[0, 1]
        
        factor_matrix = np.column_stack([style_factors[f] for f in style_factors])
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = [(0, 1) for _ in style_factors]
        
        try:
            result = minimize(
                objective,
                np.ones(len(style_factors)) / len(style_factors),
                args=(returns_array, factor_matrix),
                constraints=constraints,
                bounds=bounds,
                method='SLSQP'
            )
            
            for i, factor in enumerate(style_factors):
                decomposition.style_weights[factor] = result.x[i]
        except:
            pass
        
        # Risk decomposition
        if benchmark_returns:
            benchmark_array = np.array(benchmark_returns)
            residuals = returns_array - beta * benchmark_array
            
            decomposition.market_risk = np.std(benchmark_array) * np.sqrt(self.annualization_factor)
            decomposition.specific_risk = np.std(residuals) * np.sqrt(self.annualization_factor)
            decomposition.total_risk = np.std(returns_array) * np.sqrt(self.annualization_factor)
        
        return decomposition
    
    def generate_summary(self, report: PerformanceReport) -> Dict[str, Any]:
        """Generate performance summary."""
        metrics = report.metrics
        
        summary = {
            "total_return": metrics.performance.total_return,
            "annualized_return": metrics.performance.annualized_return,
            "max_drawdown": metrics.drawdown.max_drawdown,
            "sharpe_ratio": metrics.risk_adjusted.sharpe_ratio,
            "sortino_ratio": metrics.risk_adjusted.sortino_ratio,
            "calmar_ratio": metrics.risk_adjusted.calmar_ratio,
            "win_rate": metrics.trade.win_rate,
            "profit_factor": metrics.trade.profit_factor,
            "total_trades": metrics.trade.total_trades,
            "volatility": metrics.volatility.historical_volatility,
            "overall_score": metrics.overall_score,
            "consistency_score": metrics.consistency_score
        }
        
        # Add benchmark comparison
        if report.benchmark:
            summary.update({
                "excess_return": report.benchmark.excess_return,
                "relative_return": report.benchmark.relative_return,
                "alpha": report.benchmark.alpha,
                "beta": report.benchmark.beta,
                "information_ratio": report.benchmark.information_ratio,
                "relative_win_rate": report.benchmark.relative_win_rate
            })
        
        return summary
    
    def identify_strengths(self, report: PerformanceReport) -> List[str]:
        """Identify performance strengths."""
        strengths = []
        metrics = report.metrics
        
        # Strong returns
        if metrics.performance.annualized_return > 0.15:
            strengths.append("Strong annualized returns (>15%)")
        elif metrics.performance.annualized_return > 0.10:
            strengths.append("Good annualized returns (>10%)")
        
        # Good risk management
        if metrics.drawdown.max_drawdown < 0.10:
            strengths.append("Excellent drawdown control (<10%)")
        elif metrics.drawdown.max_drawdown < 0.15:
            strengths.append("Good drawdown control (<15%)")
        
        # High win rate
        if metrics.trade.win_rate > 0.60:
            strengths.append("High win rate (>60%)")
        elif metrics.trade.win_rate > 0.50:
            strengths.append("Positive win rate (>50%)")
        
        # Strong risk-adjusted returns
        if metrics.risk_adjusted.sharpe_ratio > 2:
            strengths.append("Excellent Sharpe ratio (>2)")
        elif metrics.risk_adjusted.sharpe_ratio > 1:
            strengths.append("Good Sharpe ratio (>1)")
        
        # High profit factor
        if metrics.trade.profit_factor > 2:
            strengths.append("Excellent profit factor (>2)")
        elif metrics.trade.profit_factor > 1.5:
            strengths.append("Good profit factor (>1.5)")
        
        # Consistency
        if metrics.consistency_score > 0.7:
            strengths.append("High consistency in performance")
        
        # Benchmark comparison
        if report.benchmark:
            if report.benchmark.alpha > 0:
                strengths.append(f"Positive alpha ({report.benchmark.alpha:.2%})")
            if report.benchmark.information_ratio > 1:
                strengths.append("Strong information ratio (>1)")
        
        return strengths
    
    def identify_weaknesses(self, report: PerformanceReport) -> List[str]:
        """Identify performance weaknesses."""
        weaknesses = []
        metrics = report.metrics
        
        # Poor returns
        if metrics.performance.annualized_return < 0:
            weaknesses.append("Negative annualized returns")
        elif metrics.performance.annualized_return < 0.05:
            weaknesses.append("Low annualized returns (<5%)")
        
        # High drawdown
        if metrics.drawdown.max_drawdown > 0.25:
            weaknesses.append("High maximum drawdown (>25%)")
        elif metrics.drawdown.max_drawdown > 0.20:
            weaknesses.append("Significant maximum drawdown (>20%)")
        
        # Low win rate
        if metrics.trade.win_rate < 0.35:
            weaknesses.append("Low win rate (<35%)")
        
        # Poor risk-adjusted returns
        if metrics.risk_adjusted.sharpe_ratio < 0:
            weaknesses.append("Negative Sharpe ratio")
        elif metrics.risk_adjusted.sharpe_ratio < 0.5:
            weaknesses.append("Low Sharpe ratio (<0.5)")
        
        # Low profit factor
        if metrics.trade.profit_factor < 1:
            weaknesses.append("Profit factor below 1 (unprofitable)")
        elif metrics.trade.profit_factor < 1.2:
            weaknesses.append("Low profit factor (<1.2)")
        
        # Consistency issues
        if metrics.consistency_score < 0.4:
            weaknesses.append("Low consistency in performance")
        
        # Benchmark comparison
        if report.benchmark:
            if report.benchmark.alpha < 0:
                weaknesses.append(f"Negative alpha ({report.benchmark.alpha:.2%})")
            if report.benchmark.beta > 2:
                weaknesses.append("High beta (>2) - high market sensitivity")
        
        return weaknesses
    
    def generate_recommendations(self, report: PerformanceReport) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        metrics = report.metrics
        
        # Return recommendations
        if metrics.performance.annualized_return < 0.10:
            recommendations.append("Focus on increasing return generation through improved strategy selection")
        elif metrics.performance.annualized_return < 0.05:
            recommendations.append("Significant strategy improvement needed - consider fundamental changes")
        
        # Drawdown recommendations
        if metrics.drawdown.max_drawdown > 0.20:
            recommendations.append("Implement stricter risk controls to reduce maximum drawdown")
            recommendations.append("Consider adding diversification to reduce drawdown risk")
        
        # Win rate recommendations
        if metrics.trade.win_rate < 0.40:
            recommendations.append("Improve trade selection criteria to increase win rate")
            recommendations.append("Review entry and exit signals for optimization")
        
        # Profit factor recommendations
        if metrics.trade.profit_factor < 1.2:
            recommendations.append("Improve risk-reward ratio - cut losses earlier or let winners run")
            recommendations.append("Review position sizing to improve profit factor")
        
        # Sharpe ratio recommendations
        if metrics.risk_adjusted.sharpe_ratio < 0.5:
            recommendations.append("Reduce volatility or increase returns to improve Sharpe ratio")
            recommendations.append("Consider risk-adjusted position sizing")
        
        # Consistency recommendations
        if metrics.consistency_score < 0.5:
            recommendations.append("Work on maintaining consistent performance across market conditions")
            recommendations.append("Review strategy performance in different market regimes")
        
        # Benchmark recommendations
        if report.benchmark:
            if report.benchmark.alpha < 0:
                recommendations.append("Improve stock selection to generate positive alpha")
            if report.benchmark.beta > 1.5:
                recommendations.append("Reduce market exposure to lower beta")
            if report.benchmark.tracking_error > 0.20:
                recommendations.append("Reduce tracking error for more consistent relative performance")
        
        return recommendations
    
    def generate_report_html(self, report: PerformanceReport) -> str:
        """
        Generate HTML report from performance analysis.
        
        Args:
            report: Performance report
            
        Returns:
            HTML content
        """
        metrics = report.metrics
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Performance Analysis Report</title>
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
                .strength {{ background: #e8f5e9; padding: 10px; border-left: 4px solid #4CAF50; margin: 5px 0; }}
                .weakness {{ background: #ffebee; padding: 10px; border-left: 4px solid #f44336; margin: 5px 0; }}
                .recommendation {{ background: #e3f2fd; padding: 10px; border-left: 4px solid #2196F3; margin: 5px 0; }}
                .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .badge-success {{ background: #4CAF50; color: white; }}
                .badge-danger {{ background: #f44336; color: white; }}
                .badge-warning {{ background: #ff9800; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Performance Analysis Report</h1>
                    <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p><strong>Total Trades:</strong> {metrics.trade.total_trades}</p>
                </div>
                
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-value">{metrics.performance.total_return:.2%}</div>
                        <div class="metric-label">Total Return</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.performance.annualized_return:.2%}</div>
                        <div class="metric-label">Annualized Return</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.risk_adjusted.sharpe_ratio:.2f}</div>
                        <div class="metric-label">Sharpe Ratio</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.drawdown.max_drawdown:.2%}</div>
                        <div class="metric-label">Max Drawdown</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.trade.win_rate:.2%}</div>
                        <div class="metric-label">Win Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.overall_score:.2%}</div>
                        <div class="metric-label">Overall Score</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>Performance Summary</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                            <th>Rating</th>
                        </tr>
                        <tr>
                            <td>Total Return</td>
                            <td>{metrics.performance.total_return:.2%}</td>
                            <td><span class="badge {('badge-success' if metrics.performance.total_return > 0 else 'badge-danger')}">
                                {('✅' if metrics.performance.total_return > 0 else '❌')}
                            </span></td>
                        </tr>
                        <tr>
                            <td>Annualized Return</td>
                            <td>{metrics.performance.annualized_return:.2%}</td>
                            <td><span class="badge {('badge-success' if metrics.performance.annualized_return > 0.10 else 'badge-warning' if metrics.performance.annualized_return > 0 else 'badge-danger')}">
                                {('✅' if metrics.performance.annualized_return > 0.10 else '⚠️' if metrics.performance.annualized_return > 0 else '❌')}
                            </span></td>
                        </tr>
                        <tr>
                            <td>Sharpe Ratio</td>
                            <td>{metrics.risk_adjusted.sharpe_ratio:.2f}</td>
                            <td><span class="badge {('badge-success' if metrics.risk_adjusted.sharpe_ratio > 1 else 'badge-warning' if metrics.risk_adjusted.sharpe_ratio > 0 else 'badge-danger')}">
                                {('✅' if metrics.risk_adjusted.sharpe_ratio > 1 else '⚠️' if metrics.risk_adjusted.sharpe_ratio > 0 else '❌')}
                            </span></td>
                        </tr>
                        <tr>
                            <td>Max Drawdown</td>
                            <td>{metrics.drawdown.max_drawdown:.2%}</td>
                            <td><span class="badge {('badge-success' if metrics.drawdown.max_drawdown < 0.15 else 'badge-warning' if metrics.drawdown.max_drawdown < 0.25 else 'badge-danger')}">
                                {('✅' if metrics.drawdown.max_drawdown < 0.15 else '⚠️' if metrics.drawdown.max_drawdown < 0.25 else '❌')}
                            </span></td>
                        </tr>
                        <tr>
                            <td>Win Rate</td>
                            <td>{metrics.trade.win_rate:.2%}</td>
                            <td><span class="badge {('badge-success' if metrics.trade.win_rate > 0.50 else 'badge-warning' if metrics.trade.win_rate > 0.40 else 'badge-danger')}">
                                {('✅' if metrics.trade.win_rate > 0.50 else '⚠️' if metrics.trade.win_rate > 0.40 else '❌')}
                            </span></td>
                        </tr>
                        <tr>
                            <td>Profit Factor</td>
                            <td>{metrics.trade.profit_factor:.2f}</td>
                            <td><span class="badge {('badge-success' if metrics.trade.profit_factor > 1.5 else 'badge-warning' if metrics.trade.profit_factor > 1 else 'badge-danger')}">
                                {('✅' if metrics.trade.profit_factor > 1.5 else '⚠️' if metrics.trade.profit_factor > 1 else '❌')}
                            </span></td>
                        </tr>
                    </table>
                </div>
                
                {f'''
                <div class="section">
                    <h2>Benchmark Comparison</h2>
                    <table>
                        <tr>
                            <th>Metric</th>
                            <th>Strategy</th>
                            <th>Benchmark</th>
                            <th>Relative</th>
                        </tr>
                        <tr>
                            <td>Return</td>
                            <td>{report.benchmark.strategy_return:.2%}</td>
                            <td>{report.benchmark.benchmark_return:.2%}</td>
                            <td class="{('positive' if report.benchmark.excess_return > 0 else 'negative')}">
                                {report.benchmark.excess_return:.2%}
                            </td>
                        </tr>
                        <tr>
                            <td>Volatility</td>
                            <td>{report.benchmark.strategy_volatility:.2%}</td>
                            <td>{report.benchmark.benchmark_volatility:.2%}</td>
                            <td class="{('positive' if report.benchmark.strategy_volatility < report.benchmark.benchmark_volatility else 'negative')}">
                                {report.benchmark.relative_volatility:.2f}x
                            </td>
                        </tr>
                        <tr>
                            <td>Sharpe Ratio</td>
                            <td>{report.benchmark.strategy_sharpe:.2f}</td>
                            <td>{report.benchmark.benchmark_sharpe:.2f}</td>
                            <td class="{('positive' if report.benchmark.relative_sharpe > 0 else 'negative')}">
                                {report.benchmark.relative_sharpe:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td>Alpha</td>
                            <td colspan="2">{report.benchmark.alpha:.2%}</td>
                            <td class="{('positive' if report.benchmark.alpha > 0 else 'negative')}">
                                {('✅' if report.benchmark.alpha > 0 else '❌')}
                            </td>
                        </tr>
                        <tr>
                            <td>Beta</td>
                            <td colspan="2">{report.benchmark.beta:.2f}</td>
                            <td class="{('positive' if 0.5 < report.benchmark.beta < 1.5 else 'warning')}">
                                {('✅' if 0.5 < report.benchmark.beta < 1.5 else '⚠️')}
                            </td>
                        </tr>
                        <tr>
                            <td>Information Ratio</td>
                            <td colspan="2">{report.benchmark.information_ratio:.2f}</td>
                            <td class="{('positive' if report.benchmark.information_ratio > 0.5 else 'negative')}">
                                {('✅' if report.benchmark.information_ratio > 0.5 else '❌')}
                            </td>
                        </tr>
                    </table>
                </div>
                ''' if report.benchmark else ''}
                
                <div class="section">
                    <h2>Strengths</h2>
                    {''.join(f'<div class="strength">✅ {strength}</div>' for strength in report.strengths)}
                    {'' if report.strengths else '<p>No strengths identified.</p>'}
                </div>
                
                <div class="section">
                    <h2>Weaknesses</h2>
                    {''.join(f'<div class="weakness">❌ {weakness}</div>' for weakness in report.weaknesses)}
                    {'' if report.weaknesses else '<p>No weaknesses identified.</p>'}
                </div>
                
                <div class="section">
                    <h2>Recommendations</h2>
                    {''.join(f'<div class="recommendation">💡 {recommendation}</div>' for recommendation in report.recommendations)}
                    {'' if report.recommendations else '<p>No recommendations needed.</p>'}
                </div>
                
                <div style="text-align: center; padding: 20px; color: #666; border-top: 1px solid #ddd; margin-top: 20px;">
                    <p>Generated by NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD</p>
                    <p>All Rights Reserved</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_market_returns(self, n_periods: int) -> np.ndarray:
        """Get market returns for attribution calculation."""
        # Simulated market returns (can be replaced with actual data)
        np.random.seed(42)
        return np.random.normal(0.0005, 0.01, n_periods)
    
    def _get_growth_returns(self, n_periods: int) -> np.ndarray:
        """Get growth factor returns."""
        np.random.seed(43)
        return np.random.normal(0.0007, 0.015, n_periods)
    
    def _get_value_returns(self, n_periods: int) -> np.ndarray:
        """Get value factor returns."""
        np.random.seed(44)
        return np.random.normal(0.0003, 0.012, n_periods)
    
    def _get_momentum_returns(self, n_periods: int) -> np.ndarray:
        """Get momentum factor returns."""
        np.random.seed(45)
        return np.random.normal(0.0008, 0.018, n_periods)
    
    def _get_quality_returns(self, n_periods: int) -> np.ndarray:
        """Get quality factor returns."""
        np.random.seed(46)
        return np.random.normal(0.0004, 0.014, n_periods)


# Factory function
def create_performance_analyzer(
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
    confidence_level: float = 0.95
) -> PerformanceAnalyzer:
    """
    Create a performance analyzer with default configuration.
    
    Args:
        risk_free_rate: Risk-free rate
        annualization_factor: Number of periods in a year
        confidence_level: Confidence level for calculations
        
    Returns:
        Configured PerformanceAnalyzer instance
    """
    return PerformanceAnalyzer(
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        confidence_level=confidence_level
    )
