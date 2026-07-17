# trading/bots/ai_bot/strategies/strategy_selector.py
# NEXUS AI TRADING SYSTEM - Strategy Selector
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Strategy Selector for NEXUS AI Trading Bot.
Provides intelligent strategy selection and switching including:
- Market regime detection
- Strategy performance tracking
- Adaptive strategy selection
- Strategy ranking and scoring
- Automated strategy switching
- Performance-based optimization
- Multi-strategy portfolio management
- Risk-adjusted selection
"""

import asyncio
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyType
from trading.bots.ai_bot.strategies.strategy_factory import StrategyFactory, StrategyCategory
from trading.bots.ai_bot.market_data.market_data_provider import MarketDataProvider
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.selector")


# ============================================================================
# Enums & Constants
# ============================================================================

class SelectionMode(str, Enum):
    """Selection modes."""
    STATIC = "static"              # Always use the same strategy
    ADAPTIVE = "adaptive"          # Adapt based on market conditions
    PERFORMANCE = "performance"    # Select best performing
    ROTATION = "rotation"          # Rotate through strategies
    ENSEMBLE = "ensemble"          # Use ensemble of strategies
    HYBRID = "hybrid"              # Hybrid selection


class SelectionCriteria(str, Enum):
    """Selection criteria."""
    MAXIMIZE_PROFIT = "maximize_profit"
    MINIMIZE_RISK = "minimize_risk"
    BALANCED = "balanced"
    MAXIMIZE_SHARPE = "maximize_sharpe"
    MINIMIZE_DRAWDOWN = "minimize_drawdown"
    MAXIMIZE_WIN_RATE = "maximize_win_rate"
    CUSTOM = "custom"


@dataclass
class StrategyScore:
    """Strategy score data."""
    name: str
    score: float
    rank: int
    criteria_scores: Dict[str, float]
    performance_metrics: Dict[str, float]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketRegime:
    """Market regime data."""
    regime: str
    confidence: float
    indicators: Dict[str, float]
    timestamp: datetime
    duration_days: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySelection:
    """Strategy selection result."""
    selected_strategy: str
    selection_mode: SelectionMode
    scores: List[StrategyScore]
    regime: MarketRegime
    confidence: float
    reason: str
    alternatives: List[str]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Strategy Selector
# ============================================================================

class StrategySelector:
    """
    Strategy Selector for NEXUS AI Trading Bot.
    Provides intelligent strategy selection and switching.
    """

    def __init__(
        self,
        market_data_provider: MarketDataProvider,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize strategy selector.

        Args:
            market_data_provider: Market data provider
            config: Configuration dictionary
        """
        self.market_data = market_data_provider
        self.config = config or {}

        # Strategy factory
        self.strategy_factory = StrategyFactory()

        # Selection configuration
        self.mode = SelectionMode(self.config.get("mode", "adaptive"))
        self.criteria = SelectionCriteria(self.config.get("criteria", "balanced"))
        self.update_frequency = self.config.get("update_frequency", 60)  # seconds
        self.lookback_period = self.config.get("lookback_period", 100)
        self.min_performance_period = self.config.get("min_performance_period", 20)
        self.switch_threshold = self.config.get("switch_threshold", 0.1)
        self.ensemble_size = self.config.get("ensemble_size", 3)

        # Strategy tracking
        self._strategy_performance: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._strategy_scores: Dict[str, List[StrategyScore]] = defaultdict(list)
        self._active_strategies: Set[str] = set()
        self._strategy_weights: Dict[str, float] = {}

        # Market regime tracking
        self._current_regime: Optional[MarketRegime] = None
        self._regime_history: List[MarketRegime] = []
        self._regime_detector = self._create_regime_detector()

        # Selection history
        self._selection_history: List[StrategySelection] = []
        self._current_selection: Optional[StrategySelection] = None

        # Performance metrics
        self._performance = {
            "selections_performed": 0,
            "switches": 0,
            "average_selection_time_ms": 0.0,
            "selection_accuracy": 0.0,
            "by_mode": defaultdict(int),
            "by_criteria": defaultdict(int),
        }

        # State management
        self._running = False
        self._lock = asyncio.Lock()

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "selection": [],
            "switch": [],
            "regime_change": [],
            "error": [],
        }

        logger.info(
            "StrategySelector initialized",
            extra={
                "mode": self.mode.value,
                "criteria": self.criteria.value,
                "update_frequency": self.update_frequency,
            }
        )

    # ========================================================================
    # Strategy Tracking
    # ========================================================================

    def register_strategy(self, name: str, strategy: BaseStrategy) -> None:
        """
        Register a strategy for selection.

        Args:
            name: Strategy name
            strategy: Strategy instance
        """
        if name not in self._active_strategies:
            self._active_strategies.add(name)
            self._strategy_weights[name] = 1.0 / len(self._active_strategies)

            logger.info(f"Strategy registered for selection: {name}")

            # Register event handlers
            strategy.on("trade", self._handle_strategy_trade)
            strategy.on("position", self._handle_strategy_position)
            strategy.on("error", self._handle_strategy_error)

    def unregister_strategy(self, name: str) -> None:
        """
        Unregister a strategy.

        Args:
            name: Strategy name
        """
        if name in self._active_strategies:
            self._active_strategies.remove(name)
            self._strategy_weights.pop(name, None)
            self._strategy_performance.pop(name, None)
            self._strategy_scores.pop(name, None)

            logger.info(f"Strategy unregistered: {name}")

    def update_strategy_performance(
        self,
        name: str,
        metrics: Dict[str, float],
    ) -> None:
        """
        Update strategy performance metrics.

        Args:
            name: Strategy name
            metrics: Performance metrics
        """
        if name in self._active_strategies:
            self._strategy_performance[name].append({
                "timestamp": datetime.utcnow(),
                "metrics": metrics,
            })

    # ========================================================================
    # Strategy Selection
    # ========================================================================

    async def select_strategy(
        self,
        symbol: str,
        forced_mode: Optional[SelectionMode] = None,
    ) -> StrategySelection:
        """
        Select the best strategy for current market conditions.

        Args:
            symbol: Trading symbol
            forced_mode: Force specific selection mode

        Returns:
            StrategySelection
        """
        start_time = time.time()

        try:
            # Detect market regime
            regime = await self._detect_market_regime(symbol)

            # Get available strategies
            strategies = self._get_available_strategies()

            if not strategies:
                return StrategySelection(
                    selected_strategy="none",
                    selection_mode=forced_mode or self.mode,
                    scores=[],
                    regime=regime,
                    confidence=0.0,
                    reason="No strategies available",
                    alternatives=[],
                    timestamp=datetime.utcnow(),
                )

            # Score strategies
            scores = await self._score_strategies(strategies, regime, symbol)

            # Select strategy based on mode
            mode = forced_mode or self.mode

            if mode == SelectionMode.STATIC:
                selected = self._select_static(scores, strategies)
            elif mode == SelectionMode.ADAPTIVE:
                selected = self._select_adaptive(scores, regime)
            elif mode == SelectionMode.PERFORMANCE:
                selected = self._select_performance(scores)
            elif mode == SelectionMode.ROTATION:
                selected = self._select_rotation(scores)
            elif mode == SelectionMode.ENSEMBLE:
                selected = self._select_ensemble(scores)
            else:
                selected = self._select_hybrid(scores, regime)

            # Create selection result
            selection = StrategySelection(
                selected_strategy=selected,
                selection_mode=mode,
                scores=scores,
                regime=regime,
                confidence=self._calculate_selection_confidence(scores, selected),
                reason=self._generate_selection_reason(scores, selected, regime),
                alternatives=[s.name for s in scores[:3] if s.name != selected],
                timestamp=datetime.utcnow(),
                metadata={
                    "symbol": symbol,
                    "strategies_available": len(strategies),
                    "scores_count": len(scores),
                },
            )

            # Check if we should switch
            if self._should_switch(selection):
                self._perform_switch(selection)

            self._selection_history.append(selection)
            self._current_selection = selection

            # Update performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._performance["selections_performed"] += 1
            self._performance["by_mode"][mode.value] += 1
            self._performance["average_selection_time_ms"] = (
                (self._performance["average_selection_time_ms"] *
                 (self._performance["selections_performed"] - 1) +
                 elapsed_ms) / self._performance["selections_performed"]
            )

            # Emit event
            self._emit_event("selection", selection)

            logger.info(
                f"Strategy selected: {selected}",
                extra={
                    "mode": mode.value,
                    "regime": regime.regime,
                    "confidence": selection.confidence,
                }
            )

            return selection

        except Exception as e:
            logger.error(f"Error selecting strategy: {e}")
            self._emit_event("error", {"error": str(e)})

            # Return current selection or default
            if self._current_selection:
                return self._current_selection

            return StrategySelection(
                selected_strategy="default",
                selection_mode=forced_mode or self.mode,
                scores=[],
                regime=MarketRegime(
                    regime="unknown",
                    confidence=0.0,
                    indicators={},
                    timestamp=datetime.utcnow(),
                ),
                confidence=0.0,
                reason=f"Error: {str(e)}",
                alternatives=[],
                timestamp=datetime.utcnow(),
                metadata={"error": str(e)},
            )

    # ========================================================================
    # Selection Strategies
    # ========================================================================

    def _select_static(
        self,
        scores: List[StrategyScore],
        strategies: List[str],
    ) -> str:
        """
        Static selection (always use the same strategy).

        Args:
            scores: Strategy scores
            strategies: Available strategies

        Returns:
            Selected strategy name
        """
        # Use the first strategy or the one with highest historical score
        if scores:
            return scores[0].name
        return strategies[0] if strategies else "none"

    def _select_adaptive(
        self,
        scores: List[StrategyScore],
        regime: MarketRegime,
    ) -> str:
        """
        Adaptive selection based on market regime.

        Args:
            scores: Strategy scores
            regime: Market regime

        Returns:
            Selected strategy name
        """
        # Weight scores based on regime
        regime_weights = self._get_regime_weights(regime)

        for score in scores:
            # Apply regime-based adjustment
            regime_factor = regime_weights.get(score.name, 1.0)
            score.score *= regime_factor

        # Sort by adjusted score
        scores.sort(key=lambda x: x.score, reverse=True)

        return scores[0].name if scores else "none"

    def _select_performance(
        self,
        scores: List[StrategyScore],
    ) -> str:
        """
        Selection based on performance.

        Args:
            scores: Strategy scores

        Returns:
            Selected strategy name
        """
        # Sort by performance score
        scores.sort(key=lambda x: x.score, reverse=True)

        return scores[0].name if scores else "none"

    def _select_rotation(
        self,
        scores: List[StrategyScore],
    ) -> str:
        """
        Rotate through strategies.

        Args:
            scores: Strategy scores

        Returns:
            Selected strategy name
        """
        if not scores:
            return "none"

        # Get last selected
        last_selected = self._current_selection.selected_strategy if self._current_selection else None

        # Find next strategy in rotation
        strategy_names = [s.name for s in scores]

        if last_selected in strategy_names:
            idx = strategy_names.index(last_selected)
            next_idx = (idx + 1) % len(strategy_names)
            return strategy_names[next_idx]

        return strategy_names[0]

    def _select_ensemble(
        self,
        scores: List[StrategyScore],
    ) -> str:
        """
        Ensemble selection (use top N strategies).

        Args:
            scores: Strategy scores

        Returns:
            Selected strategy name (for compatibility)
        """
        # For ensemble, we return the top strategy but weights are set for all
        scores.sort(key=lambda x: x.score, reverse=True)

        # Update weights for ensemble
        top_n = min(self.ensemble_size, len(scores))
        total_score = sum(s.score for s in scores[:top_n])

        if total_score > 0:
            for i, score in enumerate(scores[:top_n]):
                self._strategy_weights[score.name] = score.score / total_score
        else:
            for score in scores[:top_n]:
                self._strategy_weights[score.name] = 1.0 / top_n

        return scores[0].name if scores else "none"

    def _select_hybrid(
        self,
        scores: List[StrategyScore],
        regime: MarketRegime,
    ) -> str:
        """
        Hybrid selection combining multiple criteria.

        Args:
            scores: Strategy scores
            regime: Market regime

        Returns:
            Selected strategy name
        """
        # Combine multiple selection methods
        method_scores = {}

        # Performance-based
        perf_score = self._select_performance(scores)
        method_scores[perf_score] = method_scores.get(perf_score, 0) + 0.4

        # Regime-based
        regime_score = self._select_adaptive(scores, regime)
        method_scores[regime_score] = method_scores.get(regime_score, 0) + 0.3

        # Rotation
        rot_score = self._select_rotation(scores)
        method_scores[rot_score] = method_scores.get(rot_score, 0) + 0.3

        # Select highest combined score
        return max(method_scores.items(), key=lambda x: x[1])[0]

    # ========================================================================
    # Strategy Scoring
    # ========================================================================

    async def _score_strategies(
        self,
        strategies: List[str],
        regime: MarketRegime,
        symbol: str,
    ) -> List[StrategyScore]:
        """
        Score all strategies.

        Args:
            strategies: List of strategy names
            regime: Market regime
            symbol: Trading symbol

        Returns:
            List of StrategyScore
        """
        scores = []

        for name in strategies:
            try:
                # Get performance metrics
                metrics = self._get_strategy_metrics(name)

                if not metrics:
                    # Use default score
                    score = 0.5
                    criteria_scores = {"default": 0.5}
                else:
                    # Calculate scores based on criteria
                    criteria_scores = self._calculate_criteria_scores(metrics, regime)

                    # Calculate overall score
                    score = self._calculate_overall_score(criteria_scores)

                # Create score object
                strategy_score = StrategyScore(
                    name=name,
                    score=score,
                    rank=0,
                    criteria_scores=criteria_scores,
                    performance_metrics=metrics or {},
                    timestamp=datetime.utcnow(),
                    metadata={
                        "symbol": symbol,
                        "regime": regime.regime,
                    },
                )

                scores.append(strategy_score)

                # Store in history
                self._strategy_scores[name].append(strategy_score)

            except Exception as e:
                logger.error(f"Error scoring strategy {name}: {e}")

        # Rank scores
        scores.sort(key=lambda x: x.score, reverse=True)
        for i, score in enumerate(scores):
            score.rank = i + 1

        return scores

    def _calculate_criteria_scores(
        self,
        metrics: Dict[str, float],
        regime: MarketRegime,
    ) -> Dict[str, float]:
        """
        Calculate scores for each criterion.

        Args:
            metrics: Strategy metrics
            regime: Market regime

        Returns:
            Dict of criterion -> score
        """
        scores = {}

        # Profit criteria (30%)
        total_pnl = metrics.get("total_pnl", 0)
        max_pnl = max(metrics.get("max_pnl", 1), 1)
        scores["profit"] = self._normalize_score(total_pnl / max_pnl)

        # Risk criteria (25%)
        max_drawdown = metrics.get("max_drawdown", 0.5)
        scores["risk"] = 1 - self._normalize_score(max_drawdown)

        # Win rate criteria (20%)
        win_rate = metrics.get("win_rate", 0.5)
        scores["win_rate"] = self._normalize_score(win_rate)

        # Sharpe ratio criteria (15%)
        sharpe = metrics.get("sharpe_ratio", 0.5)
        scores["sharpe"] = self._normalize_score(sharpe / 2)

        # Consistency criteria (10%)
        volatility = metrics.get("volatility", 0.5)
        scores["consistency"] = 1 - self._normalize_score(volatility)

        # Adjust for regime
        regime_adjustment = self._get_regime_adjustment(regime)

        for key in scores:
            if key in regime_adjustment:
                scores[key] *= regime_adjustment[key]

        return scores

    def _calculate_overall_score(self, criteria_scores: Dict[str, float]) -> float:
        """
        Calculate overall score from criteria scores.

        Args:
            criteria_scores: Dict of criterion -> score

        Returns:
            Overall score
        """
        # Weighted average based on selection criteria
        weights = {
            "profit": 0.30,
            "risk": 0.25,
            "win_rate": 0.20,
            "sharpe": 0.15,
            "consistency": 0.10,
        }

        total_score = 0
        total_weight = 0

        for criterion, score in criteria_scores.items():
            weight = weights.get(criterion, 0.1)
            total_score += score * weight
            total_weight += weight

        if total_weight > 0:
            return total_score / total_weight

        return 0.5

    def _normalize_score(self, value: float) -> float:
        """
        Normalize a score to 0-1 range.

        Args:
            value: Raw value

        Returns:
            Normalized score
        """
        return max(0.0, min(1.0, (value + 1) / 2))

    # ========================================================================
    # Market Regime Detection
    # ========================================================================

    async def _detect_market_regime(self, symbol: str) -> MarketRegime:
        """
        Detect current market regime.

        Args:
            symbol: Trading symbol

        Returns:
            MarketRegime
        """
        try:
            # Get market data
            data = await self._get_market_data(symbol)

            if data is None or len(data) < 50:
                return MarketRegime(
                    regime="unknown",
                    confidence=0.0,
                    indicators={},
                    timestamp=datetime.utcnow(),
                )

            close = data['close'].values
            high = data['high'].values
            low = data['low'].values
            volume = data['volume'].values

            # Calculate indicators
            indicators = self._calculate_regime_indicators(close, high, low, volume)

            # Determine regime
            regime = self._classify_regime(indicators)

            # Calculate confidence
            confidence = self._calculate_regime_confidence(indicators)

            # Update regime history
            if self._current_regime:
                duration_days = (datetime.utcnow() - self._current_regime.timestamp).days
            else:
                duration_days = 0

            # Create regime object
            market_regime = MarketRegime(
                regime=regime,
                confidence=confidence,
                indicators=indicators,
                timestamp=datetime.utcnow(),
                duration_days=duration_days,
                metadata={
                    "symbol": symbol,
                    "data_points": len(data),
                },
            )

            # Check for regime change
            if self._current_regime and self._current_regime.regime != regime:
                self._emit_event("regime_change", {
                    "old_regime": self._current_regime.regime,
                    "new_regime": regime,
                    "confidence": confidence,
                })

            self._current_regime = market_regime
            self._regime_history.append(market_regime)

            return market_regime

        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return MarketRegime(
                regime="unknown",
                confidence=0.0,
                indicators={},
                timestamp=datetime.utcnow(),
                metadata={"error": str(e)},
            )

    def _calculate_regime_indicators(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> Dict[str, float]:
        """
        Calculate regime indicators.

        Args:
            close: Close prices
            high: High prices
            low: Low prices
            volume: Volume data

        Returns:
            Dict of indicator -> value
        """
        indicators = {}

        # Trend indicators
        if len(close) > 20:
            # Moving average slope
            ma20 = np.mean(close[-20:])
            ma50 = np.mean(close[-50:]) if len(close) >= 50 else ma20
            indicators["trend_strength"] = (ma20 - ma50) / ma50

            # ADX
            adx = talib.ADX(high, low, close, timeperiod=14)
            indicators["adx"] = adx[-1] if adx[-1] is not None else 25

            # RSI
            rsi = talib.RSI(close, timeperiod=14)
            indicators["rsi"] = rsi[-1] if rsi[-1] is not None else 50

        # Volatility indicators
        if len(close) > 20:
            returns = np.diff(np.log(close))
            indicators["volatility"] = np.std(returns[-20:]) * np.sqrt(252)

            # Bollinger Band width
            upper, middle, lower = talib.BBANDS(close, timeperiod=20)
            if upper[-1] is not None and middle[-1] != 0:
                indicators["bb_width"] = (upper[-1] - lower[-1]) / middle[-1]
            else:
                indicators["bb_width"] = 0

        # Volume indicators
        if len(volume) > 20:
            avg_volume = np.mean(volume[-20:])
            indicators["volume_trend"] = volume[-1] / avg_volume

        # Price momentum
        if len(close) > 10:
            indicators["momentum"] = (close[-1] - close[-10]) / close[-10]

        return indicators

    def _classify_regime(self, indicators: Dict[str, float]) -> str:
        """
        Classify market regime from indicators.

        Args:
            indicators: Dict of indicators

        Returns:
            Regime classification
        """
        trend = indicators.get("trend_strength", 0)
        rsi = indicators.get("rsi", 50)
        adx = indicators.get("adx", 25)
        volatility = indicators.get("volatility", 0.02)
        bb_width = indicators.get("bb_width", 0.05)
        momentum = indicators.get("momentum", 0)

        # Trending regime
        if abs(trend) > 0.02 and adx > 25:
            if trend > 0:
                if abs(momentum) > 0.03:
                    return "strong_uptrend"
                return "uptrend"
            else:
                if abs(momentum) > 0.03:
                    return "strong_downtrend"
                return "downtrend"

        # Ranging regime
        if bb_width < 0.05 and abs(trend) < 0.02:
            if rsi > 70:
                return "range_overbought"
            elif rsi < 30:
                return "range_oversold"
            return "ranging"

        # Volatile regime
        if volatility > 0.04:
            if abs(trend) > 0.02:
                return "volatile_trending"
            return "volatile_choppy"

        # Mixed regime
        if adx > 25 and bb_width > 0.05:
            if rsi > 60:
                return "bullish_breakout"
            elif rsi < 40:
                return "bearish_breakout"

        return "neutral"

    def _calculate_regime_confidence(self, indicators: Dict[str, float]) -> float:
        """
        Calculate confidence in regime classification.

        Args:
            indicators: Dict of indicators

        Returns:
            Confidence (0-1)
        """
        confidence = 0.0

        # Check indicator consistency
        if "trend_strength" in indicators:
            trend = abs(indicators["trend_strength"])
            confidence += min(trend * 20, 0.3)

        if "adx" in indicators:
            adx = indicators["adx"]
            confidence += min((adx - 20) / 30, 0.3) if adx > 20 else 0

        if "volatility" in indicators:
            vol = indicators["volatility"]
            confidence += min(vol * 10, 0.2)

        if "bb_width" in indicators:
            width = indicators["bb_width"]
            if width < 0.03:
                confidence += 0.2

        # Ensure we have enough indicators
        indicator_count = len([v for v in indicators.values() if v is not None])
        confidence *= min(indicator_count / 4, 1.0)

        return min(confidence, 1.0)

    def _create_regime_detector(self):
        """Create regime detector."""
        # Would implement more sophisticated regime detection
        return None

    # ========================================================================
    # Strategy Switching
    # ========================================================================

    def _should_switch(self, selection: StrategySelection) -> bool:
        """
        Check if we should switch strategies.

        Args:
            selection: Current selection

        Returns:
            True if should switch
        """
        if not self._current_selection:
            return True

        # Check if selected strategy changed
        if selection.selected_strategy != self._current_selection.selected_strategy:
            # Check if improvement is significant
            current_score = self._get_strategy_score(self._current_selection.selected_strategy)
            new_score = self._get_strategy_score(selection.selected_strategy)

            if new_score - current_score > self.switch_threshold:
                return True

        return False

    def _perform_switch(self, selection: StrategySelection) -> None:
        """
        Perform strategy switch.

        Args:
            selection: New selection
        """
        old_strategy = self._current_selection.selected_strategy if self._current_selection else None
        new_strategy = selection.selected_strategy

        self._performance["switches"] += 1

        logger.info(
            f"Switching strategy: {old_strategy} -> {new_strategy}",
            extra={
                "old_score": self._get_strategy_score(old_strategy) if old_strategy else 0,
                "new_score": self._get_strategy_score(new_strategy),
                "reason": selection.reason,
            }
        )

        self._emit_event("switch", {
            "old_strategy": old_strategy,
            "new_strategy": new_strategy,
            "reason": selection.reason,
            "confidence": selection.confidence,
        })

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _get_available_strategies(self) -> List[str]:
        """
        Get available strategies.

        Returns:
            List of strategy names
        """
        strategies = []

        for name in self._active_strategies:
            # Check if strategy is available
            if name in self._strategy_scores:
                strategies.append(name)

        return strategies

    def _get_strategy_metrics(self, name: str) -> Optional[Dict[str, float]]:
        """
        Get strategy performance metrics.

        Args:
            name: Strategy name

        Returns:
            Dict of metrics
        """
        if name not in self._strategy_performance:
            return None

        history = self._strategy_performance[name]

        if len(history) < self.min_performance_period:
            return None

        # Calculate metrics from history
        metrics = {
            "total_pnl": 0,
            "max_pnl": 0,
            "win_rate": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "volatility": 0,
            "consistency": 0,
        }

        try:
            # Extract PnL from history
            pnl_values = []
            wins = 0
            losses = 0

            for entry in history:
                if "pnl" in entry["metrics"]:
                    pnl = entry["metrics"]["pnl"]
                    pnl_values.append(pnl)

                    if pnl > 0:
                        wins += 1
                    elif pnl < 0:
                        losses += 1

            if pnl_values:
                metrics["total_pnl"] = sum(pnl_values)
                metrics["max_pnl"] = max(pnl_values)
                metrics["win_rate"] = wins / (wins + losses) if (wins + losses) > 0 else 0

                # Calculate volatility
                metrics["volatility"] = np.std(pnl_values) if len(pnl_values) > 1 else 0

                # Calculate max drawdown
                cumulative = np.cumsum(pnl_values)
                peak = np.maximum.accumulate(cumulative)
                drawdown = (peak - cumulative) / (peak + 1e-10)
                metrics["max_drawdown"] = np.max(drawdown)

                # Calculate Sharpe ratio
                if metrics["volatility"] > 0:
                    metrics["sharpe_ratio"] = np.mean(pnl_values) / metrics["volatility"] * np.sqrt(252)

                # Calculate consistency
                if len(pnl_values) > 1:
                    metrics["consistency"] = 1 - np.std(pnl_values) / (np.abs(np.mean(pnl_values)) + 1e-10)
                else:
                    metrics["consistency"] = 1.0

        except Exception as e:
            logger.error(f"Error calculating metrics for {name}: {e}")

        return metrics

    def _get_strategy_score(self, name: str) -> float:
        """
        Get strategy score.

        Args:
            name: Strategy name

        Returns:
            Score
        """
        if name in self._strategy_scores and self._strategy_scores[name]:
            return self._strategy_scores[name][-1].score

        return 0.5

    def _get_regime_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Get regime-based weights.

        Args:
            regime: Market regime

        Returns:
            Dict of strategy -> weight
        """
        # Map regime to strategy preferences
        regime_weights = {
            "strong_uptrend": {
                "momentum": 1.5,
                "trend_following": 1.4,
                "breakout": 1.3,
                "hybrid": 1.2,
                "mean_reversion": 0.5,
                "scalping": 0.8,
            },
            "downtrend": {
                "momentum": 0.5,
                "trend_following": 0.8,
                "breakout": 0.6,
                "hybrid": 1.0,
                "mean_reversion": 1.3,
                "scalping": 0.7,
            },
            "ranging": {
                "mean_reversion": 1.5,
                "grid_trading": 1.4,
                "scalping": 1.3,
                "hybrid": 1.2,
                "momentum": 0.5,
                "trend_following": 0.4,
            },
            "volatile_choppy": {
                "scalping": 1.4,
                "hybrid": 1.3,
                "mean_reversion": 1.2,
                "grid_trading": 1.1,
                "momentum": 0.6,
                "trend_following": 0.5,
            },
            "neutral": {
                "hybrid": 1.3,
                "scalping": 1.2,
                "mean_reversion": 1.1,
                "momentum": 1.0,
                "trend_following": 1.0,
                "grid_trading": 1.0,
            },
        }

        return regime_weights.get(regime.regime, {name: 1.0 for name in self._active_strategies})

    def _get_regime_adjustment(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Get regime-based criteria adjustment.

        Args:
            regime: Market regime

        Returns:
            Dict of criterion -> adjustment
        """
        adjustments = {
            "strong_uptrend": {
                "profit": 1.3,
                "risk": 1.1,
                "win_rate": 1.2,
                "sharpe": 1.1,
                "consistency": 1.0,
            },
            "downtrend": {
                "profit": 0.8,
                "risk": 0.9,
                "win_rate": 0.8,
                "sharpe": 0.9,
                "consistency": 1.0,
            },
            "ranging": {
                "profit": 1.0,
                "risk": 1.2,
                "win_rate": 1.1,
                "sharpe": 1.0,
                "consistency": 1.3,
            },
            "volatile_choppy": {
                "profit": 0.9,
                "risk": 0.7,
                "win_rate": 0.9,
                "sharpe": 0.8,
                "consistency": 0.8,
            },
            "neutral": {
                "profit": 1.0,
                "risk": 1.0,
                "win_rate": 1.0,
                "sharpe": 1.0,
                "consistency": 1.0,
            },
        }

        return adjustments.get(regime.regime, {
            "profit": 1.0,
            "risk": 1.0,
            "win_rate": 1.0,
            "sharpe": 1.0,
            "consistency": 1.0,
        })

    def _calculate_selection_confidence(
        self,
        scores: List[StrategyScore],
        selected: str,
    ) -> float:
        """
        Calculate confidence in selection.

        Args:
            scores: Strategy scores
            selected: Selected strategy

        Returns:
            Confidence (0-1)
        """
        if not scores:
            return 0.0

        # Find selected strategy score
        selected_score = None
        for score in scores:
            if score.name == selected:
                selected_score = score.score
                break

        if selected_score is None:
            return 0.0

        # Calculate score difference from average
        avg_score = np.mean([s.score for s in scores])
        std_score = np.std([s.score for s in scores]) + 1e-10

        z_score = (selected_score - avg_score) / std_score

        # Convert to confidence (0-1)
        confidence = 0.5 + 0.5 * min(z_score / 2, 1.0)

        return max(0.0, min(1.0, confidence))

    def _generate_selection_reason(
        self,
        scores: List[StrategyScore],
        selected: str,
        regime: MarketRegime,
    ) -> str:
        """
        Generate selection reason.

        Args:
            scores: Strategy scores
            selected: Selected strategy
            regime: Market regime

        Returns:
            Selection reason
        """
        reasons = []

        # Regime-based reason
        if regime.confidence > 0.7:
            reasons.append(f"Market regime: {regime.regime} (confidence: {regime.confidence:.2f})")

        # Score-based reason
        selected_score = None
        for score in scores:
            if score.name == selected:
                selected_score = score
                break

        if selected_score:
            reasons.append(f"Selected score: {selected_score.score:.3f}")

            # Top criteria
            top_criteria = sorted(
                selected_score.criteria_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:2]

            if top_criteria:
                reasons.append(f"Best criteria: {top_criteria[0][0]} ({top_criteria[0][1]:.2f})")

        # Performance reason
        metrics = self._get_strategy_metrics(selected)
        if metrics:
            win_rate = metrics.get("win_rate", 0)
            if win_rate > 0.6:
                reasons.append(f"High win rate: {win_rate:.1%}")

        return " | ".join(reasons) if reasons else "No specific reason"

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def _handle_strategy_trade(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy trade event.

        Args:
            data: Event data
        """
        # Update performance tracking
        strategy_name = data.get("strategy")
        if strategy_name and strategy_name in self._active_strategies:
            self.update_strategy_performance(strategy_name, data.get("metrics", {}))

    def _handle_strategy_position(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy position event.

        Args:
            data: Event data
        """
        pass

    def _handle_strategy_error(self, data: Dict[str, Any]) -> None:
        """
        Handle strategy error event.

        Args:
            data: Event data
        """
        self._emit_event("error", data)

    # ========================================================================
    # Event System
    # ========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler function
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler function
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def _get_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get market data for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            DataFrame with price data
        """
        try:
            return await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe="1h",
                limit=self.lookback_period,
            )
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None

    def get_current_selection(self) -> Optional[StrategySelection]:
        """
        Get current strategy selection.

        Returns:
            StrategySelection or None
        """
        return self._current_selection

    def get_selection_history(self, limit: int = 100) -> List[StrategySelection]:
        """
        Get selection history.

        Args:
            limit: Number of selections

        Returns:
            List of StrategySelection
        """
        return self._selection_history[-limit:]

    def get_strategy_scores(self, name: str, limit: int = 100) -> List[StrategyScore]:
        """
        Get strategy score history.

        Args:
            name: Strategy name
            limit: Number of scores

        Returns:
            List of StrategyScore
        """
        if name in self._strategy_scores:
            return self._strategy_scores[name][-limit:]
        return []

    def get_regime_history(self, limit: int = 100) -> List[MarketRegime]:
        """
        Get regime history.

        Args:
            limit: Number of regimes

        Returns:
            List of MarketRegime
        """
        return self._regime_history[-limit:]

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "active_strategies": len(self._active_strategies),
            "current_selection": self._current_selection.selected_strategy if self._current_selection else None,
            "current_regime": self._current_regime.regime if self._current_regime else None,
            "selection_history": len(self._selection_history),
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy selector."""
        if self._running:
            return

        self._running = True
        logger.info("StrategySelector started")

    async def stop(self) -> None:
        """Stop the strategy selector."""
        self._running = False

        # Clean up
        async with self._lock:
            self._selection_history.clear()
            self._strategy_performance.clear()

        logger.info("StrategySelector stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_strategy_selector(
    market_data_provider: MarketDataProvider,
    config: Optional[Dict[str, Any]] = None,
) -> StrategySelector:
    """
    Factory function to create a StrategySelector instance.

    Args:
        market_data_provider: Market data provider
        config: Configuration dictionary

    Returns:
        StrategySelector instance
    """
    return StrategySelector(
        market_data_provider=market_data_provider,
        config=config,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the strategy selector
    pass
