# trading/signals/optimizer.py
"""
NEXUS AI TRADING SYSTEM - Signal Optimizer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides signal optimization capabilities including:
- Signal filtering and refinement
- Confidence calibration
- Signal combination strategies
- Performance-based optimization
- Multi-strategy signal fusion
- Adaptive signal parameters
"""

import asyncio
import math
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict, deque

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from .base import Signal, SignalType, SignalStrength
from .storage import SignalRecord, SignalStorage, SignalOutcome
from .realtime import SignalEnvelope, SignalAggregation, SignalPriority

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class OptimizationMetric(str, Enum):
    """Metrics for signal optimization"""
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    COMBINED = "combined"


class SignalFilterType(str, Enum):
    """Types of signal filters"""
    CONFIDENCE = "confidence"
    VOLATILITY = "volatility"
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLUME = "volume"
    TIME = "time"
    POSITION = "position"
    COMPOSITE = "composite"


@dataclass
class SignalOptimizerConfig:
    """Configuration for signal optimizer"""
    # Optimization parameters
    optimization_metric: OptimizationMetric = OptimizationMetric.SHARPE_RATIO
    lookback_period: int = 100
    min_samples: int = 20
    
    # Confidence calibration
    confidence_calibration: bool = True
    confidence_smoothing: float = 0.9  # Exponential smoothing factor
    
    # Filtering
    filters: List[SignalFilterType] = field(default_factory=lambda: [
        SignalFilterType.CONFIDENCE,
        SignalFilterType.VOLATILITY,
    ])
    confidence_threshold: float = 0.5
    volatility_max: float = 0.05
    momentum_min: float = -0.02
    momentum_max: float = 0.02
    volume_min: float = 0.5
    
    # Signal combination
    combine_method: str = "weighted"  # weighted, average, max, min
    min_signals_for_combination: int = 2
    max_signals_for_combination: int = 5
    
    # Adaptive parameters
    adaptive_thresholds: bool = True
    adaptation_rate: float = 0.05
    recalibration_interval: int = 50
    
    # Performance tracking
    track_performance: bool = True
    performance_window: int = 100


@dataclass
class SignalPerformance:
    """Performance tracking for a signal"""
    signal_id: str
    total_occurrences: int = 0
    successful_occurrences: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    confidence_adjustment: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update(self, pnl: float, success: bool) -> None:
        """Update performance metrics."""
        self.total_occurrences += 1
        if success:
            self.successful_occurrences += 1
        self.total_pnl += pnl
        
        self.history.append({"pnl": pnl, "success": success})
        
        if self.total_occurrences > 0:
            self.win_rate = self.successful_occurrences / self.total_occurrences
            self.avg_pnl = self.total_pnl / self.total_occurrences
        
        if pnl > self.max_profit:
            self.max_profit = pnl
        if pnl < self.max_loss:
            self.max_loss = pnl
        
        self.last_updated = datetime.utcnow()


@dataclass
class OptimizedSignal:
    """Optimized signal result"""
    original_signal: Signal
    optimized_confidence: float
    adjusted_strength: SignalStrength
    filter_results: Dict[str, bool]
    combination_source: Optional[List[Signal]] = None
    performance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# SIGNAL OPTIMIZER
# ============================================================================

class SignalOptimizer:
    """
    Optimizes trading signals through filtering, calibration, and combination.
    
    Features:
    - Signal filtering and refinement
    - Confidence calibration
    - Signal combination
    - Performance-based optimization
    - Adaptive thresholds
    - Multi-signal fusion
    """
    
    def __init__(
        self,
        config: Optional[SignalOptimizerConfig] = None,
        signal_storage: Optional[SignalStorage] = None,
    ):
        """
        Initialize the signal optimizer.
        
        Args:
            config: Optimizer configuration
            signal_storage: Signal storage instance
        """
        self.config = config or SignalOptimizerConfig()
        self.signal_storage = signal_storage or SignalStorage()
        
        # Performance tracking
        self._signal_performance: Dict[str, SignalPerformance] = {}
        self._strategy_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Adaptive thresholds
        self._adaptive_thresholds: Dict[str, float] = {}
        self._threshold_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Calibration data
        self._calibration_data: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
        self._confidence_mapping: Dict[str, float] = defaultdict(float)
        
        # Statistics
        self._stats = {
            "signals_processed": 0,
            "signals_filtered": 0,
            "signals_combined": 0,
            "signals_calibrated": 0,
            "avg_confidence_change": 0.0,
            "filter_pass_rate": 0.0,
            "optimization_time_ms": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # SIGNAL OPTIMIZATION
    # ========================================================================
    
    async def optimize_signal(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[OptimizedSignal]:
        """
        Optimize a signal through filtering, calibration, and enhancement.
        
        Args:
            envelope: Signal envelope to optimize
            context: Additional context for optimization
            
        Returns:
            Optional[OptimizedSignal]: Optimized signal or None
        """
        start_time = time.time()
        
        # Apply filters
        filter_results = await self._apply_filters(envelope, context)
        
        if not all(filter_results.values()):
            self._stats["signals_filtered"] += 1
            self.logger.debug(f"Signal {envelope.signal.signal_id} filtered out")
            return None
        
        # Calibrate confidence
        calibrated_confidence = await self._calibrate_confidence(envelope, context)
        
        # Calculate performance score
        performance_score = await self._calculate_performance_score(envelope, context)
        
        # Determine adjusted strength
        adjusted_strength = self._determine_strength(calibrated_confidence)
        
        # Create optimized signal
        optimized = OptimizedSignal(
            original_signal=envelope.signal,
            optimized_confidence=calibrated_confidence,
            adjusted_strength=adjusted_strength,
            filter_results=filter_results,
            performance_score=performance_score,
            metadata={
                "original_confidence": envelope.signal.confidence,
                "calibrated_confidence": calibrated_confidence,
                "strategy_id": envelope.strategy_id,
                "strategy_name": envelope.strategy_name,
                "priority": envelope.priority.value,
            },
        )
        
        # Update stats
        self._stats["signals_processed"] += 1
        self._stats["signals_calibrated"] += 1
        self._stats["avg_confidence_change"] = (
            (self._stats["avg_confidence_change"] * (self._stats["signals_calibrated"] - 1) +
             (calibrated_confidence - envelope.signal.confidence)) /
            self._stats["signals_calibrated"]
        )
        
        processing_time = (time.time() - start_time) * 1000
        self._stats["optimization_time_ms"] = (
            (self._stats["optimization_time_ms"] * (self._stats["signals_processed"] - 1) +
             processing_time) /
            self._stats["signals_processed"]
        )
        
        return optimized
    
    async def combine_signals(
        self,
        envelopes: List[SignalEnvelope],
    ) -> Optional[OptimizedSignal]:
        """
        Combine multiple signals into a single optimized signal.
        
        Args:
            envelopes: List of signal envelopes to combine
            
        Returns:
            Optional[OptimizedSignal]: Combined optimized signal
        """
        if len(envelopes) < self.config.min_signals_for_combination:
            return None
        
        if len(envelopes) > self.config.max_signals_for_combination:
            # Take the top N by confidence
            envelopes = sorted(envelopes, key=lambda x: x.signal.confidence, reverse=True)[:self.config.max_signals_for_combination]
        
        # Group by symbol
        symbols = set(e.signal.symbol for e in envelopes)
        if len(symbols) > 1:
            self.logger.warning("Combining signals from different symbols")
            # Group by symbol and combine separately
            combined = []
            for symbol in symbols:
                symbol_envelopes = [e for e in envelopes if e.signal.symbol == symbol]
                result = await self._combine_same_symbol(symbol_envelopes)
                if result:
                    combined.append(result)
            return combined[0] if combined else None
        
        return await self._combine_same_symbol(envelopes)
    
    async def _combine_same_symbol(
        self,
        envelopes: List[SignalEnvelope],
    ) -> Optional[OptimizedSignal]:
        """
        Combine signals for the same symbol.
        
        Args:
            envelopes: List of signal envelopes for same symbol
            
        Returns:
            Optional[OptimizedSignal]: Combined optimized signal
        """
        if not envelopes:
            return None
        
        # Determine combined signal type
        signal_types = [e.signal.signal_type for e in envelopes]
        type_counts = defaultdict(int)
        for st in signal_types:
            type_counts[st] += 1
        
        # Majority vote for signal type
        combined_type = max(type_counts, key=type_counts.get)
        
        # Skip neutral/hold
        if combined_type in [SignalType.NEUTRAL, SignalType.HOLD]:
            return None
        
        # Calculate combined confidence
        if self.config.combine_method == "weighted":
            # Weighted by strategy weight
            total_weight = sum(e.weight for e in envelopes)
            combined_confidence = sum(
                e.signal.confidence * e.weight / total_weight
                for e in envelopes
            )
        elif self.config.combine_method == "average":
            combined_confidence = sum(e.signal.confidence for e in envelopes) / len(envelopes)
        elif self.config.combine_method == "max":
            combined_confidence = max(e.signal.confidence for e in envelopes)
        elif self.config.combine_method == "min":
            combined_confidence = min(e.signal.confidence for e in envelopes)
        else:
            combined_confidence = sum(e.signal.confidence for e in envelopes) / len(envelopes)
        
        # Calculate combined price (average)
        combined_price = sum(e.signal.price for e in envelopes) / len(envelopes)
        
        # Determine strength
        combined_strength = self._determine_strength(combined_confidence)
        
        # Get best position size (max)
        combined_size = max(e.signal.position_size or 0 for e in envelopes)
        
        # Create combined signal
        combined_signal = Signal(
            symbol=envelopes[0].signal.symbol,
            signal_type=combined_type,
            strength=combined_strength,
            confidence=combined_confidence,
            price=combined_price,
            position_size=combined_size,
            stop_loss=min(e.signal.stop_loss for e in envelopes) if all(e.signal.stop_loss for e in envelopes) else None,
            take_profit=max(e.signal.take_profit for e in envelopes) if all(e.signal.take_profit for e in envelopes) else None,
            metadata={
                "combined_from": [e.signal.signal_id for e in envelopes],
                "source_signals": [e.to_dict() for e in envelopes],
                "combine_method": self.config.combine_method,
            },
        )
        
        # Create optimized signal
        optimized = OptimizedSignal(
            original_signal=combined_signal,
            optimized_confidence=combined_confidence,
            adjusted_strength=combined_strength,
            filter_results={"combined": True},
            combination_source=[e.signal for e in envelopes],
            performance_score=await self._calculate_performance_score_for_combined(envelopes),
            metadata={
                "combined_from": [e.signal.signal_id for e in envelopes],
                "strategy_ids": [e.strategy_id for e in envelopes],
                "strategy_names": [e.strategy_name for e in envelopes],
                "priority": max(envelopes, key=lambda x: x.priority.value).priority.value,
            },
        )
        
        self._stats["signals_combined"] += 1
        
        return optimized
    
    # ========================================================================
    # FILTERING
    # ========================================================================
    
    async def _apply_filters(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bool]:
        """
        Apply configured filters to a signal.
        
        Args:
            envelope: Signal envelope
            context: Context for filtering
            
        Returns:
            Dict[str, bool]: Results of each filter
        """
        results = {}
        
        for filter_type in self.config.filters:
            if filter_type == SignalFilterType.CONFIDENCE:
                results["confidence"] = await self._filter_confidence(envelope)
            elif filter_type == SignalFilterType.VOLATILITY:
                results["volatility"] = await self._filter_volatility(envelope, context)
            elif filter_type == SignalFilterType.TREND:
                results["trend"] = await self._filter_trend(envelope, context)
            elif filter_type == SignalFilterType.MOMENTUM:
                results["momentum"] = await self._filter_momentum(envelope, context)
            elif filter_type == SignalFilterType.VOLUME:
                results["volume"] = await self._filter_volume(envelope, context)
            elif filter_type == SignalFilterType.TIME:
                results["time"] = await self._filter_time(envelope)
            elif filter_type == SignalFilterType.POSITION:
                results["position"] = await self._filter_position(envelope)
            elif filter_type == SignalFilterType.COMPOSITE:
                results["composite"] = await self._filter_composite(envelope, context)
        
        return results
    
    async def _filter_confidence(self, envelope: SignalEnvelope) -> bool:
        """Filter by confidence threshold."""
        confidence = envelope.signal.confidence
        
        # Apply adaptive threshold if enabled
        if self.config.adaptive_thresholds:
            threshold = self._get_adaptive_threshold(
                envelope.strategy_id,
                "confidence",
                self.config.confidence_threshold,
            )
            return confidence >= threshold
        
        return confidence >= self.config.confidence_threshold
    
    async def _filter_volatility(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Filter by market volatility."""
        if not context:
            return True
        
        volatility = context.get("volatility", 0)
        return volatility <= self.config.volatility_max
    
    async def _filter_trend(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Filter by trend alignment."""
        if not context:
            return True
        
        trend = context.get("trend", 0)
        signal_type = envelope.signal.signal_type
        
        if signal_type == SignalType.BUY:
            return trend > 0
        elif signal_type == SignalType.SELL:
            return trend < 0
        
        return True
    
    async def _filter_momentum(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Filter by momentum."""
        if not context:
            return True
        
        momentum = context.get("momentum", 0)
        return self.config.momentum_min <= momentum <= self.config.momentum_max
    
    async def _filter_volume(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Filter by volume."""
        if not context:
            return True
        
        volume_ratio = context.get("volume_ratio", 1.0)
        return volume_ratio >= self.config.volume_min
    
    async def _filter_time(self, envelope: SignalEnvelope) -> bool:
        """Filter by time constraints."""
        # Allow signals only during trading hours if configured
        # This would be extended with time-based filtering
        return True
    
    async def _filter_position(self, envelope: SignalEnvelope) -> bool:
        """Filter by position constraints."""
        # Check if position limits are reached
        # This would be extended with position management
        return True
    
    async def _filter_composite(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Composite filter combining multiple conditions."""
        score = 0.0
        
        # Confidence factor
        confidence = envelope.signal.confidence
        score += max(0, (confidence - 0.5) * 2) * 0.3
        
        # Performance factor
        performance = self._strategy_performance.get(envelope.strategy_id, {})
        win_rate = performance.get("win_rate", 0.5)
        score += win_rate * 0.3
        
        # Context factors
        if context:
            volatility_score = 1 - min(1, context.get("volatility", 0) / self.config.volatility_max)
            score += volatility_score * 0.2
            
            momentum = context.get("momentum", 0)
            momentum_score = max(0, 1 - abs(momentum))
            score += momentum_score * 0.2
        
        return score >= 0.5
    
    # ========================================================================
    # CONFIDENCE CALIBRATION
    # ========================================================================
    
    async def _calibrate_confidence(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calibrate signal confidence based on historical performance.
        
        Args:
            envelope: Signal envelope
            context: Context for calibration
            
        Returns:
            float: Calibrated confidence
        """
        if not self.config.confidence_calibration:
            return envelope.signal.confidence
        
        original_confidence = envelope.signal.confidence
        
        # Get performance data for this strategy
        performance = self._signal_performance.get(envelope.strategy_id)
        if not performance:
            # No historical data, use original confidence
            return original_confidence
        
        # Calculate calibration factor based on historical win rate
        win_rate = performance.win_rate
        calibration_factor = win_rate / 0.5  # Normalize around 0.5
        
        # Apply calibration
        calibrated = original_confidence * min(calibration_factor, 1.5)
        
        # Apply smoothing
        if hasattr(self, "_last_calibrated"):
            calibrated = self._last_calibrated * self.config.confidence_smoothing + calibrated * (1 - self.config.confidence_smoothing)
        
        self._last_calibrated = calibrated
        
        # Clamp to valid range
        return max(0.1, min(0.95, calibrated))
    
    # ========================================================================
    # PERFORMANCE SCORING
    # ========================================================================
    
    async def _calculate_performance_score(
        self,
        envelope: SignalEnvelope,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate performance score for a signal.
        
        Args:
            envelope: Signal envelope
            context: Context for scoring
            
        Returns:
            float: Performance score (0-1)
        """
        strategy_id = envelope.strategy_id
        performance = self._strategy_performance.get(strategy_id, {})
        
        if not performance:
            return 0.5  # Default score
        
        # Calculate score based on multiple metrics
        score = 0.0
        
        # Win rate
        win_rate = performance.get("win_rate", 0.5)
        score += win_rate * 0.4
        
        # Profit factor
        profit_factor = performance.get("profit_factor", 1.0)
        profit_factor_score = min(1, profit_factor / 2)
        score += profit_factor_score * 0.3
        
        # Sharpe ratio
        sharpe = performance.get("sharpe_ratio", 0)
        sharpe_score = min(1, max(0, (sharpe + 1) / 3))
        score += sharpe_score * 0.3
        
        return min(1, score)
    
    async def _calculate_performance_score_for_combined(
        self,
        envelopes: List[SignalEnvelope],
    ) -> float:
        """
        Calculate performance score for combined signals.
        
        Args:
            envelopes: List of signal envelopes
            
        Returns:
            float: Combined performance score
        """
        if not envelopes:
            return 0.5
        
        scores = []
        for envelope in envelopes:
            score = await self._calculate_performance_score(envelope)
            scores.append(score * envelope.weight)
        
        return sum(scores) / sum(e.weight for e in envelopes) if envelopes else 0.5
    
    # ========================================================================
    # ADAPTIVE THRESHOLDS
    # ========================================================================
    
    def _get_adaptive_threshold(
        self,
        strategy_id: str,
        threshold_type: str,
        default: float,
    ) -> float:
        """
        Get adaptive threshold for a strategy.
        
        Args:
            strategy_id: Strategy ID
            threshold_type: Threshold type
            default: Default threshold value
            
        Returns:
            float: Adaptive threshold
        """
        key = f"{strategy_id}_{threshold_type}"
        
        if key not in self._adaptive_thresholds:
            return default
        
        return self._adaptive_thresholds[key]
    
    async def _update_adaptive_thresholds(self) -> None:
        """
        Update adaptive thresholds based on performance.
        """
        if not self.config.adaptive_thresholds:
            return
        
        for strategy_id, performance in self._strategy_performance.items():
            win_rate = performance.get("win_rate", 0.5)
            
            # Adjust confidence threshold based on win rate
            confidence_key = f"{strategy_id}_confidence"
            current = self._adaptive_thresholds.get(confidence_key, self.config.confidence_threshold)
            
            # If win rate is high, lower threshold (more signals)
            # If win rate is low, raise threshold (fewer signals)
            target = max(0.3, min(0.9, 0.6 - (win_rate - 0.5) * 0.4))
            
            # Smooth adjustment
            self._adaptive_thresholds[confidence_key] = (
                current * (1 - self.config.adaptation_rate) +
                target * self.config.adaptation_rate
            )
            
            # Store history
            self._threshold_history[confidence_key].append(
                (datetime.utcnow(), self._adaptive_thresholds[confidence_key])
            )
    
    # ========================================================================
    # STRENGTH DETERMINATION
    # ========================================================================
    
    def _determine_strength(self, confidence: float) -> SignalStrength:
        """
        Determine signal strength based on confidence.
        
        Args:
            confidence: Signal confidence
            
        Returns:
            SignalStrength: Determined strength
        """
        if confidence >= 0.85:
            return SignalStrength.VERY_STRONG
        elif confidence >= 0.7:
            return SignalStrength.STRONG
        elif confidence >= 0.55:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK
    
    # ========================================================================
    # PERFORMANCE UPDATE
    # ========================================================================
    
    async def update_performance(
        self,
        signal_id: str,
        pnl: float,
        success: bool,
    ) -> None:
        """
        Update performance for a signal.
        
        Args:
            signal_id: Signal ID
            pnl: Profit/Loss
            success: Whether the trade was successful
        """
        # Get signal record
        record = await self.signal_storage.get_signal(signal_id)
        if not record:
            return
        
        # Update signal performance
        strategy_id = record.strategy_id
        if strategy_id not in self._signal_performance:
            self._signal_performance[strategy_id] = SignalPerformance(signal_id=strategy_id)
        
        performance = self._signal_performance[strategy_id]
        performance.update(pnl, success)
        
        # Update strategy performance
        self._strategy_performance[strategy_id] = {
            "win_rate": performance.win_rate,
            "total_pnl": performance.total_pnl,
            "avg_pnl": performance.avg_pnl,
            "max_profit": performance.max_profit,
            "max_loss": performance.max_loss,
            "total_occurrences": performance.total_occurrences,
            "successful_occurrences": performance.successful_occurrences,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Recalculate adaptive thresholds if needed
        if self.config.adaptive_thresholds:
            await self._update_adaptive_thresholds()
    
    # ========================================================================
    # METRICS AND STATISTICS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get optimizer metrics.
        
        Returns:
            Dict[str, Any]: Optimizer metrics
        """
        total = self._stats["signals_processed"] + self._stats["signals_filtered"]
        
        return {
            **self._stats,
            "filter_pass_rate": (
                self._stats["signals_processed"] / max(1, total) * 100
            ),
            "active_thresholds": len(self._adaptive_thresholds),
            "strategy_performance": dict(self._strategy_performance),
            "adaptive_thresholds": self._adaptive_thresholds,
            "confidence_mapping": dict(self._confidence_mapping),
        }
    
    def get_performance(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance data.
        
        Args:
            strategy_id: Optional strategy ID
            
        Returns:
            Dict[str, Any]: Performance data
        """
        if strategy_id:
            return {
                "strategy_id": strategy_id,
                "performance": self._strategy_performance.get(strategy_id, {}),
                "signal_performance": self._signal_performance.get(strategy_id),
            }
        
        return {
            "strategies": dict(self._strategy_performance),
            "signal_performance": {
                k: {
                    "win_rate": v.win_rate,
                    "total_pnl": v.total_pnl,
                    "avg_pnl": v.avg_pnl,
                    "total_occurrences": v.total_occurrences,
                    "successful_occurrences": v.successful_occurrences,
                }
                for k, v in self._signal_performance.items()
            },
        }
    
    # ========================================================================
    # RESET AND CLEANUP
    # ========================================================================
    
    def reset(self) -> None:
        """Reset optimizer state."""
        self._signal_performance.clear()
        self._strategy_performance.clear()
        self._adaptive_thresholds.clear()
        self._threshold_history.clear()
        self._calibration_data.clear()
        self._confidence_mapping.clear()
        self._stats = {
            "signals_processed": 0,
            "signals_filtered": 0,
            "signals_combined": 0,
            "signals_calibrated": 0,
            "avg_confidence_change": 0.0,
            "filter_pass_rate": 0.0,
            "optimization_time_ms": 0.0,
        }
        self.logger.info("Signal optimizer reset")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "OptimizationMetric",
    "SignalFilterType",
    
    # Models
    "SignalOptimizerConfig",
    "SignalPerformance",
    "OptimizedSignal",
    
    # Optimizer
    "SignalOptimizer",
]
