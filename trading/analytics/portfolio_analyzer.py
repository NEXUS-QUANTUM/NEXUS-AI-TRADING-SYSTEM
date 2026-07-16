"""
NEXUS AI TRADING SYSTEM - Portfolio Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced portfolio analysis with risk assessment, optimization,
diversification, and stress testing capabilities.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, Bounds, LinearConstraint
from scipy.stats import norm
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

from nexus.shared.types.trading import Trade, TradeDirection, TradeStatus, Position
from nexus.shared.utilities.logger import Logger
from nexus.trading.analytics.metrics_calculator import MetricsCalculator

logger = Logger(__name__)


class OptimizationObjective(Enum):
    """Types of portfolio optimization objectives"""
    MAXIMIZE_RETURN = "maximize_return"
    MINIMIZE_RISK = "minimize_risk"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MAXIMIZE_SORTINO = "maximize_sortino"
    MAXIMIZE_CALMAR = "maximize_calmar"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_OMEGA = "maximize_omega"
    MAXIMIZE_UTILITY = "maximize_utility"
    MINIMIZE_VAR = "minimize_var"
    MINIMIZE_CVAR = "minimize_cvar"


class RiskConstraint(Enum):
    """Types of risk constraints"""
    MAX_DRAWDOWN = "max_drawdown"
    MAX_VAR = "max_var"
    MAX_CVAR = "max_cvar"
    MAX_VOLATILITY = "max_volatility"
    MAX_BETA = "max_beta"
    MAX_CORRELATION = "max_correlation"
    MAX_LEVERAGE = "max_leverage"
    MAX_POSITION_SIZE = "max_position_size"


@dataclass
class AssetAllocation:
    """Asset allocation configuration"""
    symbol: str = ""
    weight: float = 0.0
    target_weight: float = 0.0
    min_weight: float = 0.0
    max_weight: float = 1.0
    
    # Performance metrics
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0
    cvar_95: float = 0.0
    max_drawdown: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "weight": self.weight,
            "target_weight": self.target_weight,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "expected_sharpe": self.expected_sharpe,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "max_drawdown": self.max_drawdown
        }


@dataclass
class PortfolioRiskMetrics:
    """Portfolio risk metrics"""
    # Volatility
    volatility: float = 0.0
    volatility_annualized: float = 0.0
    
    # Value at Risk
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    
    # Drawdown
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    average_drawdown: float = 0.0
    
    # Risk ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    
    # Risk decomposition
    systematic_risk: float = 0.0
    idiosyncratic_risk: float = 0.0
    total_risk: float = 0.0
    
    # Risk concentration
    herfindahl_index: float = 0.0
    effective_number_of_bets: float = 0.0
    concentration_ratio_top5: float = 0.0
    
    # Market risk
    beta: float = 0.0
    r_squared: float = 0.0
    
    # Extreme risk
    expected_shortfall: float = 0.0
    tail_risk: float = 0.0
    risk_of_ruin: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "volatility": self.volatility,
            "volatility_annualized": self.volatility_annualized,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "average_drawdown": self.average_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "omega_ratio": self.omega_ratio,
            "systematic_risk": self.systematic_risk,
            "idiosyncratic_risk": self.idiosyncratic_risk,
            "total_risk": self.total_risk,
            "herfindahl_index": self.herfindahl_index,
            "effective_number_of_bets": self.effective_number_of_bets,
            "concentration_ratio_top5": self.concentration_ratio_top5,
            "beta": self.beta,
            "r_squared": self.r_squared,
            "expected_shortfall": self.expected_shortfall,
            "tail_risk": self.tail_risk,
            "risk_of_ruin": self.risk_of_ruin
        }


@dataclass
class PortfolioPerformance:
    """Portfolio performance metrics"""
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    cumulative_return: List[float] = field(default_factory=list)
    
    # Return distribution
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    yearly_returns: Dict[str, float] = field(default_factory=dict)
    
    # Return statistics
    mean_return: float = 0.0
    median_return: float = 0.0
    max_return: float = 0.0
    min_return: float = 0.0
    
    # Positive/negative periods
    positive_periods: int = 0
    negative_periods: int = 0
    positive_ratio: float = 0.0
    
    # Consecutive periods
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Worst periods
    worst_month: Dict[str, Any] = field(default_factory=dict)
    worst_year: Dict[str, Any] = field(default_factory=dict)
    best_month: Dict[str, Any] = field(default_factory=dict)
    best_year: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "mean_return": self.mean_return,
            "median_return": self.median_return,
            "max_return": self.max_return,
            "min_return": self.min_return,
            "positive_periods": self.positive_periods,
            "negative_periods": self.negative_periods,
            "positive_ratio": self.positive_ratio,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "worst_month": self.worst_month,
            "worst_year": self.worst_year,
            "best_month": self.best_month,
            "best_year": self.best_year
        }


@dataclass
class PortfolioOptimizationResult:
    """Portfolio optimization result"""
    # Optimal weights
    weights: Dict[str, float] = field(default_factory=dict)
    
    # Performance of optimized portfolio
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0
    cvar_95: float = 0.0
    max_drawdown: float = 0.0
    
    # Optimization details
    objective_achieved: float = 0.0
    iterations: int = 0
    convergence: bool = False
    
    # Efficient frontier points
    efficient_frontier: List[Dict[str, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "weights": self.weights,
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "expected_sharpe": self.expected_sharpe,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "max_drawdown": self.max_drawdown,
            "objective_achieved": self.objective_achieved,
            "iterations": self.iterations,
            "convergence": self.convergence
        }


@dataclass
class StressTestResult:
    """Stress test result"""
    scenario_name: str = ""
    scenario_type: str = ""
    
    # Impact on portfolio
    return_impact: float = 0.0
    value_change: float = 0.0
    drawdown_impact: float = 0.0
    
    # Risk impact
    var_change: float = 0.0
    volatility_change: float = 0.0
    
    # Sensitivity
    delta_sensitivity: float = 0.0
    gamma_sensitivity: float = 0.0
    vega_sensitivity: float = 0.0
    
    # Confidence
    confidence: float = 0.0
    probability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "return_impact": self.return_impact,
            "value_change": self.value_change,
            "drawdown_impact": self.drawdown_impact,
            "var_change": self.var_change,
            "volatility_change": self.volatility_change,
            "delta_sensitivity": self.delta_sensitivity,
            "gamma_sensitivity": self.gamma_sensitivity,
            "vega_sensitivity": self.vega_sensitivity,
            "confidence": self.confidence,
            "probability": self.probability
        }


@dataclass
class PortfolioAnalysisResult:
    """Complete portfolio analysis result"""
    # Core metrics
    risk_metrics: PortfolioRiskMetrics = field(default_factory=PortfolioRiskMetrics)
    performance: PortfolioPerformance = field(default_factory=PortfolioPerformance)
    
    # Allocations
    current_allocations: List[AssetAllocation] = field(default_factory=list)
    target_allocations: List[AssetAllocation] = field(default_factory=list)
    
    # Optimization
    optimization_result: Optional[PortfolioOptimizationResult] = None
    
    # Stress testing
    stress_test_results: List[StressTestResult] = field(default_factory=list)
    
    # Diversification
    diversification_score: float = 0.0
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Summary
    summary: Dict[str, Any] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "risk_metrics": self.risk_metrics.to_dict(),
            "performance": self.performance.to_dict(),
            "current_allocations": [a.to_dict() for a in self.current_allocations],
            "target_allocations": [a.to_dict() for a in self.target_allocations],
            "optimization_result": self.optimization_result.to_dict() if self.optimization_result else None,
            "stress_test_results": [s.to_dict() for s in self.stress_test_results],
            "diversification_score": self.diversification_score,
            "summary": self.summary,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations
        }


class PortfolioAnalyzer:
    """
    Advanced portfolio analyzer with comprehensive risk assessment,
    optimization, diversification, and stress testing capabilities.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        annualization_factor: int = 252,
        confidence_level: float = 0.95,
        max_iterations: int = 1000
    ):
        """
        Initialize the portfolio analyzer.
        
        Args:
            risk_free_rate: Risk-free rate for calculations
            annualization_factor: Number of periods in a year
            confidence_level: Confidence level for VaR calculations
            max_iterations: Maximum iterations for optimization
        """
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.confidence_level = confidence_level
        self.max_iterations = max_iterations
        self._metrics_calculator = MetricsCalculator(
            risk_free_rate=risk_free_rate,
            annualization_factor=annualization_factor,
            confidence_level=confidence_level
        )
        self._logger = Logger(__name__)
    
    def analyze_portfolio(
        self,
        positions: List[Position],
        prices: Dict[str, List[float]],
        returns: Dict[str, List[float]],
        benchmark_returns: Optional[List[float]] = None,
        market_returns: Optional[List[float]] = None
    ) -> PortfolioAnalysisResult:
        """
        Perform comprehensive portfolio analysis.
        
        Args:
            positions: List of portfolio positions
            prices: Price series for each asset
            returns: Return series for each asset
            benchmark_returns: Benchmark return series
            market_returns: Market return series for beta calculation
            
        Returns:
            Complete portfolio analysis result
        """
        self._logger.info("Starting portfolio analysis")
        
        result = PortfolioAnalysisResult()
        
        try:
            # Calculate current allocations
            result.current_allocations = self._calculate_allocations(positions)
            
            # Calculate risk metrics
            result.risk_metrics = self._calculate_portfolio_risk(
                positions, returns, market_returns
            )
            
            # Calculate performance metrics
            result.performance = self._calculate_portfolio_performance(
                positions, returns
            )
            
            # Calculate diversification
            result.diversification_score = self._calculate_diversification(
                positions, returns
            )
            
            # Calculate correlation matrix
            result.correlation_matrix = self._calculate_correlation_matrix(
                returns
            )
            
            # Generate summary
            result.summary = self._generate_summary(result)
            
            # Identify strengths and weaknesses
            result.strengths = self._identify_strengths(result)
            result.weaknesses = self._identify_weaknesses(result)
            
            # Generate recommendations
            result.recommendations = self._generate_recommendations(result)
            
            self._logger.info("Portfolio analysis completed")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error in portfolio analysis: {str(e)}")
            raise
    
    def optimize_portfolio(
        self,
        returns: Dict[str, List[float]],
        objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE,
        constraints: Optional[Dict[str, float]] = None,
        min_weights: Optional[Dict[str, float]] = None,
        max_weights: Optional[Dict[str, float]] = None
    ) -> PortfolioOptimizationResult:
        """
        Optimize portfolio allocation.
        
        Args:
            returns: Return series for each asset
            objective: Optimization objective
            constraints: Risk constraints
            min_weights: Minimum weights for each asset
            max_weights: Maximum weights for each asset
            
        Returns:
            Portfolio optimization result
        """
        self._logger.info(f"Starting portfolio optimization with objective: {objective.value}")
        
        result = PortfolioOptimizationResult()
        
        try:
            symbols = list(returns.keys())
            n_assets = len(symbols)
            
            if n_assets < 2:
                self._logger.warning("Need at least 2 assets for optimization")
                return result
            
            # Prepare data
            returns_matrix = np.column_stack([returns[s] for s in symbols])
            mean_returns = np.mean(returns_matrix, axis=0)
            cov_matrix = np.cov(returns_matrix.T)
            
            # Set bounds
            bounds = [(0, 1) for _ in range(n_assets)]
            if min_weights:
                for i, symbol in enumerate(symbols):
                    if symbol in min_weights:
                        bounds[i] = (min_weights[symbol], bounds[i][1])
            if max_weights:
                for i, symbol in enumerate(symbols):
                    if symbol in max_weights:
                        bounds[i] = (bounds[i][0], max_weights[symbol])
            
            # Set constraints
            constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
            
            # Define objective functions
            def objective_sharpe(weights):
                portfolio_return = np.dot(weights, mean_returns)
                portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                return -(portfolio_return - self.risk_free_rate / self.annualization_factor) / portfolio_volatility if portfolio_volatility > 0 else 0
            
            def objective_return(weights):
                return -np.dot(weights, mean_returns)
            
            def objective_risk(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            def objective_sortino(weights):
                portfolio_returns = np.dot(weights, returns_matrix.T)
                downside_returns = portfolio_returns[portfolio_returns < 0]
                downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
                portfolio_return = np.mean(portfolio_returns)
                return -portfolio_return / downside_deviation if downside_deviation > 0 else 0
            
            def objective_calmar(weights):
                portfolio_returns = np.dot(weights, returns_matrix.T)
                portfolio_return = np.mean(portfolio_returns) * self.annualization_factor
                # Simulated max drawdown
                max_dd = self._simulate_max_drawdown(portfolio_returns)
                return -portfolio_return / max_dd if max_dd > 0 else 0
            
            # Select objective
            objective_func = objective_sharpe
            if objective == OptimizationObjective.MAXIMIZE_RETURN:
                objective_func = objective_return
            elif objective == OptimizationObjective.MINIMIZE_RISK:
                objective_func = objective_risk
            elif objective == OptimizationObjective.MAXIMIZE_SORTINO:
                objective_func = objective_sortino
            elif objective == OptimizationObjective.MAXIMIZE_CALMAR:
                objective_func = objective_calmar
            
            # Initial guess
            initial_weights = np.ones(n_assets) / n_assets
            
            # Optimize
            opt_result = minimize(
                objective_func,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': self.max_iterations}
            )
            
            if opt_result.success:
                result.weights = {symbols[i]: float(opt_result.x[i]) for i in range(n_assets)}
                result.convergence = True
                result.iterations = opt_result.nit
                result.objective_achieved = -opt_result.fun
                
                # Calculate optimized portfolio metrics
                optimized_returns = np.dot(opt_result.x, returns_matrix.T)
                result.expected_return = np.mean(optimized_returns) * self.annualization_factor
                result.expected_volatility = np.std(optimized_returns) * np.sqrt(self.annualization_factor)
                
                excess_returns = optimized_returns - self.risk_free_rate / self.annualization_factor
                result.expected_sharpe = np.mean(excess_returns) / np.std(optimized_returns) * np.sqrt(self.annualization_factor) if np.std(optimized_returns) > 0 else 0
                
                # Calculate VaR
                result.var_95 = np.percentile(optimized_returns, 5)
                result.cvar_95 = np.mean(optimized_returns[optimized_returns <= result.var_95]) if np.any(optimized_returns <= result.var_95) else 0
                
                # Calculate efficient frontier
                result.efficient_frontier = self._calculate_efficient_frontier(
                    mean_returns, cov_matrix, n_assets
                )
                
                self._logger.info(f"Optimization completed: Sharpe = {result.expected_sharpe:.2f}")
            else:
                self._logger.warning(f"Optimization failed: {opt_result.message}")
            
        except Exception as e:
            self._logger.error(f"Error in portfolio optimization: {str(e)}")
        
        return result
    
    def stress_test_portfolio(
        self,
        positions: List[Position],
        returns: Dict[str, List[float]],
        scenarios: Optional[List[Dict[str, float]]] = None
    ) -> List[StressTestResult]:
        """
        Perform stress testing on portfolio.
        
        Args:
            positions: List of portfolio positions
            returns: Return series for each asset
            scenarios: Custom stress scenarios
            
        Returns:
            List of stress test results
        """
        self._logger.info("Starting portfolio stress testing")
        
        results = []
        
        try:
            # Default scenarios if not provided
            if scenarios is None:
                scenarios = self._get_default_scenarios()
            
            # Calculate current portfolio value
            portfolio_value = sum([p.volume * p.current_price for p in positions])
            
            for scenario in scenarios:
                result = StressTestResult()
                result.scenario_name = scenario.get("name", "Unknown")
                result.scenario_type = scenario.get("type", "market")
                result.probability = scenario.get("probability", 0.01)
                result.confidence = scenario.get("confidence", 0.95)
                
                # Apply shocks to each asset
                total_impact = 0
                var_impact = 0
                volatility_impact = 0
                max_dd_impact = 0
                
                for position in positions:
                    symbol = position.symbol
                    if symbol in returns and len(returns[symbol]) > 0:
                        asset_returns = returns[symbol]
                        shock = scenario.get(symbol, scenario.get("default_shock", -0.05))
                        
                        # Calculate impact
                        position_value = position.volume * position.current_price
                        impact = position_value * shock
                        total_impact += impact
                        
                        # Calculate VaR impact
                        var = np.percentile(asset_returns, 5)
                        var_impact += position_value * (var - shock)
                        
                        # Calculate volatility impact
                        vol = np.std(asset_returns)
                        volatility_impact += position_value * (shock / vol if vol > 0 else 0)
                        
                        # Calculate drawdown impact
                        max_dd = self._simulate_max_drawdown(asset_returns)
                        max_dd_impact = max(max_dd_impact, shock / max_dd if max_dd > 0 else 0)
                
                result.return_impact = total_impact / portfolio_value if portfolio_value > 0 else 0
                result.value_change = total_impact
                result.drawdown_impact = max_dd_impact
                result.var_change = var_impact / portfolio_value if portfolio_value > 0 else 0
                result.volatility_change = volatility_impact
                
                results.append(result)
            
            self._logger.info(f"Stress testing completed: {len(results)} scenarios tested")
            
        except Exception as e:
            self._logger.error(f"Error in stress testing: {str(e)}")
        
        return results
    
    def _calculate_allocations(self, positions: List[Position]) -> List[AssetAllocation]:
        """Calculate current portfolio allocations."""
        allocations = []
        
        if not positions:
            return allocations
        
        total_value = sum([p.volume * p.current_price for p in positions])
        
        for position in positions:
            allocation = AssetAllocation()
            allocation.symbol = position.symbol
            position_value = position.volume * position.current_price
            allocation.weight = position_value / total_value if total_value > 0 else 0
            allocation.target_weight = allocation.weight  # Initial target = current
            
            # Set min/max weights based on position size
            if allocation.weight > 0.1:
                allocation.min_weight = allocation.weight * 0.5
                allocation.max_weight = allocation.weight * 1.5
            elif allocation.weight > 0.05:
                allocation.min_weight = 0.02
                allocation.max_weight = 0.15
            else:
                allocation.min_weight = 0
                allocation.max_weight = 0.05
            
            allocations.append(allocation)
        
        return allocations
    
    def _calculate_portfolio_risk(
        self,
        positions: List[Position],
        returns: Dict[str, List[float]],
        market_returns: Optional[List[float]] = None
    ) -> PortfolioRiskMetrics:
        """Calculate portfolio risk metrics."""
        metrics = PortfolioRiskMetrics()
        
        if not positions or not returns:
            return metrics
        
        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(positions, returns)
        
        if not portfolio_returns:
            return metrics
        
        returns_array = np.array(portfolio_returns)
        
        # Volatility
        metrics.volatility = np.std(returns_array)
        metrics.volatility_annualized = metrics.volatility * np.sqrt(self.annualization_factor)
        
        # Value at Risk
        metrics.var_95 = np.percentile(returns_array, 5)
        metrics.var_99 = np.percentile(returns_array, 1)
        metrics.cvar_95 = np.mean(returns_array[returns_array <= metrics.var_95]) if np.any(returns_array <= metrics.var_95) else 0
        metrics.cvar_99 = np.mean(returns_array[returns_array <= metrics.var_99]) if np.any(returns_array <= metrics.var_99) else 0
        
        # Drawdown
        cumulative_returns = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown_series = (running_max - cumulative_returns) / running_max
        
        metrics.max_drawdown = np.max(drawdown_series)
        metrics.current_drawdown = drawdown_series[-1] if len(drawdown_series) > 0 else 0
        metrics.average_drawdown = np.mean(drawdown_series)
        
        # Risk ratios
        excess_returns = returns_array - self.risk_free_rate / self.annualization_factor
        metrics.sharpe_ratio = np.mean(excess_returns) / np.std(returns_array) * np.sqrt(self.annualization_factor) if np.std(returns_array) > 0 else 0
        
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        metrics.sortino_ratio = np.mean(returns_array) / downside_deviation * np.sqrt(self.annualization_factor) if downside_deviation > 0 else 0
        
        metrics.calmar_ratio = (np.mean(returns_array) * self.annualization_factor) / metrics.max_drawdown if metrics.max_drawdown > 0 else 0
        
        # Omega ratio
        gains = returns_array[returns_array > 0]
        losses = returns_array[returns_array < 0]
        metrics.omega_ratio = np.sum(gains) / np.abs(np.sum(losses)) if np.abs(np.sum(losses)) > 0 else float('inf')
        
        # Risk decomposition
        if market_returns is not None:
            market_array = np.array(market_returns)
            if len(market_array) == len(returns_array):
                beta, alpha = np.polyfit(market_array, returns_array, 1)
                metrics.beta = beta
                correlation = np.corrcoef(returns_array, market_array)[0, 1]
                metrics.r_squared = correlation ** 2
                
                # Systematic and idiosyncratic risk
                metrics.systematic_risk = metrics.volatility_annualized * abs(beta)
                metrics.idiosyncratic_risk = metrics.volatility_annualized * np.sqrt(1 - metrics.r_squared)
                metrics.total_risk = metrics.systematic_risk + metrics.idiosyncratic_risk
        
        # Risk concentration
        weights = np.array([p.volume * p.current_price for p in positions])
        weights = weights / np.sum(weights) if np.sum(weights) > 0 else weights
        
        metrics.herfindahl_index = np.sum(weights ** 2)
        metrics.effective_number_of_bets = 1 / metrics.herfindahl_index if metrics.herfindahl_index > 0 else 0
        metrics.concentration_ratio_top5 = np.sum(np.sort(weights)[-5:]) if len(weights) >= 5 else np.sum(weights)
        
        # Extreme risk
        metrics.expected_shortfall = metrics.cvar_95
        metrics.tail_risk = (np.percentile(returns_array, 95) / np.percentile(returns_array, 5)) if np.percentile(returns_array, 5) != 0 else 0
        metrics.risk_of_ruin = self._calculate_risk_of_ruin(returns_array)
        
        return metrics
    
    def _calculate_portfolio_performance(
        self,
        positions: List[Position],
        returns: Dict[str, List[float]]
    ) -> PortfolioPerformance:
        """Calculate portfolio performance metrics."""
        performance = PortfolioPerformance()
        
        if not positions or not returns:
            return performance
        
        # Calculate portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(positions, returns)
        
        if not portfolio_returns:
            return performance
        
        returns_array = np.array(portfolio_returns)
        
        # Basic returns
        performance.total_return = np.prod(1 + returns_array) - 1
        performance.annualized_return = (1 + performance.total_return) ** (self.annualization_factor / len(returns_array)) - 1
        
        # Cumulative returns
        performance.cumulative_return = list(np.cumprod(1 + returns_array) - 1)
        
        # Return statistics
        performance.mean_return = np.mean(returns_array)
        performance.median_return = np.median(returns_array)
        performance.max_return = np.max(returns_array)
        performance.min_return = np.min(returns_array)
        
        # Positive/negative periods
        performance.positive_periods = np.sum(returns_array > 0)
        performance.negative_periods = np.sum(returns_array < 0)
        performance.positive_ratio = performance.positive_periods / len(returns_array) if len(returns_array) > 0 else 0
        
        # Consecutive periods
        win_series = (returns_array > 0).astype(int)
        loss_series = (returns_array < 0).astype(int)
        performance.max_consecutive_wins = self._max_consecutive(win_series, 1)
        performance.max_consecutive_losses = self._max_consecutive(loss_series, 1)
        
        # Monthly returns
        performance.monthly_returns = self._calculate_period_returns(returns_array, 21)
        
        # Yearly returns
        performance.yearly_returns = self._calculate_period_returns(returns_array, self.annualization_factor)
        
        # Best/Worst
        if performance.monthly_returns:
            best_month = max(performance.monthly_returns.items(), key=lambda x: x[1])
            worst_month = min(performance.monthly_returns.items(), key=lambda x: x[1])
            performance.best_month = {"period": best_month[0], "return": best_month[1]}
            performance.worst_month = {"period": worst_month[0], "return": worst_month[1]}
        
        if performance.yearly_returns:
            best_year = max(performance.yearly_returns.items(), key=lambda x: x[1])
            worst_year = min(performance.yearly_returns.items(), key=lambda x: x[1])
            performance.best_year = {"period": best_year[0], "return": best_year[1]}
            performance.worst_year = {"period": worst_year[0], "return": worst_year[1]}
        
        return performance
    
    def _calculate_diversification(
        self,
        positions: List[Position],
        returns: Dict[str, List[float]]
    ) -> float:
        """Calculate diversification score."""
        if len(positions) < 2:
            return 0.0
        
        # Calculate correlation matrix
        symbols = [p.symbol for p in positions]
        correlation_matrix = np.zeros((len(symbols), len(symbols)))
        
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    correlation_matrix[i, j] = 1.0
                elif symbol1 in returns and symbol2 in returns:
                    if len(returns[symbol1]) == len(returns[symbol2]):
                        corr = np.corrcoef(returns[symbol1], returns[symbol2])[0, 1]
                        correlation_matrix[i, j] = corr if not np.isnan(corr) else 0
        
        # Calculate average correlation
        avg_corr = (np.sum(correlation_matrix) - len(symbols)) / (len(symbols) * (len(symbols) - 1))
        
        # Diversification score (0-1)
        diversification_score = 1 - avg_corr
        
        return max(0, min(1, diversification_score))
    
    def _calculate_correlation_matrix(
        self,
        returns: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix."""
        symbols = list(returns.keys())
        correlation_matrix = {}
        
        for symbol1 in symbols:
            correlation_matrix[symbol1] = {}
            for symbol2 in symbols:
                if symbol1 == symbol2:
                    correlation_matrix[symbol1][symbol2] = 1.0
                elif symbol1 in returns and symbol2 in returns:
                    if len(returns[symbol1]) == len(returns[symbol2]):
                        corr = np.corrcoef(returns[symbol1], returns[symbol2])[0, 1]
                        correlation_matrix[symbol1][symbol2] = corr if not np.isnan(corr) else 0
        
        return correlation_matrix
    
    def _calculate_portfolio_returns(
        self,
        positions: List[Position],
        returns: Dict[str, List[float]]
    ) -> List[float]:
        """Calculate portfolio returns based on positions."""
        if not positions or not returns:
            return []
        
        # Get portfolio weights
        total_value = sum([p.volume * p.current_price for p in positions])
        weights = {}
        
        for position in positions:
            symbol = position.symbol
            if symbol in returns:
                position_value = position.volume * position.current_price
                weights[symbol] = position_value / total_value if total_value > 0 else 0
        
        # Calculate weighted returns
        min_length = min([len(returns[s]) for s in weights.keys() if s in returns])
        portfolio_returns = []
        
        for i in range(min_length):
            period_return = 0
            for symbol, weight in weights.items():
                if symbol in returns and i < len(returns[symbol]):
                    period_return += weight * returns[symbol][i]
            portfolio_returns.append(period_return)
        
        return portfolio_returns
    
    def _calculate_efficient_frontier(
        self,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        n_assets: int
    ) -> List[Dict[str, float]]:
        """Calculate efficient frontier points."""
        frontier = []
        
        # Calculate min and max returns
        min_return = np.min(mean_returns)
        max_return = np.max(mean_returns)
        
        # Generate points along the frontier
        n_points = 20
        
        for i in range(n_points + 1):
            target_return = min_return + (max_return - min_return) * (i / n_points)
            
            # Minimize volatility for target return
            constraints = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x: np.dot(x, mean_returns) - target_return}
            ]
            
            bounds = [(0, 1) for _ in range(n_assets)]
            initial_weights = np.ones(n_assets) / n_assets
            
            result = minimize(
                lambda x: np.sqrt(np.dot(x.T, np.dot(cov_matrix, x))),
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 500}
            )
            
            if result.success:
                volatility = np.sqrt(np.dot(result.x.T, np.dot(cov_matrix, result.x)))
                frontier.append({
                    'return': target_return * self.annualization_factor,
                    'volatility': volatility * np.sqrt(self.annualization_factor),
                    'sharpe': (target_return - self.risk_free_rate / self.annualization_factor) / volatility if volatility > 0 else 0
                })
        
        return frontier
    
    def _simulate_max_drawdown(self, returns: List[float]) -> float:
        """Simulate maximum drawdown from returns."""
        if not returns:
            return 0
        
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (running_max - cumulative) / running_max
        
        return np.max(drawdown)
    
    def _calculate_risk_of_ruin(self, returns: np.ndarray) -> float:
        """Calculate risk of ruin."""
        if len(returns) == 0:
            return 0
        
        win_rate = np.mean(returns > 0)
        avg_win = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0
        avg_loss = np.mean(returns[returns < 0]) if np.any(returns < 0) else 0
        
        if avg_loss == 0:
            return 0
        
        kelly_fraction = win_rate - (1 - win_rate) * (avg_win / abs(avg_loss))
        
        if kelly_fraction > 0:
            risk_of_ruin = np.exp(-2 * kelly_fraction * 0.01)
        else:
            risk_of_ruin = 1.0
        
        return min(risk_of_ruin, 1.0)
    
    def _max_consecutive(self, series: np.ndarray, target: int) -> int:
        """Calculate maximum consecutive occurrences."""
        max_count = 0
        current_count = 0
        
        for value in series:
            if value == target:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def _calculate_period_returns(
        self,
        returns: np.ndarray,
        periods_per_year: int
    ) -> Dict[str, float]:
        """Calculate period returns."""
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
    
    def _get_default_scenarios(self) -> List[Dict[str, float]]:
        """Get default stress test scenarios."""
        return [
            {
                "name": "Market Crash",
                "type": "market",
                "default_shock": -0.20,
                "probability": 0.01,
                "confidence": 0.95
            },
            {
                "name": "Moderate Decline",
                "type": "market",
                "default_shock": -0.10,
                "probability": 0.05,
                "confidence": 0.95
            },
            {
                "name": "Volatility Spike",
                "type": "volatility",
                "default_shock": -0.08,
                "probability": 0.03,
                "confidence": 0.90
            },
            {
                "name": "Rate Hike",
                "type": "macro",
                "default_shock": -0.06,
                "probability": 0.04,
                "confidence": 0.90
            },
            {
                "name": "Liquidity Crisis",
                "type": "liquidity",
                "default_shock": -0.15,
                "probability": 0.02,
                "confidence": 0.95
            },
            {
                "name": "Flash Crash",
                "type": "market",
                "default_shock": -0.30,
                "probability": 0.005,
                "confidence": 0.99
            }
        ]
    
    def _generate_summary(self, result: PortfolioAnalysisResult) -> Dict[str, Any]:
        """Generate portfolio summary."""
        return {
            "total_value": sum([a.weight for a in result.current_allocations]),
            "num_assets": len(result.current_allocations),
            "diversification_score": result.diversification_score,
            "max_drawdown": result.risk_metrics.max_drawdown,
            "sharpe_ratio": result.risk_metrics.sharpe_ratio,
            "volatility": result.risk_metrics.volatility_annualized,
            "var_95": result.risk_metrics.var_95,
            "risk_score": self._calculate_risk_score(result),
            "efficiency_score": self._calculate_efficiency_score(result)
        }
    
    def _calculate_risk_score(self, result: PortfolioAnalysisResult) -> float:
        """Calculate risk score (0-1, lower is better)."""
        scores = []
        
        # Max drawdown (30%)
        dd_score = min(result.risk_metrics.max_drawdown / 0.3, 1)
        scores.append(dd_score * 0.3)
        
        # Volatility (30%)
        vol_score = min(result.risk_metrics.volatility_annualized / 0.5, 1)
        scores.append(vol_score * 0.3)
        
        # VaR (20%)
        var_score = min(abs(result.risk_metrics.var_95) / 0.1, 1)
        scores.append(var_score * 0.2)
        
        # Risk of ruin (20%)
        ror_score = min(result.risk_metrics.risk_of_ruin / 0.5, 1)
        scores.append(ror_score * 0.2)
        
        return sum(scores)
    
    def _calculate_efficiency_score(self, result: PortfolioAnalysisResult) -> float:
        """Calculate efficiency score (0-1, higher is better)."""
        scores = []
        
        # Sharpe ratio (40%)
        sr_score = min(result.risk_metrics.sharpe_ratio / 2, 1)
        scores.append(sr_score * 0.4)
        
        # Diversification (30%)
        scores.append(result.diversification_score * 0.3)
        
        # Return/risk (30%)
        rr_score = min(result.performance.annualized_return / (result.risk_metrics.volatility_annualized * 2), 1)
        scores.append(rr_score * 0.3)
        
        return sum(scores)
    
    def _identify_strengths(self, result: PortfolioAnalysisResult) -> List[str]:
        """Identify portfolio strengths."""
        strengths = []
        
        if result.diversification_score > 0.7:
            strengths.append("High diversification across assets")
        
        if result.risk_metrics.sharpe_ratio > 1:
            strengths.append("Good risk-adjusted returns")
        
        if result.risk_metrics.max_drawdown < 0.1:
            strengths.append("Low maximum drawdown")
        
        if result.performance.positive_ratio > 0.6:
            strengths.append("High percentage of profitable periods")
        
        if result.risk_metrics.effective_number_of_bets > 5:
            strengths.append("Good spread of risk across multiple positions")
        
        if result.risk_metrics.var_95 > -0.02:
            strengths.append("Low VaR - limited downside risk")
        
        return strengths
    
    def _identify_weaknesses(self, result: PortfolioAnalysisResult) -> List[str]:
        """Identify portfolio weaknesses."""
        weaknesses = []
        
        if result.diversification_score < 0.3:
            weaknesses.append("Low diversification - high concentration risk")
        
        if result.risk_metrics.sharpe_ratio < 0.5:
            weaknesses.append("Poor risk-adjusted returns")
        
        if result.risk_metrics.max_drawdown > 0.25:
            weaknesses.append("High maximum drawdown")
        
        if result.performance.positive_ratio < 0.4:
            weaknesses.append("Low percentage of profitable periods")
        
        if result.risk_metrics.herfindahl_index > 0.3:
            weaknesses.append("High concentration in few assets")
        
        if result.risk_metrics.var_95 < -0.05:
            weaknesses.append("High VaR - significant downside risk")
        
        return weaknesses
    
    def _generate_recommendations(self, result: PortfolioAnalysisResult) -> List[str]:
        """Generate portfolio improvement recommendations."""
        recommendations = []
        
        # Diversification recommendations
        if result.diversification_score < 0.4:
            recommendations.append("Increase diversification by adding uncorrelated assets")
        
        if result.risk_metrics.herfindahl_index > 0.3:
            recommendations.append("Reduce concentration by rebalancing large positions")
        
        # Risk recommendations
        if result.risk_metrics.max_drawdown > 0.2:
            recommendations.append("Implement stricter risk controls to reduce drawdown")
        
        if result.risk_metrics.var_95 < -0.04:
            recommendations.append("Reduce VaR by hedging or adding defensive positions")
        
        # Performance recommendations
        if result.risk_metrics.sharpe_ratio < 0.5:
            recommendations.append("Improve Sharpe ratio by enhancing return or reducing volatility")
        
        if result.performance.positive_ratio < 0.5:
            recommendations.append("Increase win rate through better portfolio selection")
        
        # Efficiency recommendations
        if result.summary.get("efficiency_score", 0) < 0.5:
            recommendations.append("Consider portfolio optimization to improve efficiency")
        
        # Position sizing
        if result.risk_metrics.risk_of_ruin > 0.2:
            recommendations.append("Reduce position sizes to lower risk of ruin")
        
        return recommendations


# Factory function
def create_portfolio_analyzer(
    risk_free_rate: float = 0.02,
    annualization_factor: int = 252,
    confidence_level: float = 0.95
) -> PortfolioAnalyzer:
    """
    Create a portfolio analyzer with default configuration.
    
    Args:
        risk_free_rate: Risk-free rate
        annualization_factor: Number of periods in a year
        confidence_level: Confidence level for VaR calculations
        
    Returns:
        Configured PortfolioAnalyzer instance
    """
    return PortfolioAnalyzer(
        risk_free_rate=risk_free_rate,
        annualization_factor=annualization_factor,
        confidence_level=confidence_level
    )
