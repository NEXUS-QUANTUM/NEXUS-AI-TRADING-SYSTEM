# trading/bots/hedge_bot/strategies/cross_hedge.py

"""
NEXUS HEDGE BOT - CROSS HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced cross-asset hedging strategy that hedges positions in one asset
using correlated or inverse-correlated assets, including cross-currency,
cross-sector, and cross-market hedges.

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

class CrossHedgeType(str, Enum):
    """Types of cross hedges."""
    ASSET = "asset"                          # Different asset class (e.g., stocks vs bonds)
    CURRENCY = "currency"                    # Different currency
    SECTOR = "sector"                        # Different sector
    GEOGRAPHIC = "geographic"                # Different geography
    COMPLEMENTARY = "complementary"          # Complementary assets (e.g., oil and airlines)
    SUBSTITUTE = "substitute"                # Substitute assets (e.g., BTC vs ETH)
    INVERSE = "inverse"                      # Inverse relationship (e.g., USD/JPY vs EUR/JPY)
    HEDGE_FUND = "hedge_fund"                # Hedge fund correlations
    MACRO = "macro"                          # Macro-economic hedge


class CrossHedgeMethod(str, Enum):
    """Methods for cross hedging."""
    REGRESSION = "regression"                # Linear regression
    ROLLING_REGRESSION = "rolling_regression" # Rolling regression
    RIDGE = "ridge"                          # Ridge regression
    LASSO = "lasso"                          # Lasso regression
    ELASTIC_NET = "elastic_net"              # Elastic Net
    BAYESIAN = "bayesian"                    # Bayesian regression
    RANDOM_FOREST = "random_forest"          # Random forest
    NEURAL = "neural"                        # Neural network


class CrossHedgeStyle(str, Enum):
    """Styles of cross hedging."""
    SINGLE = "single"                        # Single hedge asset
    BASKET = "basket"                        # Basket of hedge assets
    DYNAMIC = "dynamic"                      # Dynamic hedge ratio
    ADAPTIVE = "adaptive"                    # Adaptive hedge selection
    OPTIMAL = "optimal"                      # Optimal hedge ratio
    MINIMUM_VARIANCE = "minimum_variance"    # Minimum variance hedge


# === DATA MODELS ===

@dataclass
class CrossHedgeRelationship:
    """Cross hedge relationship between assets."""
    relationship_id: str = field(default_factory=lambda: str(uuid4()))
    target_asset: str = ""
    hedge_asset: str = ""
    hedge_ratio: float = 0.0
    intercept: float = 0.0
    r_squared: float = 0.0
    std_error: float = 0.0
    p_value: float = 0.0
    t_statistic: float = 0.0
    correlation: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    hedge_effectiveness: float = 0.0
    n_observations: int = 0
    method: CrossHedgeMethod = CrossHedgeMethod.REGRESSION
    type: CrossHedgeType = CrossHedgeType.ASSET
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "method": self.method.value,
            "type": self.type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossHedgeRelationship":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["method"] = CrossHedgeMethod(data["method"])
        data["type"] = CrossHedgeType(data["type"])
        return cls(**data)


@dataclass
class CrossHedgePosition:
    """Cross hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    target_asset: str = ""
    hedge_asset: str = ""
    hedge_ratio: float = 0.0
    target_size: float = 0.0
    hedge_size: float = 0.0
    target_entry_price: float = 0.0
    hedge_entry_price: float = 0.0
    target_current_price: float = 0.0
    hedge_current_price: float = 0.0
    correlation: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hedge_effectiveness: float = 0.0
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


# === CROSS HEDGE STRATEGY ===

class CrossHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced cross-asset hedging strategy that hedges positions using
    correlated or inverse-correlated assets.
    """

    def __init__(
        self,
        name: str = "cross_hedge",
        hedge_type: CrossHedgeType = CrossHedgeType.ASSET,
        hedge_method: CrossHedgeMethod = CrossHedgeMethod.ROLLING_REGRESSION,
        hedge_style: CrossHedgeStyle = CrossHedgeStyle.DYNAMIC,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the cross hedge strategy.

        Args:
            name: Strategy name
            hedge_type: Type of cross hedge
            hedge_method: Method for hedge calculation
            hedge_style: Style of cross hedging
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.hedge_type = hedge_type
        self.hedge_method = hedge_method
        self.hedge_style = hedge_style
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Hedge relationships
        self._relationships: Dict[str, CrossHedgeRelationship] = {}
        self._relationship_history: Dict[str, List[CrossHedgeRelationship]] = {}

        # Hedge positions
        self._hedge_positions: List[CrossHedgePosition] = []
        self._position_history: List[CrossHedgePosition] = []

        # Configuration
        self._config = {
            "lookback_days": 60,
            "min_observations": 30,
            "rolling_window": 30,
            "max_hedge_assets": 5,
            "min_hedge_ratio": 0.01,
            "max_hedge_ratio": 2.0,
            "correlation_threshold": 0.5,
            "r_squared_threshold": 0.3,
            "rebalance_threshold": 0.05,
            "max_position_size": 0.15,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "confidence_threshold": 0.60,
            "volatility_adjustment": True,
            "dynamic_hedge_ratio": True,
            "adaptive_selection": True,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "average_hedge_ratio": 0.0,
            "hedge_effectiveness": 0.0,
            "tracking_error": 0.0,
            "correlation_exposure": 0.0,
        }

        # Price data
        self._price_data: Dict[str, List[float]] = {}
        self._returns_data: Dict[str, List[float]] = {}

        # Regression models
        self._regression_models: Dict[str, Any] = {}
        self._scaler = StandardScaler()

        # Hedge pool
        self._hedge_pool: Dict[str, List[str]] = {}

        logger.info(
            "cross_hedge_strategy_initialized",
            name=name,
            hedge_type=hedge_type.value,
            hedge_method=hedge_method.value,
            hedge_style=hedge_style.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate cross hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with cross hedge signals
        """
        try:
            # Update price data
            await self._update_price_data(market_data)

            # Identify hedge relationships
            relationships = await self._identify_relationships(market_data)

            # Generate hedge signals
            signals = await self._generate_hedge_signals(relationships, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "relationships": [r.to_dict() for r in relationships],
                "signals": [s.to_dict() for s in signals],
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "cross_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _update_price_data(self, market_data: Dict[str, Any]) -> None:
        """Update price data for all assets."""
        with self._lock:
            symbols = market_data.get("symbols", [])

            for symbol in symbols:
                price = market_data.get("prices", {}).get(symbol, 0)
                if price > 0:
                    if symbol not in self._price_data:
                        self._price_data[symbol] = []
                        self._returns_data[symbol] = []

                    self._price_data[symbol].append(price)

                    # Calculate returns
                    if len(self._price_data[symbol]) > 1:
                        ret = (price - self._price_data[symbol][-2]) / self._price_data[symbol][-2]
                        self._returns_data[symbol].append(ret)

                    # Limit history
                    max_history = self._config["lookback_days"] * 24
                    if len(self._price_data[symbol]) > max_history:
                        self._price_data[symbol] = self._price_data[symbol][-max_history:]
                        self._returns_data[symbol] = self._returns_data[symbol][-max_history:]

    async def _identify_relationships(
        self,
        market_data: Dict[str, Any]
    ) -> List[CrossHedgeRelationship]:
        """
        Identify cross hedge relationships.

        Args:
            market_data: Current market data

        Returns:
            List of cross hedge relationships
        """
        relationships = []

        try:
            symbols = list(self._price_data.keys())
            if len(symbols) < 2:
                return relationships

            # Build hedge pool
            await self._build_hedge_pool(symbols)

            # For each target asset, find hedge assets
            for target in symbols:
                hedge_assets = self._hedge_pool.get(target, [])

                for hedge in hedge_assets:
                    if hedge not in self._price_data or len(self._price_data[hedge]) < 10:
                        continue

                    # Calculate relationship
                    relationship = await self._calculate_relationship(target, hedge, market_data)

                    if relationship and relationship.r_squared >= self._config["r_squared_threshold"]:
                        relationships.append(relationship)

        except Exception as e:
            logger.error("relationship_identification_failed", error=str(e))

        # Sort by hedge effectiveness
        relationships.sort(key=lambda x: x.hedge_effectiveness, reverse=True)

        return relationships

    async def _build_hedge_pool(self, symbols: List[str]) -> None:
        """
        Build pool of potential hedge assets.

        Args:
            symbols: List of symbols
        """
        with self._lock:
            self._hedge_pool = {}

            for target in symbols:
                hedge_assets = []

                for potential_hedge in symbols:
                    if potential_hedge == target:
                        continue

                    # Check correlation
                    if target in self._returns_data and potential_hedge in self._returns_data:
                        target_returns = self._returns_data[target][-30:]
                        hedge_returns = self._returns_data[potential_hedge][-30:]

                        if len(target_returns) > 10 and len(hedge_returns) > 10:
                            corr = np.corrcoef(target_returns, hedge_returns)[0, 1]
                            if abs(corr) >= self._config["correlation_threshold"]:
                                hedge_assets.append(potential_hedge)

                # Limit number of hedge assets
                if len(hedge_assets) > self._config["max_hedge_assets"]:
                    # Keep top correlated
                    hedge_corrs = []
                    for h in hedge_assets:
                        corr = np.corrcoef(
                            self._returns_data[target][-30:],
                            self._returns_data[h][-30:]
                        )[0, 1]
                        hedge_corrs.append((h, abs(corr)))

                    hedge_corrs.sort(key=lambda x: x[1], reverse=True)
                    hedge_assets = [h for h, _ in hedge_corrs[:self._config["max_hedge_assets"]]]

                self._hedge_pool[target] = hedge_assets

    async def _calculate_relationship(
        self,
        target: str,
        hedge: str,
        market_data: Dict[str, Any]
    ) -> Optional[CrossHedgeRelationship]:
        """
        Calculate relationship between target and hedge assets.

        Args:
            target: Target asset
            hedge: Hedge asset
            market_data: Current market data

        Returns:
            CrossHedgeRelationship or None
        """
        try:
            # Get aligned returns
            target_returns = self._returns_data.get(target, [])
            hedge_returns = self._returns_data.get(hedge, [])

            if len(target_returns) < self._config["min_observations"] or len(hedge_returns) < self._config["min_observations"]:
                return None

            # Align lengths
            min_len = min(len(target_returns), len(hedge_returns))
            target_returns = target_returns[-min_len:]
            hedge_returns = hedge_returns[-min_len:]

            x = np.array(hedge_returns).reshape(-1, 1)
            y = np.array(target_returns)

            # Calculate correlation
            correlation = np.corrcoef(target_returns, hedge_returns)[0, 1]

            if abs(correlation) < self._config["correlation_threshold"]:
                return None

            # Calculate regression based on method
            if self.hedge_method == CrossHedgeMethod.REGRESSION:
                model = LinearRegression()
                model.fit(x, y)
                hedge_ratio = model.coef_[0]
                intercept = model.intercept_
                r_squared = model.score(x, y)

            elif self.hedge_method == CrossHedgeMethod.ROLLING_REGRESSION:
                # Use last 30 days for rolling regression
                window = min(self._config["rolling_window"], len(x))
                x_window = x[-window:]
                y_window = y[-window:]
                model = LinearRegression()
                model.fit(x_window, y_window)
                hedge_ratio = model.coef_[0]
                intercept = model.intercept_
                r_squared = model.score(x_window, y_window)

            elif self.hedge_method == CrossHedgeMethod.RIDGE:
                model = Ridge(alpha=1.0)
                model.fit(x, y)
                hedge_ratio = model.coef_[0]
                intercept = model.intercept_
                r_squared = model.score(x, y)

            elif self.hedge_method == CrossHedgeMethod.LASSO:
                model = Lasso(alpha=0.01)
                model.fit(x, y)
                hedge_ratio = model.coef_[0]
                intercept = model.intercept_
                r_squared = model.score(x, y)

            else:
                model = LinearRegression()
                model.fit(x, y)
                hedge_ratio = model.coef_[0]
                intercept = model.intercept_
                r_squared = model.score(x, y)

            # Calculate standard error and t-statistic
            n = len(x)
            y_pred = model.predict(x)
            residuals = y - y_pred
            ss_res = np.sum(residuals ** 2)
            se_beta = np.sqrt(ss_res / (n - 2)) / np.sqrt(np.sum((x - np.mean(x)) ** 2))
            t_statistic = hedge_ratio / se_beta if se_beta > 0 else 0
            p_value = 2 * (1 - stats.t.cdf(abs(t_statistic), n - 2))

            # Calculate hedge effectiveness
            hedge_effectiveness = r_squared * abs(correlation)

            # Determine cross hedge type
            cross_type = self._determine_hedge_type(target, hedge, market_data)

            # Calculate beta and alpha
            beta = hedge_ratio
            alpha = intercept

            return CrossHedgeRelationship(
                target_asset=target,
                hedge_asset=hedge,
                hedge_ratio=float(hedge_ratio),
                intercept=float(intercept),
                r_squared=float(r_squared),
                std_error=float(se_beta),
                p_value=float(p_value),
                t_statistic=float(t_statistic),
                correlation=float(correlation),
                beta=float(beta),
                alpha=float(alpha),
                hedge_effectiveness=float(hedge_effectiveness),
                n_observations=n,
                method=self.hedge_method,
                type=cross_type,
            )

        except Exception as e:
            logger.error(
                "relationship_calculation_failed",
                target=target,
                hedge=hedge,
                error=str(e),
            )
            return None

    def _determine_hedge_type(
        self,
        target: str,
        hedge: str,
        market_data: Dict[str, Any]
    ) -> CrossHedgeType:
        """Determine cross hedge type."""
        # Simplified - in production, this would use metadata
        if "USD" in target and "USD" in hedge:
            return CrossHedgeType.CURRENCY
        elif "BTC" in target and "ETH" in hedge:
            return CrossHedgeType.SUBSTITUTE
        elif "OIL" in target and "AIRLINE" in hedge:
            return CrossHedgeType.COMPLEMENTARY
        else:
            return CrossHedgeType.ASSET

    async def _generate_hedge_signals(
        self,
        relationships: List[CrossHedgeRelationship],
        market_data: Dict[str, Any]
    ) -> List[HedgeSignal]:
        """
        Generate hedge signals from relationships.

        Args:
            relationships: List of cross hedge relationships
            market_data: Current market data

        Returns:
            List of hedge signals
        """
        signals = []

        for relationship in relationships:
            # Skip if hedge ratio is too small
            if abs(relationship.hedge_ratio) < self._config["min_hedge_ratio"]:
                continue

            # Check if we already have a position
            if any(p.target_asset == relationship.target_asset for p in self._hedge_positions):
                continue

            # Calculate confidence
            confidence = self._calculate_relationship_confidence(relationship)

            if confidence < self._config["confidence_threshold"]:
                continue

            # Determine hedge direction
            direction = self._determine_direction(relationship)

            # Calculate position size
            target_price = market_data.get("prices", {}).get(relationship.target_asset, 0)
            hedge_price = market_data.get("prices", {}).get(relationship.hedge_asset, 0)

            if target_price <= 0 or hedge_price <= 0:
                continue

            # Calculate hedge size
            target_size = self._config["max_position_size"] * confidence
            hedge_size = target_size * abs(relationship.hedge_ratio)

            # Apply volatility adjustment
            if self._config["volatility_adjustment"]:
                vol_ratio = self._calculate_volatility_ratio(
                    relationship.target_asset,
                    relationship.hedge_asset
                )
                hedge_size *= vol_ratio

            # Apply position size limits
            target_size = max(
                self._config["min_position_size"],
                min(self._config["max_position_size"], target_size)
            )

            # Calculate stop loss and take profit
            stop_loss = self._calculate_cross_stop(relationship, target_price)
            take_profit = self._calculate_cross_target(relationship, target_price)

            signal = HedgeSignal(
                hedge_type=HedgeType.CROSS,
                direction=direction,
                size=target_size,
                entry_price=target_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Cross hedge: {relationship.target_asset} -> {relationship.hedge_asset} (ratio={relationship.hedge_ratio:.2f})",
                metadata={
                    "target_asset": relationship.target_asset,
                    "hedge_asset": relationship.hedge_asset,
                    "hedge_ratio": relationship.hedge_ratio,
                    "hedge_size": hedge_size,
                    "r_squared": relationship.r_squared,
                    "correlation": relationship.correlation,
                    "method": relationship.method.value,
                    "type": relationship.type.value,
                }
            )

            signals.append(signal)

        return signals

    def _calculate_relationship_confidence(
        self,
        relationship: CrossHedgeRelationship
    ) -> float:
        """Calculate confidence in a relationship."""
        confidence = 0.5

        # R-squared contribution
        confidence += relationship.r_squared * 0.3

        # Correlation contribution
        confidence += abs(relationship.correlation) * 0.2

        # Hedge effectiveness contribution
        confidence += relationship.hedge_effectiveness * 0.2

        # Statistical significance
        if relationship.p_value < 0.05:
            confidence += 0.1

        # Sample size
        if relationship.n_observations > 60:
            confidence += 0.1

        return min(0.95, confidence)

    def _determine_direction(self, relationship: CrossHedgeRelationship) -> HedgeDirection:
        """Determine hedge direction."""
        if relationship.correlation > 0:
            return HedgeDirection.SHORT  # Short hedge asset to hedge target
        else:
            return HedgeDirection.LONG   # Long hedge asset to hedge target

    def _calculate_volatility_ratio(self, target: str, hedge: str) -> float:
        """Calculate volatility ratio for adjustment."""
        target_vol = self._calculate_volatility(target)
        hedge_vol = self._calculate_volatility(hedge)

        if hedge_vol > 0:
            ratio = target_vol / hedge_vol
            return max(0.5, min(2.0, ratio))
        return 1.0

    def _calculate_volatility(self, symbol: str) -> float:
        """Calculate volatility for a symbol."""
        if symbol not in self._returns_data or len(self._returns_data[symbol]) < 10:
            return 0.2

        returns = self._returns_data[symbol][-30:]
        return np.std(returns)

    def _calculate_cross_stop(
        self,
        relationship: CrossHedgeRelationship,
        price: float
    ) -> Optional[float]:
        """Calculate stop loss for cross hedge."""
        # Stop based on relationship breakdown
        stop_pct = self._config["stop_loss_pct"] * (1 + abs(relationship.hedge_ratio) * 0.2)

        if relationship.correlation > 0:
            return price * (1 - stop_pct)
        else:
            return price * (1 + stop_pct)

    def _calculate_cross_target(
        self,
        relationship: CrossHedgeRelationship,
        price: float
    ) -> Optional[float]:
        """Calculate take profit for cross hedge."""
        target_pct = self._config["take_profit_pct"] * (1 + abs(relationship.hedge_ratio) * 0.1)

        if relationship.correlation > 0:
            return price * (1 + target_pct)
        else:
            return price * (1 - target_pct)

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.target_asset in market_data.get("prices", {}):
                    position.target_current_price = market_data["prices"][position.target_asset]
                if position.hedge_asset in market_data.get("prices", {}):
                    position.hedge_current_price = market_data["prices"][position.hedge_asset]

                # Calculate PnL
                position.pnl = (
                    (position.target_current_price - position.target_entry_price) -
                    (position.hedge_current_price - position.hedge_entry_price) * position.hedge_ratio
                ) * position.target_size
                position.pnl_pct = position.pnl / (position.target_entry_price * position.target_size) * 100 if position.target_entry_price > 0 else 0
                position.last_update = datetime.utcnow()

                # Update correlation
                position.correlation = self._calculate_current_correlation(
                    position.target_asset,
                    position.hedge_asset
                )

                # Update hedge effectiveness
                position.hedge_effectiveness = self._calculate_current_effectiveness(position)

    def _calculate_current_correlation(self, target: str, hedge: str) -> float:
        """Calculate current correlation between assets."""
        if target not in self._returns_data or hedge not in self._returns_data:
            return 0.0

        target_returns = self._returns_data[target][-30:]
        hedge_returns = self._returns_data[hedge][-30:]

        if len(target_returns) < 10 or len(hedge_returns) < 10:
            return 0.0

        return np.corrcoef(target_returns, hedge_returns)[0, 1]

    def _calculate_current_effectiveness(self, position: CrossHedgePosition) -> float:
        """Calculate current hedge effectiveness."""
        if abs(position.pnl) < 0.001:
            return 0.0

        # Simplified effectiveness calculation
        target_return = (position.target_current_price - position.target_entry_price) / position.target_entry_price
        hedge_return = (position.hedge_current_price - position.hedge_entry_price) / position.hedge_entry_price

        if abs(hedge_return) > 0:
            effectiveness = abs(target_return / hedge_return)
            return min(1.0, effectiveness)
        return 0.0

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._hedge_positions:
                avg_ratio = sum(p.hedge_ratio for p in self._hedge_positions) / len(self._hedge_positions)
                self._performance["average_hedge_ratio"] = avg_ratio

                avg_effectiveness = sum(p.hedge_effectiveness for p in self._hedge_positions) / len(self._hedge_positions)
                self._performance["hedge_effectiveness"] = avg_effectiveness

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "average_hedge_ratio": self._performance["average_hedge_ratio"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "tracking_error": self._performance["tracking_error"],
                "relationships": len(self._relationships),
                "hedge_pool_size": sum(len(v) for v in self._hedge_pool.values()),
                "config": self._config,
            }

    def get_relationships(self) -> List[Dict[str, Any]]:
        """Get all hedge relationships."""
        return [r.to_dict() for r in self._relationships.values()]

    def get_relationship(self, target: str) -> Optional[CrossHedgeRelationship]:
        """Get relationship for a target asset."""
        return self._relationships.get(target)

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("cross_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("cross_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("cross_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "CrossHedgeStrategy",
    "CrossHedgeRelationship",
    "CrossHedgePosition",
    "CrossHedgeType",
    "CrossHedgeMethod",
    "CrossHedgeStyle",
]

logger.info("cross_hedge_module_loaded", version="3.0.0")
