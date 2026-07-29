# trading/bots/hedge_bot/strategies/beta_hedge.py

"""
NEXUS HEDGE BOT - BETA HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced beta hedging strategy that dynamically adjusts portfolio beta
exposure using regression analysis, volatility forecasting, and
adaptive rebalancing.

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
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class BetaCalculationMethod(str, Enum):
    """Methods for calculating beta."""
    OLS = "ols"                      # Ordinary Least Squares
    ROBUST = "robust"                # Robust regression
    BAYESIAN = "bayesian"            # Bayesian regression
    ROLLING = "rolling"              # Rolling window regression
    EXPONENTIAL = "exponential"      # Exponentially weighted
    RIDGE = "ridge"                  # Ridge regression
    LASSO = "lasso"                  # Lasso regression
    DYNAMIC = "dynamic"              # Dynamic conditional beta


class BetaHedgeType(str, Enum):
    """Types of beta hedging."""
    FULL = "full"                    # Full beta hedge (beta = 0)
    TARGET = "target"                # Target beta hedge
    NEUTRAL = "neutral"              # Market neutral (beta = 0)
    DYNAMIC = "dynamic"              # Dynamic beta targeting
    VOLATILITY_ADJUSTED = "vol_adjusted"  # Volatility-adjusted beta


class BetaRegime(str, Enum):
    """Beta regimes."""
    LOW_BETA = "low_beta"           # Beta < 0.5
    NORMAL_BETA = "normal_beta"     # 0.5 < Beta < 1.5
    HIGH_BETA = "high_beta"         # Beta > 1.5
    NEGATIVE_BETA = "negative_beta" # Beta < 0
    UNSTABLE = "unstable"           # Beta instability detected


# === DATA MODELS ===

@dataclass
class BetaEstimate:
    """Beta estimate with confidence intervals."""
    beta: float = 0.0
    alpha: float = 0.0
    r_squared: float = 0.0
    std_error: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    p_value: float = 0.0
    t_statistic: float = 0.0
    n_observations: int = 0
    method: BetaCalculationMethod = BetaCalculationMethod.OLS
    regime: BetaRegime = BetaRegime.NORMAL_BETA
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "method": self.method.value,
            "regime": self.regime.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BetaEstimate":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["method"] = BetaCalculationMethod(data["method"])
        data["regime"] = BetaRegime(data["regime"])
        return cls(**data)


@dataclass
class BetaHedgePosition:
    """Beta hedge position."""
    symbol: str = ""
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    beta: float = 0.0
    hedged_beta: float = 0.0
    target_beta: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
        }


# === BETA HEDGE STRATEGY ===

class BetaHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced beta hedging strategy that dynamically adjusts portfolio beta
    exposure using regression analysis and adaptive rebalancing.
    """

    def __init__(
        self,
        name: str = "beta_hedge",
        hedge_type: BetaHedgeType = BetaHedgeType.DYNAMIC,
        calculation_method: BetaCalculationMethod = BetaCalculationMethod.ROLLING,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the beta hedge strategy.

        Args:
            name: Strategy name
            hedge_type: Type of beta hedging
            calculation_method: Method for beta calculation
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.hedge_type = hedge_type
        self.calculation_method = calculation_method
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Beta cache
        self._beta_cache: Dict[str, BetaEstimate] = {}
        self._beta_history: Dict[str, List[BetaEstimate]] = {}
        self._hedge_positions: List[BetaHedgePosition] = []

        # Market data cache
        self._price_history: Dict[str, List[float]] = {}
        self._benchmark_history: List[float] = []
        self._returns_history: Dict[str, List[float]] = {}

        # Configuration
        self._config = {
            "lookback_days": 60,
            "min_observations": 30,
            "rolling_window": 30,
            "target_beta": 0.0,
            "beta_tolerance": 0.1,
            "rebalance_threshold": 0.05,
            "max_position_size": 0.20,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "confidence_threshold": 0.70,
            "max_beta": 2.5,
            "min_beta": -2.5,
            "volatility_adjustment": True,
            "regime_detection": True,
            "adaptive_rebalancing": True,
            "hedge_benchmark": "SPX",  # Default benchmark
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "avg_hedge_duration": 0.0,
            "beta_exposure_reduction": 0.0,
            "tracking_error": 0.0,
            "hedge_effectiveness": 0.0,
        }

        # Regression models
        self._regression_models: Dict[str, Any] = {}
        self._scaler = StandardScaler()

        # Initialize benchmark
        self._benchmark_symbol = self._config["hedge_benchmark"]

        logger.info(
            "beta_hedge_strategy_initialized",
            name=name,
            hedge_type=hedge_type.value,
            calculation_method=calculation_method.value,
            benchmark=self._benchmark_symbol,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate beta hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with beta hedge signals
        """
        try:
            # Update price history
            await self._update_price_history(market_data)

            # Calculate beta for portfolio
            portfolio_beta = await self._calculate_portfolio_beta(market_data)

            # Determine beta regime
            beta_regime = await self._determine_beta_regime(portfolio_beta)

            # Generate hedge signal
            signal = await self._generate_beta_signal(portfolio_beta, beta_regime, market_data)

            # Update positions
            await self._update_hedge_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "portfolio_beta": portfolio_beta.to_dict() if portfolio_beta else None,
                "beta_regime": beta_regime.value if beta_regime else None,
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "beta_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _update_price_history(self, market_data: Dict[str, Any]) -> None:
        """Update price history for all symbols."""
        with self._lock:
            symbols = market_data.get("symbols", [])

            for symbol in symbols:
                price = market_data.get("prices", {}).get(symbol, 0)
                if price > 0:
                    if symbol not in self._price_history:
                        self._price_history[symbol] = []
                    self._price_history[symbol].append(price)

                    # Keep history limited
                    max_history = self._config["lookback_days"] * 24  # Assuming hourly data
                    if len(self._price_history[symbol]) > max_history:
                        self._price_history[symbol] = self._price_history[symbol][-max_history:]

            # Update benchmark price
            benchmark_price = market_data.get("prices", {}).get(self._benchmark_symbol, 0)
            if benchmark_price > 0:
                self._benchmark_history.append(benchmark_price)
                if len(self._benchmark_history) > self._config["lookback_days"] * 24:
                    self._benchmark_history = self._benchmark_history[-self._config["lookback_days"] * 24:]

    async def _calculate_portfolio_beta(self, market_data: Dict[str, Any]) -> Optional[BetaEstimate]:
        """
        Calculate portfolio beta using the specified method.

        Args:
            market_data: Current market data

        Returns:
            BetaEstimate or None if calculation fails
        """
        try:
            symbols = market_data.get("symbols", [])

            if not symbols or not self._price_history:
                return None

            # Calculate portfolio returns
            portfolio_returns = []
            benchmark_returns = []

            # Get prices for each symbol
            symbol_prices = {}
            for symbol in symbols:
                if symbol in self._price_history and len(self._price_history[symbol]) > 10:
                    symbol_prices[symbol] = self._price_history[symbol]

            if not symbol_prices:
                return None

            # Calculate weighted portfolio returns
            weights = {s: 1.0 / len(symbol_prices) for s in symbol_prices.keys()}

            min_len = min(len(prices) for prices in symbol_prices.values())
            min_len = min(min_len, len(self._benchmark_history))

            if min_len < self._config["min_observations"]:
                return None

            # Align data
            for i in range(1, min_len):
                portfolio_return = 0
                for symbol, prices in symbol_prices.items():
                    if len(prices) > i:
                        ret = (prices[-i] - prices[-i-1]) / prices[-i-1] if prices[-i-1] > 0 else 0
                        portfolio_return += weights.get(symbol, 0) * ret
                portfolio_returns.append(portfolio_return)

                if len(self._benchmark_history) > i:
                    bench_ret = (self._benchmark_history[-i] - self._benchmark_history[-i-1]) / self._benchmark_history[-i-1] if self._benchmark_history[-i-1] > 0 else 0
                    benchmark_returns.append(bench_ret)

            if len(portfolio_returns) < self._config["min_observations"]:
                return None

            # Calculate beta using selected method
            beta_estimate = await self._calculate_beta(
                portfolio_returns,
                benchmark_returns,
                method=self.calculation_method,
            )

            return beta_estimate

        except Exception as e:
            logger.error("portfolio_beta_calculation_failed", error=str(e))
            return None

    async def _calculate_beta(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float],
        method: BetaCalculationMethod = BetaCalculationMethod.OLS,
    ) -> BetaEstimate:
        """
        Calculate beta using the specified method.

        Args:
            portfolio_returns: List of portfolio returns
            benchmark_returns: List of benchmark returns
            method: Beta calculation method

        Returns:
            BetaEstimate
        """
        x = np.array(benchmark_returns).reshape(-1, 1)
        y = np.array(portfolio_returns)

        if len(x) < self._config["min_observations"]:
            raise ValueError("Insufficient data for beta calculation")

        beta = 0.0
        alpha = 0.0
        r_squared = 0.0
        std_error = 0.0
        p_value = 0.0
        t_statistic = 0.0

        if method == BetaCalculationMethod.OLS:
            # Ordinary Least Squares
            model = LinearRegression()
            model.fit(x, y)
            beta = model.coef_[0]
            alpha = model.intercept_

            # Calculate statistics
            y_pred = model.predict(x)
            residuals = y - y_pred
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Standard error
            n = len(y)
            se_beta = np.sqrt(ss_res / (n - 2)) / np.sqrt(np.sum((x - np.mean(x)) ** 2))
            std_error = se_beta

            # t-statistic and p-value
            t_statistic = beta / se_beta if se_beta > 0 else 0
            p_value = 2 * (1 - stats.t.cdf(abs(t_statistic), n - 2))

        elif method == BetaCalculationMethod.ROBUST:
            # Robust regression using Huber loss
            from sklearn.linear_model import HuberRegressor
            model = HuberRegressor()
            model.fit(x, y.flatten())
            beta = model.coef_[0]
            alpha = model.intercept_

        elif method == BetaCalculationMethod.RIDGE:
            # Ridge regression
            model = Ridge(alpha=1.0)
            model.fit(x, y)
            beta = model.coef_[0]
            alpha = model.intercept_

        elif method == BetaCalculationMethod.LASSO:
            # Lasso regression
            model = Lasso(alpha=0.01)
            model.fit(x, y)
            beta = model.coef_[0]
            alpha = model.intercept_

        elif method == BetaCalculationMethod.EXPONENTIAL:
            # Exponentially weighted beta
            weights = np.exp(np.linspace(-1, 0, len(x)))
            weights = weights / weights.sum()

            x_mean = np.average(x, weights=weights)
            y_mean = np.average(y, weights=weights)

            covariance = np.average((x - x_mean) * (y - y_mean), weights=weights)
            variance = np.average((x - x_mean) ** 2, weights=weights)

            beta = covariance / variance if variance > 0 else 0
            alpha = y_mean - beta * x_mean

        elif method == BetaCalculationMethod.DYNAMIC:
            # Dynamic conditional beta
            # Simple implementation: use Kalman filter approximation
            beta_series = []
            window = 20
            for i in range(window, len(x)):
                x_window = x[i-window:i]
                y_window = y[i-window:i]
                model = LinearRegression()
                model.fit(x_window, y_window)
                beta_series.append(model.coef_[0])

            beta = np.mean(beta_series) if beta_series else 0

        # Determine beta regime
        regime = self._determine_regime_from_value(beta)

        # Calculate confidence interval
        confidence_lower = beta - 1.96 * std_error if std_error > 0 else beta - 0.1
        confidence_upper = beta + 1.96 * std_error if std_error > 0 else beta + 0.1

        return BetaEstimate(
            beta=float(beta),
            alpha=float(alpha),
            r_squared=float(r_squared),
            std_error=float(std_error),
            confidence_lower=float(confidence_lower),
            confidence_upper=float(confidence_upper),
            p_value=float(p_value),
            t_statistic=float(t_statistic),
            n_observations=len(x),
            method=method,
            regime=regime,
        )

    def _determine_regime_from_value(self, beta: float) -> BetaRegime:
        """Determine beta regime from beta value."""
        if beta < -0.5:
            return BetaRegime.NEGATIVE_BETA
        elif beta < 0.5:
            return BetaRegime.LOW_BETA
        elif beta <= 1.5:
            return BetaRegime.NORMAL_BETA
        else:
            return BetaRegime.HIGH_BETA

    async def _determine_beta_regime(self, beta_estimate: Optional[BetaEstimate]) -> BetaRegime:
        """
        Determine current beta regime.

        Args:
            beta_estimate: Current beta estimate

        Returns:
            BetaRegime
        """
        if not beta_estimate:
            return BetaRegime.UNSTABLE

        regime = beta_estimate.regime

        # Check for instability
        if beta_estimate.r_squared < 0.3:
            return BetaRegime.UNSTABLE

        # Check confidence interval width
        if (beta_estimate.confidence_upper - beta_estimate.confidence_lower) > 0.5:
            return BetaRegime.UNSTABLE

        return regime

    async def _generate_beta_signal(
        self,
        portfolio_beta: Optional[BetaEstimate],
        beta_regime: BetaRegime,
        market_data: Dict[str, Any],
    ) -> Optional[HedgeSignal]:
        """
        Generate beta hedge signal based on current beta.

        Args:
            portfolio_beta: Portfolio beta estimate
            beta_regime: Current beta regime
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        if not portfolio_beta or beta_regime == BetaRegime.UNSTABLE:
            return None

        current_beta = portfolio_beta.beta
        target_beta = self._get_target_beta(beta_regime, market_data)

        # Calculate required hedge
        beta_diff = current_beta - target_beta
        if abs(beta_diff) < self._config["beta_tolerance"]:
            return None

        # Determine hedge direction
        if beta_diff > 0:
            direction = HedgeDirection.SHORT  # Need to reduce beta
        else:
            direction = HedgeDirection.LONG   # Need to increase beta

        # Calculate hedge size
        hedge_size = abs(beta_diff) * self._config["max_position_size"]
        hedge_size = min(hedge_size, self._config["max_position_size"])

        # Apply volatility adjustment
        if self._config["volatility_adjustment"]:
            vol_ratio = await self._calculate_volatility_ratio(market_data)
            hedge_size *= vol_ratio

        # Calculate confidence
        confidence = self._calculate_beta_confidence(portfolio_beta, beta_regime)

        if confidence < self._config["confidence_threshold"]:
            return None

        # Calculate stop loss and take profit
        current_price = market_data.get("prices", {}).get(self._benchmark_symbol, 0)
        stop_loss = self._calculate_stop_loss(current_price, direction, self._config["stop_loss_pct"])
        take_profit = self._calculate_take_profit(current_price, direction, self._config["take_profit_pct"])

        return HedgeSignal(
            hedge_type=HedgeType.BETA,
            direction=direction,
            size=hedge_size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Beta hedge: {current_beta:.2f} -> {target_beta:.2f} ({beta_regime.value})",
            metadata={
                "current_beta": current_beta,
                "target_beta": target_beta,
                "beta_diff": beta_diff,
                "regime": beta_regime.value,
                "method": self.calculation_method.value,
                "r_squared": portfolio_beta.r_squared,
            }
        )

    def _get_target_beta(self, beta_regime: BetaRegime, market_data: Dict[str, Any]) -> float:
        """Get target beta based on regime and strategy type."""
        if self.hedge_type == BetaHedgeType.FULL:
            return 0.0
        elif self.hedge_type == BetaHedgeType.NEUTRAL:
            return 0.0
        elif self.hedge_type == BetaHedgeType.TARGET:
            return self._config["target_beta"]
        elif self.hedge_type == BetaHedgeType.DYNAMIC:
            # Dynamic target based on market conditions
            vix = market_data.get("vix", 20.0)
            if vix > 30:
                return 0.2  # Reduce beta in high volatility
            elif vix < 15:
                return 0.8  # Increase beta in low volatility
            else:
                return 0.5
        elif self.hedge_type == BetaHedgeType.VOLATILITY_ADJUSTED:
            # Volatility-adjusted target
            vol = market_data.get("volatility", 0.2)
            target = 0.5 / (1 + vol)  # Inverse volatility weighting
            return max(0, min(1, target))
        else:
            return self._config["target_beta"]

    async def _calculate_volatility_ratio(self, market_data: Dict[str, Any]) -> float:
        """Calculate volatility ratio for adjustment."""
        current_vol = market_data.get("volatility", 0.2)
        long_term_vol = market_data.get("long_term_volatility", 0.2)

        if long_term_vol <= 0:
            return 1.0

        ratio = current_vol / long_term_vol
        return min(2.0, max(0.5, ratio))

    def _calculate_beta_confidence(
        self,
        beta_estimate: BetaEstimate,
        beta_regime: BetaRegime,
    ) -> float:
        """Calculate confidence in the beta hedge signal."""
        confidence = 0.5

        # R-squared contribution
        confidence += beta_estimate.r_squared * 0.3

        # Standard error contribution
        if beta_estimate.std_error < 0.1:
            confidence += 0.2
        elif beta_estimate.std_error < 0.2:
            confidence += 0.1

        # Regime confidence
        if beta_regime == BetaRegime.NORMAL_BETA:
            confidence += 0.1
        elif beta_regime in (BetaRegime.LOW_BETA, BetaRegime.HIGH_BETA):
            confidence += 0.05

        # P-value contribution
        if beta_estimate.p_value < 0.05:
            confidence += 0.1
        elif beta_estimate.p_value < 0.1:
            confidence += 0.05

        # Clamp
        return max(0.1, min(0.95, confidence))

    async def _update_hedge_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                # Update price
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._hedge_positions:
                avg_duration = sum(
                    (p.last_update - p.open_time).total_seconds()
                    for p in self._hedge_positions
                ) / len(self._hedge_positions)
                self._performance["avg_hedge_duration"] = avg_duration / 3600  # Hours

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "avg_hedge_duration_hours": self._performance["avg_hedge_duration"],
                "beta_exposure_reduction": self._performance["beta_exposure_reduction"],
                "tracking_error": self._performance["tracking_error"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "config": self._config,
                "beta_cache_size": len(self._beta_cache),
            }

    def get_beta_estimate(self, symbol: str) -> Optional[BetaEstimate]:
        """Get beta estimate for a symbol."""
        with self._lock:
            return self._beta_cache.get(symbol)

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("beta_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("beta_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("beta_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "BetaHedgeStrategy",
    "BetaEstimate",
    "BetaHedgePosition",
    "BetaCalculationMethod",
    "BetaHedgeType",
    "BetaRegime",
]

logger.info("beta_hedge_module_loaded", version="3.0.0")
