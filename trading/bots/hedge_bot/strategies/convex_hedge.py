# trading/bots/hedge_bot/strategies/convex_hedge.py

"""
NEXUS HEDGE BOT - CONVEX HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced convex hedging strategy that implements convexity-optimized
hedging with focus on capturing upside convexity while providing
downside protection through dynamic position sizing and option-like
payoff structures.

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

class ConvexFunctionType(str, Enum):
    """Types of convex functions for hedging."""
    EXPONENTIAL = "exponential"                # Exponential payoff
    POWER = "power"                            # Power law payoff
    HYPERBOLIC = "hyperbolic"                  # Hyperbolic payoff
    LOGISTIC = "logistic"                      # Logistic growth
    SIGMOID = "sigmoid"                        # Sigmoid function
    PIECEWISE = "piecewise"                    # Piecewise linear
    SPLINE = "spline"                          # Cubic spline
    CUSTOM = "custom"                          # Custom function


class ConvexHedgeStyle(str, Enum):
    """Styles of convex hedging."""
    AGGRESSIVE = "aggressive"                  # Maximize convexity
    MODERATE = "moderate"                      # Balanced convexity
    CONSERVATIVE = "conservative"              # Limited convexity
    DYNAMIC = "dynamic"                        # Dynamically adjusted
    OPTIMAL = "optimal"                        # Optimized for conditions
    TAIL_CAPTURE = "tail_capture"              # Focus on tail events


class ConvexityRegime(str, Enum):
    """Convexity regimes."""
    LOW = "low"                                # Low convexity opportunity
    NORMAL = "normal"                          # Normal convexity
    HIGH = "high"                              # High convexity
    EXTREME = "extreme"                        # Extreme convexity
    NEGATIVE = "negative"                      # Negative convexity


# === DATA MODELS ===

@dataclass
class ConvexHedgeParameters:
    """Parameters for convex hedging."""
    function_type: ConvexFunctionType = ConvexFunctionType.EXPONENTIAL
    curvature: float = 0.5                     # Curvature parameter (0-1)
    convexity_ratio: float = 0.7               # Target convexity ratio (0-1)
    threshold: float = 0.05                    # Activation threshold
    scaling: float = 1.0                       # Scaling factor
    power: float = 2.0                         # Power for power functions
    lambda_param: float = 2.0                  # Lambda for exponential
    kappa: float = 1.5                         # Kappa for logistic
    shift: float = 0.0                         # Horizontal shift
    vertical_shift: float = 0.0                # Vertical shift
    max_convexity: float = 0.95                # Maximum convexity ratio
    min_convexity: float = 0.05                # Minimum convexity ratio
    gamma_adjustment: float = 1.0              # Gamma adjustment factor
    vega_adjustment: float = 1.0               # Vega adjustment factor
    tail_risk_aware: bool = True               # Tail risk awareness
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "function_type": self.function_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConvexHedgeParameters":
        data = data.copy()
        data["function_type"] = ConvexFunctionType(data["function_type"])
        return cls(**data)


@dataclass
class ConvexityMetrics:
    """Convexity metrics."""
    gamma: float = 0.0                         # Gamma exposure
    vega: float = 0.0                          # Vega exposure
    theta: float = 0.0                         # Theta decay
    convexity_score: float = 0.0               # Convexity score (0-1)
    gamma_ratio: float = 0.0                   # Gamma ratio
    vega_ratio: float = 0.0                    # Vega ratio
    convexity_regime: ConvexityRegime = ConvexityRegime.NORMAL
    skewness: float = 0.0                      # Return skewness
    kurtosis: float = 3.0                      # Return kurtosis
    implied_volatility: float = 0.0            # Implied volatility
    realized_volatility: float = 0.0           # Realized volatility
    volatility_ratio: float = 1.0              # Volatility ratio
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "convexity_regime": self.convexity_regime.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConvexityMetrics":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["convexity_regime"] = ConvexityRegime(data["convexity_regime"])
        return cls(**data)


@dataclass
class ConvexHedgePosition:
    """Convex hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    convexity_ratio: float = 0.0
    payoff: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"
    parameters: ConvexHedgeParameters = field(default_factory=ConvexHedgeParameters)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "parameters": self.parameters.to_dict(),
        }


# === CONVEX HEDGE STRATEGY ===

class ConvexHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced convex hedging strategy that implements convexity-optimized
    hedging with dynamic position sizing and option-like payoff structures.
    """

    def __init__(
        self,
        name: str = "convex_hedge",
        hedge_style: ConvexHedgeStyle = ConvexHedgeStyle.DYNAMIC,
        function_type: ConvexFunctionType = ConvexFunctionType.EXPONENTIAL,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the convex hedge strategy.

        Args:
            name: Strategy name
            hedge_style: Style of convex hedging
            function_type: Type of convex function
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
        self._hedge_positions: List[ConvexHedgePosition] = []
        self._position_history: List[ConvexHedgePosition] = []

        # Convexity metrics
        self._convexity_metrics = ConvexityMetrics()
        self._convexity_history: List[ConvexityMetrics] = []

        # Configuration
        self._config = {
            "max_convexity": 0.95,
            "min_convexity": 0.05,
            "curvature_initial": 0.5,
            "curvature_min": 0.1,
            "curvature_max": 1.0,
            "convexity_ratio_initial": 0.7,
            "convexity_ratio_min": 0.3,
            "convexity_ratio_max": 0.9,
            "threshold_initial": 0.05,
            "threshold_min": 0.01,
            "threshold_max": 0.15,
            "power_initial": 2.0,
            "power_min": 1.5,
            "power_max": 4.0,
            "lambda_initial": 2.0,
            "lambda_min": 1.0,
            "lambda_max": 5.0,
            "kappa_initial": 1.5,
            "kappa_min": 0.5,
            "kappa_max": 3.0,
            "max_position_size": 0.20,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.10,
            "take_profit_pct": 0.20,
            "trailing_stop_pct": 0.05,
            "convexity_threshold": 0.5,
            "volatility_lookback": 30,
            "rebalance_threshold": 0.02,
            "adaptive_parameters": True,
            "gamma_scaling": True,
            "vega_hedging": True,
            "tail_risk_awareness": True,
            "max_gamma": 10.0,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "gamma_effectiveness": 0.0,
            "vega_effectiveness": 0.0,
            "convexity_score": 0.0,
            "average_gamma": 0.0,
            "average_vega": 0.0,
            "hedge_effectiveness": 0.0,
            "upside_capture": 0.0,
            "downside_protection": 0.0,
        }

        # Parameter optimization cache
        self._optimization_cache: Dict[str, Any] = {}
        self._parameter_history: List[ConvexHedgeParameters] = []

        # Initialize parameters
        self._current_parameters = ConvexHedgeParameters(
            function_type=function_type,
            curvature=self._config["curvature_initial"],
            convexity_ratio=self._config["convexity_ratio_initial"],
            threshold=self._config["threshold_initial"],
            power=self._config["power_initial"],
            lambda_param=self._config["lambda_initial"],
            kappa=self._config["kappa_initial"],
            max_convexity=self._config["max_convexity"],
            min_convexity=self._config["min_convexity"],
            tail_risk_aware=self._config["tail_risk_awareness"],
        )

        logger.info(
            "convex_hedge_strategy_initialized",
            name=name,
            hedge_style=hedge_style.value,
            function_type=function_type.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate convex hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with convex hedge signals
        """
        try:
            # Calculate convexity metrics
            await self._calculate_convexity_metrics(market_data)

            # Optimize parameters for current market conditions
            if self._config["adaptive_parameters"]:
                await self._optimize_parameters(market_data)

            # Calculate optimal convexity ratio
            convexity_ratio = await self._calculate_convexity_ratio(market_data)

            # Generate convex hedge signal
            signal = await self._generate_hedge_signal(convexity_ratio, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "convexity_metrics": self._convexity_metrics.to_dict(),
                "hedge_parameters": self._current_parameters.to_dict(),
                "convexity_ratio": convexity_ratio,
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "convex_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _calculate_convexity_metrics(self, market_data: Dict[str, Any]) -> None:
        """
        Calculate convexity metrics from market data.

        Args:
            market_data: Current market data
        """
        try:
            # Get price history
            prices = market_data.get("historical_prices", [])
            if len(prices) < 30:
                return

            returns = []
            for i in range(1, len(prices)):
                if prices[i-1] > 0:
                    ret = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(ret)

            if len(returns) < 30:
                return

            returns_array = np.array(returns)

            # Calculate gamma (implied from curvature)
            gamma = self._calculate_gamma(returns_array)

            # Calculate vega (volatility sensitivity)
            vega = self._calculate_vega(market_data)

            # Calculate theta (time decay)
            theta = self._calculate_theta(market_data)

            # Calculate skewness and kurtosis
            skewness = stats.skew(returns_array)
            kurtosis = stats.kurtosis(returns_array)

            # Calculate convexity score
            convexity_score = self._calculate_convexity_score(
                gamma, vega, skewness, kurtosis
            )

            # Determine convexity regime
            regime = self._determine_convexity_regime(convexity_score, gamma, vega)

            # Calculate volatility ratio
            implied_vol = market_data.get("implied_volatility", 0.2)
            realized_vol = market_data.get("realized_volatility", 0.2)
            vol_ratio = implied_vol / realized_vol if realized_vol > 0 else 1.0

            self._convexity_metrics = ConvexityMetrics(
                gamma=gamma,
                vega=vega,
                theta=theta,
                convexity_score=convexity_score,
                gamma_ratio=gamma / (gamma + 1.0) if gamma >= 0 else 0,
                vega_ratio=vega / (vega + 1.0) if vega >= 0 else 0,
                convexity_regime=regime,
                skewness=skewness,
                kurtosis=kurtosis,
                implied_volatility=implied_vol,
                realized_volatility=realized_vol,
                volatility_ratio=vol_ratio,
            )

            # Store history
            self._convexity_history.append(self._convexity_metrics)
            if len(self._convexity_history) > 100:
                self._convexity_history = self._convexity_history[-100:]

        except Exception as e:
            logger.error("convexity_metrics_calculation_failed", error=str(e))

    def _calculate_gamma(self, returns: np.ndarray) -> float:
        """Calculate gamma from return distribution."""
        # Gamma is the rate of change of delta with respect to price
        # Simplified: use curvature of cumulative return distribution
        sorted_returns = np.sort(returns)
        n = len(sorted_returns)

        # Calculate curvature using cubic fit
        x = np.linspace(-1, 1, n)
        z = np.polyfit(x, sorted_returns, 3)
        curvature = abs(z[0]) * 100  # Scale for interpretability

        return min(curvature, self._config["max_gamma"])

    def _calculate_vega(self, market_data: Dict[str, Any]) -> float:
        """Calculate vega (volatility sensitivity)."""
        implied_vol = market_data.get("implied_volatility", 0.2)
        realized_vol = market_data.get("realized_volatility", 0.2)

        if realized_vol > 0:
            vega = implied_vol / realized_vol - 1
        else:
            vega = 0

        return max(-1.0, min(1.0, vega))

    def _calculate_theta(self, market_data: Dict[str, Any]) -> float:
        """Calculate theta (time decay)."""
        # Simplified: use implied volatility term structure
        dt = 1.0 / 252  # One day
        iv = market_data.get("implied_volatility", 0.2)
        theta = -0.5 * iv ** 2 * dt

        return theta

    def _calculate_convexity_score(
        self,
        gamma: float,
        vega: float,
        skewness: float,
        kurtosis: float,
    ) -> float:
        """Calculate convexity score (0-1)."""
        score = 0.0

        # Gamma contribution
        if gamma > 5.0:
            score += 0.3
        elif gamma > 2.0:
            score += 0.2
        elif gamma > 0.5:
            score += 0.1

        # Vega contribution
        if abs(vega) > 0.3:
            score += 0.2
        elif abs(vega) > 0.1:
            score += 0.1

        # Skewness contribution
        if skewness < -0.5:
            score += 0.2
        elif skewness < -0.3:
            score += 0.1

        # Kurtosis contribution
        if kurtosis > 4.0:
            score += 0.3
        elif kurtosis > 3.5:
            score += 0.2

        return min(1.0, score)

    def _determine_convexity_regime(
        self,
        convexity_score: float,
        gamma: float,
        vega: float,
    ) -> ConvexityRegime:
        """Determine convexity regime."""
        if convexity_score > 0.8 and gamma > 5.0:
            return ConvexityRegime.EXTREME
        elif convexity_score > 0.6 and gamma > 2.0:
            return ConvexityRegime.HIGH
        elif convexity_score > 0.3:
            return ConvexityRegime.NORMAL
        elif convexity_score < 0.1 or gamma < 0.1:
            return ConvexityRegime.NEGATIVE
        else:
            return ConvexityRegime.LOW

    async def _optimize_parameters(self, market_data: Dict[str, Any]) -> None:
        """
        Optimize convex hedge parameters for current market conditions.

        Args:
            market_data: Current market data
        """
        try:
            convexity_score = self._convexity_metrics.convexity_score
            regime = self._convexity_metrics.convexity_regime

            # Adjust based on convexity regime
            if regime == ConvexityRegime.EXTREME:
                # High convexity opportunity
                self._current_parameters.curvature = min(
                    self._config["curvature_max"],
                    self._current_parameters.curvature * 1.3
                )
                self._current_parameters.convexity_ratio = min(
                    self._config["convexity_ratio_max"],
                    self._current_parameters.convexity_ratio * 1.2
                )
                self._current_parameters.gamma_adjustment = 1.5

            elif regime == ConvexityRegime.HIGH:
                # Good convexity opportunity
                self._current_parameters.curvature = min(
                    self._config["curvature_max"],
                    self._current_parameters.curvature * 1.1
                )
                self._current_parameters.convexity_ratio = min(
                    self._config["convexity_ratio_max"],
                    self._current_parameters.convexity_ratio * 1.1
                )
                self._current_parameters.gamma_adjustment = 1.2

            elif regime == ConvexityRegime.LOW:
                # Low convexity - reduce positioning
                self._current_parameters.curvature = max(
                    self._config["curvature_min"],
                    self._current_parameters.curvature * 0.8
                )
                self._current_parameters.convexity_ratio = max(
                    self._config["convexity_ratio_min"],
                    self._current_parameters.convexity_ratio * 0.8
                )
                self._current_parameters.gamma_adjustment = 0.7

            elif regime == ConvexityRegime.NEGATIVE:
                # Negative convexity - minimize
                self._current_parameters.curvature = self._config["curvature_min"]
                self._current_parameters.convexity_ratio = self._config["convexity_ratio_min"]
                self._current_parameters.gamma_adjustment = 0.5

            # Adjust for volatility
            vol_ratio = self._convexity_metrics.volatility_ratio
            if vol_ratio > 1.2:
                # Volatility premium - increase convexity
                self._current_parameters.vega_adjustment = 1.3
            elif vol_ratio < 0.8:
                # Volatility discount - decrease convexity
                self._current_parameters.vega_adjustment = 0.7

            # Adjust threshold based on volatility
            realized_vol = self._convexity_metrics.realized_volatility
            self._current_parameters.threshold = realized_vol * 0.3

            # Apply style-specific adjustments
            await self._apply_style_adjustments()

            # Clamp all parameters
            self._clamp_parameters()

            # Store parameter history
            self._parameter_history.append(self._current_parameters)
            if len(self._parameter_history) > 100:
                self._parameter_history = self._parameter_history[-100:]

        except Exception as e:
            logger.error("parameter_optimization_failed", error=str(e))

    async def _apply_style_adjustments(self) -> None:
        """Apply style-specific parameter adjustments."""
        style = self.hedge_style

        if style == ConvexHedgeStyle.AGGRESSIVE:
            self._current_parameters.convexity_ratio = min(
                0.95,
                self._current_parameters.convexity_ratio * 1.3
            )
            self._current_parameters.curvature = min(
                1.0,
                self._current_parameters.curvature * 1.2
            )
            self._current_parameters.gamma_adjustment = 1.5

        elif style == ConvexHedgeStyle.CONSERVATIVE:
            self._current_parameters.convexity_ratio = max(
                0.3,
                self._current_parameters.convexity_ratio * 0.7
            )
            self._current_parameters.curvature = max(
                0.3,
                self._current_parameters.curvature * 0.7
            )
            self._current_parameters.gamma_adjustment = 0.6

        elif style == ConvexHedgeStyle.TAIL_CAPTURE:
            self._current_parameters.threshold = min(
                0.05,
                self._current_parameters.threshold * 0.5
            )
            self._current_parameters.power = max(
                3.0,
                self._current_parameters.power * 1.2
            )

    def _clamp_parameters(self) -> None:
        """Clamp parameters to configured bounds."""
        self._current_parameters.curvature = max(
            self._config["curvature_min"],
            min(self._config["curvature_max"], self._current_parameters.curvature)
        )
        self._current_parameters.convexity_ratio = max(
            self._config["convexity_ratio_min"],
            min(self._config["convexity_ratio_max"], self._current_parameters.convexity_ratio)
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
        self._current_parameters.max_convexity = max(
            0.5,
            min(0.99, self._current_parameters.max_convexity)
        )
        self._current_parameters.min_convexity = max(
            0.01,
            min(0.5, self._current_parameters.min_convexity)
        )
        self._current_parameters.gamma_adjustment = max(
            0.5,
            min(2.0, self._current_parameters.gamma_adjustment)
        )
        self._current_parameters.vega_adjustment = max(
            0.5,
            min(2.0, self._current_parameters.vega_adjustment)
        )

    async def _calculate_convexity_ratio(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate optimal convexity ratio.

        Args:
            market_data: Current market data

        Returns:
            Convexity ratio (0-1)
        """
        convexity_score = self._convexity_metrics.convexity_score
        regime = self._convexity_metrics.convexity_regime

        # Base ratio from convexity score
        base_ratio = convexity_score

        # Apply convex function transformation
        convex_ratio = self._apply_convex_function(base_ratio)

        # Apply gamma and vega adjustments
        ratio = convex_ratio * self._current_parameters.gamma_adjustment
        ratio *= self._current_parameters.vega_adjustment

        # Apply style-specific scaling
        if self.hedge_style == ConvexHedgeStyle.AGGRESSIVE:
            ratio = min(ratio * 1.3, 0.95)
        elif self.hedge_style == ConvexHedgeStyle.CONSERVATIVE:
            ratio = max(ratio * 0.7, 0.1)

        # Clamp
        ratio = max(
            self._current_parameters.min_convexity,
            min(self._current_parameters.max_convexity, ratio)
        )

        return ratio

    def _apply_convex_function(self, x: float) -> float:
        """
        Apply convex function to input value.

        Args:
            x: Input value (0-1)

        Returns:
            Convex transformed value (0-1)
        """
        params = self._current_parameters
        x = max(0, min(1, x))

        if params.function_type == ConvexFunctionType.EXPONENTIAL:
            # Exponential: f(x) = (e^(lambda*x) - 1) / (e^lambda - 1)
            lam = params.lambda_param
            return (np.exp(lam * x) - 1) / (np.exp(lam) - 1)

        elif params.function_type == ConvexFunctionType.POWER:
            # Power law: f(x) = x^p
            return x ** params.power

        elif params.function_type == ConvexFunctionType.HYPERBOLIC:
            # Hyperbolic: f(x) = tanh(k*x) / tanh(k)
            k = params.kappa
            return np.tanh(k * x) / np.tanh(k)

        elif params.function_type == ConvexFunctionType.LOGISTIC:
            # Logistic: f(x) = 1 / (1 + exp(-k*(x - threshold)))
            k = params.kappa
            threshold = params.threshold
            return 1 / (1 + np.exp(-k * (x - threshold)))

        elif params.function_type == ConvexFunctionType.SIGMOID:
            # Sigmoid: f(x) = 1 / (1 + exp(-x))
            return 1 / (1 + np.exp(-x))

        elif params.function_type == ConvexFunctionType.PIECEWISE:
            # Piecewise linear with increasing slope
            if x < params.threshold:
                return x * params.curvature
            else:
                return params.threshold * params.curvature + (
                    x - params.threshold
                ) * (1 + params.curvature)

        else:
            # Default: exponential
            lam = params.lambda_param
            return (np.exp(lam * x) - 1) / (np.exp(lam) - 1)

    async def _generate_hedge_signal(
        self,
        convexity_ratio: float,
        market_data: Dict[str, Any],
    ) -> Optional[HedgeSignal]:
        """
        Generate convex hedge signal.

        Args:
            convexity_ratio: Calculated convexity ratio
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        if convexity_ratio < self._config["min_convexity"]:
            return None

        current_price = market_data.get("price", 0)
        if current_price <= 0:
            return None

        # Determine direction
        direction = HedgeDirection.LONG  # Convexity capture

        # Calculate position size
        size = convexity_ratio * self._config["max_position_size"]

        # Calculate confidence
        confidence = self._calculate_hedge_confidence()

        if confidence < self.config.min_confidence:
            return None

        # Calculate gamma-adjusted stop loss and take profit
        gamma = self._convexity_metrics.gamma
        if gamma > 0:
            stop_loss_pct = self._config["stop_loss_pct"] / (1 + gamma * 0.5)
            take_profit_pct = self._config["take_profit_pct"] * (1 + gamma * 0.3)
        else:
            stop_loss_pct = self._config["stop_loss_pct"]
            take_profit_pct = self._config["take_profit_pct"]

        stop_loss = self._calculate_stop_loss(
            current_price,
            direction,
            stop_loss_pct
        )
        take_profit = self._calculate_take_profit(
            current_price,
            direction,
            take_profit_pct
        )

        return HedgeSignal(
            hedge_type=HedgeType.CONVEX,
            direction=direction,
            size=size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Convex hedge: ratio={convexity_ratio:.2f}, regime={self._convexity_metrics.convexity_regime.value}",
            metadata={
                "convexity_ratio": convexity_ratio,
                "gamma": self._convexity_metrics.gamma,
                "vega": self._convexity_metrics.vega,
                "convexity_score": self._convexity_metrics.convexity_score,
                "regime": self._convexity_metrics.convexity_regime.value,
                "function_type": self._current_parameters.function_type.value,
                "curvature": self._current_parameters.curvature,
            }
        )

    def _calculate_hedge_confidence(self) -> float:
        """Calculate confidence in the hedge signal."""
        confidence = 0.5

        # Convexity score contribution
        score = self._convexity_metrics.convexity_score
        confidence += score * 0.3

        # Regime confidence
        regime = self._convexity_metrics.convexity_regime
        if regime in (ConvexityRegime.HIGH, ConvexityRegime.EXTREME):
            confidence += 0.2
        elif regime == ConvexityRegime.NORMAL:
            confidence += 0.1

        # Parameter confidence
        if len(self._parameter_history) > 5:
            recent = self._parameter_history[-5:]
            curvature_std = np.std([p.curvature for p in recent])
            if curvature_std < 0.1:
                confidence += 0.1

        # Volatility ratio confidence
        vol_ratio = self._convexity_metrics.volatility_ratio
        if 0.8 < vol_ratio < 1.2:
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

                    # Update gamma and convexity
                    returns = (position.current_price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0
                    position.gamma = self._calculate_gamma_for_position(returns)
                    position.convexity_ratio = self._apply_convex_function(
                        max(0, 1 + returns)
                    )

    def _calculate_gamma_for_position(self, returns: float) -> float:
        """Calculate gamma for a position."""
        # Simplified gamma calculation based on returns
        if returns > 0:
            return 1 / (1 + returns) ** 2
        else:
            return 1 / (1 - returns) ** 2

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._hedge_positions:
                avg_gamma = sum(p.gamma for p in self._hedge_positions) / len(self._hedge_positions)
                avg_vega = sum(p.vega for p in self._hedge_positions) / len(self._hedge_positions)
                avg_convexity = sum(p.convexity_ratio for p in self._hedge_positions) / len(self._hedge_positions)

                self._performance["average_gamma"] = avg_gamma
                self._performance["average_vega"] = avg_vega
                self._performance["convexity_score"] = avg_convexity

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
                "average_gamma": self._performance["average_gamma"],
                "average_vega": self._performance["average_vega"],
                "convexity_score": self._performance["convexity_score"],
                "gamma_effectiveness": self._performance["gamma_effectiveness"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "convexity_regime": self._convexity_metrics.convexity_regime.value,
                "current_parameters": self._current_parameters.to_dict(),
                "config": self._config,
            }

    def get_convexity_metrics(self) -> Dict[str, Any]:
        """Get current convexity metrics."""
        return self._convexity_metrics.to_dict()

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("convex_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("convex_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("convex_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "ConvexHedgeStrategy",
    "ConvexHedgeParameters",
    "ConvexHedgePosition",
    "ConvexHedgeStyle",
    "ConvexFunctionType",
    "ConvexityRegime",
    "ConvexityMetrics",
]

logger.info("convex_hedge_module_loaded", version="3.0.0")
