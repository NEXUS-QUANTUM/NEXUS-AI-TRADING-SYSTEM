# trading/bots/hedge_bot/strategies/concave_hedge.py

"""
NEXUS HEDGE BOT - CONCAVE HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced concave hedging strategy that implements convexity-adjusted hedging
with asymmetric payoff structures, designed to protect against tail risks
while maintaining upside participation.

Version: 3.0.0
"""

import asyncio
import json
import math
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import numpy as np
import pandas as pd
import structlog
from scipy import stats
from scipy.optimize import minimize, brentq
from scipy.integrate import quad
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class ConcaveFunctionType(str, Enum):
    """Types of concave functions for hedging."""
    QUADRATIC = "quadratic"                    # Quadratic payoff
    POWER = "power"                            # Power law payoff
    LOGARITHMIC = "logarithmic"                # Logarithmic payoff
    SQUARE_ROOT = "square_root"                # Square root payoff
    EXPONENTIAL = "exponential"                # Exponential decay
    S_CURVE = "s_curve"                        # S-curve (sigmoid)
    PIECEWISE = "piecewise"                    # Piecewise linear
    CUSTOM = "custom"                          # Custom function


class ConcaveHedgeStyle(str, Enum):
    """Styles of concave hedging."""
    PROTECTIVE = "protective"                  # Protect against downside
    PARTICIPATORY = "participatory"            # Participate in upside
    BALANCED = "balanced"                      # Balanced approach
    AGGRESSIVE = "aggressive"                  # Aggressive protection
    DEFENSIVE = "defensive"                    # Maximum protection
    OPTIMAL = "optimal"                        # Optimized for conditions


class TailRiskRegime(str, Enum):
    """Tail risk regimes."""
    NORMAL = "normal"                          # Normal market conditions
    ELEVATED = "elevated"                      # Elevated tail risk
    HIGH = "high"                              # High tail risk
    EXTREME = "extreme"                        # Extreme tail risk
    CRASH = "crash"                            # Market crash regime


# === DATA MODELS ===

@dataclass
class ConcaveHedgeParameters:
    """Parameters for concave hedging."""
    function_type: ConcaveFunctionType = ConcaveFunctionType.QUADRATIC
    curvature: float = 0.5                     # Curvature parameter (0-1)
    asymmetry: float = 0.0                     # Asymmetry parameter (-1 to 1)
    threshold: float = 0.0                     # Activation threshold
    scaling: float = 1.0                       # Scaling factor
    power: float = 2.0                         # Power for power functions
    lambda_param: float = 1.0                  # Lambda for exponential
    kappa: float = 1.0                         # Kappa for S-curve
    shift: float = 0.0                         # Horizontal shift
    vertical_shift: float = 0.0                # Vertical shift
    max_hedge_ratio: float = 0.95              # Maximum hedge ratio
    min_hedge_ratio: float = 0.05              # Minimum hedge ratio
    tail_risk_adjustment: float = 1.0          # Tail risk adjustment factor
    confidence_level: float = 0.95             # Confidence level for VaR
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "function_type": self.function_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConcaveHedgeParameters":
        data = data.copy()
        data["function_type"] = ConcaveFunctionType(data["function_type"])
        return cls(**data)


@dataclass
class TailRiskMetrics:
    """Tail risk metrics."""
    var_95: float = 0.0                        # Value at Risk 95%
    var_99: float = 0.0                        # Value at Risk 99%
    cvar_95: float = 0.0                       # Conditional VaR 95%
    cvar_99: float = 0.0                       # Conditional VaR 99%
    expected_shortfall: float = 0.0            # Expected Shortfall
    tail_risk_score: float = 0.0               # Tail risk score (0-1)
    skewness: float = 0.0                      # Return skewness
    kurtosis: float = 3.0                      # Return kurtosis
    max_drawdown: float = 0.0                  # Maximum drawdown
    current_drawdown: float = 0.0              # Current drawdown
    regime: TailRiskRegime = TailRiskRegime.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TailRiskMetrics":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["regime"] = TailRiskRegime(data["regime"])
        return cls(**data)


@dataclass
class ConcaveHedgePosition:
    """Concave hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    hedge_ratio: float = 0.0
    concave_ratio: float = 0.0
    payoff: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"
    parameters: ConcaveHedgeParameters = field(default_factory=ConcaveHedgeParameters)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "parameters": self.parameters.to_dict(),
        }


# === CONCAVE HEDGE STRATEGY ===

class ConcaveHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced concave hedging strategy with asymmetric payoff structures
    for tail risk protection and convexity management.
    """

    def __init__(
        self,
        name: str = "concave_hedge",
        hedge_style: ConcaveHedgeStyle = ConcaveHedgeStyle.BALANCED,
        function_type: ConcaveFunctionType = ConcaveFunctionType.QUADRATIC,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the concave hedge strategy.

        Args:
            name: Strategy name
            hedge_style: Style of concave hedging
            function_type: Type of concave function
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.hedge_style = hedge_style
        self.function_type = function_type
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Hedge positions
        self._hedge_positions: List[ConcaveHedgePosition] = []
        self._position_history: List[ConcaveHedgePosition] = []

        # Risk metrics
        self._tail_risk_metrics = TailRiskMetrics()
        self._tail_risk_history: List[TailRiskMetrics] = []

        # Configuration
        self._config = {
            "max_hedge_ratio": 0.95,
            "min_hedge_ratio": 0.05,
            "curvature_initial": 0.5,
            "curvature_min": 0.1,
            "curvature_max": 1.0,
            "asymmetry_initial": 0.0,
            "asymmetry_min": -0.5,
            "asymmetry_max": 0.5,
            "threshold_initial": -0.02,
            "threshold_min": -0.10,
            "threshold_max": 0.05,
            "power_initial": 2.0,
            "power_min": 1.5,
            "power_max": 4.0,
            "lambda_initial": 1.0,
            "lambda_min": 0.5,
            "lambda_max": 3.0,
            "kappa_initial": 1.0,
            "kappa_min": 0.5,
            "kappa_max": 2.0,
            "max_position_size": 0.20,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.04,
            "tail_risk_threshold": 0.7,
            "confidence_level": 0.95,
            "lookback_days": 30,
            "rebalance_threshold": 0.02,
            "adaptive_parameters": True,
            "tail_risk_scaling": True,
            "asymmetric_payoff": True,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "tail_protection_score": 0.0,
            "upside_participation": 0.0,
            "average_hedge_ratio": 0.0,
            "concavity_score": 0.0,
            "hedge_effectiveness": 0.0,
            "max_drawdown_avoided": 0.0,
        }

        # Parameter optimization cache
        self._optimization_cache: Dict[str, Any] = {}
        self._parameter_history: List[ConcaveHedgeParameters] = []

        # Initialize parameters
        self._current_parameters = ConcaveHedgeParameters(
            function_type=function_type,
            curvature=self._config["curvature_initial"],
            asymmetry=self._config["asymmetry_initial"],
            threshold=self._config["threshold_initial"],
            power=self._config["power_initial"],
            lambda_param=self._config["lambda_initial"],
            kappa=self._config["kappa_initial"],
            max_hedge_ratio=self._config["max_hedge_ratio"],
            min_hedge_ratio=self._config["min_hedge_ratio"],
            confidence_level=self._config["confidence_level"],
        )

        logger.info(
            "concave_hedge_strategy_initialized",
            name=name,
            hedge_style=hedge_style.value,
            function_type=function_type.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate concave hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with concave hedge signals
        """
        try:
            # Calculate tail risk metrics
            await self._calculate_tail_risk(market_data)

            # Optimize parameters for current market conditions
            if self._config["adaptive_parameters"]:
                await self._optimize_parameters(market_data)

            # Calculate optimal hedge ratio
            hedge_ratio = await self._calculate_hedge_ratio(market_data)

            # Generate concave hedge signal
            signal = await self._generate_hedge_signal(hedge_ratio, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "tail_risk_metrics": self._tail_risk_metrics.to_dict(),
                "hedge_parameters": self._current_parameters.to_dict(),
                "hedge_ratio": hedge_ratio,
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "concave_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _calculate_tail_risk(self, market_data: Dict[str, Any]) -> None:
        """
        Calculate tail risk metrics from market data.

        Args:
            market_data: Current market data
        """
        try:
            # Get return history
            returns = market_data.get("returns", [])
            if not returns:
                returns = self._get_historical_returns(market_data)

            if len(returns) < 30:
                return

            returns_array = np.array(returns)

            # Calculate VaR
            var_95 = np.percentile(returns_array, 5)
            var_99 = np.percentile(returns_array, 1)

            # Calculate CVaR (Expected Shortfall)
            cvar_95 = returns_array[returns_array <= var_95].mean() if len(returns_array[returns_array <= var_95]) > 0 else var_95
            cvar_99 = returns_array[returns_array <= var_99].mean() if len(returns_array[returns_array <= var_99]) > 0 else var_99

            # Calculate skewness and kurtosis
            skewness = stats.skew(returns_array)
            kurtosis = stats.kurtosis(returns_array)

            # Calculate drawdown
            cumulative = np.cumprod(1 + returns_array)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / peak
            max_drawdown = np.max(drawdown)
            current_drawdown = drawdown[-1] if len(drawdown) > 0 else 0

            # Determine tail risk regime
            regime = self._determine_tail_risk_regime(var_95, var_99, kurtosis, max_drawdown)

            # Calculate tail risk score
            tail_risk_score = self._calculate_tail_risk_score(
                var_95, var_99, kurtosis, max_drawdown, skewness
            )

            self._tail_risk_metrics = TailRiskMetrics(
                var_95=float(var_95),
                var_99=float(var_99),
                cvar_95=float(cvar_95),
                cvar_99=float(cvar_99),
                expected_shortfall=float(cvar_95),
                tail_risk_score=tail_risk_score,
                skewness=float(skewness),
                kurtosis=float(kurtosis),
                max_drawdown=float(max_drawdown),
                current_drawdown=float(current_drawdown),
                regime=regime,
            )

            # Store history
            self._tail_risk_history.append(self._tail_risk_metrics)
            if len(self._tail_risk_history) > 100:
                self._tail_risk_history = self._tail_risk_history[-100:]

        except Exception as e:
            logger.error("tail_risk_calculation_failed", error=str(e))

    def _get_historical_returns(self, market_data: Dict[str, Any]) -> List[float]:
        """Get historical returns from market data."""
        prices = market_data.get("historical_prices", [])
        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        return returns

    def _determine_tail_risk_regime(
        self,
        var_95: float,
        var_99: float,
        kurtosis: float,
        max_drawdown: float,
    ) -> TailRiskRegime:
        """Determine tail risk regime from metrics."""
        if var_99 < -0.10 or max_drawdown > 0.20:
            return TailRiskRegime.CRASH
        elif var_99 < -0.05 or max_drawdown > 0.10:
            return TailRiskRegime.EXTREME
        elif var_95 < -0.03 or kurtosis > 5.0:
            return TailRiskRegime.HIGH
        elif var_95 < -0.02 or kurtosis > 4.0:
            return TailRiskRegime.ELEVATED
        else:
            return TailRiskRegime.NORMAL

    def _calculate_tail_risk_score(
        self,
        var_95: float,
        var_99: float,
        kurtosis: float,
        max_drawdown: float,
        skewness: float,
    ) -> float:
        """Calculate tail risk score (0-1)."""
        score = 0.0

        # VaR contribution
        if var_95 < -0.03:
            score += 0.3
        elif var_95 < -0.02:
            score += 0.2

        if var_99 < -0.05:
            score += 0.3
        elif var_99 < -0.03:
            score += 0.2

        # Kurtosis contribution
        if kurtosis > 5.0:
            score += 0.2
        elif kurtosis > 4.0:
            score += 0.1

        # Drawdown contribution
        if max_drawdown > 0.15:
            score += 0.2
        elif max_drawdown > 0.10:
            score += 0.1

        # Skewness contribution
        if skewness < -0.5:
            score += 0.1

        return min(1.0, score)

    async def _optimize_parameters(self, market_data: Dict[str, Any]) -> None:
        """
        Optimize concave hedge parameters for current market conditions.

        Args:
            market_data: Current market data
        """
        try:
            tail_risk_score = self._tail_risk_metrics.tail_risk_score
            regime = self._tail_risk_metrics.regime

            # Adjust based on tail risk
            if regime in (TailRiskRegime.CRASH, TailRiskRegime.EXTREME):
                # Increase curvature and protection
                self._current_parameters.curvature = min(
                    self._config["curvature_max"],
                    self._current_parameters.curvature * 1.3
                )
                self._current_parameters.asymmetry = max(
                    self._config["asymmetry_min"],
                    self._current_parameters.asymmetry - 0.1
                )
                self._current_parameters.max_hedge_ratio = min(
                    1.0,
                    self._current_parameters.max_hedge_ratio * 1.1
                )

            elif regime == TailRiskRegime.HIGH:
                # Moderate adjustment
                self._current_parameters.curvature = min(
                    self._config["curvature_max"],
                    self._current_parameters.curvature * 1.1
                )
                self._current_parameters.tail_risk_adjustment = 1.2

            elif regime == TailRiskRegime.NORMAL:
                # Return to baseline
                self._current_parameters.curvature = self._config["curvature_initial"]
                self._current_parameters.asymmetry = self._config["asymmetry_initial"]
                self._current_parameters.tail_risk_adjustment = 1.0
                self._current_parameters.max_hedge_ratio = self._config["max_hedge_ratio"]

            # Adjust threshold based on volatility
            volatility = market_data.get("volatility", 0.2)
            self._current_parameters.threshold = -volatility * 0.5

            # Adjust power for extreme events
            if tail_risk_score > self._config["tail_risk_threshold"]:
                self._current_parameters.power = min(
                    self._config["power_max"],
                    self._current_parameters.power * 1.2
                )
            else:
                self._current_parameters.power = self._config["power_initial"]

            # Clamp all parameters
            self._clamp_parameters()

            # Store parameter history
            self._parameter_history.append(self._current_parameters)
            if len(self._parameter_history) > 100:
                self._parameter_history = self._parameter_history[-100:]

        except Exception as e:
            logger.error("parameter_optimization_failed", error=str(e))

    def _clamp_parameters(self) -> None:
        """Clamp parameters to configured bounds."""
        self._current_parameters.curvature = max(
            self._config["curvature_min"],
            min(self._config["curvature_max"], self._current_parameters.curvature)
        )
        self._current_parameters.asymmetry = max(
            self._config["asymmetry_min"],
            min(self._config["asymmetry_max"], self._current_parameters.asymmetry)
        )
        self._current_parameters.threshold = max(
            self._config["threshold_min"],
            min(self._config["threshold_max"], self._current_parameters.threshold)
        )
        self._current_parameters.power = max(
            self._config["power_min"],
            min(self._config["power_max"], self._current_parameters.power)
        )
        self._current_parameters.lambda_param = max(
            self._config["lambda_min"],
            min(self._config["lambda_max"], self._current_parameters.lambda_param)
        )
        self._current_parameters.kappa = max(
            self._config["kappa_min"],
            min(self._config["kappa_max"], self._current_parameters.kappa)
        )
        self._current_parameters.max_hedge_ratio = max(
            0.5,
            min(0.99, self._current_parameters.max_hedge_ratio)
        )
        self._current_parameters.min_hedge_ratio = max(
            0.01,
            min(0.5, self._current_parameters.min_hedge_ratio)
        )
        self._current_parameters.tail_risk_adjustment = max(
            0.5,
            min(2.0, self._current_parameters.tail_risk_adjustment)
        )

    async def _calculate_hedge_ratio(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate optimal hedge ratio using concave function.

        Args:
            market_data: Current market data

        Returns:
            Hedge ratio (0-1)
        """
        tail_risk_score = self._tail_risk_metrics.tail_risk_score

        # Base hedge ratio from tail risk
        base_ratio = tail_risk_score

        # Apply concave function
        concave_ratio = self._apply_concave_function(base_ratio)

        # Apply tail risk adjustment
        ratio = concave_ratio * self._current_parameters.tail_risk_adjustment

        # Apply style-specific adjustments
        if self.hedge_style == ConcaveHedgeStyle.PROTECTIVE:
            ratio = max(ratio, 0.6)  # Minimum protection
        elif self.hedge_style == ConcaveHedgeStyle.AGGRESSIVE:
            ratio = max(ratio, 0.8)
        elif self.hedge_style == ConcaveHedgeStyle.DEFENSIVE:
            ratio = max(ratio, 0.9)
        elif self.hedge_style == ConcaveHedgeStyle.PARTICIPATORY:
            ratio = min(ratio, 0.7)  # Limit protection to maintain participation

        # Clamp
        ratio = max(
            self._current_parameters.min_hedge_ratio,
            min(self._current_parameters.max_hedge_ratio, ratio)
        )

        return ratio

    def _apply_concave_function(self, x: float) -> float:
        """
        Apply concave function to input value.

        Args:
            x: Input value (0-1)

        Returns:
            Concave transformed value (0-1)
        """
        params = self._current_parameters
        x = max(0, min(1, x))

        if params.function_type == ConcaveFunctionType.QUADRATIC:
            # Quadratic: f(x) = x^p
            return x ** params.power

        elif params.function_type == ConcaveFunctionType.POWER:
            # Power law: f(x) = x^p with asymmetry
            if x < params.threshold:
                return (x / params.threshold) ** params.power * params.threshold
            else:
                return params.threshold + (1 - params.threshold) * (
                    (x - params.threshold) / (1 - params.threshold)
                ) ** (1 / params.power)

        elif params.function_type == ConcaveFunctionType.LOGARITHMIC:
            # Logarithmic: f(x) = log(1 + k*x) / log(1 + k)
            if x == 0:
                return 0
            k = params.kappa
            return np.log(1 + k * x) / np.log(1 + k)

        elif params.function_type == ConcaveFunctionType.SQUARE_ROOT:
            # Square root: f(x) = sqrt(x)
            return np.sqrt(x)

        elif params.function_type == ConcaveFunctionType.EXPONENTIAL:
            # Exponential: f(x) = 1 - exp(-lambda*x)
            return 1 - np.exp(-params.lambda_param * x)

        elif params.function_type == ConcaveFunctionType.S_CURVE:
            # S-curve: f(x) = 1 / (1 + exp(-k*(x - threshold)))
            k = params.kappa
            threshold = params.threshold
            return 1 / (1 + np.exp(-k * (x - threshold)))

        elif params.function_type == ConcaveFunctionType.PIECEWISE:
            # Piecewise linear with different slopes
            if x < params.threshold:
                return x * params.curvature
            else:
                return params.threshold * params.curvature + (
                    x - params.threshold
                ) * (1 - params.threshold * params.curvature) / (1 - params.threshold)

        else:
            # Default: identity
            return x

    async def _generate_hedge_signal(
        self,
        hedge_ratio: float,
        market_data: Dict[str, Any],
    ) -> Optional[HedgeSignal]:
        """
        Generate concave hedge signal.

        Args:
            hedge_ratio: Calculated hedge ratio
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        if hedge_ratio < self._config["min_hedge_ratio"]:
            return None

        current_price = market_data.get("price", 0)
        if current_price <= 0:
            return None

        # Determine direction
        direction = HedgeDirection.SHORT  # Protective hedge

        # Calculate position size
        size = hedge_ratio * self._config["max_position_size"]

        # Calculate confidence
        confidence = self._calculate_hedge_confidence()

        if confidence < self.config.min_confidence:
            return None

        # Calculate stop loss and take profit
        stop_loss = self._calculate_stop_loss(
            current_price,
            direction,
            self._config["stop_loss_pct"]
        )
        take_profit = self._calculate_take_profit(
            current_price,
            direction,
            self._config["take_profit_pct"]
        )

        return HedgeSignal(
            hedge_type=HedgeType.CONCAVE,
            direction=direction,
            size=size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Concave hedge: ratio={hedge_ratio:.2f}, regime={self._tail_risk_metrics.regime.value}",
            metadata={
                "hedge_ratio": hedge_ratio,
                "concave_ratio": self._apply_concave_function(self._tail_risk_metrics.tail_risk_score),
                "tail_risk_score": self._tail_risk_metrics.tail_risk_score,
                "regime": self._tail_risk_metrics.regime.value,
                "function_type": self._current_parameters.function_type.value,
                "curvature": self._current_parameters.curvature,
            }
        )

    def _calculate_hedge_confidence(self) -> float:
        """Calculate confidence in the hedge signal."""
        confidence = 0.5

        # Tail risk score contribution
        tail_risk_score = self._tail_risk_metrics.tail_risk_score
        confidence += tail_risk_score * 0.3

        # Regime confidence
        regime = self._tail_risk_metrics.regime
        if regime in (TailRiskRegime.EXTREME, TailRiskRegime.CRASH):
            confidence += 0.2
        elif regime == TailRiskRegime.HIGH:
            confidence += 0.1

        # Parameter confidence
        if len(self._parameter_history) > 5:
            # Check parameter stability
            recent = self._parameter_history[-5:]
            curvature_std = np.std([p.curvature for p in recent])
            if curvature_std < 0.1:
                confidence += 0.1

        # Clamp
        return max(0.1, min(0.95, confidence))

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

                    # Update concave ratio
                    market_return = (position.current_price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0
                    position.concave_ratio = self._apply_concave_function(
                        max(0, 1 + market_return)
                    )

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._hedge_positions:
                avg_ratio = sum(p.hedge_ratio for p in self._hedge_positions) / len(self._hedge_positions)
                self._performance["average_hedge_ratio"] = avg_ratio

                # Calculate hedge effectiveness
                portfolio_pnl = self._performance.get("portfolio_pnl", 0)
                if portfolio_pnl != 0:
                    self._performance["hedge_effectiveness"] = abs(total_pnl / portfolio_pnl)

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "average_hedge_ratio": self._performance["average_hedge_ratio"],
                "tail_protection_score": self._performance["tail_protection_score"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "tail_risk_regime": self._tail_risk_metrics.regime.value,
                "tail_risk_score": self._tail_risk_metrics.tail_risk_score,
                "current_parameters": self._current_parameters.to_dict(),
                "config": self._config,
            }

    def get_tail_risk_metrics(self) -> Dict[str, Any]:
        """Get current tail risk metrics."""
        return self._tail_risk_metrics.to_dict()

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("concave_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("concave_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("concave_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "ConcaveHedgeStrategy",
    "ConcaveHedgeParameters",
    "ConcaveHedgePosition",
    "ConcaveHedgeStyle",
    "ConcaveFunctionType",
    "TailRiskRegime",
    "TailRiskMetrics",
]

logger.info("concave_hedge_module_loaded", version="3.0.0")
