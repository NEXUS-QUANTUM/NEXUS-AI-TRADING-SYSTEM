# trading/bots/hedge_bot/strategies/defensive_hedge.py

"""
NEXUS HEDGE BOT - DEFENSIVE HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced defensive hedging strategy focused on capital preservation,
downside protection, and risk mitigation during adverse market conditions
with dynamic adjustment of hedge ratios based on market stress indicators.

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
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class DefenseLevel(str, Enum):
    """Defensive hedge levels."""
    LIGHT = "light"                          # Light defensive positioning
    MODERATE = "moderate"                    # Moderate defensive positioning
    HEAVY = "heavy"                          # Heavy defensive positioning
    MAXIMUM = "maximum"                      # Maximum defensive positioning
    LIQUIDATE = "liquidate"                  # Liquidation mode


class MarketStressLevel(str, Enum):
    """Market stress levels."""
    NORMAL = "normal"                        # Normal market conditions
    ELEVATED = "elevated"                    # Elevated stress
    HIGH = "high"                            # High stress
    EXTREME = "extreme"                      # Extreme stress
    CRISIS = "crisis"                        # Crisis conditions


class DefensiveHedgeType(str, Enum):
    """Types of defensive hedges."""
    PUT_SPREAD = "put_spread"                # Put spread hedge
    COLLAR = "collar"                        # Collar hedge
    PROTECTIVE_PUT = "protective_put"        # Protective put
    COVERED_CALL = "covered_call"            # Covered call
    CASH_HEDGE = "cash_hedge"                # Cash hedge
    SHORT_HEDGE = "short_hedge"              # Short hedge
    PAIR_HEDGE = "pair_hedge"                # Pair hedge
    VOLATILITY_HEDGE = "volatility_hedge"    # Volatility hedge
    TAIL_HEDGE = "tail_hedge"                # Tail risk hedge


# === DATA MODELS ===

@dataclass
class MarketStressIndicators:
    """Market stress indicators."""
    vix_level: float = 20.0                  # VIX level
    vix_percentile: float = 0.5              # VIX percentile
    credit_spread: float = 0.02              # Credit spread
    volatility_ratio: float = 1.0            # Volatility ratio
    skewness: float = 0.0                    # Market skewness
    kurtosis: float = 3.0                    # Market kurtosis
    max_drawdown: float = 0.0                # Max drawdown
    current_drawdown: float = 0.0            # Current drawdown
    put_call_ratio: float = 0.7              # Put/Call ratio
    fear_greed_index: float = 50.0           # Fear & Greed Index
    stress_level: MarketStressLevel = MarketStressLevel.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "stress_level": self.stress_level.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketStressIndicators":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["stress_level"] = MarketStressLevel(data["stress_level"])
        return cls(**data)


@dataclass
class DefensiveHedgeParameters:
    """Parameters for defensive hedging."""
    defense_level: DefenseLevel = DefenseLevel.MODERATE
    hedge_ratio: float = 0.5                 # Base hedge ratio
    max_hedge_ratio: float = 0.95            # Maximum hedge ratio
    min_hedge_ratio: float = 0.05            # Minimum hedge ratio
    stop_loss_pct: float = 0.03              # Tighter stop loss
    take_profit_pct: float = 0.06            # Lower take profit
    trailing_stop_pct: float = 0.02          # Tighter trailing stop
    position_size_reduction: float = 0.0     # Position size reduction
    volatility_multiplier: float = 1.0       # Volatility multiplier
    drawdown_threshold: float = 0.05         # Drawdown threshold
    stress_threshold: float = 0.7            # Stress threshold
    recovery_mode: bool = False              # Recovery mode active
    cash_reserve_pct: float = 0.10           # Cash reserve percentage
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "defense_level": self.defense_level.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DefensiveHedgeParameters":
        data = data.copy()
        data["defense_level"] = DefenseLevel(data["defense_level"])
        return cls(**data)


@dataclass
class DefensiveHedgePosition:
    """Defensive hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    hedge_type: DefensiveHedgeType = DefensiveHedgeType.PROTECTIVE_PUT
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    hedge_ratio: float = 0.0
    protection_level: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    defense_level: DefenseLevel = DefenseLevel.MODERATE
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "hedge_type": self.hedge_type.value,
            "defense_level": self.defense_level.value,
        }


# === DEFENSIVE HEDGE STRATEGY ===

class DefensiveHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced defensive hedging strategy focused on capital preservation
    and downside protection during adverse market conditions.
    """

    def __init__(
        self,
        name: str = "defensive_hedge",
        default_defense_level: DefenseLevel = DefenseLevel.MODERATE,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the defensive hedge strategy.

        Args:
            name: Strategy name
            default_defense_level: Default defense level
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.default_defense_level = default_defense_level
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Hedge positions
        self._hedge_positions: List[DefensiveHedgePosition] = []
        self._position_history: List[DefensiveHedgePosition] = []

        # Stress indicators
        self._stress_indicators = MarketStressIndicators()
        self._stress_history: List[MarketStressIndicators] = []

        # Parameters
        self._parameters = DefensiveHedgeParameters(defense_level=default_defense_level)
        self._parameter_history: List[DefensiveHedgeParameters] = []

        # Configuration
        self._config = {
            "max_hedge_ratio": 0.95,
            "min_hedge_ratio": 0.05,
            "stress_lookback_days": 30,
            "drawdown_lookback_days": 60,
            "volatility_lookback_days": 30,
            "stress_threshold_normal": 0.3,
            "stress_threshold_elevated": 0.5,
            "stress_threshold_high": 0.7,
            "stress_threshold_extreme": 0.85,
            "drawdown_threshold": 0.05,
            "recovery_threshold": 0.02,
            "max_position_size": 0.15,
            "min_position_size": 0.005,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
            "trailing_stop_pct": 0.02,
            "cash_reserve_min": 0.05,
            "cash_reserve_max": 0.30,
            "auto_recovery": True,
            "gradual_adjustment": True,
            "adjustment_step": 0.05,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "drawdown_avoided": 0.0,
            "capital_protection": 0.0,
            "current_defense_level": self.default_defense_level.value,
            "current_stress_level": MarketStressLevel.NORMAL.value,
            "recovery_mode": False,
            "cash_reserve": 0.0,
        }

        # Recovery tracking
        self._recovery_mode = False
        self._recovery_start_time: Optional[datetime] = None
        self._drawdown_peak: float = 0.0
        self._current_drawdown: float = 0.0

        logger.info(
            "defensive_hedge_strategy_initialized",
            name=name,
            default_defense_level=default_defense_level.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate defensive hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with defensive hedge signals
        """
        try:
            # Update market stress indicators
            await self._update_stress_indicators(market_data)

            # Determine defense level
            defense_level = await self._determine_defense_level(market_data)

            # Update hedge parameters
            await self._update_parameters(defense_level, market_data)

            # Generate defensive hedge signal
            signal = await self._generate_hedge_signal(market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Check for recovery
            if self._config["auto_recovery"]:
                await self._check_recovery(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "stress_indicators": self._stress_indicators.to_dict(),
                "defense_level": defense_level.value,
                "parameters": self._parameters.to_dict(),
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "recovery_mode": self._recovery_mode,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "defensive_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _update_stress_indicators(self, market_data: Dict[str, Any]) -> None:
        """
        Update market stress indicators.

        Args:
            market_data: Current market data
        """
        try:
            # Get VIX
            vix = market_data.get("vix", 20.0)
            vix_percentile = self._calculate_percentile(vix, "vix")

            # Get volatility
            volatility = market_data.get("volatility", 0.2)
            vol_ratio = market_data.get("volatility_ratio", 1.0)

            # Get drawdown
            returns = market_data.get("returns", [])
            if returns:
                cumulative = np.cumprod(1 + np.array(returns))
                peak = np.maximum.accumulate(cumulative)
                drawdown = (peak - cumulative) / peak
                max_drawdown = np.max(drawdown)
                current_drawdown = drawdown[-1] if len(drawdown) > 0 else 0
            else:
                max_drawdown = 0.0
                current_drawdown = 0.0

            # Get skewness and kurtosis
            if returns:
                skewness = stats.skew(returns)
                kurtosis = stats.kurtosis(returns)
            else:
                skewness = 0.0
                kurtosis = 3.0

            # Get put/call ratio and fear/greed index
            put_call_ratio = market_data.get("put_call_ratio", 0.7)
            fear_greed_index = market_data.get("fear_greed_index", 50.0)

            # Determine stress level
            stress_score = self._calculate_stress_score(
                vix=vix,
                volatility=volatility,
                drawdown=current_drawdown,
                put_call_ratio=put_call_ratio,
                fear_greed_index=fear_greed_index,
            )

            stress_level = self._determine_stress_level(stress_score)

            self._stress_indicators = MarketStressIndicators(
                vix_level=vix,
                vix_percentile=vix_percentile,
                credit_spread=market_data.get("credit_spread", 0.02),
                volatility_ratio=vol_ratio,
                skewness=skewness,
                kurtosis=kurtosis,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                put_call_ratio=put_call_ratio,
                fear_greed_index=fear_greed_index,
                stress_level=stress_level,
            )

            # Store history
            self._stress_history.append(self._stress_indicators)
            if len(self._stress_history) > 100:
                self._stress_history = self._stress_history[-100:]

            # Update drawdown tracking
            self._current_drawdown = current_drawdown
            if current_drawdown > self._drawdown_peak:
                self._drawdown_peak = current_drawdown

        except Exception as e:
            logger.error("stress_indicators_update_failed", error=str(e))

    def _calculate_percentile(self, value: float, indicator: str) -> float:
        """Calculate percentile of a value."""
        # Simplified - in production, use historical distribution
        if indicator == "vix":
            # VIX typically ranges from 10 to 40
            if value < 15:
                return 0.1
            elif value < 20:
                return 0.3
            elif value < 25:
                return 0.5
            elif value < 30:
                return 0.7
            else:
                return 0.9
        return 0.5

    def _calculate_stress_score(
        self,
        vix: float,
        volatility: float,
        drawdown: float,
        put_call_ratio: float,
        fear_greed_index: float,
    ) -> float:
        """Calculate stress score (0-1)."""
        score = 0.0

        # VIX contribution
        if vix > 30:
            score += 0.3
        elif vix > 25:
            score += 0.2
        elif vix > 20:
            score += 0.1

        # Volatility contribution
        if volatility > 0.3:
            score += 0.2
        elif volatility > 0.25:
            score += 0.1

        # Drawdown contribution
        if drawdown > 0.10:
            score += 0.3
        elif drawdown > 0.05:
            score += 0.2
        elif drawdown > 0.03:
            score += 0.1

        # Put/Call ratio contribution
        if put_call_ratio > 1.0:
            score += 0.1

        # Fear & Greed contribution
        if fear_greed_index < 20:
            score += 0.1

        return min(1.0, score)

    def _determine_stress_level(self, stress_score: float) -> MarketStressLevel:
        """Determine stress level from stress score."""
        thresholds = self._config
        if stress_score >= thresholds["stress_threshold_extreme"]:
            return MarketStressLevel.EXTREME
        elif stress_score >= thresholds["stress_threshold_high"]:
            return MarketStressLevel.HIGH
        elif stress_score >= thresholds["stress_threshold_elevated"]:
            return MarketStressLevel.ELEVATED
        else:
            return MarketStressLevel.NORMAL

    async def _determine_defense_level(self, market_data: Dict[str, Any]) -> DefenseLevel:
        """
        Determine defense level based on stress indicators.

        Args:
            market_data: Current market data

        Returns:
            DefenseLevel
        """
        stress_level = self._stress_indicators.stress_level
        drawdown = self._current_drawdown

        # Base defense level
        if stress_level == MarketStressLevel.CRISIS or drawdown > 0.15:
            return DefenseLevel.LIQUIDATE
        elif stress_level == MarketStressLevel.EXTREME or drawdown > 0.10:
            return DefenseLevel.MAXIMUM
        elif stress_level == MarketStressLevel.HIGH or drawdown > 0.07:
            return DefenseLevel.HEAVY
        elif stress_level == MarketStressLevel.ELEVATED or drawdown > 0.04:
            return DefenseLevel.MODERATE
        else:
            return DefenseLevel.LIGHT

    async def _update_parameters(
        self,
        defense_level: DefenseLevel,
        market_data: Dict[str, Any]
    ) -> None:
        """
        Update hedge parameters based on defense level.

        Args:
            defense_level: Current defense level
            market_data: Current market data
        """
        with self._lock:
            params = DefensiveHedgeParameters(defense_level=defense_level)

            if defense_level == DefenseLevel.LIGHT:
                params.hedge_ratio = 0.25
                params.max_hedge_ratio = 0.40
                params.stop_loss_pct = 0.05
                params.take_profit_pct = 0.10
                params.position_size_reduction = 0.0
                params.cash_reserve_pct = 0.05

            elif defense_level == DefenseLevel.MODERATE:
                params.hedge_ratio = 0.50
                params.max_hedge_ratio = 0.65
                params.stop_loss_pct = 0.04
                params.take_profit_pct = 0.08
                params.position_size_reduction = 0.20
                params.cash_reserve_pct = 0.10

            elif defense_level == DefenseLevel.HEAVY:
                params.hedge_ratio = 0.75
                params.max_hedge_ratio = 0.85
                params.stop_loss_pct = 0.03
                params.take_profit_pct = 0.06
                params.position_size_reduction = 0.40
                params.cash_reserve_pct = 0.20

            elif defense_level == DefenseLevel.MAXIMUM:
                params.hedge_ratio = 0.90
                params.max_hedge_ratio = 0.95
                params.stop_loss_pct = 0.02
                params.take_profit_pct = 0.04
                params.position_size_reduction = 0.60
                params.cash_reserve_pct = 0.30

            elif defense_level == DefenseLevel.LIQUIDATE:
                params.hedge_ratio = 0.95
                params.max_hedge_ratio = 0.98
                params.stop_loss_pct = 0.01
                params.take_profit_pct = 0.02
                params.position_size_reduction = 0.80
                params.cash_reserve_pct = 0.40
                params.recovery_mode = True

            # Adjust for volatility
            volatility = market_data.get("volatility", 0.2)
            if volatility > 0.3:
                params.volatility_multiplier = 1.5
                params.hedge_ratio *= 1.2
            elif volatility > 0.25:
                params.volatility_multiplier = 1.25

            # Adjust for drawdown
            if self._current_drawdown > self._config["drawdown_threshold"]:
                params.drawdown_threshold = self._current_drawdown
                params.hedge_ratio *= (1 + self._current_drawdown)

            # Clamp values
            params.hedge_ratio = max(
                self._config["min_hedge_ratio"],
                min(self._config["max_hedge_ratio"], params.hedge_ratio)
            )
            params.cash_reserve_pct = max(
                self._config["cash_reserve_min"],
                min(self._config["cash_reserve_max"], params.cash_reserve_pct)
            )
            params.position_size_reduction = max(0, min(0.90, params.position_size_reduction))

            # Apply gradual adjustment
            if self._config["gradual_adjustment"] and self._parameters.defense_level != defense_level:
                step = self._config["adjustment_step"]
                current_ratio = self._parameters.hedge_ratio
                target_ratio = params.hedge_ratio
                if abs(target_ratio - current_ratio) > step:
                    params.hedge_ratio = current_ratio + np.sign(target_ratio - current_ratio) * step

            self._parameters = params

            # Store history
            self._parameter_history.append(params)
            if len(self._parameter_history) > 100:
                self._parameter_history = self._parameter_history[-100:]

    async def _generate_hedge_signal(self, market_data: Dict[str, Any]) -> Optional[HedgeSignal]:
        """
        Generate defensive hedge signal.

        Args:
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        hedge_ratio = self._parameters.hedge_ratio

        if hedge_ratio < self._config["min_hedge_ratio"]:
            return None

        current_price = market_data.get("price", 0)
        if current_price <= 0:
            return None

        # Determine hedge type
        hedge_type = self._determine_defensive_hedge_type()

        # Calculate position size
        base_size = self._config["max_position_size"]
        size = base_size * hedge_ratio
        size *= (1 - self._parameters.position_size_reduction)

        # Calculate confidence
        confidence = self._calculate_defensive_confidence()

        if confidence < self.config.min_confidence:
            return None

        # Calculate stop loss and take profit
        stop_loss = self._calculate_defensive_stop(current_price)
        take_profit = self._calculate_defensive_target(current_price)

        return HedgeSignal(
            hedge_type=HedgeType.DEFENSIVE,
            direction=HedgeDirection.SHORT,
            size=size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Defensive hedge: level={self._parameters.defense_level.value}, stress={self._stress_indicators.stress_level.value}",
            metadata={
                "defense_level": self._parameters.defense_level.value,
                "stress_level": self._stress_indicators.stress_level.value,
                "hedge_ratio": hedge_ratio,
                "hedge_type": hedge_type.value,
                "position_size_reduction": self._parameters.position_size_reduction,
                "cash_reserve_pct": self._parameters.cash_reserve_pct,
            }
        )

    def _determine_defensive_hedge_type(self) -> DefensiveHedgeType:
        """Determine defensive hedge type based on conditions."""
        stress_level = self._stress_indicators.stress_level

        if stress_level == MarketStressLevel.CRISIS:
            return DefensiveHedgeType.TAIL_HEDGE
        elif stress_level == MarketStressLevel.EXTREME:
            return DefensiveHedgeType.PROTECTIVE_PUT
        elif stress_level == MarketStressLevel.HIGH:
            return DefensiveHedgeType.PUT_SPREAD
        elif stress_level == MarketStressLevel.ELEVATED:
            return DefensiveHedgeType.COLLAR
        else:
            return DefensiveHedgeType.SHORT_HEDGE

    def _calculate_defensive_confidence(self) -> float:
        """Calculate confidence in the defensive hedge."""
        confidence = 0.5

        # Stress level contribution
        stress_level = self._stress_indicators.stress_level
        if stress_level == MarketStressLevel.EXTREME:
            confidence += 0.3
        elif stress_level == MarketStressLevel.HIGH:
            confidence += 0.2
        elif stress_level == MarketStressLevel.ELEVATED:
            confidence += 0.1

        # Drawdown contribution
        if self._current_drawdown > 0.10:
            confidence += 0.2
        elif self._current_drawdown > 0.05:
            confidence += 0.1

        # VIX contribution
        if self._stress_indicators.vix_level > 30:
            confidence += 0.1

        return min(0.95, confidence)

    def _calculate_defensive_stop(self, price: float) -> Optional[float]:
        """Calculate defensive stop loss."""
        stop_pct = self._parameters.stop_loss_pct
        return price * (1 - stop_pct)

    def _calculate_defensive_target(self, price: float) -> Optional[float]:
        """Calculate defensive take profit."""
        target_pct = self._parameters.take_profit_pct
        return price * (1 + target_pct)

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

    async def _check_recovery(self, market_data: Dict[str, Any]) -> None:
        """Check if recovery mode should be activated or deactivated."""
        stress_level = self._stress_indicators.stress_level
        drawdown = self._current_drawdown

        if self._recovery_mode:
            # Check if we can exit recovery
            if stress_level in (MarketStressLevel.NORMAL, MarketStressLevel.ELEVATED) and drawdown < self._config["recovery_threshold"]:
                self._recovery_mode = False
                self._recovery_start_time = None
                logger.info("defensive_recovery_deactivated")
        else:
            # Check if we need to enter recovery
            if stress_level in (MarketStressLevel.EXTREME, MarketStressLevel.CRISIS) or drawdown > 0.10:
                self._recovery_mode = True
                self._recovery_start_time = datetime.utcnow()
                logger.info("defensive_recovery_activated")

        self._parameters.recovery_mode = self._recovery_mode

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)
            self._performance["total_pnl"] = sum(p.pnl for p in self._hedge_positions)
            self._performance["current_defense_level"] = self._parameters.defense_level.value
            self._performance["current_stress_level"] = self._stress_indicators.stress_level.value
            self._performance["recovery_mode"] = self._recovery_mode
            self._performance["cash_reserve"] = self._parameters.cash_reserve_pct

            if self._current_drawdown > 0:
                self._performance["drawdown_avoided"] = self._drawdown_peak - self._current_drawdown

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "defense_level": self._parameters.defense_level.value,
                "stress_level": self._stress_indicators.stress_level.value,
                "hedge_ratio": self._parameters.hedge_ratio,
                "position_size_reduction": self._parameters.position_size_reduction,
                "cash_reserve_pct": self._parameters.cash_reserve_pct,
                "recovery_mode": self._recovery_mode,
                "current_drawdown": self._current_drawdown,
                "drawdown_peak": self._drawdown_peak,
                "drawdown_avoided": self._performance["drawdown_avoided"],
                "config": self._config,
            }

    def get_stress_indicators(self) -> Dict[str, Any]:
        """Get current stress indicators."""
        return self._stress_indicators.to_dict()

    def get_defense_parameters(self) -> Dict[str, Any]:
        """Get current defense parameters."""
        return self._parameters.to_dict()

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def get_drawdown_analysis(self) -> Dict[str, Any]:
        """Get drawdown analysis."""
        return {
            "current_drawdown": self._current_drawdown,
            "peak_drawdown": self._drawdown_peak,
            "drawdown_avoided": self._performance.get("drawdown_avoided", 0.0),
            "recovery_mode": self._recovery_mode,
            "recovery_start": self._recovery_start_time.isoformat() if self._recovery_start_time else None,
            "stress_level": self._stress_indicators.stress_level.value,
        }

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("defensive_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("defensive_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("defensive_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "DefensiveHedgeStrategy",
    "DefenseLevel",
    "MarketStressLevel",
    "DefensiveHedgeType",
    "MarketStressIndicators",
    "DefensiveHedgeParameters",
    "DefensiveHedgePosition",
]

logger.info("defensive_hedge_module_loaded", version="3.0.0")
