"""
NEXUS AI TRADING SYSTEM - VaR Calculator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced Value at Risk (VaR) calculation system with multiple methodologies,
portfolio VaR, marginal VaR, and comprehensive risk analytics.
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
VAR_CALCULATION_COUNTER = Counter(
    "nexus_var_calculations_total",
    "Total number of VaR calculations",
    ["method", "status"],
)
VAR_CALCULATION_DURATION = Histogram(
    "nexus_var_calculation_duration_seconds",
    "Duration of VaR calculations",
    ["method"],
)


class VaRMethod(Enum):
    """VaR calculation methods."""

    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    HYBRID = "hybrid"
    EXTREME_VALUE = "extreme_value"
    CORNISH_FISHER = "cornish_fisher"
    KERNEL = "kernel"


class VaRType(Enum):
    """Types of VaR."""

    INDIVIDUAL = "individual"
    PORTFOLIO = "portfolio"
    MARGINAL = "marginal"
    INCREMENTAL = "incremental"
    COMPONENT = "component"
    CONDITIONAL = "conditional"


@dataclass
class VaRResult:
    """VaR calculation result."""

    value: float
    confidence_level: float
    method: VaRMethod
    var_type: VaRType
    horizon_days: int = 1
    expected_shortfall: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    components: Optional[Dict[str, float]] = None
    marginal_var: Optional[Dict[str, float]] = None
    incremental_var: Optional[Dict[str, float]] = None
    component_var: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "confidence_level": self.confidence_level,
            "method": self.method.value,
            "var_type": self.var_type.value,
            "horizon_days": self.horizon_days,
            "expected_shortfall": self.expected_shortfall,
            "confidence_interval": self.confidence_interval,
            "components": self.components,
            "marginal_var": self.marginal_var,
            "incremental_var": self.incremental_var,
            "component_var": self.component_var,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class VaRConfig:
    """Configuration for VaR calculation."""

    confidence_level: float = 0.95
    horizon_days: int = 1
    method: VaRMethod = VaRMethod.HISTORICAL
    lookback_days: int = 252
    min_data_points: int = 50

    # Monte Carlo parameters
    mc_simulations: int = 10000

    # Extreme Value parameters
    evt_threshold: float = 0.05  # 5% threshold

    # Kernel parameters
    kernel_bandwidth: float = 0.1

    # Cornish-Fisher parameters
    use_cornish_fisher: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "confidence_level": self.confidence_level,
            "horizon_days": self.horizon_days,
            "method": self.method.value,
            "lookback_days": self.lookback_days,
            "min_data_points": self.min_data_points,
            "mc_simulations": self.mc_simulations,
            "evt_threshold": self.evt_threshold,
            "kernel_bandwidth": self.kernel_bandwidth,
            "use_cornish_fisher": self.use_cornish_fisher,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VaRConfig":
        """Create from dictionary."""
        return cls(
            confidence_level=data.get("confidence_level", 0.95),
            horizon_days=data.get("horizon_days", 1),
            method=VaRMethod(data.get("method", "historical")),
            lookback_days=data.get("lookback_days", 252),
            min_data_points=data.get("min_data_points", 50),
            mc_simulations=data.get("mc_simulations", 10000),
            evt_threshold=data.get("evt_threshold", 0.05),
            kernel_bandwidth=data.get("kernel_bandwidth", 0.1),
            use_cornish_fisher=data.get("use_cornish_fisher", False),
        )


class VaRCalculator:
    """
    Advanced Value at Risk calculation system.
    """

    def __init__(
        self,
        config: Optional[Union[VaRConfig, Dict[str, Any]]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the VaR calculator.

        Args:
            config: VaR configuration
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        if isinstance(config, dict):
            self.config = VaRConfig.from_dict(config)
        elif isinstance(config, VaRConfig):
            self.config = config
        else:
            self.config = VaRConfig()

        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._calculation_history: List[VaRResult] = []

        logger.info("VaRCalculator initialized")

    async def calculate_var(
        self,
        returns: Union[List[float], np.ndarray],
        config: Optional[Union[VaRConfig, Dict[str, Any]]] = None,
        var_type: VaRType = VaRType.INDIVIDUAL,
    ) -> VaRResult:
        """
        Calculate Value at Risk.

        Args:
            returns: Return series
            config: VaR configuration
            var_type: Type of VaR

        Returns:
            VaR result
        """
        start_time = time.time()

        # Parse config
        if config:
            if isinstance(config, dict):
                calc_config = VaRConfig.from_dict(config)
            else:
                calc_config = config
        else:
            calc_config = self.config

        # Prepare returns
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < calc_config.min_data_points:
            logger.warning(f"Insufficient data: {len(returns)} < {calc_config.min_data_points}")
            return VaRResult(
                value=0.0,
                confidence_level=calc_config.confidence_level,
                method=calc_config.method,
                var_type=var_type,
                horizon_days=calc_config.horizon_days,
                metadata={"error": "Insufficient data points"},
            )

        try:
            # Calculate VaR based on method
            if calc_config.method == VaRMethod.HISTORICAL:
                result = await self._calculate_historical_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.PARAMETRIC:
                result = await self._calculate_parametric_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.MONTE_CARLO:
                result = await self._calculate_monte_carlo_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.HYBRID:
                result = await self._calculate_hybrid_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.EXTREME_VALUE:
                result = await self._calculate_extreme_value_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.CORNISH_FISHER:
                result = await self._calculate_cornish_fisher_var(returns, calc_config, var_type)
            elif calc_config.method == VaRMethod.KERNEL:
                result = await self._calculate_kernel_var(returns, calc_config, var_type)
            else:
                raise ValueError(f"Unsupported method: {calc_config.method}")

            # Calculate expected shortfall
            result.expected_shortfall = await self._calculate_expected_shortfall(
                returns, calc_config, result.value
            )

            # Calculate confidence interval
            result.confidence_interval = await self._calculate_confidence_interval(
                returns, calc_config, result.value
            )

            # Record history
            async with self._lock:
                self._calculation_history.append(result)
                if len(self._calculation_history) > 1000:
                    self._calculation_history = self._calculation_history[-1000:]

            # Update metrics
            VAR_CALCULATION_COUNTER.labels(
                method=calc_config.method.value,
                status="success",
            ).inc()
            VAR_CALCULATION_DURATION.labels(
                method=calc_config.method.value,
            ).observe(time.time() - start_time)

            logger.info(
                f"VaR calculated: {result.value:.4f} at {calc_config.confidence_level:.2%} "
                f"({calc_config.method.value})"
            )

            return result

        except Exception as e:
            VAR_CALCULATION_COUNTER.labels(
                method=calc_config.method.value,
                status="error",
            ).inc()
            logger.error(f"Error calculating VaR: {e}")
            raise

    async def calculate_portfolio_var(
        self,
        returns_data: Dict[str, np.ndarray],
        weights: Union[List[float], Dict[str, float]],
        config: Optional[Union[VaRConfig, Dict[str, Any]]] = None,
    ) -> VaRResult:
        """
        Calculate portfolio VaR with decomposition.

        Args:
            returns_data: Dictionary of returns for each asset
            weights: Asset weights (list or dict)
            config: VaR configuration

        Returns:
            VaR result with decomposition
        """
        start_time = time.time()

        # Parse config
        if config:
            if isinstance(config, dict):
                calc_config = VaRConfig.from_dict(config)
            else:
                calc_config = config
        else:
            calc_config = self.config

        # Process returns and weights
        symbols = list(returns_data.keys())

        if isinstance(weights, dict):
            weights_list = [weights.get(s, 0) for s in symbols]
        else:
            weights_list = weights

        # Normalize weights
        total_weight = sum(weights_list)
        if total_weight > 0:
            weights_list = [w / total_weight for w in weights_list]

        # Create returns matrix
        returns_matrix = np.array([returns_data[s] for s in symbols])

        # Calculate portfolio returns
        portfolio_returns = np.sum(returns_matrix.T * weights_list, axis=1)

        # Calculate portfolio VaR
        var_result = await self.calculate_var(
            returns=portfolio_returns,
            config=calc_config,
            var_type=VaRType.PORTFOLIO,
        )

        # Calculate component VaR
        component_var = await self._calculate_component_var(
            returns_matrix, weights_list, var_result.value
        )

        # Calculate marginal VaR
        marginal_var = await self._calculate_marginal_var(
            returns_matrix, weights_list, var_result.value
        )

        # Calculate incremental VaR
        incremental_var = await self._calculate_incremental_var(
            returns_matrix, weights_list, var_result.value
        )

        var_result.components = {s: v for s, v in zip(symbols, component_var)}
        var_result.marginal_var = {s: v for s, v in zip(symbols, marginal_var)}
        var_result.incremental_var = {s: v for s, v in zip(symbols, incremental_var)}
        var_result.component_var = {
            s: component_var[i] / var_result.value if var_result.value > 0 else 0
            for i, s in enumerate(symbols)
        }
        var_result.metadata["weights"] = {s: w for s, w in zip(symbols, weights_list)}
        var_result.metadata["symbols"] = symbols

        # Record duration
        VAR_CALCULATION_DURATION.labels(
            method=calc_config.method.value,
        ).observe(time.time() - start_time)

        return var_result

    # Individual VaR Methods

    async def _calculate_historical_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate historical VaR."""
        # Scale for horizon
        if config.horizon_days > 1:
            scaled_returns = returns * np.sqrt(config.horizon_days)
        else:
            scaled_returns = returns

        # Calculate VaR
        var = -np.percentile(scaled_returns, (1 - config.confidence_level) * 100)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "data_points": len(returns),
                "percentile": (1 - config.confidence_level) * 100,
            },
        )

    async def _calculate_parametric_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate parametric VaR (normal distribution)."""
        mean = np.mean(returns)
        std = np.std(returns)

        # Adjust for horizon
        if config.horizon_days > 1:
            mean_adj = mean * config.horizon_days
            std_adj = std * np.sqrt(config.horizon_days)
        else:
            mean_adj = mean
            std_adj = std

        # Calculate VaR
        z_score = stats.norm.ppf(1 - config.confidence_level)
        var = -(mean_adj + z_score * std_adj)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "mean": mean,
                "std": std,
                "z_score": z_score,
                "data_points": len(returns),
            },
        )

    async def _calculate_monte_carlo_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate Monte Carlo VaR."""
        mean = np.mean(returns)
        std = np.std(returns)
        simulations = config.mc_simulations

        # Generate random returns
        random_returns = np.random.normal(mean, std, (simulations, config.horizon_days))
        cumulative_returns = np.sum(random_returns, axis=1)

        # Calculate VaR
        var = -np.percentile(cumulative_returns, (1 - config.confidence_level) * 100)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "simulations": simulations,
                "mean": mean,
                "std": std,
                "data_points": len(returns),
            },
        )

    async def _calculate_hybrid_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate hybrid VaR (historical + volatility scaling)."""
        # Historical VaR
        historical_var = await self._calculate_historical_var(returns, config, var_type)

        # EWMA volatility
        lambda_ewma = 0.94
        volatility = self._calculate_ewma_volatility(returns, lambda_ewma)

        # Long-term volatility
        long_term_vol = np.std(returns)

        # Scale VaR
        if long_term_vol > 0:
            var = historical_var.value * (volatility / long_term_vol)
        else:
            var = historical_var.value

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "historical_var": historical_var.value,
                "volatility": volatility,
                "long_term_vol": long_term_vol,
                "data_points": len(returns),
            },
        )

    async def _calculate_extreme_value_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate EVT-based VaR using Generalized Pareto Distribution."""
        threshold = np.percentile(returns, config.evt_threshold * 100)

        # Get exceedances
        exceedances = returns[returns < threshold]
        exceedances = -exceedances  # Positive values for losses

        if len(exceedances) < 10:
            logger.warning(f"Too few exceedances ({len(exceedances)}), falling back to historical")
            return await self._calculate_historical_var(returns, config, var_type)

        # Fit GPD
        params = stats.genpareto.fit(exceedances)
        shape, loc, scale = params

        # Calculate VaR using GPD
        n = len(returns)
        n_exceed = len(exceedances)
        p = 1 - config.confidence_level

        if shape != 0:
            gpd_quantile = loc + (scale / shape) * (
                ((n / n_exceed) * p) ** (-shape) - 1
            )
        else:
            gpd_quantile = loc - scale * np.log((n / n_exceed) * p)

        var = gpd_quantile

        # Adjust for horizon
        if config.horizon_days > 1:
            var *= np.sqrt(config.horizon_days)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "threshold": threshold,
                "exceedances": len(exceedances),
                "gpd_shape": shape,
                "gpd_loc": loc,
                "gpd_scale": scale,
                "data_points": len(returns),
            },
        )

    async def _calculate_cornish_fisher_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate Cornish-Fisher VaR (adjusts for skewness and kurtosis)."""
        mean = np.mean(returns)
        std = np.std(returns)
        skew = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)

        # Cornish-Fisher expansion
        z_score = stats.norm.ppf(1 - config.confidence_level)
        z_cf = z_score + (1/6) * (z_score**2 - 1) * skew + \
               (1/24) * (z_score**3 - 3*z_score) * kurtosis + \
               (1/36) * (2*z_score**3 - 5*z_score) * skew**2

        # Adjust for horizon
        if config.horizon_days > 1:
            mean_adj = mean * config.horizon_days
            std_adj = std * np.sqrt(config.horizon_days)
        else:
            mean_adj = mean
            std_adj = std

        var = -(mean_adj + z_cf * std_adj)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "mean": mean,
                "std": std,
                "skew": skew,
                "kurtosis": kurtosis,
                "z_score_original": z_score,
                "z_score_cf": z_cf,
                "data_points": len(returns),
            },
        )

    async def _calculate_kernel_var(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var_type: VaRType,
    ) -> VaRResult:
        """Calculate kernel-based VaR."""
        # Use kernel density estimation
        kernel = stats.gaussian_kde(returns, bw_method=config.kernel_bandwidth)

        # Find quantile using kernel density
        def find_quantile(target):
            from scipy.optimize import root_scalar

            def cdf_func(x):
                return kernel.integrate_box_1d(-np.inf, x) - target

            result = root_scalar(cdf_func, bracket=[-1, 1], method="bisect")
            return result.root

        quantile = find_quantile(1 - config.confidence_level)
        var = -quantile

        # Adjust for horizon
        if config.horizon_days > 1:
            var *= np.sqrt(config.horizon_days)

        return VaRResult(
            value=var,
            confidence_level=config.confidence_level,
            method=config.method,
            var_type=var_type,
            horizon_days=config.horizon_days,
            metadata={
                "bandwidth": config.kernel_bandwidth,
                "quantile": quantile,
                "data_points": len(returns),
            },
        )

    # Portfolio VaR Methods

    async def _calculate_component_var(
        self,
        returns_matrix: np.ndarray,
        weights: List[float],
        portfolio_var: float,
    ) -> np.ndarray:
        """
        Calculate component VaR.

        Args:
            returns_matrix: Returns matrix (components x time)
            weights: Component weights
            portfolio_var: Portfolio VaR

        Returns:
            Component VaR array
        """
        n_components = len(weights)

        # Calculate covariance matrix
        covariance = np.cov(returns_matrix)

        # Portfolio standard deviation
        portfolio_std = np.sqrt(weights.T @ covariance @ weights)

        if portfolio_std == 0:
            return np.zeros(n_components)

        # Marginal VaR
        marginal_var = (covariance @ weights) / portfolio_std

        # Component VaR
        component_var = weights * marginal_var * portfolio_var / portfolio_std

        return component_var

    async def _calculate_marginal_var(
        self,
        returns_matrix: np.ndarray,
        weights: List[float],
        portfolio_var: float,
    ) -> np.ndarray:
        """
        Calculate marginal VaR.

        Args:
            returns_matrix: Returns matrix (components x time)
            weights: Component weights
            portfolio_var: Portfolio VaR

        Returns:
            Marginal VaR array
        """
        n_components = len(weights)

        # Calculate covariance matrix
        covariance = np.cov(returns_matrix)

        # Portfolio standard deviation
        portfolio_std = np.sqrt(weights.T @ covariance @ weights)

        if portfolio_std == 0:
            return np.zeros(n_components)

        # Marginal VaR
        marginal_var = (covariance @ weights) / portfolio_std * portfolio_var / portfolio_std

        return marginal_var

    async def _calculate_incremental_var(
        self,
        returns_matrix: np.ndarray,
        weights: List[float],
        portfolio_var: float,
    ) -> np.ndarray:
        """
        Calculate incremental VaR for each component.

        Args:
            returns_matrix: Returns matrix (components x time)
            weights: Component weights
            portfolio_var: Portfolio VaR

        Returns:
            Incremental VaR array
        """
        n_components = len(weights)
        incremental_var = []

        for i in range(n_components):
            # Remove component from portfolio
            reduced_weights = weights.copy()
            reduced_weights[i] = 0

            # Normalize remaining weights
            total_remaining = sum(reduced_weights)
            if total_remaining > 0:
                reduced_weights = [w / total_remaining for w in reduced_weights]
            else:
                incremental_var.append(0)
                continue

            # Calculate reduced portfolio returns
            reduced_returns = np.sum(returns_matrix.T * reduced_weights, axis=1)

            # Calculate reduced portfolio VaR
            reduced_var = await self._calculate_historical_var(
                reduced_returns,
                VaRConfig(confidence_level=self.config.confidence_level),
                VaRType.INDIVIDUAL,
            )

            # Incremental VaR
            ivar = portfolio_var - reduced_var.value
            incremental_var.append(ivar)

        return np.array(incremental_var)

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

    async def _calculate_expected_shortfall(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var: float,
    ) -> float:
        """
        Calculate Expected Shortfall (CVaR).

        Args:
            returns: Return series
            config: VaR configuration
            var: VaR value

        Returns:
            Expected Shortfall
        """
        # Get returns beyond VaR
        losses = returns[returns < -var]

        if len(losses) > 0:
            es = -np.mean(losses)
        else:
            # Fallback: use VaR
            es = var

        # Adjust for horizon
        if config.horizon_days > 1:
            es *= np.sqrt(config.horizon_days)

        return es

    async def _calculate_confidence_interval(
        self,
        returns: np.ndarray,
        config: VaRConfig,
        var: float,
    ) -> Optional[Tuple[float, float]]:
        """
        Calculate confidence interval for VaR.

        Args:
            returns: Return series
            config: VaR configuration
            var: VaR value

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
            if config.method == VaRMethod.HISTORICAL:
                sample_var = -np.percentile(sample, (1 - config.confidence_level) * 100)
            elif config.method == VaRMethod.PARAMETRIC:
                mean = np.mean(sample)
                std = np.std(sample)
                z_score = stats.norm.ppf(1 - config.confidence_level)
                sample_var = -(mean + z_score * std)
            else:
                # Fallback to historical
                sample_var = -np.percentile(sample, (1 - config.confidence_level) * 100)

            var_samples.append(sample_var)

        # Calculate confidence interval
        if len(var_samples) > 0:
            lower = np.percentile(var_samples, 5)
            upper = np.percentile(var_samples, 95)
            return (lower, upper)

        return None

    async def get_history(
        self,
        method: Optional[Union[VaRMethod, str]] = None,
        var_type: Optional[Union[VaRType, str]] = None,
        limit: int = 100,
    ) -> List[VaRResult]:
        """
        Get VaR calculation history.

        Args:
            method: Filter by method
            var_type: Filter by VaR type
            limit: Maximum number of results

        Returns:
            List of VaR results
        """
        async with self._lock:
            history = self._calculation_history

            if method:
                if isinstance(method, str):
                    method = VaRMethod(method)
                history = [h for h in history if h.method == method]

            if var_type:
                if isinstance(var_type, str):
                    var_type = VaRType(var_type)
                history = [h for h in history if h.var_type == var_type]

            return history[-limit:]

    async def get_var_series(
        self,
        returns: Union[List[float], np.ndarray],
        window: int = 252,
        confidence_level: float = 0.95,
        method: Union[VaRMethod, str] = VaRMethod.HISTORICAL,
    ) -> pd.Series:
        """
        Calculate rolling VaR series.

        Args:
            returns: Return series
            window: Rolling window size
            confidence_level: Confidence level
            method: VaR method

        Returns:
            VaR time series
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < window:
            logger.warning(f"Insufficient data for rolling VaR: {len(returns)} < {window}")
            return pd.Series()

        if isinstance(method, str):
            method = VaRMethod(method)

        var_values = []
        dates = []

        # Use historical VaR for rolling calculation
        calc_config = VaRConfig(
            confidence_level=confidence_level,
            method=method,
            horizon_days=1,
        )

        for i in range(window, len(returns) + 1):
            window_returns = returns[i-window:i]
            result = await self._calculate_historical_var(
                window_returns,
                calc_config,
                VaRType.INDIVIDUAL,
            )
            var_values.append(result.value)
            dates.append(datetime.utcnow())  # In real implementation, use actual dates

        return pd.Series(var_values, index=dates)

    async def calculate_backtest(
        self,
        returns: Union[List[float], np.ndarray],
        var_results: List[VaRResult],
    ) -> Dict[str, Any]:
        """
        Backtest VaR calculations.

        Args:
            returns: Actual returns
            var_results: VaR results to backtest

        Returns:
            Backtest results
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) != len(var_results):
            logger.warning("Mismatch between returns and VaR results for backtest")

        # Count VaR breaches
        breaches = 0
        breaches_by_confidence = {}

        for i, result in enumerate(var_results):
            if i >= len(returns):
                break

            actual_return = returns[i]
            var_value = result.value

            if -actual_return > var_value:
                breaches += 1
                confidence = result.confidence_level
                breaches_by_confidence[confidence] = breaches_by_confidence.get(confidence, 0) + 1

        total = len(var_results)

        backtest_results = {
            "total_observations": total,
            "total_breaches": breaches,
            "breach_rate": breaches / total if total > 0 else 0,
            "expected_breach_rate": 1 - result.confidence_level if result else 0,
            "breaches_by_confidence": breaches_by_confidence,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Calculate Kupiec test statistic
        if total > 0 and result:
            expected_breaches = total * (1 - result.confidence_level)
            if expected_breaches > 0:
                from scipy.stats import chi2

                test_stat = (
                    (breaches - expected_breaches) ** 2 /
                    (expected_breaches * (1 - (1 - result.confidence_level)))
                )
                backtest_results["kupiec_test_stat"] = test_stat
                backtest_results["kupiec_p_value"] = 1 - chi2.cdf(test_stat, 1)

        return backtest_results

    async def shutdown(self):
        """Shutdown the VaR calculator."""
        logger.info("VaRCalculator shut down")


# Export singleton
var_calculator = VaRCalculator()
