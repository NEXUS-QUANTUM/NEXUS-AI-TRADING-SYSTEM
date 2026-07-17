"""
NEXUS AI TRADING SYSTEM - Risk Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced risk calculation system for computing various risk metrics,
value at risk, expected shortfall, and risk-adjusted performance measures
for trading portfolios and positions.
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from prometheus_client import Counter, Histogram
from scipy import stats
from scipy.optimize import minimize

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
RISK_CALCULATION_COUNTER = Counter(
    "nexus_risk_calculations_total",
    "Total number of risk calculations",
    ["calc_type", "status"],
)
RISK_CALCULATION_DURATION = Histogram(
    "nexus_risk_calculation_duration_seconds",
    "Duration of risk calculations",
    ["calc_type"],
)


class VarMethod(Enum):
    """Value at Risk calculation methods."""

    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    HYBRID = "hybrid"
    EXTREME_VALUE = "extreme_value"


class RiskMeasure(Enum):
    """Risk measures."""

    VAR = "var"
    CVAR = "cvar"
    VAR_RATIO = "var_ratio"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    AVG_DRAWDOWN = "avg_drawdown"
    DRAWDOWN_DURATION = "drawdown_duration"


@dataclass
class RiskResult:
    """Risk calculation result."""

    value: float
    confidence_level: float
    method: VarMethod
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    components: Optional[Dict[str, float]] = None
    confidence_interval: Optional[Tuple[float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "confidence_level": self.confidence_level,
            "method": self.method.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "components": self.components,
            "confidence_interval": self.confidence_interval,
        }


@dataclass
class RiskContribution:
    """Risk contribution of portfolio components."""

    component: str
    weight: float
    marginal_risk: float
    contribution: float
    percentage: float
    std_dev: float
    correlation: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component": self.component,
            "weight": self.weight,
            "marginal_risk": self.marginal_risk,
            "contribution": self.contribution,
            "percentage": self.percentage,
            "std_dev": self.std_dev,
            "correlation": self.correlation,
        }


class RiskCalculator:
    """
    Advanced risk calculation system for trading portfolios.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the risk calculator.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._calculation_history: List[RiskResult] = []

        # Load configuration
        self.risk_config = self.config.get("risk_calculator", {})
        self.default_confidence = self.risk_config.get("default_confidence", 0.95)
        self.default_method = VarMethod(
            self.risk_config.get("default_method", "historical")
        )
        self.monte_carlo_simulations = self.risk_config.get(
            "monte_carlo_simulations", 10000
        )
        self.lookback_days = self.risk_config.get("lookback_days", 252)
        self.min_data_points = self.risk_config.get("min_data_points", 50)

        logger.info("RiskCalculator initialized")

    async def calculate_var(
        self,
        returns: Union[List[float], np.ndarray],
        confidence_level: float = 0.95,
        method: Union[VarMethod, str] = VarMethod.HISTORICAL,
        horizon: int = 1,
        **kwargs,
    ) -> RiskResult:
        """
        Calculate Value at Risk (VaR).

        Args:
            returns: Return series
            confidence_level: Confidence level (0-1)
            method: Calculation method
            horizon: Time horizon in days
            **kwargs: Additional parameters

        Returns:
            RiskResult object
        """
        start_time = time.time()

        # Parse method
        if isinstance(method, str):
            method = VarMethod(method)

        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < self.min_data_points:
            logger.warning(f"Insufficient data points: {len(returns)} < {self.min_data_points}")
            return RiskResult(
                value=0.0,
                confidence_level=confidence_level,
                method=method,
                metadata={"error": "Insufficient data points"},
            )

        try:
            # Calculate based on method
            if method == VarMethod.HISTORICAL:
                var = await self._calculate_historical_var(returns, confidence_level, horizon)
            elif method == VarMethod.PARAMETRIC:
                var = await self._calculate_parametric_var(returns, confidence_level, horizon)
            elif method == VarMethod.MONTE_CARLO:
                var = await self._calculate_monte_carlo_var(returns, confidence_level, horizon, **kwargs)
            elif method == VarMethod.HYBRID:
                var = await self._calculate_hybrid_var(returns, confidence_level, horizon, **kwargs)
            elif method == VarMethod.EXTREME_VALUE:
                var = await self._calculate_extreme_value_var(returns, confidence_level, horizon, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Calculate confidence interval
            confidence_interval = await self._calculate_var_confidence_interval(
                returns, var, confidence_level, method
            )

            result = RiskResult(
                value=var,
                confidence_level=confidence_level,
                method=method,
                confidence_interval=confidence_interval,
                metadata={
                    "horizon_days": horizon,
                    "data_points": len(returns),
                    "method": method.value,
                },
            )

            # Store result
            async with self._lock:
                self._calculation_history.append(result)
                if len(self._calculation_history) > 1000:
                    self._calculation_history = self._calculation_history[-1000:]

            # Record metrics
            RISK_CALCULATION_COUNTER.labels(
                calc_type="var",
                status="success",
            ).inc()
            RISK_CALCULATION_DURATION.labels(
                calc_type="var",
            ).observe(time.time() - start_time)

            logger.info(
                f"VaR calculated: {var:.4f} at {confidence_level:.2%} "
                f"({method.value})"
            )

            return result

        except Exception as e:
            RISK_CALCULATION_COUNTER.labels(
                calc_type="var",
                status="error",
            ).inc()
            logger.error(f"Error calculating VaR: {e}")
            raise

    async def _calculate_historical_var(
        self,
        returns: np.ndarray,
        confidence_level: float,
        horizon: int,
    ) -> float:
        """
        Calculate historical VaR.

        Args:
            returns: Return series
            confidence_level: Confidence level
            horizon: Time horizon

        Returns:
            VaR value
        """
        # Adjust for horizon
        if horizon > 1:
            # Scale returns by sqrt of horizon (assuming i.i.d.)
            scaled_returns = returns * np.sqrt(horizon)
        else:
            scaled_returns = returns

        # Historical VaR is the percentile of returns
        var = -np.percentile(scaled_returns, (1 - confidence_level) * 100)

        return var

    async def _calculate_parametric_var(
        self,
        returns: np.ndarray,
        confidence_level: float,
        horizon: int,
    ) -> float:
        """
        Calculate parametric VaR (normal distribution).

        Args:
            returns: Return series
            confidence_level: Confidence level
            horizon: Time horizon

        Returns:
            VaR value
        """
        mean = np.mean(returns)
        std = np.std(returns)

        # Adjust for horizon
        if horizon > 1:
            mean_adj = mean * horizon
            std_adj = std * np.sqrt(horizon)
        else:
            mean_adj = mean
            std_adj = std

        # Calculate VaR using normal distribution
        z_score = stats.norm.ppf(1 - confidence_level)
        var = -(mean_adj + z_score * std_adj)

        return var

    async def _calculate_monte_carlo_var(
        self,
        returns: np.ndarray,
        confidence_level: float,
        horizon: int,
        **kwargs,
    ) -> float:
        """
        Calculate Monte Carlo VaR.

        Args:
            returns: Return series
            confidence_level: Confidence level
            horizon: Time horizon
            **kwargs: Additional parameters

        Returns:
            VaR value
        """
        simulations = kwargs.get("simulations", self.monte_carlo_simulations)

        # Fit distribution to returns
        mean = np.mean(returns)
        std = np.std(returns)

        # Generate random returns
        random_returns = np.random.normal(mean, std, (simulations, horizon))
        cumulative_returns = np.sum(random_returns, axis=1)

        var = -np.percentile(cumulative_returns, (1 - confidence_level) * 100)

        return var

    async def _calculate_hybrid_var(
        self,
        returns: np.ndarray,
        confidence_level: float,
        horizon: int,
        **kwargs,
    ) -> float:
        """
        Calculate hybrid VaR (historical + GARCH).

        Args:
            returns: Return series
            confidence_level: Confidence level
            horizon: Time horizon
            **kwargs: Additional parameters

        Returns:
            VaR value
        """
        # Use historical VaR with volatility scaling
        historical_var = await self._calculate_historical_var(
            returns, confidence_level, 1
        )

        # Estimate current volatility using EWMA
        lambda_ewma = kwargs.get("lambda_ewma", 0.94)
        volatility = self._calculate_ewma_volatility(returns, lambda_ewma)

        # Long-term volatility
        long_term_vol = np.std(returns)

        # Scale VaR by volatility ratio
        if long_term_vol > 0:
            var = historical_var * (volatility / long_term_vol)
            # Adjust for horizon
            if horizon > 1:
                var *= np.sqrt(horizon)
        else:
            var = historical_var

        return var

    async def _calculate_extreme_value_var(
        self,
        returns: np.ndarray,
        confidence_level: float,
        horizon: int,
        **kwargs,
    ) -> float:
        """
        Calculate EVT-based VaR.

        Args:
            returns: Return series
            confidence_level: Confidence level
            horizon: Time horizon
            **kwargs: Additional parameters

        Returns:
            VaR value
        """
        # Use Generalized Pareto Distribution (GPD)
        threshold = kwargs.get("threshold", np.percentile(returns, 5))

        # Get exceedances
        exceedances = returns[returns < threshold]
        exceedances = -exceedances  # Positive values for losses

        if len(exceedances) < 10:
            # Fallback to historical VaR
            return await self._calculate_historical_var(returns, confidence_level, horizon)

        # Fit GPD
        params = stats.genpareto.fit(exceedances)
        shape, loc, scale = params

        # Calculate VaR using GPD
        n = len(returns)
        n_exceed = len(exceedances)
        p = 1 - confidence_level

        # GPD quantile
        gpd_quantile = loc + (scale / shape) * (
            ((n / n_exceed) * p) ** (-shape) - 1
        ) if shape != 0 else loc - scale * np.log((n / n_exceed) * p)

        var = gpd_quantile

        # Adjust for horizon
        if horizon > 1:
            var *= np.sqrt(horizon)

        return var

    def _calculate_ewma_volatility(
        self,
        returns: np.ndarray,
        lambda_ewma: float = 0.94,
    ) -> float:
        """
        Calculate EWMA volatility.

        Args:
            returns: Return series
            lambda_ewma: Decay factor

        Returns:
            EWMA volatility
        """
        if len(returns) < 2:
            return np.std(returns)

        # Initial variance
        variance = np.var(returns)

        # EWMA calculation
        for i in range(1, len(returns)):
            variance = lambda_ewma * variance + (1 - lambda_ewma) * returns[i-1] ** 2

        return np.sqrt(variance)

    async def _calculate_var_confidence_interval(
        self,
        returns: np.ndarray,
        var: float,
        confidence_level: float,
        method: VarMethod,
    ) -> Optional[Tuple[float, float]]:
        """
        Calculate confidence interval for VaR.

        Args:
            returns: Return series
            var: VaR value
            confidence_level: Confidence level
            method: Calculation method

        Returns:
            Confidence interval or None
        """
        if len(returns) < 100:
            return None

        # Bootstrap method
        n_bootstrap = 1000
        var_samples = []

        for _ in range(n_bootstrap):
            # Bootstrap sample
            indices = np.random.randint(0, len(returns), len(returns))
            sample = returns[indices]

            # Calculate VaR for sample
            if method == VarMethod.HISTORICAL:
                sample_var = -np.percentile(sample, (1 - confidence_level) * 100)
            elif method == VarMethod.PARAMETRIC:
                mean = np.mean(sample)
                std = np.std(sample)
                z_score = stats.norm.ppf(1 - confidence_level)
                sample_var = -(mean + z_score * std)
            else:
                # Fallback to historical for other methods
                sample_var = -np.percentile(sample, (1 - confidence_level) * 100)

            var_samples.append(sample_var)

        # Calculate confidence interval
        lower = np.percentile(var_samples, 5)
        upper = np.percentile(var_samples, 95)

        return (lower, upper)

    async def calculate_cvar(
        self,
        returns: Union[List[float], np.ndarray],
        confidence_level: float = 0.95,
        method: Union[VarMethod, str] = VarMethod.HISTORICAL,
        **kwargs,
    ) -> RiskResult:
        """
        Calculate Conditional VaR (Expected Shortfall).

        Args:
            returns: Return series
            confidence_level: Confidence level
            method: Calculation method
            **kwargs: Additional parameters

        Returns:
            RiskResult object
        """
        start_time = time.time()

        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < self.min_data_points:
            return RiskResult(
                value=0.0,
                confidence_level=confidence_level,
                method=VarMethod.HISTORICAL,
                metadata={"error": "Insufficient data points"},
            )

        try:
            # Calculate VaR first
            var_result = await self.calculate_var(
                returns=returns,
                confidence_level=confidence_level,
                method=method,
                **kwargs,
            )

            var = var_result.value

            # CVaR is the average of losses beyond VaR
            losses = returns[returns < -var]

            if len(losses) > 0:
                cvar = -np.mean(losses)
            else:
                cvar = var  # Fallback to VaR

            result = RiskResult(
                value=cvar,
                confidence_level=confidence_level,
                method=VarMethod.HISTORICAL,
                metadata={
                    "var": var,
                    "data_points": len(returns),
                    "losses_beyond_var": len(losses),
                },
            )

            # Record metrics
            RISK_CALCULATION_COUNTER.labels(
                calc_type="cvar",
                status="success",
            ).inc()
            RISK_CALCULATION_DURATION.labels(
                calc_type="cvar",
            ).observe(time.time() - start_time)

            return result

        except Exception as e:
            RISK_CALCULATION_COUNTER.labels(
                calc_type="cvar",
                status="error",
            ).inc()
            logger.error(f"Error calculating CVaR: {e}")
            raise

    async def calculate_portfolio_var(
        self,
        positions: List[Dict[str, Any]],
        returns_data: Dict[str, np.ndarray],
        weights: Optional[List[float]] = None,
        confidence_level: float = 0.95,
        method: Union[VarMethod, str] = VarMethod.HISTORICAL,
    ) -> Dict[str, Any]:
        """
        Calculate portfolio VaR with risk decomposition.

        Args:
            positions: List of position dictionaries
            returns_data: Dictionary of returns for each position
            weights: Position weights (if not provided, calculated from positions)
            confidence_level: Confidence level
            method: Calculation method

        Returns:
            Portfolio risk results
        """
        start_time = time.time()

        try:
            # Calculate weights from positions if not provided
            if weights is None:
                total_value = sum(p.get("value", 0) for p in positions)
                if total_value > 0:
                    weights = [p.get("value", 0) / total_value for p in positions]
                else:
                    weights = [1.0 / len(positions)] * len(positions)

            # Get symbols
            symbols = [p.get("symbol", p.get("id", f"pos_{i}")) for i, p in enumerate(positions)]

            # Align returns data
            aligned_returns = []
            for symbol in symbols:
                if symbol in returns_data:
                    aligned_returns.append(returns_data[symbol])

            if not aligned_returns:
                raise ValueError("No returns data available for positions")

            # Convert to numpy array
            returns_matrix = np.array(aligned_returns)

            # Calculate portfolio returns
            portfolio_returns = np.sum(returns_matrix.T * weights, axis=1)

            # Calculate portfolio VaR
            var_result = await self.calculate_var(
                returns=portfolio_returns,
                confidence_level=confidence_level,
                method=method,
            )

            # Calculate risk contributions
            risk_contributions = await self._calculate_risk_contributions(
                returns_matrix, weights, var_result.value
            )

            # Calculate diversification ratio
            portfolio_std = np.std(portfolio_returns)
            weighted_std = np.sum([w * np.std(returns_matrix[i]) for i, w in enumerate(weights)])
            diversification_ratio = weighted_std / portfolio_std if portfolio_std > 0 else 1.0

            result = {
                "portfolio_var": var_result.value,
                "confidence_level": confidence_level,
                "method": method.value if isinstance(method, VarMethod) else method,
                "risk_contributions": [rc.to_dict() for rc in risk_contributions],
                "diversification_ratio": diversification_ratio,
                "portfolio_std": portfolio_std,
                "weighted_std": weighted_std,
                "position_weights": weights,
                "symbols": symbols,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Record metrics
            RISK_CALCULATION_COUNTER.labels(
                calc_type="portfolio_var",
                status="success",
            ).inc()
            RISK_CALCULATION_DURATION.labels(
                calc_type="portfolio_var",
            ).observe(time.time() - start_time)

            return result

        except Exception as e:
            RISK_CALCULATION_COUNTER.labels(
                calc_type="portfolio_var",
                status="error",
            ).inc()
            logger.error(f"Error calculating portfolio VaR: {e}")
            raise

    async def _calculate_risk_contributions(
        self,
        returns_matrix: np.ndarray,
        weights: List[float],
        portfolio_var: float,
    ) -> List[RiskContribution]:
        """
        Calculate risk contributions for portfolio components.

        Args:
            returns_matrix: Returns matrix (components x time)
            weights: Component weights
            portfolio_var: Portfolio VaR

        Returns:
            List of RiskContribution objects
        """
        contributions = []

        n_components = len(weights)

        for i in range(n_components):
            # Component returns
            component_returns = returns_matrix[i]

            # Standard deviation
            std_dev = np.std(component_returns)

            # Correlations with portfolio
            portfolio_returns = np.sum(returns_matrix.T * weights, axis=1)
            correlation = np.corrcoef(component_returns, portfolio_returns)[0, 1]

            # Marginal risk contribution
            marginal_risk = weights[i] * std_dev * correlation

            # Total risk
            total_risk = np.std(portfolio_returns)

            # Contribution
            contribution = marginal_risk * weights[i] * portfolio_var / total_risk if total_risk > 0 else 0

            # Percentage
            percentage = contribution / portfolio_var if portfolio_var > 0 else 0

            contributions.append(RiskContribution(
                component=f"Component_{i}",
                weight=weights[i],
                marginal_risk=marginal_risk,
                contribution=contribution,
                percentage=percentage,
                std_dev=std_dev,
                correlation=correlation,
            ))

        return contributions

    async def calculate_drawdown_metrics(
        self,
        returns: Union[List[float], np.ndarray],
    ) -> Dict[str, float]:
        """
        Calculate drawdown metrics.

        Args:
            returns: Return series

        Returns:
            Drawdown metrics
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < 2:
            return {
                "max_drawdown": 0.0,
                "avg_drawdown": 0.0,
                "current_drawdown": 0.0,
                "max_drawdown_duration": 0.0,
                "avg_drawdown_duration": 0.0,
                "drawdown_count": 0,
            }

        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)

        # Drawdown series
        drawdown = (running_max - cum_returns) / running_max

        # Max drawdown
        max_drawdown = np.max(drawdown)

        # Average drawdown
        avg_drawdown = np.mean(drawdown)

        # Current drawdown
        current_drawdown = drawdown[-1] if len(drawdown) > 0 else 0

        # Drawdown duration
        durations = []
        in_drawdown = False
        start_idx = 0

        for i, dd in enumerate(drawdown):
            if dd > 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
            elif dd == 0 and in_drawdown:
                in_drawdown = False
                durations.append(i - start_idx)

        if in_drawdown:
            durations.append(len(drawdown) - start_idx)

        max_duration = max(durations) if durations else 0
        avg_duration = np.mean(durations) if durations else 0

        return {
            "max_drawdown": max_drawdown,
            "avg_drawdown": avg_drawdown,
            "current_drawdown": current_drawdown,
            "max_drawdown_duration": max_duration,
            "avg_drawdown_duration": avg_duration,
            "drawdown_count": len(durations),
        }

    async def calculate_risk_adjusted_metrics(
        self,
        returns: Union[List[float], np.ndarray],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> Dict[str, float]:
        """
        Calculate risk-adjusted performance metrics.

        Args:
            returns: Return series
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year

        Returns:
            Risk-adjusted metrics
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < 2:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "omega_ratio": 0.0,
                "tail_ratio": 0.0,
                "information_ratio": 0.0,
            }

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Sharpe Ratio
        excess_returns = returns - risk_free_rate / periods_per_year
        sharpe = mean_return / std_return * np.sqrt(periods_per_year) if std_return > 0 else 0

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        sortino = mean_return / downside_deviation * np.sqrt(periods_per_year) if downside_deviation > 0 else 0

        # Calmar Ratio
        drawdown_metrics = await self.calculate_drawdown_metrics(returns)
        max_drawdown = drawdown_metrics["max_drawdown"]
        calmar = mean_return * periods_per_year / max_drawdown if max_drawdown > 0 else 0

        # Omega Ratio
        threshold = risk_free_rate / periods_per_year
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        omega = np.sum(gains) / np.sum(losses) if np.sum(losses) > 0 else 0

        # Tail Ratio
        tail_5 = np.percentile(returns, 5)
        tail_95 = np.percentile(returns, 95)
        tail_ratio = tail_95 / abs(tail_5) if abs(tail_5) > 0 else 0

        return {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "omega_ratio": omega,
            "tail_ratio": tail_ratio,
            "information_ratio": sharpe,  # Simplified
        }

    async def calculate_correlation_risk(
        self,
        returns_data: Dict[str, np.ndarray],
        correlation_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Calculate correlation-based risk metrics.

        Args:
            returns_data: Dictionary of returns for each symbol
            correlation_threshold: Threshold for high correlation

        Returns:
            Correlation risk metrics
        """
        symbols = list(returns_data.keys())
        n_symbols = len(symbols)

        if n_symbols < 2:
            return {
                "average_correlation": 0.0,
                "max_correlation": 0.0,
                "min_correlation": 0.0,
                "high_correlation_pairs": [],
                "risk_score": 0.0,
            }

        # Calculate correlation matrix
        returns_matrix = np.array([returns_data[s] for s in symbols])
        corr_matrix = np.corrcoef(returns_matrix)

        # Calculate statistics
        upper_tri_indices = np.triu_indices_from(corr_matrix, k=1)
        correlations = corr_matrix[upper_tri_indices]

        avg_correlation = np.mean(correlations)
        max_correlation = np.max(correlations)
        min_correlation = np.min(correlations)

        # Find high correlation pairs
        high_corr_pairs = []
        for i in range(n_symbols):
            for j in range(i + 1, n_symbols):
                if corr_matrix[i, j] > correlation_threshold:
                    high_corr_pairs.append({
                        "symbol1": symbols[i],
                        "symbol2": symbols[j],
                        "correlation": corr_matrix[i, j],
                    })

        # Risk score based on average correlation
        risk_score = min(1.0, avg_correlation * 1.5)  # Scale to 0-1

        return {
            "average_correlation": avg_correlation,
            "max_correlation": max_correlation,
            "min_correlation": min_correlation,
            "high_correlation_pairs": high_corr_pairs,
            "risk_score": risk_score,
            "correlation_matrix": corr_matrix.tolist(),
            "symbols": symbols,
        }

    async def optimize_portfolio_risk(
        self,
        returns_data: Dict[str, np.ndarray],
        target_return: Optional[float] = None,
        risk_aversion: float = 1.0,
        constraints: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Optimize portfolio for risk minimization.

        Args:
            returns_data: Dictionary of returns for each symbol
            target_return: Target return (if None, minimize risk)
            risk_aversion: Risk aversion parameter
            constraints: Additional constraints

        Returns:
            Optimal weights and risk metrics
        """
        symbols = list(returns_data.keys())
        returns_matrix = np.array([returns_data[s] for s in symbols])
        n_assets = len(symbols)

        # Calculate expected returns and covariance
        expected_returns = np.mean(returns_matrix, axis=1)
        covariance = np.cov(returns_matrix)

        # Define objective function
        def objective(weights):
            portfolio_return = np.sum(weights * expected_returns)
            portfolio_risk = np.sqrt(weights.T @ covariance @ weights)
            return -portfolio_return / portfolio_risk * risk_aversion

        # Constraints
        constraints_list = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]

        if target_return is not None:
            constraints_list.append({
                "type": "eq",
                "fun": lambda x: np.sum(x * expected_returns) - target_return,
            })

        if constraints:
            for constraint in constraints:
                constraints_list.append(constraint)

        # Bounds
        bounds = [(0, 1) for _ in range(n_assets)]

        # Optimize
        initial_weights = np.ones(n_assets) / n_assets
        result = minimize(
            objective,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints_list,
        )

        optimal_weights = result.x

        # Calculate optimized metrics
        portfolio_return = np.sum(optimal_weights * expected_returns)
        portfolio_risk = np.sqrt(optimal_weights.T @ covariance @ optimal_weights)
        sharpe_ratio = portfolio_return / portfolio_risk if portfolio_risk > 0 else 0

        return {
            "optimal_weights": {symbols[i]: optimal_weights[i] for i in range(n_assets)},
            "expected_return": portfolio_return * 252,  # Annualized
            "expected_risk": portfolio_risk * np.sqrt(252),  # Annualized
            "sharpe_ratio": sharpe_ratio * np.sqrt(252),
            "diversification_ratio": np.sum(np.sqrt(np.diag(covariance)) * optimal_weights) / portfolio_risk if portfolio_risk > 0 else 1.0,
            "converged": result.success,
            "iterations": result.nit,
            "symbols": symbols,
        }

    async def get_risk_history(
        self,
        calc_type: str = "var",
        limit: int = 100,
    ) -> List[RiskResult]:
        """
        Get risk calculation history.

        Args:
            calc_type: Type of calculation
            limit: Maximum number of results

        Returns:
            List of risk results
        """
        async with self._lock:
            history = self._calculation_history

            if calc_type == "var":
                # Filter by method
                history = [h for h in history if "var" in h.metadata.get("method", "")]
            elif calc_type == "cvar":
                # CVaR results have losses_beyond_var in metadata
                history = [h for h in history if "losses_beyond_var" in h.metadata]

            return history[-limit:]

    async def shutdown(self):
        """Shutdown the risk calculator."""
        logger.info("RiskCalculator shut down")


# Export singleton
risk_calculator = RiskCalculator()
