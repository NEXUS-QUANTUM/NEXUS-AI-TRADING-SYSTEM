"""
NEXUS AI TRADING SYSTEM - Risk Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced risk analysis system for comprehensive risk assessment,
scenario analysis, stress testing, and portfolio risk management.
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from prometheus_client import Counter, Gauge, Histogram
from scipy import stats
from scipy.optimize import minimize

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
RISK_ANALYSIS_COUNTER = Counter(
    "nexus_risk_analyses_total",
    "Total number of risk analyses performed",
    ["analysis_type", "status"],
)
RISK_ANALYSIS_DURATION = Histogram(
    "nexus_risk_analysis_duration_seconds",
    "Duration of risk analysis",
    ["analysis_type"],
)
RISK_METRIC_GAUGE = Gauge(
    "nexus_risk_metrics",
    "Current risk metrics",
    ["metric", "portfolio"],
)


class RiskMetric(Enum):
    """Risk metrics."""

    # Portfolio metrics
    VAR_95 = "var_95"
    VAR_99 = "var_99"
    CVAR_95 = "cvar_95"
    CVAR_99 = "cvar_99"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"

    # Risk ratios
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    STERLING_RATIO = "sterling_ratio"
    OMEGA_RATIO = "omega_ratio"
    TAIL_RATIO = "tail_ratio"

    # Position risk
    POSITION_CONCENTRATION = "position_concentration"
    SECTOR_EXPOSURE = "sector_exposure"
    CORRELATION_RISK = "correlation_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    LEVERAGE_RISK = "leverage_risk"

    # Market risk
    BETA = "beta"
    ALPHA = "alpha"
    R_SQUARED = "r_squared"
    TREYNOR_RATIO = "treynor_ratio"
    INFORMATION_RATIO = "information_ratio"

    # Advanced risk
    DOWNSIDE_DEVIATION = "downside_deviation"
    UPSIDE_POTENTIAL = "upside_potential"
    PAIN_INDEX = "pain_index"
    MARTIN_RATIO = "martin_ratio"
    BURKE_RATIO = "burke_ratio"


class RiskLevel(Enum):
    """Risk levels."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


class ScenarioType(Enum):
    """Scenario types for stress testing."""

    MARKET_CRASH = "market_crash"
    FLASH_CRASH = "flash_crash"
    BLACK_SWAN = "black_swan"
    BEAR_MARKET = "bear_market"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    RATE_HIKE = "rate_hike"
    GEOPOLITICAL = "geopolitical"
    CUSTOM = "custom"


@dataclass
class RiskAnalysisConfig:
    """Configuration for risk analysis."""

    # VaR parameters
    confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99])
    var_method: str = "historical"  # "historical", "parametric", "monte_carlo"

    # Monte Carlo parameters
    monte_carlo_simulations: int = 10000
    monte_carlo_horizon: int = 252

    # Stress testing
    stress_scenarios: List[ScenarioType] = field(default_factory=list)
    stress_shock_percent: float = 0.20  # 20% shock

    # Portfolio limits
    max_position_concentration: float = 0.10  # 10%
    max_sector_exposure: float = 0.30  # 30%
    max_correlation_threshold: float = 0.70
    max_leverage: float = 2.0

    # Risk limits
    max_var_95: float = 0.05  # 5%
    max_var_99: float = 0.08  # 8%
    max_drawdown: float = 0.20  # 20%
    max_risk_score: float = 0.70

    # Analysis settings
    lookback_days: int = 252
    use_rolling_windows: bool = True
    rolling_window_days: int = 30
    min_data_points: int = 50

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "confidence_levels": self.confidence_levels,
            "var_method": self.var_method,
            "monte_carlo_simulations": self.monte_carlo_simulations,
            "monte_carlo_horizon": self.monte_carlo_horizon,
            "stress_scenarios": [s.value for s in self.stress_scenarios],
            "stress_shock_percent": self.stress_shock_percent,
            "max_position_concentration": self.max_position_concentration,
            "max_sector_exposure": self.max_sector_exposure,
            "max_correlation_threshold": self.max_correlation_threshold,
            "max_leverage": self.max_leverage,
            "max_var_95": self.max_var_95,
            "max_var_99": self.max_var_99,
            "max_drawdown": self.max_drawdown,
            "max_risk_score": self.max_risk_score,
            "lookback_days": self.lookback_days,
            "use_rolling_windows": self.use_rolling_windows,
            "rolling_window_days": self.rolling_window_days,
            "min_data_points": self.min_data_points,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAnalysisConfig":
        """Create from dictionary."""
        return cls(
            confidence_levels=data.get("confidence_levels", [0.95, 0.99]),
            var_method=data.get("var_method", "historical"),
            monte_carlo_simulations=data.get("monte_carlo_simulations", 10000),
            monte_carlo_horizon=data.get("monte_carlo_horizon", 252),
            stress_scenarios=[ScenarioType(s) for s in data.get("stress_scenarios", [])],
            stress_shock_percent=data.get("stress_shock_percent", 0.20),
            max_position_concentration=data.get("max_position_concentration", 0.10),
            max_sector_exposure=data.get("max_sector_exposure", 0.30),
            max_correlation_threshold=data.get("max_correlation_threshold", 0.70),
            max_leverage=data.get("max_leverage", 2.0),
            max_var_95=data.get("max_var_95", 0.05),
            max_var_99=data.get("max_var_99", 0.08),
            max_drawdown=data.get("max_drawdown", 0.20),
            max_risk_score=data.get("max_risk_score", 0.70),
            lookback_days=data.get("lookback_days", 252),
            use_rolling_windows=data.get("use_rolling_windows", True),
            rolling_window_days=data.get("rolling_window_days", 30),
            min_data_points=data.get("min_data_points", 50),
        )


@dataclass
class RiskMetrics:
    """Risk metrics result."""

    # Value at Risk
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration_days: float = 0.0

    # Risk ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sterling_ratio: float = 0.0
    omega_ratio: float = 0.0
    tail_ratio: float = 0.0

    # Market risk
    beta: float = 0.0
    alpha: float = 0.0
    r_squared: float = 0.0
    treynor_ratio: float = 0.0
    information_ratio: float = 0.0

    # Position risk
    position_concentration: float = 0.0
    sector_exposure: float = 0.0
    correlation_risk: float = 0.0
    liquidity_risk: float = 0.0
    leverage_risk: float = 0.0

    # Advanced risk
    downside_deviation: float = 0.0
    upside_potential: float = 0.0
    pain_index: float = 0.0
    martin_ratio: float = 0.0
    burke_ratio: float = 0.0

    # Risk score
    overall_risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MODERATE

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "avg_drawdown": self.avg_drawdown,
            "drawdown_duration_days": self.drawdown_duration_days,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "sterling_ratio": self.sterling_ratio,
            "omega_ratio": self.omega_ratio,
            "tail_ratio": self.tail_ratio,
            "beta": self.beta,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "treynor_ratio": self.treynor_ratio,
            "information_ratio": self.information_ratio,
            "position_concentration": self.position_concentration,
            "sector_exposure": self.sector_exposure,
            "correlation_risk": self.correlation_risk,
            "liquidity_risk": self.liquidity_risk,
            "leverage_risk": self.leverage_risk,
            "downside_deviation": self.downside_deviation,
            "upside_potential": self.upside_potential,
            "pain_index": self.pain_index,
            "martin_ratio": self.martin_ratio,
            "burke_ratio": self.burke_ratio,
            "overall_risk_score": self.overall_risk_score,
            "risk_level": self.risk_level.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class StressTestResult:
    """Stress test result."""

    scenario: ScenarioType
    shock_description: str
    portfolio_impact: float
    var_impact: float
    max_drawdown_impact: float
    loss_probability: float
    recovery_time_days: float
    risk_score_after: float
    risk_level_after: RiskLevel
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.value,
            "shock_description": self.shock_description,
            "portfolio_impact": self.portfolio_impact,
            "var_impact": self.var_impact,
            "max_drawdown_impact": self.max_drawdown_impact,
            "loss_probability": self.loss_probability,
            "recovery_time_days": self.recovery_time_days,
            "risk_score_after": self.risk_score_after,
            "risk_level_after": self.risk_level_after.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ScenarioResult:
    """Scenario analysis result."""

    name: str
    scenario_type: ScenarioType
    description: str
    returns: List[float]
    metrics: RiskMetrics
    probability: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskAnalyzer:
    """
    Advanced risk analysis system for comprehensive risk assessment.
    """

    def __init__(
        self,
        config: Optional[Union[RiskAnalysisConfig, Dict[str, Any]]] = None,
        market_data_service: Optional[Any] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the risk analyzer.

        Args:
            config: Risk analysis configuration
            market_data_service: Market data service instance
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        if isinstance(config, dict):
            self.config = RiskAnalysisConfig.from_dict(config)
        elif isinstance(config, RiskAnalysisConfig):
            self.config = config
        else:
            self.config = RiskAnalysisConfig()

        self.market_data_service = market_data_service
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._risk_history: List[RiskMetrics] = []
        self._scenario_results: List[ScenarioResult] = []
        self._stress_results: List[StressTestResult] = []

        logger.info("RiskAnalyzer initialized")

    async def analyze_risk(
        self,
        returns: Union[List[float], np.ndarray],
        portfolio_value: float,
        positions: Optional[List[Dict[str, Any]]] = None,
        benchmark_returns: Optional[Union[List[float], np.ndarray]] = None,
        config: Optional[Union[RiskAnalysisConfig, Dict[str, Any]]] = None,
    ) -> RiskMetrics:
        """
        Perform comprehensive risk analysis.

        Args:
            returns: Portfolio returns
            portfolio_value: Current portfolio value
            positions: Current positions
            benchmark_returns: Benchmark returns
            config: Risk analysis configuration

        Returns:
            Risk metrics
        """
        start_time = time.time()

        # Use config if provided
        if config:
            if isinstance(config, dict):
                analysis_config = RiskAnalysisConfig.from_dict(config)
            else:
                analysis_config = config
        else:
            analysis_config = self.config

        # Convert to numpy
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < analysis_config.min_data_points:
            logger.warning(f"Insufficient data points: {len(returns)} < {analysis_config.min_data_points}")
            return RiskMetrics()

        metrics = RiskMetrics()

        try:
            # Calculate VaR
            await self._calculate_var(metrics, returns, analysis_config)

            # Calculate CVaR
            await self._calculate_cvar(metrics, returns, analysis_config)

            # Calculate drawdown
            await self._calculate_drawdown(metrics, returns)

            # Calculate risk ratios
            await self._calculate_risk_ratios(metrics, returns)

            # Calculate market risk
            if benchmark_returns is not None:
                benchmark_returns = np.array(benchmark_returns)
                benchmark_returns = benchmark_returns[~np.isnan(benchmark_returns)]
                if len(benchmark_returns) > 0:
                    await self._calculate_market_risk(metrics, returns, benchmark_returns)

            # Calculate position risk
            if positions:
                await self._calculate_position_risk(metrics, positions, portfolio_value)

            # Calculate advanced risk metrics
            await self._calculate_advanced_risk(metrics, returns)

            # Calculate overall risk score
            await self._calculate_risk_score(metrics, analysis_config)

            # Determine risk level
            metrics.risk_level = self._determine_risk_level(metrics.overall_risk_score)

            # Record metrics
            metrics.timestamp = datetime.utcnow()

            # Update history
            async with self._lock:
                self._risk_history.append(metrics)
                if len(self._risk_history) > 1000:
                    self._risk_history = self._risk_history[-1000:]

            # Update metrics
            RISK_ANALYSIS_COUNTER.labels(
                analysis_type="comprehensive",
                status="success",
            ).inc()
            RISK_ANALYSIS_DURATION.labels(
                analysis_type="comprehensive",
            ).observe(time.time() - start_time)

            # Update gauges
            self._update_risk_gauges(metrics)

            logger.info(
                f"Risk analysis completed: VaR 95%: {metrics.var_95:.4f}, "
                f"Score: {metrics.overall_risk_score:.3f}, "
                f"Level: {metrics.risk_level.value}"
            )

            return metrics

        except Exception as e:
            RISK_ANALYSIS_COUNTER.labels(
                analysis_type="comprehensive",
                status="error",
            ).inc()
            logger.error(f"Error in risk analysis: {e}")
            raise

    async def _calculate_var(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
        config: RiskAnalysisConfig,
    ):
        """Calculate Value at Risk."""
        if config.var_method == "historical":
            # Historical VaR
            metrics.var_95 = -np.percentile(returns, (1 - 0.95) * 100)
            metrics.var_99 = -np.percentile(returns, (1 - 0.99) * 100)

        elif config.var_method == "parametric":
            # Parametric VaR (assumes normal distribution)
            mean = np.mean(returns)
            std = np.std(returns)
            metrics.var_95 = -(mean + std * stats.norm.ppf(1 - 0.95))
            metrics.var_99 = -(mean + std * stats.norm.ppf(1 - 0.99))

        elif config.var_method == "monte_carlo":
            # Monte Carlo VaR
            mean = np.mean(returns)
            std = np.std(returns)
            simulations = np.random.normal(mean, std, config.monte_carlo_simulations)
            metrics.var_95 = -np.percentile(simulations, (1 - 0.95) * 100)
            metrics.var_99 = -np.percentile(simulations, (1 - 0.99) * 100)

    async def _calculate_cvar(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
        config: RiskAnalysisConfig,
    ):
        """Calculate Conditional VaR (Expected Shortfall)."""
        # CVaR 95%
        var_95 = np.percentile(returns, (1 - 0.95) * 100)
        cvar_95 = returns[returns <= var_95].mean()
        metrics.cvar_95 = -cvar_95 if not np.isnan(cvar_95) else 0

        # CVaR 99%
        var_99 = np.percentile(returns, (1 - 0.99) * 100)
        cvar_99 = returns[returns <= var_99].mean()
        metrics.cvar_99 = -cvar_99 if not np.isnan(cvar_99) else 0

    async def _calculate_drawdown(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
    ):
        """Calculate drawdown metrics."""
        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)

        # Drawdown series
        drawdown = (running_max - cum_returns) / running_max

        metrics.max_drawdown = np.max(drawdown)
        metrics.current_drawdown = drawdown[-1] if len(drawdown) > 0 else 0
        metrics.avg_drawdown = np.mean(drawdown)

        # Calculate drawdown duration
        in_drawdown = False
        max_duration = 0
        current_duration = 0

        for dd in drawdown:
            if dd > 0:
                if not in_drawdown:
                    in_drawdown = True
                    current_duration = 1
                else:
                    current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                in_drawdown = False
                current_duration = 0

        metrics.drawdown_duration_days = max_duration

    async def _calculate_risk_ratios(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
    ):
        """Calculate risk ratios."""
        risk_free_rate = 0.02  # 2% annual risk-free rate
        periods_per_year = 252  # Daily returns

        # Mean and std
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Sharpe Ratio
        excess_returns = returns - risk_free_rate / periods_per_year
        if std_return > 0:
            metrics.sharpe_ratio = mean_return / std_return * np.sqrt(periods_per_year)

        # Sortino Ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0
        if downside_deviation > 0:
            metrics.sortino_ratio = mean_return / downside_deviation * np.sqrt(periods_per_year)

        # Calmar Ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = mean_return * periods_per_year / metrics.max_drawdown

        # Sterling Ratio
        avg_drawdown = metrics.avg_drawdown
        if avg_drawdown > 0:
            metrics.sterling_ratio = mean_return * periods_per_year / (avg_drawdown + 0.1)

        # Omega Ratio
        threshold = risk_free_rate / periods_per_year
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        if len(losses) > 0 and np.sum(losses) > 0:
            metrics.omega_ratio = np.sum(gains) / np.sum(losses)

        # Tail Ratio
        tail_5_percent = np.percentile(returns, 5)
        tail_95_percent = np.percentile(returns, 95)
        if abs(tail_5_percent) > 0:
            metrics.tail_ratio = tail_95_percent / abs(tail_5_percent)

    async def _calculate_market_risk(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ):
        """Calculate market risk metrics."""
        # Beta and Alpha (using CAPM)
        cov_matrix = np.cov(returns, benchmark_returns)
        if cov_matrix[1, 1] > 0:
            beta = cov_matrix[0, 1] / cov_matrix[1, 1]
            metrics.beta = beta

            # Alpha (annualized)
            mean_return = np.mean(returns) * 252
            mean_benchmark = np.mean(benchmark_returns) * 252
            risk_free_rate = 0.02
            metrics.alpha = mean_return - (risk_free_rate + beta * (mean_benchmark - risk_free_rate))

            # R-squared
            correlation = np.corrcoef(returns, benchmark_returns)[0, 1]
            metrics.r_squared = correlation ** 2

            # Treynor Ratio
            if beta > 0:
                metrics.treynor_ratio = (mean_return - risk_free_rate) / beta

            # Information Ratio
            excess_returns = returns - benchmark_returns
            if np.std(excess_returns) > 0:
                metrics.information_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    async def _calculate_position_risk(
        self,
        metrics: RiskMetrics,
        positions: List[Dict[str, Any]],
        portfolio_value: float,
    ):
        """Calculate position risk metrics."""
        if not positions or portfolio_value == 0:
            return

        # Position concentration (largest position)
        position_values = [p.get("value", 0) for p in positions]
        if position_values:
            max_position = max(position_values)
            metrics.position_concentration = max_position / portfolio_value

        # Sector exposure
        sectors = {}
        for pos in positions:
            sector = pos.get("sector", "unknown")
            value = pos.get("value", 0)
            sectors[sector] = sectors.get(sector, 0) + value

        if sectors:
            max_sector = max(sectors.values())
            metrics.sector_exposure = max_sector / portfolio_value

        # Correlation risk
        # This would require full correlation matrix of positions
        # Simplified calculation using average correlation
        if len(positions) > 1:
            # Assume average correlation of 0.5 for simplicity
            # In practice, would calculate from historical data
            n_positions = len(positions)
            avg_correlation = 0.5
            metrics.correlation_risk = avg_correlation * (1 - 1/n_positions)

        # Liquidity risk (based on position size vs average volume)
        # Simplified: assume 1% of portfolio
        metrics.liquidity_risk = 0.01

        # Leverage risk
        total_value = sum(p.get("value", 0) for p in positions)
        if portfolio_value > 0:
            metrics.leverage_risk = total_value / portfolio_value - 1

    async def _calculate_advanced_risk(
        self,
        metrics: RiskMetrics,
        returns: np.ndarray,
    ):
        """Calculate advanced risk metrics."""
        # Downside deviation
        downside_returns = returns[returns < 0]
        metrics.downside_deviation = np.std(downside_returns) if len(downside_returns) > 0 else 0

        # Upside potential
        upside_returns = returns[returns > 0]
        metrics.upside_potential = np.mean(upside_returns) if len(upside_returns) > 0 else 0

        # Pain Index (Martin Ratio)
        # Pain = sum of drawdowns / number of periods
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (running_max - cum_returns) / running_max
        pain = np.mean(drawdown * 100)

        if pain > 0:
            # Martin Ratio = (Return - Risk-Free) / Pain
            risk_free = 0.02
            metrics.martin_ratio = (np.mean(returns) * 252 - risk_free) / pain

            # Pain Index
            metrics.pain_index = pain

        # Burke Ratio
        # Burke = (Return - Risk-Free) / sqrt(sum of drawdowns^2 / n)
        if len(drawdown) > 0 and np.sum(drawdown ** 2) > 0:
            burke_denominator = np.sqrt(np.sum(drawdown ** 2) / len(drawdown))
            metrics.burke_ratio = (np.mean(returns) * 252 - risk_free) / burke_denominator

    async def _calculate_risk_score(
        self,
        metrics: RiskMetrics,
        config: RiskAnalysisConfig,
    ):
        """Calculate overall risk score."""
        scores = []

        # VaR score (0-1, higher = more risk)
        if config.max_var_95 > 0:
            var_score = min(1, metrics.var_95 / config.max_var_95)
            scores.append(var_score * 0.20)

        # Drawdown score
        if config.max_drawdown > 0:
            dd_score = min(1, metrics.max_drawdown / config.max_drawdown)
            scores.append(dd_score * 0.20)

        # Sharpe ratio score (inverse)
        sharpe_score = max(0, 1 - (metrics.sharpe_ratio / 2))  # 2 is considered good
        scores.append(sharpe_score * 0.15)

        # Sortino ratio score
        sortino_score = max(0, 1 - (metrics.sortino_ratio / 2))
        scores.append(sortino_score * 0.10)

        # Position concentration score
        if config.max_position_concentration > 0:
            conc_score = min(1, metrics.position_concentration / config.max_position_concentration)
            scores.append(conc_score * 0.10)

        # Leverage score
        if config.max_leverage > 0:
            lev_score = min(1, metrics.leverage_risk / config.max_leverage)
            scores.append(lev_score * 0.10)

        # Correlation risk score
        if config.max_correlation_threshold > 0:
            corr_score = min(1, metrics.correlation_risk / config.max_correlation_threshold)
            scores.append(corr_score * 0.10)

        # Downside deviation score
        if metrics.downside_deviation > 0:
            dd_dev_score = min(1, metrics.downside_deviation * 10)  # 10% downside deviation is high
            scores.append(dd_dev_score * 0.05)

        metrics.overall_risk_score = np.mean(scores)

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level based on score."""
        if score < 0.15:
            return RiskLevel.VERY_LOW
        elif score < 0.30:
            return RiskLevel.LOW
        elif score < 0.50:
            return RiskLevel.MODERATE
        elif score < 0.70:
            return RiskLevel.HIGH
        elif score < 0.85:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.EXTREME

    def _update_risk_gauges(self, metrics: RiskMetrics):
        """Update Prometheus gauges."""
        gauges = {
            "var_95": metrics.var_95,
            "var_99": metrics.var_99,
            "cvar_95": metrics.cvar_95,
            "cvar_99": metrics.cvar_99,
            "max_drawdown": metrics.max_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "overall_risk_score": metrics.overall_risk_score,
        }

        for metric, value in gauges.items():
            RISK_METRIC_GAUGE.labels(
                metric=metric,
                portfolio="default",
            ).set(value)

    async def stress_test_portfolio(
        self,
        returns: Union[List[float], np.ndarray],
        portfolio_value: float,
        scenarios: Optional[List[Union[ScenarioType, str]]] = None,
    ) -> List[StressTestResult]:
        """
        Perform stress testing on portfolio.

        Args:
            returns: Portfolio returns
            portfolio_value: Current portfolio value
            scenarios: Stress scenarios to test

        Returns:
            List of stress test results
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) < self.config.min_data_points:
            logger.warning("Insufficient data points for stress testing")
            return []

        if scenarios is None:
            scenarios = self.config.stress_scenarios
            if not scenarios:
                scenarios = list(ScenarioType)

        results = []

        for scenario in scenarios:
            if isinstance(scenario, str):
                scenario = ScenarioType(scenario)

            # Apply scenario shock
            shocked_returns = await self._apply_scenario(returns, scenario)

            # Calculate metrics after shock
            metrics = await self.analyze_risk(
                returns=shocked_returns,
                portfolio_value=portfolio_value,
            )

            # Calculate impact
            impact = (portfolio_value * (1 + np.mean(shocked_returns)) - portfolio_value) / portfolio_value
            var_impact = metrics.var_95 - self._risk_history[-1].var_95 if self._risk_history else 0

            # Create result
            result = StressTestResult(
                scenario=scenario,
                shock_description=self._get_scenario_description(scenario),
                portfolio_impact=impact,
                var_impact=var_impact,
                max_drawdown_impact=metrics.max_drawdown,
                loss_probability=np.mean(shocked_returns < 0),
                recovery_time_days=self._estimate_recovery_time(shocked_returns),
                risk_score_after=metrics.overall_risk_score,
                risk_level_after=metrics.risk_level,
                details={
                    "var_95_after": metrics.var_95,
                    "var_99_after": metrics.var_99,
                    "drawdown_after": metrics.max_drawdown,
                    "sharpe_after": metrics.sharpe_ratio,
                },
            )

            results.append(result)

            async with self._lock:
                self._stress_results.append(result)
                if len(self._stress_results) > 100:
                    self._stress_results = self._stress_results[-100:]

        return results

    async def _apply_scenario(
        self,
        returns: np.ndarray,
        scenario: ScenarioType,
    ) -> np.ndarray:
        """
        Apply scenario shock to returns.

        Args:
            returns: Original returns
            scenario: Scenario type

        Returns:
            Shocked returns
        """
        shocked_returns = returns.copy()
        shock_amount = self.config.stress_shock_percent

        if scenario == ScenarioType.MARKET_CRASH:
            # 20-30% market decline over 5-10 days
            shock_days = np.random.randint(5, 11)
            decline = -np.random.uniform(0.20, 0.30)
            for i in range(min(shock_days, len(shocked_returns))):
                shocked_returns[-i-1] *= (1 + decline / shock_days)

        elif scenario == ScenarioType.FLASH_CRASH:
            # 10-20% crash in 1-2 days
            decline = -np.random.uniform(0.10, 0.20)
            shocked_returns[-1] *= (1 + decline)

        elif scenario == ScenarioType.BLACK_SWAN:
            # Rare extreme event (>3 std)
            std = np.std(returns)
            shock = -np.random.uniform(3, 5) * std
            shocked_returns[-1] = shock

        elif scenario == ScenarioType.BEAR_MARKET:
            # 15-25% decline over 1-3 months
            decline = -np.random.uniform(0.15, 0.25)
            shock_days = np.random.randint(20, 60)
            for i in range(min(shock_days, len(shocked_returns))):
                shocked_returns[-i-1] *= (1 + decline / shock_days)

        elif scenario == ScenarioType.VOLATILITY_SPIKE:
            # 2-3x volatility spike
            factor = np.random.uniform(2, 3)
            shocked_returns[-10:] = returns[-10:] * factor

        elif scenario == ScenarioType.LIQUIDITY_CRISIS:
            # 5-15% decline with high volatility
            decline = -np.random.uniform(0.05, 0.15)
            shock_days = np.random.randint(5, 15)
            for i in range(min(shock_days, len(shocked_returns))):
                shocked_returns[-i-1] *= (1 + decline / shock_days)
            # Add additional volatility
            shocked_returns[-10:] *= (1 + np.random.normal(0, 0.05, min(10, len(shocked_returns))))

        elif scenario == ScenarioType.RATE_HIKE:
            # Market repricing due to rate hike
            shock = -np.random.uniform(0.03, 0.08)
            shocked_returns[-5:] *= (1 + shock)

        elif scenario == ScenarioType.GEOPOLITICAL:
            # Sudden market reaction
            shock = -np.random.uniform(0.05, 0.15)
            shocked_returns[-3:] *= (1 + shock)

        return shocked_returns

    def _get_scenario_description(self, scenario: ScenarioType) -> str:
        """Get scenario description."""
        descriptions = {
            ScenarioType.MARKET_CRASH: "20-30% market decline over 5-10 days",
            ScenarioType.FLASH_CRASH: "10-20% crash in 1-2 days",
            ScenarioType.BLACK_SWAN: "Rare extreme event (>3 std deviation)",
            ScenarioType.BEAR_MARKET: "15-25% decline over 1-3 months",
            ScenarioType.VOLATILITY_SPIKE: "2-3x volatility spike",
            ScenarioType.LIQUIDITY_CRISIS: "5-15% decline with high volatility",
            ScenarioType.RATE_HIKE: "Market repricing due to rate hike",
            ScenarioType.GEOPOLITICAL: "Sudden geopolitical market reaction",
            ScenarioType.CUSTOM: "Custom stress scenario",
        }
        return descriptions.get(scenario, "Custom scenario")

    def _estimate_recovery_time(self, returns: np.ndarray) -> float:
        """
        Estimate recovery time from drawdown.

        Args:
            returns: Return series

        Returns:
            Estimated recovery time in days
        """
        if len(returns) < 2:
            return 30.0

        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + returns)
        cum_returns = cum_returns / cum_returns[0]  # Normalize to 1

        # Find max drawdown
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = 1 - cum_returns / running_max
        max_dd_idx = np.argmax(drawdown)

        if max_dd_idx == len(returns) - 1:
            return 30.0  # Still in drawdown

        # Calculate recovery time
        recovery_value = cum_returns[max_dd_idx]
        recovery_idx = max_dd_idx

        for i in range(max_dd_idx + 1, len(cum_returns)):
            if cum_returns[i] >= recovery_value:
                recovery_idx = i
                break

        return recovery_idx - max_dd_idx

    async def scenario_analysis(
        self,
        returns: Union[List[float], np.ndarray],
        scenarios: List[Dict[str, Any]],
    ) -> List[ScenarioResult]:
        """
        Perform scenario analysis.

        Args:
            returns: Portfolio returns
            scenarios: List of scenario definitions

        Returns:
            List of scenario results
        """
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]

        results = []

        for scenario_data in scenarios:
            name = scenario_data.get("name", "Scenario")
            description = scenario_data.get("description", "")
            scenario_type = scenario_data.get("type", ScenarioType.CUSTOM)
            scenario_returns = scenario_data.get("returns", returns)
            probability = scenario_data.get("probability", 0.5)

            if isinstance(scenario_type, str):
                scenario_type = ScenarioType(scenario_type)

            # Analyze risk for scenario
            metrics = await self.analyze_risk(
                returns=scenario_returns,
                portfolio_value=100000,  # Normalized value
            )

            result = ScenarioResult(
                name=name,
                scenario_type=scenario_type,
                description=description,
                returns=scenario_returns.tolist(),
                metrics=metrics,
                probability=probability,
                metadata=scenario_data.get("metadata", {}),
            )

            results.append(result)

            async with self._lock:
                self._scenario_results.append(result)
                if len(self._scenario_results) > 100:
                    self._scenario_results = self._scenario_results[-100:]

        return results

    async def get_risk_history(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[RiskMetrics]:
        """
        Get risk metric history.

        Args:
            limit: Maximum number of entries
            since: Time since

        Returns:
            List of risk metrics
        """
        async with self._lock:
            history = self._risk_history

            if since:
                history = [h for h in history if h.timestamp >= since]

            return history[-limit:]

    async def get_risk_report(self) -> Dict[str, Any]:
        """
        Get comprehensive risk report.

        Returns:
            Risk report
        """
        if not self._risk_history:
            return {
                "status": "no_data",
                "message": "No risk data available",
            }

        latest = self._risk_history[-1]

        report = {
            "current_risk": latest.to_dict(),
            "summary": {
                "risk_level": latest.risk_level.value,
                "risk_score": latest.overall_risk_score,
                "var_95": latest.var_95,
                "var_99": latest.var_99,
                "max_drawdown": latest.max_drawdown,
                "sharpe_ratio": latest.sharpe_ratio,
            },
            "history": {
                "points": len(self._risk_history),
                "start_time": self._risk_history[0].timestamp.isoformat(),
                "end_time": latest.timestamp.isoformat(),
            },
            "recent_stress_tests": [
                r.to_dict() for r in self._stress_results[-5:]
            ] if self._stress_results else [],
        }

        return report

    async def shutdown(self):
        """Shutdown the risk analyzer."""
        logger.info("RiskAnalyzer shut down")


# Export singleton
risk_analyzer = RiskAnalyzer()
