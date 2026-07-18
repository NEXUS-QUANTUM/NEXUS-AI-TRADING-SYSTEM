# trading/signals/confidence.py
"""
NEXUS AI TRADING SYSTEM - Signal Confidence Scoring
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides comprehensive confidence scoring for trading signals including:
- Multi-factor confidence calculation
- Historical performance weighting
- Market condition adjustment
- Adaptive confidence calibration
- Ensemble confidence aggregation
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict, deque

import numpy as np

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData
from .base import Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ConfidenceFactor(str, Enum):
    """Factors contributing to signal confidence"""
    HISTORICAL_ACCURACY = "historical_accuracy"
    MARKET_CONDITION = "market_condition"
    INDICATOR_STRENGTH = "indicator_strength"
    MULTIPLE_CONFIRMATIONS = "multiple_confirmations"
    VOLATILITY_ADJUSTMENT = "volatility_adjustment"
    TREND_ALIGNMENT = "trend_alignment"
    VOLUME_CONFIRMATION = "volume_confirmation"
    TIME_DECAY = "time_decay"
    STRATEGY_PERFORMANCE = "strategy_performance"
    ENSEMBLE_AGREEMENT = "ensemble_agreement"
    RISK_ADJUSTMENT = "risk_adjustment"


@dataclass
class ConfidenceConfig:
    """Configuration for confidence scoring"""
    # Weight configuration
    factor_weights: Dict[ConfidenceFactor, float] = field(default_factory=lambda: {
        ConfidenceFactor.HISTORICAL_ACCURACY: 0.25,
        ConfidenceFactor.MARKET_CONDITION: 0.15,
        ConfidenceFactor.INDICATOR_STRENGTH: 0.20,
        ConfidenceFactor.MULTIPLE_CONFIRMATIONS: 0.15,
        ConfidenceFactor.VOLATILITY_ADJUSTMENT: 0.10,
        ConfidenceFactor.TREND_ALIGNMENT: 0.10,
        ConfidenceFactor.VOLUME_CONFIRMATION: 0.05,
    })
    
    # Historical performance
    historical_lookback: int = 100
    historical_weight_decay: float = 0.95
    
    # Calibration
    calibrate_confidence: bool = True
    calibration_window: int = 50
    calibration_min_samples: int = 20
    
    # Adjustment
    min_confidence: float = 0.1
    max_confidence: float = 0.95
    volatility_adjustment_factor: float = 0.5
    time_decay_rate: float = 0.1  # Per hour
    
    # Ensemble
    ensemble_method: str = "weighted_average"  # weighted_average, max, min, median


@dataclass
class ConfidenceResult:
    """Result of confidence scoring"""
    signal: Signal
    confidence: float
    factor_scores: Dict[ConfidenceFactor, float]
    factor_weights: Dict[ConfidenceFactor, float]
    raw_confidence: float
    adjusted_confidence: float
    calibration_factor: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HistoricalPerformance:
    """Historical performance data for confidence calibration"""
    total_signals: int = 0
    successful_signals: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    avg_confidence: float = 0.0
    confidence_accuracy_correlation: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    history: deque = field(default_factory=lambda: deque(maxlen=1000))


# ============================================================================
# CONFIDENCE SCORING ENGINE
# ============================================================================

class ConfidenceScoringEngine:
    """
    Advanced confidence scoring for trading signals.
    
    Features:
    - Multi-factor confidence calculation
    - Historical performance weighting
    - Market condition adjustment
    - Adaptive calibration
    - Ensemble aggregation
    """
    
    def __init__(self, config: Optional[ConfidenceConfig] = None):
        """
        Initialize the confidence scoring engine.
        
        Args:
            config: Confidence configuration
        """
        self.config = config or ConfidenceConfig()
        
        # Performance tracking
        self._performance: Dict[str, HistoricalPerformance] = {}
        self._strategy_performance: Dict[str, HistoricalPerformance] = {}
        
        # Calibration data
        self._calibration_data: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
        self._calibration_factors: Dict[str, float] = {}
        
        # Factor scoring caches
        self._factor_cache: Dict[str, Dict[ConfidenceFactor, float]] = defaultdict(dict)
        
        # Statistics
        self._stats = {
            "total_signals_scored": 0,
            "avg_confidence": 0.0,
            "avg_calibration_factor": 1.0,
            "factor_usage": defaultdict(int),
            "calibration_updates": 0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # CONFIDENCE SCORING
    # ========================================================================
    
    async def calculate_confidence(
        self,
        signal: Signal,
        context: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceResult:
        """
        Calculate confidence score for a signal.
        
        Args:
            signal: Signal to score
            context: Context for scoring
            
        Returns:
            ConfidenceResult: Confidence result
        """
        start_time = time.time()
        context = context or {}
        
        # Calculate factor scores
        factor_scores = await self._calculate_factor_scores(signal, context)
        
        # Calculate raw confidence
        raw_confidence = self._calculate_raw_confidence(factor_scores)
        
        # Apply calibration
        calibration_factor = await self._get_calibration_factor(signal)
        adjusted_confidence = raw_confidence * calibration_factor
        
        # Apply constraints
        adjusted_confidence = max(self.config.min_confidence, adjusted_confidence)
        adjusted_confidence = min(self.config.max_confidence, adjusted_confidence)
        
        # Create result
        result = ConfidenceResult(
            signal=signal,
            confidence=adjusted_confidence,
            factor_scores=factor_scores,
            factor_weights=self.config.factor_weights,
            raw_confidence=raw_confidence,
            adjusted_confidence=adjusted_confidence,
            calibration_factor=calibration_factor,
            metadata={
                "processing_time_ms": (time.time() - start_time) * 1000,
                "context": context.get("metadata", {}),
                "calibration_data": {
                    "samples": len(self._calibration_data.get(signal.symbol, [])),
                    "factor": calibration_factor,
                },
            },
        )
        
        # Update statistics
        self._update_stats(result)
        
        return result
    
    async def calculate_ensemble_confidence(
        self,
        signals: List[Signal],
        context: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceResult:
        """
        Calculate confidence for an ensemble of signals.
        
        Args:
            signals: List of signals
            context: Context for scoring
            
        Returns:
            ConfidenceResult: Ensemble confidence result
        """
        if not signals:
            raise ValueError("No signals provided for ensemble")
        
        # Score each signal
        results = []
        for signal in signals:
            result = await self.calculate_confidence(signal, context)
            results.append(result)
        
        # Aggregate confidence
        confidences = [r.confidence for r in results]
        factor_scores = defaultdict(list)
        
        for result in results:
            for factor, score in result.factor_scores.items():
                factor_scores[factor].append(score)
        
        # Combine using ensemble method
        if self.config.ensemble_method == "weighted_average":
            # Weight by strategy performance if available
            weights = []
            for result in results:
                strategy = result.metadata.get("strategy_id", "default")
                performance = self._strategy_performance.get(strategy)
                if performance and performance.win_rate > 0:
                    weight = performance.win_rate
                else:
                    weight = 1.0
                weights.append(weight)
            
            total_weight = sum(weights)
            combined_confidence = sum(c * w for c, w in zip(confidences, weights)) / total_weight if total_weight > 0 else 0
        
        elif self.config.ensemble_method == "max":
            combined_confidence = max(confidences)
        
        elif self.config.ensemble_method == "min":
            combined_confidence = min(confidences)
        
        elif self.config.ensemble_method == "median":
            combined_confidence = np.median(confidences)
        
        else:
            combined_confidence = sum(confidences) / len(confidences)
        
        # Aggregate factor scores
        aggregated_scores = {
            factor: sum(scores) / len(scores) if scores else 0
            for factor, scores in factor_scores.items()
        }
        
        # Create ensemble signal
        # Use the first signal as base (or merge)
        base_signal = signals[0]
        ensemble_signal = Signal(
            symbol=base_signal.symbol,
            signal_type=base_signal.signal_type,
            strength=base_signal.strength,
            confidence=combined_confidence,
            price=base_signal.price,
            position_size=base_signal.position_size,
            stop_loss=base_signal.stop_loss,
            take_profit=base_signal.take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                "ensemble": True,
                "source_signals": [s.signal_id for s in signals],
                "source_confidences": confidences,
                "ensemble_method": self.config.ensemble_method,
            },
        )
        
        # Create result
        result = ConfidenceResult(
            signal=ensemble_signal,
            confidence=combined_confidence,
            factor_scores=aggregated_scores,
            factor_weights=self.config.factor_weights,
            raw_confidence=combined_confidence,
            adjusted_confidence=combined_confidence,
            calibration_factor=1.0,
            metadata={
                "ensemble": True,
                "source_count": len(signals),
                "source_confidences": confidences,
                "method": self.config.ensemble_method,
            },
        )
        
        return result
    
    # ========================================================================
    # FACTOR SCORING
    # ========================================================================
    
    async def _calculate_factor_scores(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> Dict[ConfidenceFactor, float]:
        """
        Calculate scores for each confidence factor.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            Dict[ConfidenceFactor, float]: Factor scores
        """
        scores = {}
        
        # Historical accuracy
        scores[ConfidenceFactor.HISTORICAL_ACCURACY] = await self._score_historical_accuracy(signal)
        
        # Market condition
        scores[ConfidenceFactor.MARKET_CONDITION] = await self._score_market_condition(signal, context)
        
        # Indicator strength
        scores[ConfidenceFactor.INDICATOR_STRENGTH] = await self._score_indicator_strength(signal, context)
        
        # Multiple confirmations
        scores[ConfidenceFactor.MULTIPLE_CONFIRMATIONS] = await self._score_confirmations(signal, context)
        
        # Volatility adjustment
        scores[ConfidenceFactor.VOLATILITY_ADJUSTMENT] = await self._score_volatility(signal, context)
        
        # Trend alignment
        scores[ConfidenceFactor.TREND_ALIGNMENT] = await self._score_trend_alignment(signal, context)
        
        # Volume confirmation
        scores[ConfidenceFactor.VOLUME_CONFIRMATION] = await self._score_volume(signal, context)
        
        # Strategy performance
        scores[ConfidenceFactor.STRATEGY_PERFORMANCE] = await self._score_strategy_performance(signal, context)
        
        # Time decay
        scores[ConfidenceFactor.TIME_DECAY] = await self._score_time_decay(signal)
        
        # Risk adjustment
        scores[ConfidenceFactor.RISK_ADJUSTMENT] = await self._score_risk_adjustment(signal, context)
        
        return scores
    
    # ========================================================================
    # FACTOR SCORING METHODS
    # ========================================================================
    
    async def _score_historical_accuracy(self, signal: Signal) -> float:
        """
        Score based on historical accuracy of similar signals.
        
        Args:
            signal: Signal
            
        Returns:
            float: Score (0-1)
        """
        key = f"{signal.symbol}_{signal.signal_type.value}"
        performance = self._performance.get(key)
        
        if not performance or performance.total_signals < self.config.calibration_min_samples:
            return 0.5
        
        # Base score on win rate
        base_score = performance.win_rate
        
        # Adjust by confidence-accuracy correlation
        correlation = performance.confidence_accuracy_correlation
        if correlation > 0.3:
            base_score *= (1 + correlation * 0.2)
        elif correlation < -0.3:
            base_score *= (1 + correlation * 0.3)
        
        return max(0.1, min(0.95, base_score))
    
    async def _score_market_condition(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on market conditions.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        market_condition = context.get("market_condition", "neutral")
        
        # Map market condition to score
        condition_scores = {
            "bullish": 0.8,
            "neutral": 0.5,
            "bearish": 0.2,
            "volatile": 0.4,
            "stable": 0.7,
        }
        
        base_score = condition_scores.get(market_condition, 0.5)
        
        # Adjust based on signal type
        if signal.signal_type == SignalType.BUY:
            if market_condition == "bullish":
                base_score *= 1.2
            elif market_condition == "bearish":
                base_score *= 0.6
        elif signal.signal_type == SignalType.SELL:
            if market_condition == "bearish":
                base_score *= 1.2
            elif market_condition == "bullish":
                base_score *= 0.6
        
        return max(0.1, min(0.95, base_score))
    
    async def _score_indicator_strength(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on indicator strength.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        indicators = context.get("indicators", {})
        
        if not indicators:
            return 0.5
        
        # Calculate average indicator strength
        strength_scores = []
        
        # RSI
        if "rsi" in indicators:
            rsi = indicators["rsi"]
            if signal.signal_type == SignalType.BUY:
                strength = (30 - rsi) / 30 if rsi < 30 else 0
            else:
                strength = (rsi - 70) / 30 if rsi > 70 else 0
            strength_scores.append(max(0, min(1, strength)))
        
        # MACD
        if "macd_hist" in indicators:
            hist = indicators["macd_hist"]
            strength = min(1, abs(hist) / 10)
            if (signal.signal_type == SignalType.BUY and hist > 0) or \
               (signal.signal_type == SignalType.SELL and hist < 0):
                strength_scores.append(strength)
            else:
                strength_scores.append(0)
        
        # Bollinger Bands
        if "bb_width" in indicators:
            width = indicators["bb_width"]
            strength = min(1, width / 0.1)
            strength_scores.append(strength)
        
        if not strength_scores:
            return 0.5
        
        return sum(strength_scores) / len(strength_scores)
    
    async def _score_confirmations(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on multiple confirmations.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        confirmations = context.get("confirmations", 0)
        required_confirmations = context.get("required_confirmations", 3)
        
        if required_confirmations == 0:
            return 0.5
        
        score = min(1, confirmations / required_confirmations)
        return score
    
    async def _score_volatility(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on volatility.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        volatility = context.get("volatility", 0)
        max_volatility = context.get("max_volatility", 0.05)
        
        if max_volatility == 0:
            return 0.5
        
        # Lower volatility is better for most strategies
        normalized = 1 - min(1, volatility / max_volatility)
        
        # Adjust based on strategy type
        strategy_type = context.get("strategy_type", "mean_reversion")
        if strategy_type in ["breakout", "momentum"]:
            # These strategies prefer some volatility
            normalized = min(1, volatility / (max_volatility * 0.5))
        
        return max(0.1, min(0.95, normalized))
    
    async def _score_trend_alignment(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on trend alignment.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        trend = context.get("trend", 0)
        
        if trend == 0:
            return 0.5
        
        if signal.signal_type == SignalType.BUY:
            score = 0.5 + trend * 0.5
        elif signal.signal_type == SignalType.SELL:
            score = 0.5 - trend * 0.5
        else:
            score = 0.5
        
        return max(0.1, min(0.95, score))
    
    async def _score_volume(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on volume confirmation.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        volume_ratio = context.get("volume_ratio", 1.0)
        
        if volume_ratio < 0.5:
            return 0.2
        elif volume_ratio < 1.0:
            return 0.4
        elif volume_ratio < 1.5:
            return 0.6
        elif volume_ratio < 2.0:
            return 0.8
        else:
            return 0.95
    
    async def _score_strategy_performance(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on strategy performance.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        strategy_id = context.get("strategy_id", "default")
        performance = self._strategy_performance.get(strategy_id)
        
        if not performance:
            return 0.5
        
        # Combine win rate and average P&L
        win_rate_score = performance.win_rate
        pnl_score = min(1, (performance.avg_pnl + 1) / 2) if performance.avg_pnl else 0.5
        
        return (win_rate_score * 0.6 + pnl_score * 0.4)
    
    async def _score_time_decay(self, signal: Signal) -> float:
        """
        Score based on signal age.
        
        Args:
            signal: Signal
            
        Returns:
            float: Score (0-1)
        """
        age_hours = (datetime.utcnow() - signal.timestamp).total_seconds() / 3600
        
        if age_hours <= 0:
            return 1.0
        
        # Exponential decay
        decay = math.exp(-self.config.time_decay_rate * age_hours)
        
        return max(0.1, decay)
    
    async def _score_risk_adjustment(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> float:
        """
        Score based on risk assessment.
        
        Args:
            signal: Signal
            context: Context
            
        Returns:
            float: Score (0-1)
        """
        risk_level = context.get("risk_level", "medium")
        
        risk_scores = {
            "low": 0.9,
            "medium": 0.6,
            "high": 0.3,
        }
        
        return risk_scores.get(risk_level, 0.5)
    
    # ========================================================================
    # CONFIDENCE CALCULATION
    # ========================================================================
    
    def _calculate_raw_confidence(
        self,
        factor_scores: Dict[ConfidenceFactor, float],
    ) -> float:
        """
        Calculate raw confidence from factor scores.
        
        Args:
            factor_scores: Factor scores
            
        Returns:
            float: Raw confidence
        """
        total_weight = 0.0
        weighted_score = 0.0
        
        for factor, score in factor_scores.items():
            weight = self.config.factor_weights.get(factor, 0.5)
            total_weight += weight
            weighted_score += score * weight
        
        if total_weight == 0:
            return 0.5
        
        return weighted_score / total_weight
    
    # ========================================================================
    # CALIBRATION
    # ========================================================================
    
    async def update_performance(
        self,
        signal: Signal,
        success: bool,
        pnl: float,
        strategy_id: Optional[str] = None,
    ) -> None:
        """
        Update performance data for calibration.
        
        Args:
            signal: Signal
            success: Whether signal was successful
            pnl: Profit/Loss
            strategy_id: Strategy ID
        """
        key = f"{signal.symbol}_{signal.signal_type.value}"
        
        # Update signal performance
        if key not in self._performance:
            self._performance[key] = HistoricalPerformance()
        
        perf = self._performance[key]
        perf.total_signals += 1
        if success:
            perf.successful_signals += 1
        perf.total_pnl += pnl
        perf.avg_pnl = perf.total_pnl / perf.total_signals if perf.total_signals > 0 else 0
        perf.win_rate = perf.successful_signals / perf.total_signals if perf.total_signals > 0 else 0
        perf.avg_confidence = (
            (perf.avg_confidence * (perf.total_signals - 1) + signal.confidence) /
            perf.total_signals
        )
        perf.last_updated = datetime.utcnow()
        perf.history.append({"success": success, "pnl": pnl, "confidence": signal.confidence})
        
        # Update calibration data
        self._calibration_data[signal.symbol].append((signal.confidence, success))
        
        # Trim calibration data
        if len(self._calibration_data[signal.symbol]) > self.config.calibration_window:
            self._calibration_data[signal.symbol] = self._calibration_data[signal.symbol][-self.config.calibration_window:]
        
        # Update strategy performance
        if strategy_id:
            if strategy_id not in self._strategy_performance:
                self._strategy_performance[strategy_id] = HistoricalPerformance()
            
            strat_perf = self._strategy_performance[strategy_id]
            strat_perf.total_signals += 1
            if success:
                strat_perf.successful_signals += 1
            strat_perf.total_pnl += pnl
            strat_perf.avg_pnl = strat_perf.total_pnl / strat_perf.total_signals if strat_perf.total_signals > 0 else 0
            strat_perf.win_rate = strat_perf.successful_signals / strat_perf.total_signals if strat_perf.total_signals > 0 else 0
            strat_perf.last_updated = datetime.utcnow()
        
        # Update calibration factor
        await self._update_calibration_factor(signal)
    
    async def _update_calibration_factor(self, signal: Signal) -> None:
        """
        Update calibration factor based on historical performance.
        
        Args:
            signal: Signal
        """
        if not self.config.calibrate_confidence:
            return
        
        data = self._calibration_data.get(signal.symbol, [])
        if len(data) < self.config.calibration_min_samples:
            return
        
        # Calculate calibration factor
        avg_confidence = sum(c for c, _ in data) / len(data)
        success_rate = sum(1 for _, s in data if s) / len(data)
        
        if avg_confidence > 0:
            self._calibration_factors[signal.symbol] = success_rate / avg_confidence
        else:
            self._calibration_factors[signal.symbol] = 1.0
        
        # Apply bounds
        self._calibration_factors[signal.symbol] = max(0.5, min(1.5, self._calibration_factors[signal.symbol]))
        
        self._stats["calibration_updates"] += 1
    
    async def _get_calibration_factor(self, signal: Signal) -> float:
        """
        Get calibration factor for a signal.
        
        Args:
            signal: Signal
            
        Returns:
            float: Calibration factor
        """
        if not self.config.calibrate_confidence:
            return 1.0
        
        factor = self._calibration_factors.get(signal.symbol, 1.0)
        
        # Apply constraints
        return max(0.5, min(1.5, factor))
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def _update_stats(self, result: ConfidenceResult) -> None:
        """
        Update scoring statistics.
        
        Args:
            result: Confidence result
        """
        self._stats["total_signals_scored"] += 1
        self._stats["avg_confidence"] = (
            (self._stats["avg_confidence"] * (self._stats["total_signals_scored"] - 1) +
             result.confidence) /
            self._stats["total_signals_scored"]
        )
        
        for factor in result.factor_scores.keys():
            self._stats["factor_usage"][factor.value] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get confidence scoring metrics.
        
        Returns:
            Dict[str, Any]: Metrics
        """
        return {
            **self._stats,
            "active_strategies": len(self._strategy_performance),
            "active_symbols": len(self._performance),
            "calibration_data_points": sum(len(v) for v in self._calibration_data.values()),
            "calibration_factors": dict(self._calibration_factors),
            "performance_summary": {
                k: {
                    "win_rate": v.win_rate,
                    "avg_pnl": v.avg_pnl,
                    "total_signals": v.total_signals,
                    "avg_confidence": v.avg_confidence,
                }
                for k, v in self._performance.items()
            },
        }
    
    def get_strategy_performance(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get performance for a specific strategy.
        
        Args:
            strategy_id: Strategy ID
            
        Returns:
            Optional[Dict[str, Any]]: Performance metrics
        """
        perf = self._strategy_performance.get(strategy_id)
        if not perf:
            return None
        
        return {
            "win_rate": perf.win_rate,
            "avg_pnl": perf.avg_pnl,
            "total_signals": perf.total_signals,
            "successful_signals": perf.successful_signals,
            "total_pnl": perf.total_pnl,
            "avg_confidence": perf.avg_confidence,
            "last_updated": perf.last_updated.isoformat(),
        }
    
    # ========================================================================
    # RESET
    # ========================================================================
    
    def reset(self) -> None:
        """Reset confidence scoring state."""
        self._performance.clear()
        self._strategy_performance.clear()
        self._calibration_data.clear()
        self._calibration_factors.clear()
        self._factor_cache.clear()
        self._stats = {
            "total_signals_scored": 0,
            "avg_confidence": 0.0,
            "avg_calibration_factor": 1.0,
            "factor_usage": defaultdict(int),
            "calibration_updates": 0,
        }
        self.logger.info("Confidence scoring engine reset")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "ConfidenceFactor",
    
    # Models
    "ConfidenceConfig",
    "ConfidenceResult",
    "HistoricalPerformance",
    
    # Engine
    "ConfidenceScoringEngine",
]
