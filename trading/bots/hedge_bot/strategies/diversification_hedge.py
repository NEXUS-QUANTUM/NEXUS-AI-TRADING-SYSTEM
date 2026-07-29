# trading/bots/hedge_bot/strategies/diversification_hedge.py

"""
NEXUS HEDGE BOT - DIVERSIFICATION HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced diversification-based hedging strategy that optimizes portfolio
diversification, reduces concentration risk, and manages correlation
exposure across multiple assets and sectors.

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
from sklearn.decomposition import PCA
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

class DiversificationMetric(str, Enum):
    """Metrics for measuring diversification."""
    HERFINDAHL = "herfindahl"                  # Herfindahl-Hirschman Index
    SHANNON = "shannon"                        # Shannon entropy
    SIMPSON = "simpson"                        # Simpson index
    EFFECTIVE_N = "effective_n"                # Effective number of bets
    CONCENTRATION = "concentration"            # Concentration ratio
    DIVERSIFICATION_RATIO = "diversification_ratio"  # Diversification ratio
    RISK_CONTRIBUTION = "risk_contribution"    # Risk contribution
    CORRELATION_AVG = "correlation_avg"        # Average correlation


class DiversificationType(str, Enum):
    """Types of diversification hedging."""
    ASSET = "asset"                            # Asset class diversification
    SECTOR = "sector"                          # Sector diversification
    GEOGRAPHIC = "geographic"                  # Geographic diversification
    FACTOR = "factor"                          # Factor diversification
    STRATEGY = "strategy"                      # Strategy diversification
    TEMPORAL = "temporal"                      # Temporal diversification
    CROSS_ASSET = "cross_asset"                # Cross-asset diversification
    RISK_PARITY = "risk_parity"                # Risk parity diversification


class DiversificationRegime(str, Enum):
    """Diversification regimes."""
    UNDER_DIVERSIFIED = "under_diversified"    # Insufficient diversification
    ADEQUATE = "adequate"                      # Adequate diversification
    WELL_DIVERSIFIED = "well_diversified"      # Well diversified
    OVER_DIVERSIFIED = "over_diversified"      # Over-diversified
    CONCENTRATED = "concentrated"              # Highly concentrated
    CRISIS = "crisis"                          # Crisis regime (correlations high)


# === DATA MODELS ===

@dataclass
class DiversificationMetrics:
    """Diversification metrics for portfolio."""
    herfindahl_index: float = 0.0
    shannon_entropy: float = 0.0
    simpson_index: float = 0.0
    effective_number: float = 0.0
    concentration_ratio: float = 0.0
    diversification_ratio: float = 0.0
    risk_contribution: Dict[str, float] = field(default_factory=dict)
    average_correlation: float = 0.0
    max_correlation: float = 0.0
    min_correlation: float = 0.0
    regime: DiversificationRegime = DiversificationRegime.ADEQUATE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiversificationMetrics":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["regime"] = DiversificationRegime(data["regime"])
        return cls(**data)


@dataclass
class DiversificationHedgePosition:
    """Diversification hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    weight: float = 0.0
    target_weight: float = 0.0
    risk_contribution: float = 0.0
    correlation: float = 0.0
    marginal_risk: float = 0.0
    diversification_score: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
        }


# === DIVERSIFICATION HEDGE STRATEGY ===

class DiversificationHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced diversification-based hedging strategy that optimizes portfolio
    diversification and manages correlation exposure.
    """

    def __init__(
        self,
        name: str = "diversification_hedge",
        diversification_type: DiversificationType = DiversificationType.ASSET,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the diversification hedge strategy.

        Args:
            name: Strategy name
            diversification_type: Type of diversification
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.diversification_type = diversification_type
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Hedge positions
        self._hedge_positions: List[DiversificationHedgePosition] = []
        self._position_history: List[DiversificationHedgePosition] = []

        # Diversification metrics
        self._diversification_metrics = DiversificationMetrics()
        self._metrics_history: List[DiversificationMetrics] = []

        # Configuration
        self._config = {
            "target_herfindahl": 0.15,
            "target_effective_n": 10,
            "max_concentration_ratio": 0.40,
            "min_diversification_ratio": 1.5,
            "max_correlation": 0.70,
            "target_risk_contribution": 0.10,
            "diversification_threshold": 0.30,
            "rebalance_threshold": 0.05,
            "max_position_size": 0.12,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "confidence_threshold": 0.60,
            "max_assets": 20,
            "min_assets": 4,
            "lookback_days": 60,
            "risk_parity_optimization": True,
            "factor_diversification": True,
            "dynamic_rebalancing": True,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "diversification_improvement": 0.0,
            "concentration_reduction": 0.0,
            "risk_reduction": 0.0,
            "herfindahl_index": 0.0,
            "effective_number": 0.0,
            "hedge_effectiveness": 0.0,
        }

        # Factor exposures
        self._factor_exposures: Dict[str, float] = {}
        self._factor_history: List[Dict[str, float]] = []

        # Asset classifications
        self._asset_classes: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "diversification_hedge_strategy_initialized",
            name=name,
            diversification_type=diversification_type.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate diversification hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with diversification hedge signals
        """
        try:
            # Calculate diversification metrics
            await self._calculate_diversification_metrics(market_data)

            # Identify diversification opportunities
            opportunities = await self._identify_opportunities(market_data)

            # Generate hedge signals
            signals = await self._generate_hedge_signals(opportunities, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "diversification_metrics": self._diversification_metrics.to_dict(),
                "opportunities": [o.to_dict() for o in opportunities],
                "signals": [s.to_dict() for s in signals],
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "diversification_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _calculate_diversification_metrics(self, market_data: Dict[str, Any]) -> None:
        """
        Calculate diversification metrics for the portfolio.

        Args:
            market_data: Current market data
        """
        try:
            # Get portfolio positions
            positions = self._get_portfolio_positions(market_data)

            if len(positions) < 2:
                return

            # Calculate weights
            total_value = sum(p["value"] for p in positions)
            weights = [p["value"] / total_value for p in positions] if total_value > 0 else []

            if not weights:
                return

            # Calculate Herfindahl-Hirschman Index
            herfindahl = sum(w ** 2 for w in weights)
            herfindahl_index = herfindahl

            # Calculate Shannon entropy
            entropy = -sum(w * np.log(w) for w in weights if w > 0)
            shannon_entropy = entropy

            # Calculate Simpson index
            simpson = sum(w ** 2 for w in weights)
            simpson_index = simpson

            # Calculate effective number of bets
            effective_number = 1 / herfindahl if herfindahl > 0 else 0

            # Calculate concentration ratio (top N)
            sorted_weights = sorted(weights, reverse=True)
            concentration_ratio = sum(sorted_weights[:5])  # Top 5

            # Calculate risk contributions
            risk_contributions = await self._calculate_risk_contributions(positions, market_data)

            # Calculate average correlation
            avg_correlation = await self._calculate_avg_correlation(positions, market_data)

            # Calculate diversification ratio
            weighted_vol = sum(w * v for w, v in zip(weights, [p.get("volatility", 0.2) for p in positions]))
            portfolio_vol = np.sqrt(sum(
                weights[i] * weights[j] * corr * vols[i] * vols[j]
                for i in range(len(weights))
                for j in range(len(weights))
                for corr, vols in [(1, 1)]  # Simplified
            ))
            diversification_ratio = weighted_vol / portfolio_vol if portfolio_vol > 0 else 1.0

            # Determine regime
            regime = self._determine_regime(
                herfindahl_index,
                effective_number,
                concentration_ratio,
                avg_correlation
            )

            self._diversification_metrics = DiversificationMetrics(
                herfindahl_index=herfindahl_index,
                shannon_entropy=shannon_entropy,
                simpson_index=simpson_index,
                effective_number=effective_number,
                concentration_ratio=concentration_ratio,
                diversification_ratio=diversification_ratio,
                risk_contribution=risk_contributions,
                average_correlation=avg_correlation,
                max_correlation=max(avg_correlation, 0.5),
                min_correlation=min(avg_correlation, -0.5),
                regime=regime,
            )

            # Store history
            self._metrics_history.append(self._diversification_metrics)
            if len(self._metrics_history) > 100:
                self._metrics_history = self._metrics_history[-100:]

        except Exception as e:
            logger.error("diversification_metrics_calculation_failed", error=str(e))

    def _get_portfolio_positions(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get portfolio positions from market data."""
        positions = []

        if self.portfolio_manager:
            portfolio_positions = self.portfolio_manager.get_positions()
            for pos in portfolio_positions:
                positions.append({
                    "symbol": pos.get("symbol"),
                    "value": pos.get("value", 0),
                    "weight": pos.get("weight", 0),
                    "volatility": pos.get("volatility", 0.2),
                    "sector": pos.get("sector", "unknown"),
                    "region": pos.get("region", "unknown"),
                })
        else:
            # Fallback: use market data
            for symbol, price in market_data.get("prices", {}).items():
                positions.append({
                    "symbol": symbol,
                    "value": price * market_data.get("holdings", {}).get(symbol, 0),
                    "weight": 0,
                    "volatility": market_data.get("volatility", {}).get(symbol, 0.2),
                    "sector": market_data.get("sectors", {}).get(symbol, "unknown"),
                    "region": market_data.get("regions", {}).get(symbol, "unknown"),
                })

        # Filter out zero value positions
        return [p for p in positions if p["value"] > 0]

    async def _calculate_risk_contributions(
        self,
        positions: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate risk contributions for each position."""
        contributions = {}

        if len(positions) < 2:
            return contributions

        # Simplified risk contribution calculation
        total_risk = sum(p["value"] * p.get("volatility", 0.2) for p in positions)

        for pos in positions:
            symbol = pos.get("symbol")
            if symbol:
                risk = pos["value"] * pos.get("volatility", 0.2)
                contributions[symbol] = risk / total_risk if total_risk > 0 else 0

        return contributions

    async def _calculate_avg_correlation(
        self,
        positions: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate average correlation between positions."""
        if len(positions) < 2:
            return 0.0

        correlations = []
        symbols = [p["symbol"] for p in positions]

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = market_data.get("correlations", {}).get(
                    f"{symbols[i]}_{symbols[j]}", 0.3
                )
                correlations.append(abs(corr))

        return np.mean(correlations) if correlations else 0.0

    def _determine_regime(
        self,
        herfindahl: float,
        effective_n: float,
        concentration: float,
        avg_correlation: float
    ) -> DiversificationRegime:
        """Determine diversification regime."""
        if herfindahl > 0.5 or effective_n < 2:
            return DiversificationRegime.CONCENTRATED
        elif herfindahl > 0.25 or effective_n < 4:
            return DiversificationRegime.UNDER_DIVERSIFIED
        elif herfindahl < 0.05 or effective_n > 20:
            return DiversificationRegime.OVER_DIVERSIFIED
        elif avg_correlation > 0.7:
            return DiversificationRegime.CRISIS
        elif herfindahl < 0.15 and effective_n > 8:
            return DiversificationRegime.WELL_DIVERSIFIED
        else:
            return DiversificationRegime.ADEQUATE

    async def _identify_opportunities(
        self,
        market_data: Dict[str, Any]
    ) -> List[DiversificationHedgePosition]:
        """
        Identify diversification hedging opportunities.

        Args:
            market_data: Current market data

        Returns:
            List of diversification opportunities
        """
        opportunities = []

        metrics = self._diversification_metrics

        # Check if diversification is needed
        if metrics.regime in (DiversificationRegime.WELL_DIVERSIFIED, DiversificationRegime.OVER_DIVERSIFIED):
            return opportunities

        # Get current positions
        current_positions = self._get_portfolio_positions(market_data)

        # Identify assets for diversification
        if metrics.regime in (DiversificationRegime.CONCENTRATED, DiversificationRegime.UNDER_DIVERSIFIED):
            # Need to add uncorrelated assets
            uncorrelated_assets = await self._find_uncorrelated_assets(current_positions, market_data)

            for asset in uncorrelated_assets:
                opportunity = DiversificationHedgePosition(
                    symbol=asset["symbol"],
                    size=0,
                    entry_price=asset.get("price", 0),
                    target_weight=asset.get("target_weight", 0.05),
                    correlation=asset.get("correlation", 0),
                    diversification_score=asset.get("diversification_score", 0.5),
                )
                opportunities.append(opportunity)

        # Check for concentration issues
        if metrics.concentration_ratio > self._config["max_concentration_ratio"]:
            # Need to reduce concentrated positions
            concentrated = await self._identify_concentrated_positions(current_positions, market_data)

            for pos in concentrated:
                opportunity = DiversificationHedgePosition(
                    symbol=pos["symbol"],
                    size=pos["value"],
                    entry_price=pos.get("price", 0),
                    target_weight=pos.get("target_weight", 0),
                    correlation=pos.get("correlation", 0),
                    diversification_score=0.3,
                )
                opportunities.append(opportunity)

        # Sort by diversification score
        opportunities.sort(key=lambda x: x.diversification_score, reverse=True)

        # Limit number of opportunities
        max_ops = self._config.get("max_opportunities", 10)
        opportunities = opportunities[:max_ops]

        return opportunities

    async def _find_uncorrelated_assets(
        self,
        current_positions: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find uncorrelated assets for diversification."""
        candidates = []

        all_symbols = market_data.get("symbols", [])
        current_symbols = [p["symbol"] for p in current_positions]

        for symbol in all_symbols:
            if symbol in current_symbols:
                continue

            # Calculate correlation with current positions
            correlations = []
            for pos in current_positions:
                corr = market_data.get("correlations", {}).get(
                    f"{pos['symbol']}_{symbol}", 0.5
                )
                correlations.append(abs(corr))

            avg_corr = np.mean(correlations) if correlations else 0.5

            # Check if asset is uncorrelated
            if avg_corr < self._config["max_correlation"]:
                candidates.append({
                    "symbol": symbol,
                    "price": market_data.get("prices", {}).get(symbol, 0),
                    "correlation": avg_corr,
                    "target_weight": 1.0 / (len(current_positions) + 1),
                    "diversification_score": 1.0 - avg_corr,
                })

        # Sort by diversification score
        candidates.sort(key=lambda x: x["diversification_score"], reverse=True)

        # Limit to top candidates
        max_candidates = self._config.get("max_uncorrelated_assets", 5)
        return candidates[:max_candidates]

    async def _identify_concentrated_positions(
        self,
        positions: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify concentrated positions that need hedging."""
        concentrated = []

        total_value = sum(p["value"] for p in positions)

        for pos in positions:
            weight = pos["value"] / total_value if total_value > 0 else 0

            if weight > self._config["max_concentration_ratio"] / 2:
                concentrated.append({
                    "symbol": pos["symbol"],
                    "value": pos["value"],
                    "price": market_data.get("prices", {}).get(pos["symbol"], 0),
                    "current_weight": weight,
                    "target_weight": self._config["max_concentration_ratio"] / 2,
                    "correlation": 1.0,
                })

        return concentrated

    async def _generate_hedge_signals(
        self,
        opportunities: List[DiversificationHedgePosition],
        market_data: Dict[str, Any]
    ) -> List[HedgeSignal]:
        """
        Generate hedge signals from opportunities.

        Args:
            opportunities: List of diversification opportunities
            market_data: Current market data

        Returns:
            List of hedge signals
        """
        signals = []

        for opp in opportunities:
            # Skip if target weight is too small
            if opp.target_weight < self._config["min_position_size"]:
                continue

            # Calculate position size
            portfolio_value = market_data.get("portfolio_value", 1000000)
            size = opp.target_weight * portfolio_value / opp.entry_price if opp.entry_price > 0 else 0

            # Apply size constraints
            size = max(self._config["min_position_size"], min(self._config["max_position_size"], size))

            if size < self._config["min_position_size"]:
                continue

            # Calculate confidence
            confidence = self._calculate_opportunity_confidence(opp)

            if confidence < self._config["confidence_threshold"]:
                continue

            # Determine direction
            if opp.symbol in [p["symbol"] for p in self._get_portfolio_positions(market_data)]:
                direction = HedgeDirection.SHORT  # Reduce concentration
            else:
                direction = HedgeDirection.LONG   # Add diversification

            # Calculate stop loss and take profit
            stop_loss = self._calculate_diversification_stop(opp.entry_price, direction)
            take_profit = self._calculate_diversification_target(opp.entry_price, direction)

            signal = HedgeSignal(
                hedge_type=HedgeType.DIVERSIFICATION,
                direction=direction,
                size=size,
                entry_price=opp.entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Diversification hedge: {opp.symbol} (score={opp.diversification_score:.2f})",
                metadata={
                    "symbol": opp.symbol,
                    "target_weight": opp.target_weight,
                    "correlation": opp.correlation,
                    "diversification_score": opp.diversification_score,
                    "regime": self._diversification_metrics.regime.value,
                }
            )

            signals.append(signal)

        return signals

    def _calculate_opportunity_confidence(
        self,
        opportunity: DiversificationHedgePosition
    ) -> float:
        """Calculate confidence in a diversification opportunity."""
        confidence = 0.5

        # Diversification score contribution
        confidence += opportunity.diversification_score * 0.3

        # Correlation contribution
        if opportunity.correlation < 0.3:
            confidence += 0.2
        elif opportunity.correlation < 0.5:
            confidence += 0.1

        # Target weight contribution
        if opportunity.target_weight > 0.05:
            confidence += 0.1

        # Regime contribution
        regime = self._diversification_metrics.regime
        if regime in (DiversificationRegime.CONCENTRATED, DiversificationRegime.UNDER_DIVERSIFIED):
            confidence += 0.1

        return min(0.95, confidence)

    def _calculate_diversification_stop(
        self,
        price: float,
        direction: HedgeDirection
    ) -> Optional[float]:
        """Calculate stop loss for diversification hedge."""
        stop_pct = self._config["stop_loss_pct"]

        if direction == HedgeDirection.LONG:
            return price * (1 - stop_pct)
        else:
            return price * (1 + stop_pct)

    def _calculate_diversification_target(
        self,
        price: float,
        direction: HedgeDirection
    ) -> Optional[float]:
        """Calculate take profit for diversification hedge."""
        target_pct = self._config["take_profit_pct"]

        if direction == HedgeDirection.LONG:
            return price * (1 + target_pct)
        else:
            return price * (1 - target_pct)

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

                    # Update weight
                    portfolio_value = market_data.get("portfolio_value", 0)
                    if portfolio_value > 0:
                        position.weight = (position.size * position.current_price) / portfolio_value

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            # Calculate diversification improvement
            if self._metrics_history:
                current = self._diversification_metrics
                previous = self._metrics_history[-1] if len(self._metrics_history) > 1 else current

                herfindahl_change = previous.herfindahl_index - current.herfindahl_index
                self._performance["diversification_improvement"] = herfindahl_change
                self._performance["herfindahl_index"] = current.herfindahl_index
                self._performance["effective_number"] = current.effective_number

                if previous.concentration_ratio > 0:
                    self._performance["concentration_reduction"] = (
                        previous.concentration_ratio - current.concentration_ratio
                    ) / previous.concentration_ratio

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "herfindahl_index": self._diversification_metrics.herfindahl_index,
                "effective_number": self._diversification_metrics.effective_number,
                "concentration_ratio": self._diversification_metrics.concentration_ratio,
                "diversification_ratio": self._diversification_metrics.diversification_ratio,
                "regime": self._diversification_metrics.regime.value,
                "diversification_improvement": self._performance["diversification_improvement"],
                "concentration_reduction": self._performance["concentration_reduction"],
                "config": self._config,
            }

    def get_diversification_metrics(self) -> Dict[str, Any]:
        """Get current diversification metrics."""
        return self._diversification_metrics.to_dict()

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("diversification_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("diversification_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("diversification_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "DiversificationHedgeStrategy",
    "DiversificationMetrics",
    "DiversificationHedgePosition",
    "DiversificationMetric",
    "DiversificationType",
    "DiversificationRegime",
]

logger.info("diversification_hedge_module_loaded", version="3.0.0")
