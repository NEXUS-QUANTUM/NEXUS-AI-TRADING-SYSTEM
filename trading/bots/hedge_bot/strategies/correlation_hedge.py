# trading/bots/hedge_bot/strategies/correlation_hedge.py

"""
NEXUS HEDGE BOT - CORRELATION HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced correlation-based hedging strategy that exploits dynamic
correlation relationships between assets, using statistical methods
and machine learning to identify and hedge correlation risks.

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
from sklearn.covariance import LedoitWolf
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

class CorrelationType(str, Enum):
    """Types of correlation."""
    PEARSON = "pearson"                      # Pearson correlation
    SPEARMAN = "spearman"                    # Spearman rank correlation
    KENDALL = "kendall"                      # Kendall tau correlation
    DISTANCE = "distance"                    # Distance correlation
    PARTIAL = "partial"                      # Partial correlation
    DYNAMIC = "dynamic"                      # Dynamic conditional correlation
    RANK = "rank"                            # Rank correlation


class CorrelationHedgeStyle(str, Enum):
    """Styles of correlation hedging."""
    PAIRWISE = "pairwise"                    # Pairwise correlation hedging
    PORTFOLIO = "portfolio"                  # Portfolio-level correlation hedging
    FACTOR = "factor"                        # Factor-based correlation hedging
    DYNAMIC = "dynamic"                      # Dynamic correlation hedging
    DIVERSIFICATION = "diversification"      # Diversification-focused
    CONCENTRATION = "concentration"          # Concentration-focused


class CorrelationRegime(str, Enum):
    """Correlation regimes."""
    LOW = "low"                              # Low correlation (< 0.3)
    MODERATE = "moderate"                    # Moderate correlation (0.3 - 0.6)
    HIGH = "high"                            # High correlation (0.6 - 0.8)
    VERY_HIGH = "very_high"                  # Very high correlation (> 0.8)
    NEGATIVE = "negative"                    # Negative correlation
    DIVERGENT = "divergent"                  # Divergent correlation structure
    CRISIS = "crisis"                        # Crisis correlation (all moving together)


# === DATA MODELS ===

@dataclass
class CorrelationEstimate:
    """Correlation estimate between assets."""
    asset1: str = ""
    asset2: str = ""
    correlation: float = 0.0
    p_value: float = 0.0
    std_error: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0
    n_observations: int = 0
    method: CorrelationType = CorrelationType.PEARSON
    regime: CorrelationRegime = CorrelationRegime.MODERATE
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
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationEstimate":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["method"] = CorrelationType(data["method"])
        data["regime"] = CorrelationRegime(data["regime"])
        return cls(**data)


@dataclass
class CorrelationMatrix:
    """Correlation matrix with metadata."""
    assets: List[str] = field(default_factory=list)
    matrix: np.ndarray = field(default_factory=lambda: np.array([]))
    eigenvalues: List[float] = field(default_factory=list)
    eigenvectors: List[List[float]] = field(default_factory=list)
    condition_number: float = 0.0
    determinant: float = 0.0
    rank: int = 0
    regime: CorrelationRegime = CorrelationRegime.MODERATE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime.value,
            "matrix": self.matrix.tolist() if self.matrix.size > 0 else [],
            "eigenvalues": self.eigenvalues,
            "eigenvectors": self.eigenvectors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationMatrix":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["regime"] = CorrelationRegime(data["regime"])
        data["matrix"] = np.array(data.get("matrix", []))
        return cls(**data)


@dataclass
class CorrelationHedgePosition:
    """Correlation hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    asset1: str = ""
    asset2: str = ""
    hedge_ratio: float = 0.0
    correlation: float = 0.0
    target_correlation: float = 0.0
    size: float = 0.0
    entry_price1: float = 0.0
    entry_price2: float = 0.0
    current_price1: float = 0.0
    current_price2: float = 0.0
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


# === CORRELATION HEDGE STRATEGY ===

class CorrelationHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced correlation-based hedging strategy that exploits dynamic
    correlation relationships between assets.
    """

    def __init__(
        self,
        name: str = "correlation_hedge",
        hedge_style: CorrelationHedgeStyle = CorrelationHedgeStyle.DYNAMIC,
        correlation_type: CorrelationType = CorrelationType.DYNAMIC,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the correlation hedge strategy.

        Args:
            name: Strategy name
            hedge_style: Style of correlation hedging
            correlation_type: Type of correlation calculation
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.hedge_style = hedge_style
        self.correlation_type = correlation_type
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Correlation cache
        self._correlation_cache: Dict[str, CorrelationEstimate] = {}
        self._correlation_matrix = CorrelationMatrix()
        self._correlation_history: List[CorrelationMatrix] = []

        # Hedge positions
        self._hedge_positions: List[CorrelationHedgePosition] = []
        self._position_history: List[CorrelationHedgePosition] = []

        # Configuration
        self._config = {
            "lookback_days": 60,
            "min_observations": 30,
            "correlation_threshold": 0.6,
            "target_correlation": 0.3,
            "rebalance_threshold": 0.05,
            "max_position_size": 0.15,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "confidence_threshold": 0.70,
            "max_assets": 20,
            "min_assets": 2,
            "dcc_lambda": 0.97,
            "pca_components": 0.95,
            "regime_detection": True,
            "adaptive_threshold": True,
            "diversification_penalty": 0.1,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "correlation_exposure_reduction": 0.0,
            "average_correlation": 0.0,
            "hedge_effectiveness": 0.0,
            "tracking_error": 0.0,
        }

        # Price data
        self._price_data: Dict[str, List[float]] = {}
        self._returns_data: Dict[str, List[float]] = {}

        # Dynamic correlation model
        self._dcc_model = None
        self._pca_model = None
        self._scaler = StandardScaler()

        logger.info(
            "correlation_hedge_strategy_initialized",
            name=name,
            hedge_style=hedge_style.value,
            correlation_type=correlation_type.value,
        )

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate correlation hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with correlation hedge signals
        """
        try:
            # Update price data
            await self._update_price_data(market_data)

            # Calculate correlation matrix
            await self._calculate_correlation_matrix(market_data)

            # Detect correlation regime
            regime = await self._detect_correlation_regime()

            # Identify correlation opportunities
            opportunities = await self._identify_opportunities(market_data, regime)

            # Generate hedge signals
            signals = await self._generate_hedge_signals(opportunities, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "correlation_matrix": self._correlation_matrix.to_dict(),
                "regime": regime.value if regime else None,
                "opportunities": [o.to_dict() for o in opportunities],
                "signals": [s.to_dict() for s in signals],
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "correlation_hedge_analysis_failed",
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

    async def _calculate_correlation_matrix(self, market_data: Dict[str, Any]) -> None:
        """
        Calculate correlation matrix using specified method.

        Args:
            market_data: Current market data
        """
        try:
            symbols = list(self._returns_data.keys())
            if len(symbols) < self._config["min_assets"]:
                return

            # Align returns data
            min_len = min(len(self._returns_data[s]) for s in symbols if len(self._returns_data[s]) > 0)
            if min_len < self._config["min_observations"]:
                return

            returns_matrix = []
            valid_symbols = []

            for symbol in symbols:
                if len(self._returns_data[symbol]) >= min_len:
                    returns_matrix.append(self._returns_data[symbol][-min_len:])
                    valid_symbols.append(symbol)

            if len(valid_symbols) < self._config["min_assets"]:
                return

            returns_array = np.array(returns_matrix)

            # Calculate correlation based on type
            if self.correlation_type == CorrelationType.PEARSON:
                corr_matrix = np.corrcoef(returns_array)

            elif self.correlation_type == CorrelationType.SPEARMAN:
                corr_matrix = stats.spearmanr(returns_array, axis=1).correlation

            elif self.correlation_type == CorrelationType.KENDALL:
                corr_matrix = np.corrcoef(returns_array)

            elif self.correlation_type == CorrelationType.DYNAMIC:
                # Dynamic Conditional Correlation (simplified DCC)
                corr_matrix = await self._calculate_dynamic_correlation(returns_array)

            elif self.correlation_type == CorrelationType.PARTIAL:
                # Partial correlation using precision matrix
                precision = np.linalg.pinv(np.corrcoef(returns_array))
                d = np.sqrt(np.diag(precision))
                corr_matrix = -precision / np.outer(d, d)

            else:
                corr_matrix = np.corrcoef(returns_array)

            # Apply shrinkage for stability
            if corr_matrix.shape[0] > 2:
                lw = LedoitWolf()
                lw.fit(returns_array.T)
                corr_matrix = lw.covariance_ / np.outer(
                    np.sqrt(np.diag(lw.covariance_)),
                    np.sqrt(np.diag(lw.covariance_))
                )

            # Calculate eigenvalues and eigenvectors
            eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)
            eigenvalues = eigenvalues[::-1]  # Sort descending
            eigenvectors = eigenvectors[:, ::-1]

            # Calculate condition number and determinant
            condition_number = np.max(eigenvalues) / np.min(eigenvalues) if np.min(eigenvalues) > 0 else 0
            determinant = np.prod(eigenvalues)

            # Determine regime
            avg_corr = np.mean(corr_matrix[np.triu_indices_from(corr_matrix, k=1)])
            regime = self._determine_regime_from_value(avg_corr)

            # Store correlation matrix
            self._correlation_matrix = CorrelationMatrix(
                assets=valid_symbols,
                matrix=corr_matrix,
                eigenvalues=eigenvalues.tolist(),
                eigenvectors=eigenvectors.tolist(),
                condition_number=condition_number,
                determinant=determinant,
                rank=np.linalg.matrix_rank(corr_matrix),
                regime=regime,
            )

            # Store history
            self._correlation_history.append(self._correlation_matrix)
            if len(self._correlation_history) > 100:
                self._correlation_history = self._correlation_history[-100:]

        except Exception as e:
            logger.error("correlation_matrix_calculation_failed", error=str(e))

    async def _calculate_dynamic_correlation(self, returns: np.ndarray) -> np.ndarray:
        """
        Calculate dynamic conditional correlation.

        Args:
            returns: Returns matrix

        Returns:
            Dynamic correlation matrix
        """
        n_assets = returns.shape[0]
        n_obs = returns.shape[1]

        # Initialize DCC parameters
        lambda_ = self._config["dcc_lambda"]

        # Calculate unconditional correlation
        corr_uncond = np.corrcoef(returns)

        # Initialize dynamic correlation
        corr_dynamic = np.zeros((n_assets, n_assets, n_obs))

        for t in range(n_obs):
            if t == 0:
                corr_dynamic[:, :, t] = corr_uncond
            else:
                # Exponential smoothing
                corr_dynamic[:, :, t] = (
                    lambda_ * corr_dynamic[:, :, t-1] +
                    (1 - lambda_) * np.outer(returns[:, t], returns[:, t])
                )

        # Return the most recent correlation
        return corr_dynamic[:, :, -1]

    def _determine_regime_from_value(self, avg_correlation: float) -> CorrelationRegime:
        """Determine correlation regime from average correlation."""
        abs_corr = abs(avg_correlation)

        if avg_correlation < 0:
            return CorrelationRegime.NEGATIVE
        elif abs_corr < 0.3:
            return CorrelationRegime.LOW
        elif abs_corr < 0.6:
            return CorrelationRegime.MODERATE
        elif abs_corr < 0.8:
            return CorrelationRegime.HIGH
        else:
            return CorrelationRegime.VERY_HIGH

    async def _detect_correlation_regime(self) -> CorrelationRegime:
        """
        Detect current correlation regime.

        Returns:
            CorrelationRegime
        """
        if not self._correlation_matrix.assets:
            return CorrelationRegime.MODERATE

        # Calculate average correlation
        matrix = self._correlation_matrix.matrix
        n = matrix.shape[0]
        if n < 2:
            return CorrelationRegime.MODERATE

        triu_indices = np.triu_indices_from(matrix, k=1)
        avg_corr = np.mean(matrix[triu_indices])

        # Check for divergent regime (high variance in correlations)
        corr_std = np.std(matrix[triu_indices])

        if corr_std > 0.3 and avg_corr > 0.3:
            return CorrelationRegime.DIVERGENT
        elif avg_corr > 0.7:
            return CorrelationRegime.CRISIS
        else:
            return self._determine_regime_from_value(avg_corr)

    async def _identify_opportunities(
        self,
        market_data: Dict[str, Any],
        regime: CorrelationRegime,
    ) -> List[CorrelationEstimate]:
        """
        Identify correlation hedging opportunities.

        Args:
            market_data: Current market data
            regime: Current correlation regime

        Returns:
            List of correlation opportunities
        """
        opportunities = []

        if not self._correlation_matrix.assets:
            return opportunities

        matrix = self._correlation_matrix.matrix
        assets = self._correlation_matrix.assets
        n = len(assets)

        # Identify pairs with high correlation
        threshold = self._get_correlation_threshold(regime)

        for i in range(n):
            for j in range(i + 1, n):
                corr = matrix[i, j]
                if abs(corr) >= threshold:
                    # Calculate confidence
                    confidence = self._calculate_correlation_confidence(corr, regime)

                    if confidence >= self._config["confidence_threshold"]:
                        estimate = CorrelationEstimate(
                            asset1=assets[i],
                            asset2=assets[j],
                            correlation=corr,
                            regime=self._determine_regime_from_value(corr),
                            method=self.correlation_type,
                            n_observations=self._config["lookback_days"],
                            confidence_lower=corr - 0.05,
                            confidence_upper=corr + 0.05,
                        )
                        opportunities.append(estimate)

        # Sort by absolute correlation descending
        opportunities.sort(key=lambda x: abs(x.correlation), reverse=True)

        # Limit number of opportunities
        max_ops = self._config.get("max_opportunities", 10)
        opportunities = opportunities[:max_ops]

        return opportunities

    def _get_correlation_threshold(self, regime: CorrelationRegime) -> float:
        """
        Get correlation threshold based on regime.

        Args:
            regime: Current correlation regime

        Returns:
            Threshold value
        """
        if regime == CorrelationRegime.CRISIS:
            return 0.7
        elif regime == CorrelationRegime.DIVERGENT:
            return 0.5
        elif regime == CorrelationRegime.VERY_HIGH:
            return 0.7
        elif regime == CorrelationRegime.HIGH:
            return 0.6
        elif regime == CorrelationRegime.MODERATE:
            return 0.5
        else:
            return self._config["correlation_threshold"]

    def _calculate_correlation_confidence(
        self,
        correlation: float,
        regime: CorrelationRegime,
    ) -> float:
        """Calculate confidence in a correlation estimate."""
        confidence = 0.5

        # Magnitude contribution
        abs_corr = abs(correlation)
        if abs_corr > 0.7:
            confidence += 0.25
        elif abs_corr > 0.5:
            confidence += 0.15

        # Regime contribution
        if regime == CorrelationRegime.CRISIS:
            confidence += 0.1
        elif regime == CorrelationRegime.DIVERGENT:
            confidence += 0.05

        # Sample size contribution
        n = self._config["lookback_days"]
        if n > 60:
            confidence += 0.1
        elif n > 30:
            confidence += 0.05

        return min(0.95, confidence)

    async def _generate_hedge_signals(
        self,
        opportunities: List[CorrelationEstimate],
        market_data: Dict[str, Any],
    ) -> List[HedgeSignal]:
        """
        Generate hedge signals from opportunities.

        Args:
            opportunities: List of correlation opportunities
            market_data: Current market data

        Returns:
            List of hedge signals
        """
        signals = []

        for opp in opportunities:
            # Calculate hedge ratio
            hedge_ratio = self._calculate_hedge_ratio(opp)

            if hedge_ratio < self._config["min_position_size"]:
                continue

            # Determine direction
            direction = self._determine_hedge_direction(opp)

            # Calculate position size
            size = hedge_ratio * self._config["max_position_size"]

            # Get current prices
            price1 = market_data.get("prices", {}).get(opp.asset1, 0)
            price2 = market_data.get("prices", {}).get(opp.asset2, 0)

            if price1 <= 0 or price2 <= 0:
                continue

            # Calculate confidence
            confidence = self._calculate_signal_confidence(opp)

            if confidence < self.config.min_confidence:
                continue

            # Calculate stop loss and take profit
            stop_loss = self._calculate_correlation_stop(opp, price1, price2)
            take_profit = self._calculate_correlation_target(opp, price1, price2)

            signal = HedgeSignal(
                hedge_type=HedgeType.CORRELATION,
                direction=direction,
                size=size,
                entry_price=price1,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Correlation hedge: {opp.asset1} vs {opp.asset2} (r={opp.correlation:.2f})",
                metadata={
                    "asset1": opp.asset1,
                    "asset2": opp.asset2,
                    "correlation": opp.correlation,
                    "hedge_ratio": hedge_ratio,
                    "regime": opp.regime.value,
                    "method": opp.method.value,
                }
            )

            signals.append(signal)

        return signals

    def _calculate_hedge_ratio(self, opportunity: CorrelationEstimate) -> float:
        """Calculate hedge ratio for a correlation opportunity."""
        # Base hedge ratio
        base_ratio = abs(opportunity.correlation)

        # Adjust for regime
        if opportunity.regime == CorrelationRegime.CRISIS:
            base_ratio *= 1.2
        elif opportunity.regime == CorrelationRegime.DIVERGENT:
            base_ratio *= 0.8

        # Adjust for confidence
        confidence = self._calculate_correlation_confidence(
            opportunity.correlation,
            opportunity.regime
        )
        base_ratio *= confidence

        # Apply diversification penalty
        base_ratio *= (1 - self._config["diversification_penalty"])

        return max(self._config["min_position_size"], min(self._config["max_position_size"], base_ratio))

    def _determine_hedge_direction(self, opportunity: CorrelationEstimate) -> HedgeDirection:
        """Determine hedge direction."""
        # If correlation is positive, go long one and short the other
        # If correlation is negative, go long both or short both
        if opportunity.correlation > 0:
            return HedgeDirection.LONG  # Will be implemented as pair trade
        else:
            return HedgeDirection.SHORT  # Will be implemented as pair trade

    def _calculate_signal_confidence(self, opportunity: CorrelationEstimate) -> float:
        """Calculate confidence in a hedge signal."""
        confidence = self._calculate_correlation_confidence(
            opportunity.correlation,
            opportunity.regime
        )

        # Adjust for hedge ratio
        hedge_ratio = self._calculate_hedge_ratio(opportunity)
        if hedge_ratio > 0.1:
            confidence += 0.1

        return min(0.95, confidence)

    def _calculate_correlation_stop(
        self,
        opportunity: CorrelationEstimate,
        price1: float,
        price2: float,
    ) -> Optional[float]:
        """Calculate stop loss for correlation hedge."""
        # Use correlation break as stop signal
        stop_threshold = 0.2  # Correlation drop threshold
        if abs(opportunity.correlation) < stop_threshold:
            return None

        # Calculate stop price based on volatility
        vol1 = self._calculate_volatility(opportunity.asset1)
        vol2 = self._calculate_volatility(opportunity.asset2)

        stop_pct = self._config["stop_loss_pct"] * (1 + abs(vol1 - vol2))

        if opportunity.correlation > 0:
            return price1 * (1 - stop_pct)
        else:
            return price1 * (1 + stop_pct)

    def _calculate_correlation_target(
        self,
        opportunity: CorrelationEstimate,
        price1: float,
        price2: float,
    ) -> Optional[float]:
        """Calculate take profit for correlation hedge."""
        target_pct = self._config["take_profit_pct"] * abs(opportunity.correlation)

        if opportunity.correlation > 0:
            return price1 * (1 + target_pct)
        else:
            return price1 * (1 - target_pct)

    def _calculate_volatility(self, symbol: str) -> float:
        """Calculate volatility for a symbol."""
        if symbol not in self._returns_data or len(self._returns_data[symbol]) < 10:
            return 0.2

        returns = self._returns_data[symbol][-30:]
        return np.std(returns)

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.asset1 in market_data.get("prices", {}):
                    position.current_price1 = market_data["prices"][position.asset1]
                if position.asset2 in market_data.get("prices", {}):
                    position.current_price2 = market_data["prices"][position.asset2]

                # Calculate PnL for pair trade
                position.pnl = (
                    (position.current_price1 - position.entry_price1) -
                    (position.current_price2 - position.entry_price2) * position.hedge_ratio
                ) * position.size
                position.pnl_pct = position.pnl / (position.entry_price1 * position.size) * 100 if position.entry_price1 > 0 else 0
                position.last_update = datetime.utcnow()

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._correlation_matrix.assets:
                matrix = self._correlation_matrix.matrix
                if matrix.size > 0:
                    n = matrix.shape[0]
                    if n > 1:
                        triu_indices = np.triu_indices_from(matrix, k=1)
                        avg_corr = np.mean(matrix[triu_indices])
                        self._performance["average_correlation"] = avg_corr

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "average_correlation": self._performance["average_correlation"],
                "correlation_exposure_reduction": self._performance["correlation_exposure_reduction"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "regime": self._correlation_matrix.regime.value if self._correlation_matrix.assets else "unknown",
                "assets": len(self._correlation_matrix.assets),
                "config": self._config,
            }

    def get_correlation_matrix(self) -> Dict[str, Any]:
        """Get current correlation matrix."""
        return self._correlation_matrix.to_dict()

    def get_correlation_estimate(self, asset1: str, asset2: str) -> Optional[CorrelationEstimate]:
        """Get correlation estimate for a pair."""
        if not self._correlation_matrix.assets:
            return None

        try:
            i = self._correlation_matrix.assets.index(asset1)
            j = self._correlation_matrix.assets.index(asset2)
            corr = self._correlation_matrix.matrix[i, j]

            return CorrelationEstimate(
                asset1=asset1,
                asset2=asset2,
                correlation=corr,
                method=self.correlation_type,
                regime=self._determine_regime_from_value(corr),
            )
        except (ValueError, IndexError):
            return None

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("correlation_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("correlation_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("correlation_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "CorrelationHedgeStrategy",
    "CorrelationEstimate",
    "CorrelationMatrix",
    "CorrelationHedgePosition",
    "CorrelationType",
    "CorrelationHedgeStyle",
    "CorrelationRegime",
]

logger.info("correlation_hedge_module_loaded", version="3.0.0")
