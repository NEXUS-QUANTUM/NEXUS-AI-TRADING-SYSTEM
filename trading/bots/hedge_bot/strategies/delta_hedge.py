# trading/bots/hedge_bot/strategies/delta_hedge.py

"""
NEXUS HEDGE BOT - DELTA HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced delta hedging strategy that dynamically manages delta exposure
using Black-Scholes derived deltas, adaptive rebalancing, and
volatility-adjusted position sizing.

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
from scipy.stats import norm
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class DeltaHedgeType(str, Enum):
    """Types of delta hedging."""
    DELTA_NEUTRAL = "delta_neutral"          # Maintain delta-neutral position
    DELTA_TARGET = "delta_target"            # Target specific delta
    DYNAMIC = "dynamic"                      # Dynamic delta hedging
    VOLATILITY_ADJUSTED = "vol_adjusted"     # Volatility-adjusted delta
    GAMMA_AWARE = "gamma_aware"              # Gamma-aware delta hedging
    OPTIMAL = "optimal"                      # Optimal delta hedge


class DeltaRebalanceTrigger(str, Enum):
    """Triggers for delta rebalancing."""
    TIME = "time"                            # Time-based rebalancing
    THRESHOLD = "threshold"                  # Threshold-based rebalancing
    VOLATILITY = "volatility"                # Volatility-based rebalancing
    SIGNAL = "signal"                        # Signal-based rebalancing
    HYBRID = "hybrid"                        # Hybrid rebalancing


# === DATA MODELS ===

@dataclass
class DeltaHedgeParameters:
    """Parameters for delta hedging."""
    hedge_type: DeltaHedgeType = DeltaHedgeType.DELTA_NEUTRAL
    target_delta: float = 0.0                # Target delta value
    rebalance_threshold: float = 0.05        # Delta threshold for rebalancing
    max_delta_exposure: float = 0.20         # Maximum delta exposure
    min_delta_exposure: float = 0.01         # Minimum delta exposure
    gamma_scaling: float = 1.0               # Gamma scaling factor
    vega_adjustment: float = 1.0             # Vega adjustment factor
    volatility_scaling: float = 1.0          # Volatility scaling factor
    time_decay_factor: float = 1.0           # Time decay factor
    max_position_size: float = 0.10          # Maximum position size
    min_position_size: float = 0.01          # Minimum position size
    stop_loss_pct: float = 0.05              # Stop loss percentage
    take_profit_pct: float = 0.10            # Take profit percentage
    trailing_stop_pct: float = 0.03          # Trailing stop percentage
    confidence_threshold: float = 0.60       # Minimum confidence threshold
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "hedge_type": self.hedge_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeltaHedgeParameters":
        data = data.copy()
        data["hedge_type"] = DeltaHedgeType(data["hedge_type"])
        return cls(**data)


@dataclass
class DeltaPosition:
    """Delta hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    target_delta: float = 0.0
    current_delta: float = 0.0
    hedge_ratio: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    last_rebalance: datetime = field(default_factory=datetime.utcnow)
    rebalance_count: int = 0
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "last_rebalance": self.last_rebalance.isoformat(),
        }


# === DELTA HEDGE STRATEGY ===

class DeltaHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced delta hedging strategy that dynamically manages delta exposure
    using Black-Scholes derived deltas and adaptive rebalancing.
    """

    def __init__(
        self,
        name: str = "delta_hedge",
        hedge_type: DeltaHedgeType = DeltaHedgeType.DYNAMIC,
        rebalance_trigger: DeltaRebalanceTrigger = DeltaRebalanceTrigger.HYBRID,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the delta hedge strategy.

        Args:
            name: Strategy name
            hedge_type: Type of delta hedging
            rebalance_trigger: Trigger for rebalancing
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.hedge_type = hedge_type
        self.rebalance_trigger = rebalance_trigger
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Delta positions
        self._positions: List[DeltaPosition] = []
        self._position_history: List[DeltaPosition] = []

        # Parameters
        self._parameters = DeltaHedgeParameters(hedge_type=hedge_type)
        self._parameter_history: List[DeltaHedgeParameters] = []

        # Configuration
        self._config = {
            "max_delta": 0.95,
            "min_delta": 0.05,
            "rebalance_threshold": 0.05,
            "rebalance_interval_minutes": 15,
            "volatility_lookback_days": 30,
            "gamma_aware": True,
            "vega_adjustment": True,
            "time_decay": True,
            "max_position_size": 0.15,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "confidence_threshold": 0.60,
            "risk_free_rate": 0.02,
            "dividend_yield": 0.01,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "average_delta": 0.0,
            "average_gamma": 0.0,
            "hedge_effectiveness": 0.0,
            "rebalance_count": 0,
            "tracking_error": 0.0,
        }

        # Greeks cache
        self._greeks_cache: Dict[str, Dict[str, float]] = {}

        logger.info(
            "delta_hedge_strategy_initialized",
            name=name,
            hedge_type=hedge_type.value,
            rebalance_trigger=rebalance_trigger.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate delta hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with delta hedge signals
        """
        try:
            # Calculate delta for portfolio
            portfolio_delta = await self._calculate_portfolio_delta(market_data)

            # Determine if rebalancing is needed
            should_rebalance = await self._check_rebalance_needed(portfolio_delta, market_data)

            # Generate delta hedge signal
            signal = await self._generate_hedge_signal(portfolio_delta, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "portfolio_delta": portfolio_delta,
                "should_rebalance": should_rebalance,
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._positions],
                "performance": self._performance,
                "parameters": self._parameters.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "delta_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _calculate_portfolio_delta(self, market_data: Dict[str, Any]) -> float:
        """
        Calculate portfolio delta.

        Args:
            market_data: Current market data

        Returns:
            Portfolio delta
        """
        total_delta = 0.0
        total_value = 0.0

        # Get positions from portfolio manager
        if self.portfolio_manager:
            positions = self.portfolio_manager.get_positions()
            for position in positions:
                symbol = position.get("symbol")
                size = position.get("size", 0)
                price = position.get("current_price", 0)

                if size == 0 or price == 0:
                    continue

                # Calculate delta for this position
                delta = await self._calculate_delta(symbol, market_data)
                position_delta = size * delta * price
                total_delta += position_delta
                total_value += size * price

        if total_value == 0:
            return 0.0

        return total_delta / total_value

    async def _calculate_delta(self, symbol: str, market_data: Dict[str, Any]) -> float:
        """
        Calculate delta for a symbol.

        Args:
            symbol: Symbol to calculate delta for
            market_data: Current market data

        Returns:
            Delta value
        """
        # Check cache
        if symbol in self._greeks_cache:
            return self._greeks_cache[symbol].get("delta", 0.5)

        try:
            # Get option data
            option_data = market_data.get("options", {}).get(symbol, {})
            if option_data:
                # Use Black-Scholes delta
                price = option_data.get("price", 0)
                strike = option_data.get("strike", price)
                time_to_expiry = option_data.get("time_to_expiry", 30) / 365
                volatility = option_data.get("implied_volatility", 0.3)
                risk_free = self._config["risk_free_rate"]
                dividend = self._config["dividend_yield"]
                option_type = option_data.get("type", "call")

                d1 = (np.log(price / strike) + (risk_free - dividend + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))

                if option_type == "call":
                    delta = norm.cdf(d1)
                else:
                    delta = -norm.cdf(-d1)

                # Store in cache
                self._greeks_cache[symbol] = {
                    "delta": delta,
                    "gamma": norm.pdf(d1) / (price * volatility * np.sqrt(time_to_expiry)),
                    "vega": price * norm.pdf(d1) * np.sqrt(time_to_expiry),
                    "theta": -(price * norm.pdf(d1) * volatility) / (2 * np.sqrt(time_to_expiry)) - risk_free * strike * np.exp(-risk_free * time_to_expiry) * norm.cdf(d1),
                }

                return delta

        except Exception as e:
            logger.error("delta_calculation_failed", symbol=symbol, error=str(e))

        # Fallback: use historical beta as delta proxy
        beta = market_data.get("beta", {}).get(symbol, 1.0)
        return min(0.95, max(0.05, beta * 0.5))

    async def _check_rebalance_needed(
        self,
        portfolio_delta: float,
        market_data: Dict[str, Any]
    ) -> bool:
        """
        Check if rebalancing is needed.

        Args:
            portfolio_delta: Current portfolio delta
            market_data: Current market data

        Returns:
            True if rebalancing is needed
        """
        if not self._positions:
            return True

        target_delta = self._get_target_delta(market_data)

        if self.rebalance_trigger == DeltaRebalanceTrigger.TIME:
            # Time-based rebalancing
            last_rebalance = max(p.last_rebalance for p in self._positions)
            minutes_since = (datetime.utcnow() - last_rebalance).total_seconds() / 60
            return minutes_since >= self._config["rebalance_interval_minutes"]

        elif self.rebalance_trigger == DeltaRebalanceTrigger.THRESHOLD:
            # Threshold-based rebalancing
            delta_diff = abs(portfolio_delta - target_delta)
            return delta_diff >= self._config["rebalance_threshold"]

        elif self.rebalance_trigger == DeltaRebalanceTrigger.VOLATILITY:
            # Volatility-based rebalancing
            current_vol = market_data.get("volatility", 0.2)
            return current_vol > 0.3

        elif self.rebalance_trigger == DeltaRebalanceTrigger.HYBRID:
            # Hybrid rebalancing
            delta_diff = abs(portfolio_delta - target_delta)
            minutes_since = (datetime.utcnow() - max(p.last_rebalance for p in self._positions)).total_seconds() / 60
            return delta_diff >= self._config["rebalance_threshold"] * 0.7 or minutes_since >= self._config["rebalance_interval_minutes"] * 1.5

        return False

    def _get_target_delta(self, market_data: Dict[str, Any]) -> float:
        """Get target delta based on hedge type."""
        if self.hedge_type == DeltaHedgeType.DELTA_NEUTRAL:
            return 0.0
        elif self.hedge_type == DeltaHedgeType.DELTA_TARGET:
            return self._parameters.target_delta
        elif self.hedge_type == DeltaHedgeType.DYNAMIC:
            # Dynamic target based on market conditions
            vix = market_data.get("vix", 20.0)
            if vix > 30:
                return 0.2  # Reduce delta in high volatility
            elif vix < 15:
                return 0.5  # Increase delta in low volatility
            else:
                return 0.35
        elif self.hedge_type == DeltaHedgeType.VOLATILITY_ADJUSTED:
            vol = market_data.get("volatility", 0.2)
            return 0.5 / (1 + vol * 2)
        elif self.hedge_type == DeltaHedgeType.OPTIMAL:
            # Optimal delta based on risk-reward
            return self._calculate_optimal_delta(market_data)
        else:
            return 0.0

    def _calculate_optimal_delta(self, market_data: Dict[str, Any]) -> float:
        """Calculate optimal delta based on risk-reward."""
        # Simplified optimal delta calculation
        vol = market_data.get("volatility", 0.2)
        trend = market_data.get("trend", 0.0)
        risk_free = self._config["risk_free_rate"]

        # Kelly criterion-like calculation
        expected_return = trend * 0.5  # Simplified
        if vol > 0:
            optimal = (expected_return - risk_free) / (vol ** 2)
            return max(0, min(0.95, optimal))
        return 0.5

    async def _generate_hedge_signal(
        self,
        portfolio_delta: float,
        market_data: Dict[str, Any]
    ) -> Optional[HedgeSignal]:
        """
        Generate delta hedge signal.

        Args:
            portfolio_delta: Current portfolio delta
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        target_delta = self._get_target_delta(market_data)
        delta_diff = target_delta - portfolio_delta

        if abs(delta_diff) < self._config["rebalance_threshold"]:
            return None

        current_price = market_data.get("price", 0)
        if current_price <= 0:
            return None

        # Calculate required hedge size
        portfolio_value = market_data.get("portfolio_value", 1000000)
        hedge_size = abs(delta_diff) * portfolio_value / current_price
        hedge_size = max(self._config["min_position_size"], min(self._config["max_position_size"], hedge_size))

        # Determine direction
        if delta_diff > 0:
            direction = HedgeDirection.LONG
        else:
            direction = HedgeDirection.SHORT

        # Calculate confidence
        confidence = self._calculate_hedge_confidence(portfolio_delta, target_delta, market_data)

        if confidence < self._config["confidence_threshold"]:
            return None

        # Calculate stop loss and take profit
        stop_loss = self._calculate_delta_stop(current_price, direction)
        take_profit = self._calculate_delta_target(current_price, direction)

        return HedgeSignal(
            hedge_type=HedgeType.DELTA,
            direction=direction,
            size=hedge_size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Delta hedge: {portfolio_delta:.2f} -> {target_delta:.2f}",
            metadata={
                "portfolio_delta": portfolio_delta,
                "target_delta": target_delta,
                "delta_diff": delta_diff,
                "hedge_type": self.hedge_type.value,
                "rebalance_trigger": self.rebalance_trigger.value,
                "gamma": self._calculate_gamma(market_data),
                "vega": self._calculate_vega(market_data),
            }
        )

    def _calculate_hedge_confidence(
        self,
        portfolio_delta: float,
        target_delta: float,
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence in the delta hedge signal."""
        confidence = 0.5

        # Delta difference contribution
        delta_diff = abs(portfolio_delta - target_delta)
        if delta_diff > 0.15:
            confidence += 0.2
        elif delta_diff > 0.10:
            confidence += 0.1

        # Volatility contribution
        vol = market_data.get("volatility", 0.2)
        if vol < 0.25:
            confidence += 0.1

        # Gamma contribution
        gamma = self._calculate_gamma(market_data)
        if gamma < 1.0:
            confidence += 0.1

        # Trend contribution
        trend = market_data.get("trend", 0.0)
        if abs(trend) > 0.02:
            confidence += 0.1

        return min(0.95, confidence)

    def _calculate_gamma(self, market_data: Dict[str, Any]) -> float:
        """Calculate gamma exposure."""
        # Simplified gamma calculation
        vol = market_data.get("volatility", 0.2)
        if vol > 0:
            return 1.0 / (vol * np.sqrt(252))
        return 0.0

    def _calculate_vega(self, market_data: Dict[str, Any]) -> float:
        """Calculate vega exposure."""
        # Simplified vega calculation
        return market_data.get("vega", 0.0)

    def _calculate_delta_stop(self, price: float, direction: HedgeDirection) -> Optional[float]:
        """Calculate stop loss for delta hedge."""
        stop_pct = self._config["stop_loss_pct"]
        if direction == HedgeDirection.LONG:
            return price * (1 - stop_pct)
        else:
            return price * (1 + stop_pct)

    def _calculate_delta_target(self, price: float, direction: HedgeDirection) -> Optional[float]:
        """Calculate take profit for delta hedge."""
        target_pct = self._config["take_profit_pct"]
        if direction == HedgeDirection.LONG:
            return price * (1 + target_pct)
        else:
            return price * (1 - target_pct)

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._positions:
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

                    # Update delta
                    position.current_delta = position.delta * (position.current_price / position.entry_price)

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._positions)

            total_pnl = sum(p.pnl for p in self._positions)
            self._performance["total_pnl"] = total_pnl

            if self._positions:
                avg_delta = sum(p.current_delta for p in self._positions) / len(self._positions)
                self._performance["average_delta"] = avg_delta

                avg_gamma = sum(p.gamma for p in self._positions) / len(self._positions)
                self._performance["average_gamma"] = avg_gamma

                # Calculate hedge effectiveness
                if total_pnl != 0:
                    portfolio_pnl = self._performance.get("portfolio_pnl", 0)
                    if portfolio_pnl != 0:
                        self._performance["hedge_effectiveness"] = abs(total_pnl / portfolio_pnl)

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "average_delta": self._performance["average_delta"],
                "average_gamma": self._performance["average_gamma"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "rebalance_count": self._performance["rebalance_count"],
                "tracking_error": self._performance["tracking_error"],
                "current_parameters": self._parameters.to_dict(),
                "config": self._config,
            }

    def get_delta_exposure(self) -> Dict[str, Any]:
        """Get delta exposure analysis."""
        with self._lock:
            total_delta = sum(p.current_delta * p.size for p in self._positions)
            total_value = sum(p.current_price * p.size for p in self._positions)

            return {
                "total_delta": total_delta,
                "total_value": total_value,
                "delta_ratio": total_delta / total_value if total_value > 0 else 0,
                "positions": [p.to_dict() for p in self._positions],
            }

    def get_greeks_analysis(self) -> Dict[str, Any]:
        """Get Greeks analysis."""
        with self._lock:
            total_gamma = sum(p.gamma * p.size for p in self._positions)
            total_vega = sum(p.vega * p.size for p in self._positions)
            total_theta = sum(p.theta * p.size for p in self._positions)

            return {
                "total_gamma": total_gamma,
                "total_vega": total_vega,
                "total_theta": total_theta,
                "positions": [p.to_dict() for p in self._positions],
            }

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("delta_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("delta_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("delta_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "DeltaHedgeStrategy",
    "DeltaHedgeParameters",
    "DeltaPosition",
    "DeltaHedgeType",
    "DeltaRebalanceTrigger",
]

logger.info("delta_hedge_module_loaded", version="3.0.0")
